"""orders-service: pedidos, estado oficial, vencimiento y orden de despacho (S12-S17, I07-I12, I14)."""
import os, re, json, asyncio, time
import stomp
from fastapi import Depends, Request, Header
from pymongo.errors import DuplicateKeyError
from fornace.base import make_app, run, AppError, evento
from fornace.vault import SecretProvider
from fornace.guard import Guard, Ctx
from fornace.svc import Servicios
from fornace.db import conectar, siguiente, ahora, en_segundos
from fornace.retencion import corte, INTERVALO
from fornace.util import paginar
from fornace.topology import PERSONAL

SISTEMA = 'orders'
VIGENCIA = int(os.environ.get('PEDIDO_SEGUNDOS', '900'))        # 15 minutos
MARGEN_RESERVA = 300                                            # 5 minutos
COMUNAS = {c.strip().casefold() for c in os.environ.get('COMUNAS_COBERTURA', 'Maipú').split(',') if c.strip()}
ESTADOS = ('pendiente_pago', 'pagado', 'en_preparacion', 'en_despacho', 'entregado', 'anulado')
PAGADOS = ('pagado', 'en_preparacion', 'en_despacho', 'entregado')
TRANSICIONES = {'pagado': 'en_preparacion', 'en_preparacion': 'en_despacho', 'en_despacho': 'entregado'}
vault = SecretProvider()
guard = Guard(SISTEMA, vault)
S = {}

async def startup(app):
    S['cli'], S['db'] = await conectar(SISTEMA, vault)
    S['svc'] = Servicios('orders-service', vault, app.state.log)
    db = S['db']
    await db.pedidos.create_index('id', unique=True)
    await db.pedidos.create_index([('cuentaId', 1), ('creadoEn', -1)])
    await db.pedidos.create_index([('estado', 1), ('expiraEn', 1)])

# ---------------- STOMP (I14) ----------------
def _publicar_sync(msg: dict):
    c = vault.get('orders/activemq')
    conn = stomp.Connection10([(os.environ['STOMP_HOST'], int(os.environ['STOMP_PORT']))], timeout=4)
    conn.connect(c['usuario'], c['clave'], wait=True)
    try:
        conn.send(destination='/queue/cola_pedidos', body=json.dumps(msg, ensure_ascii=False), headers={'persistent': 'true'})
    finally:
        conn.disconnect()

async def publicar(msg):
    try:
        await asyncio.wait_for(asyncio.to_thread(_publicar_sync, msg), 8)
        return True
    except Exception as e:
        evento(log, 'orders-service', 'broker_no_disponible', tipo=type(e).__name__, pedidoId=msg.get('pedidoId'))
        return False

def msg_despacho(p, tipo):
    return {'tipo': tipo, 'pedidoId': p['id'], 'pagadoEn': p.get('pagadoEn'), 'clienteNombre': p['clienteNombre'], 'telefono': p['clienteTelefono'],
            'direccionEntrega': p['direccionEntrega'], 'items': [{'nombre': i['nombre'], 'cantidad': i['cantidad']} for i in p['items']]}

# ---------------- tareas periodicas ----------------
async def liberar_stock(p, rid=None):
    try:
        r = await S['svc'].llamar('inventory-service', 'POST', f'/internal/stock/reservations/{p["id"]}/release', rid, timeout=3.0)
        ok = r.status_code == 200
    except AppError:
        ok = False
    await S['db'].pedidos.update_one({'id': p['id']}, {'$set': {'liberacionPendiente': not ok}})
    return ok

async def expirar():
    db = S['db']
    async for p in db.pedidos.find({'estado': 'pendiente_pago', 'expiraEn': {'$lte': ahora()}}).limit(200):
        u = await db.pedidos.update_one({'id': p['id'], 'estado': 'pendiente_pago'},
                                        {'$set': {'estado': 'anulado', 'motivoAnulacion': 'vencido', 'reembolsoPendiente': False},
                                         '$push': {'historial': {'estado': 'anulado', 'fecha': ahora(), 'actor': 'sistema', 'motivo': 'vencido'}}})
        if u.modified_count:
            await liberar_stock(p)
            evento(log, 'orders-service', 'pedido_vencido', pedidoId=p['id'])

async def reintentos():
    db = S['db']
    async for p in db.pedidos.find({'estado': {'$in': list(PAGADOS)}, 'reservaConfirmada': False, 'revisar': {'$ne': True}}).limit(100):
        try:
            r = await S['svc'].llamar('inventory-service', 'POST', f'/internal/stock/reservations/{p["id"]}/confirm', None, timeout=3.0)
        except AppError:
            continue
        if r.status_code == 200:
            await db.pedidos.update_one({'id': p['id']}, {'$set': {'reservaConfirmada': True}})
        elif r.status_code in (404, 409):
            await db.pedidos.update_one({'id': p['id']}, {'$set': {'revisar': True}})   # caso residual 3.9: lo resuelve el administrador
    async for p in db.pedidos.find({'estado': {'$in': list(PAGADOS)}, 'despachoPublicado': False}).limit(100):
        if await publicar(msg_despacho(p, 'nueva')):
            await db.pedidos.update_one({'id': p['id']}, {'$set': {'despachoPublicado': True}})
    async for p in db.pedidos.find({'despachoAnuladaPendiente': True}).limit(100):
        if await publicar(msg_despacho(p, 'anulada')):
            await db.pedidos.update_one({'id': p['id']}, {'$set': {'despachoAnuladaPendiente': False}})
    async for p in db.pedidos.find({'liberacionPendiente': True}).limit(100):
        await liberar_stock(p)

async def purga():
    await S['db'].idempotencia.delete_many({'creadoEn': {'$lt': en_segundos(-86400)}})

async def retencion():
    """7.9: pedido vencido o anulado sin pago, 12 meses despues del cambio de estado (se elimina); calle, referencia y telefono
    de un pedido entregado, 12 meses despues de la entrega (se borran). Los pedidos pagados se conservan 6 anios."""
    db = S['db']
    c = corte('pedido_sin_pago')
    sin_pago = await db.pedidos.delete_many({'estado': 'anulado', 'historial.estado': {'$nin': list(PAGADOS)},
                                             'historial': {'$elemMatch': {'estado': 'anulado', 'fecha': {'$lt': c}}}})
    d = await db.pedidos.update_many({'estado': 'entregado', 'datosPersonalesBorrados': {'$ne': True},
                                      'historial': {'$elemMatch': {'estado': 'entregado', 'fecha': {'$lt': corte('direccion_pedido')}}}},
                                     {'$set': {'direccionEntrega.calle': '', 'direccionEntrega.referencia': '', 'clienteTelefono': None, 'datosPersonalesBorrados': True}})
    if sin_pago.deleted_count or d.modified_count:
        evento(log, 'orders-service', 'retencion', pedidosEliminados=sin_pago.deleted_count, direccionesBorradas=d.modified_count)

app = make_app('orders-service', startup=startup,
               tareas=[('expirar', int(os.environ.get('EXPIRAR_SEGUNDOS', '30')), expirar),
                       ('reintentos', int(os.environ.get('REINTENTO_SEGUNDOS', '30')), reintentos),
                       ('purga', 3600, purga),
                       ('retencion', INTERVALO, retencion)])
log = app.state.log

# ---------------- vistas ----------------
def estado_pago(p):
    if p['estado'] == 'pendiente_pago': return 'pendiente'
    if p.get('pagadoEn'): return 'aprobado'
    return 'sin_pago'

def detalle(p, personal=False):
    o = {'id': p['id'], 'estado': p['estado'], 'estadoPago': estado_pago(p), 'items': p['items'], 'total': p['total'],
         'direccionEntrega': p['direccionEntrega'], 'historialEstados': [{'estado': h['estado'], 'fecha': h['fecha']} for h in p['historial']],
         'boletaDisponible': bool(p.get('pagadoEn')), 'creadoEn': p['creadoEn'], 'expiraEn': p['expiraEn'] if p['estado'] == 'pendiente_pago' else None}
    if p['estado'] == 'anulado':
        o['motivo'] = p.get('motivoAnulacion'); o['reembolsoPendiente'] = bool(p.get('reembolsoPendiente'))
    if personal: o['clienteNombre'] = p['clienteNombre']
    return o

async def json_de(request):
    try: d = await request.json()
    except Exception: raise AppError(400, 'DATOS_INVALIDOS', 'El cuerpo debe ser JSON válido.')
    if not isinstance(d, dict): raise AppError(400, 'DATOS_INVALIDOS', 'El cuerpo debe ser un objeto JSON.')
    return d

def ext(r):
    try: return r.json().get('error', {})
    except Exception: return {}

# ---------------- S12 ----------------
CLI = Depends(guard.dep(roles=['cliente']))

@app.post('/orders', status_code=201)
async def s12(request: Request, idempotency_key: str = Header(None), ctx: Ctx = CLI):
    d = await json_de(request)
    items = d.get('items')
    m = []
    if not isinstance(items, list) or not (1 <= len(items) <= 30): m.append('items')
    else:
        vistos = set()
        for it in items:
            if not (isinstance(it, dict) and isinstance(it.get('productoId'), str) and re.fullmatch(r'prod_\d{3,6}', it['productoId'])
                    and isinstance(it.get('cantidad'), int) and not isinstance(it.get('cantidad'), bool) and 1 <= it['cantidad'] <= 20) or it['productoId'] in vistos:
                m.append('items'); break
            vistos.add(it['productoId'])
    dire = d.get('direccionEntrega')
    if dire is not None:
        if not isinstance(dire, dict) or not all(isinstance(dire.get(k), str) and 2 <= len(dire[k].strip()) <= 120 for k in ('calle', 'comuna')) \
           or (dire.get('referencia') is not None and (not isinstance(dire['referencia'], str) or len(dire['referencia']) > 120)):
            m.append('direccionEntrega')
    if idempotency_key is not None and not re.fullmatch(r'[A-Za-z0-9._\-]{8,80}', idempotency_key): m.append('Idempotency-Key')
    if m: raise AppError(400, 'DATOS_INVALIDOS', 'Datos inválidos en: ' + ', '.join(sorted(set(m))))
    db = S['db']
    clave = f'{ctx.cuenta}:{idempotency_key}' if idempotency_key else None
    if clave:
        try:
            await db.idempotencia.insert_one({'_id': clave, 'pedidoId': None, 'creadoEn': ahora()})
        except DuplicateKeyError:
            for _ in range(20):
                ex = await db.idempotencia.find_one({'_id': clave})
                if ex and ex['pedidoId']:
                    p = await db.pedidos.find_one({'id': ex['pedidoId']})
                    return crear_vista(p)
                await asyncio.sleep(0.25)
            raise AppError(409, 'SOLICITUD_EN_CURSO', 'La solicitud anterior sigue en proceso.')
    try:
        p = await crear_pedido(ctx, items, dire)
    except BaseException:
        if clave: await db.idempotencia.delete_one({'_id': clave})
        raise
    if clave: await db.idempotencia.update_one({'_id': clave}, {'$set': {'pedidoId': p['id']}})
    return crear_vista(p)

def crear_vista(p):
    return {'id': p['id'], 'estado': p['estado'], 'items': p['items'], 'total': p['total'], 'direccionEntrega': p['direccionEntrega'],
            'creadoEn': p['creadoEn'], 'expiraEn': p['expiraEn']}

async def crear_pedido(ctx, items, dire):
    db, svc = S['db'], S['svc']
    r = await svc.llamar('clients-service', 'GET', f'/internal/clients/by-account/{ctx.cuenta}', ctx.rid, timeout=3.0)
    if r.status_code == 404: raise AppError(403, 'CLIENTE_NO_REGISTRADO', 'Tu cuenta no tiene un perfil de cliente.')
    if r.status_code != 200: raise AppError(503, 'SERVICIO_NO_DISPONIBLE', 'Servicio no disponible. Intenta de nuevo en un momento.')
    cl = r.json()
    if dire is None:
        a = cl['direccion']; dire = {'calle': a['calle'], 'comuna': a['comuna'], 'referencia': ''}
    dire = {'calle': dire['calle'].strip(), 'comuna': dire['comuna'].strip(), 'referencia': (dire.get('referencia') or '').strip()}
    if dire['comuna'].casefold() not in COMUNAS:
        raise AppError(422, 'FUERA_DE_COBERTURA', 'Solo despachamos dentro de 3 km del local.')
    pid = await siguiente(db, 'ped', 'ped_')
    t0 = time.time()
    creado, expira = ahora(), en_segundos(VIGENCIA)
    cuerpo = {'pedidoId': pid, 'expiraEn': en_segundos(VIGENCIA + MARGEN_RESERVA), 'items': items}
    res = None
    try:
        res = await svc.llamar('inventory-service', 'POST', '/internal/stock/reservations', ctx.rid, json=cuerpo, timeout=3.0, reintentos=1)
    except AppError:
        try: await svc.llamar('inventory-service', 'POST', f'/internal/stock/reservations/{pid}/release', ctx.rid, timeout=2.0)
        except AppError: pass
        raise AppError(503, 'INVENTARIO_NO_DISPONIBLE', 'No pudimos reservar tu pedido. Intenta de nuevo en un momento.')
    if res.status_code != 201:
        e = ext(res)
        a = AppError(res.status_code if res.status_code in (404, 409) else 503, e.get('codigo', 'INVENTARIO_NO_DISPONIBLE'), e.get('mensaje', 'No pudimos reservar tu pedido.'))
        if e.get('productos'): a.extra = {'productos': e['productos']}
        raise a
    lineas = res.json()['items']
    total = sum(i['precioUnitario'] * i['cantidad'] for i in lineas)
    doc = {'id': pid, 'cuentaId': ctx.cuenta, 'clienteId': cl['clienteId'], 'clienteNombre': cl['nombreCompleto'], 'clienteTelefono': cl['telefono'],
           'clienteCorreo': ctx.email, 'estado': 'pendiente_pago', 'items': lineas, 'total': total, 'direccionEntrega': dire,
           'creadoEn': creado, 'expiraEn': expira, 'historial': [{'estado': 'pendiente_pago', 'fecha': creado, 'actor': 'cliente'}],
           'reservaConfirmada': False, 'despachoPublicado': False, 'reembolsoPendiente': False}
    try:
        await db.pedidos.insert_one(doc)
    except Exception:
        await liberar_stock({'id': pid}, ctx.rid)
        raise AppError(500, 'ERROR_INTERNO', 'Error interno.')
    evento(log, 'orders-service', 'pedido_creado', requestId=ctx.rid, cuentaId=ctx.cuenta, pedidoId=pid, total=total)
    return doc

# ---------------- S13 / S14 ----------------
@app.get('/orders')
async def s13(estado: str = None, limit: int = None, offset: int = None,
              ctx: Ctx = Depends(guard.dep(roles=['cliente'], pares=('graphql-gateway',), pares_solo_get=('graphql-gateway',)))):
    limit, offset = paginar(limit, offset)
    q = {'cuentaId': ctx.cuenta}
    if estado:
        if estado not in ESTADOS: raise AppError(400, 'DATOS_INVALIDOS', 'Filtro inválido: estado')
        q['estado'] = estado
    cur = S['db'].pedidos.find(q).sort('creadoEn', -1).skip(offset).limit(limit)
    return [{'id': p['id'], 'estado': p['estado'], 'total': p['total'], 'creadoEn': p['creadoEn']} async for p in cur]

LECTURA = Depends(guard.dep(roles=['administrador', 'cajero_virtual', 'cliente', 'encargado_despachos'], pares=('graphql-gateway',), pares_solo_get=('graphql-gateway',)))

async def propio_o_personal(pid, ctx):
    p = await S['db'].pedidos.find_one({'id': pid})
    personal = bool(set(PERSONAL) & set(ctx.roles))
    if not p or (not personal and p['cuentaId'] != ctx.cuenta):
        raise AppError(404, 'NO_ENCONTRADO', 'Pedido no encontrado.')       # C1: no se revela la existencia
    return p, personal

@app.get('/orders/{pid}')
async def s14(pid: str, ctx: Ctx = LECTURA):
    p, personal = await propio_o_personal(pid, ctx)
    return detalle(p, personal)

# ---------------- anulacion ----------------
async def anular(p, motivo, actor, permitidos, rid):
    db = S['db']
    pagado = bool(p.get('pagadoEn'))
    u = await db.pedidos.update_one({'id': p['id'], 'estado': {'$in': permitidos}},
                                    {'$set': {'estado': 'anulado', 'motivoAnulacion': motivo, 'reembolsoPendiente': pagado},
                                     '$push': {'historial': {'estado': 'anulado', 'fecha': ahora(), 'actor': actor, 'motivo': motivo}}})
    if u.modified_count == 0:
        raise AppError(409, 'TRANSICION_INVALIDA', 'El pedido ya no se puede anular.')
    await liberar_stock(p, rid)
    if pagado and p.get('despachoPublicado'):
        await db.pedidos.update_one({'id': p['id']}, {'$set': {'despachoAnuladaPendiente': True}})
        if await publicar(msg_despacho(p, 'anulada')):
            await db.pedidos.update_one({'id': p['id']}, {'$set': {'despachoAnuladaPendiente': False}})
    evento(log, 'orders-service', 'pedido_anulado', requestId=rid, pedidoId=p['id'], actor=actor, reembolso=pagado)
    return await db.pedidos.find_one({'id': p['id']})

@app.post('/orders/{pid}/cancel')
async def s15(pid: str, request: Request, ctx: Ctx = CLI):
    d = await json_de(request)
    mo = d.get('motivo')
    if not isinstance(mo, str) or not (5 <= len(mo.strip()) <= 200): raise AppError(400, 'DATOS_INVALIDOS', 'Datos inválidos en: motivo')
    p, _ = await propio_o_personal(pid, ctx)
    if p['estado'] not in ('pendiente_pago', 'pagado'):
        raise AppError(409, 'TRANSICION_INVALIDA', 'El pedido ya no se puede anular.')
    n = await anular(p, mo.strip(), 'cliente', ['pendiente_pago', 'pagado'], ctx.rid)
    return {'id': n['id'], 'estado': 'anulado', 'motivo': n['motivoAnulacion'], 'reembolsoPendiente': n['reembolsoPendiente']}

# ---------------- S16 / S17 ----------------
@app.get('/admin/orders')
async def s16(estado: str = None, fecha: str = None, limit: int = None, offset: int = None,
              ctx: Ctx = Depends(guard.dep(roles=['administrador', 'cajero_virtual', 'encargado_despachos']))):
    limit, offset = paginar(limit, offset)
    q = {}
    if estado:
        if estado not in ESTADOS: raise AppError(400, 'DATOS_INVALIDOS', 'Filtro inválido: estado')
        q['estado'] = estado
    if fecha:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', fecha): raise AppError(400, 'DATOS_INVALIDOS', 'Filtro inválido: fecha')
        q['creadoEn'] = {'$gte': fecha + 'T00:00:00Z', '$lte': fecha + 'T23:59:59Z'}
    cur = S['db'].pedidos.find(q).sort('creadoEn', -1).skip(offset).limit(limit)
    return [{'id': p['id'], 'estado': p['estado'], 'total': p['total'], 'creadoEn': p['creadoEn'], 'clienteNombre': p['clienteNombre'],
             'direccionEntrega': p['direccionEntrega'], 'revisar': bool(p.get('revisar'))} async for p in cur]

@app.patch('/admin/orders/{pid}/status')
async def s17(pid: str, request: Request, ctx: Ctx = Depends(guard.dep(roles=['administrador', 'encargado_despachos']))):
    d = await json_de(request)
    nuevo = d.get('estado')
    if nuevo not in ESTADOS: raise AppError(400, 'DATOS_INVALIDOS', 'Datos inválidos en: estado')
    p = await S['db'].pedidos.find_one({'id': pid})
    if not p: raise AppError(404, 'NO_ENCONTRADO', 'Pedido no encontrado.')
    if nuevo == 'anulado':
        if 'administrador' not in ctx.roles: raise AppError(403, 'SIN_PERMISO', 'No tienes permiso para esta acción.')
        mo = d.get('motivo')
        if not isinstance(mo, str) or not (5 <= len(mo.strip()) <= 200): raise AppError(400, 'DATOS_INVALIDOS', 'Debes indicar el motivo (5 a 200 caracteres).')
        if p['estado'] not in ('pendiente_pago', 'pagado', 'en_preparacion'):
            raise AppError(409, 'TRANSICION_INVALIDA', f'No se puede pasar de {p["estado"]} a anulado.')
        n = await anular(p, mo.strip(), 'personal', ['pendiente_pago', 'pagado', 'en_preparacion'], ctx.rid)
        return detalle(n, True)
    if TRANSICIONES.get(p['estado']) != nuevo:           # incluye 'pagado': solo lo fija el pago confirmado (I12)
        raise AppError(409, 'TRANSICION_INVALIDA', f'No se puede pasar de {p["estado"]} a {nuevo}.')
    u = await S['db'].pedidos.update_one({'id': pid, 'estado': p['estado']},
                                         {'$set': {'estado': nuevo}, '$push': {'historial': {'estado': nuevo, 'fecha': ahora(), 'actor': 'personal'}}})
    if u.modified_count == 0: raise AppError(409, 'TRANSICION_INVALIDA', 'El estado del pedido cambió. Recarga e intenta de nuevo.')
    evento(log, 'orders-service', 'estado_cambiado', requestId=ctx.rid, cuentaId=ctx.cuenta, pedidoId=pid, estado=nuevo)
    return detalle(await S['db'].pedidos.find_one({'id': pid}), True)

# ---------------- I11 / I12 (solo payments-service) ----------------
PAY = Depends(guard.dep(gateway=False, pares=('payments-service',)))

@app.get('/internal/orders/{pid}/payable')
async def i11(pid: str, cuentaId: str, ctx: Ctx = PAY):
    p = await S['db'].pedidos.find_one({'id': pid})
    if not p or p['cuentaId'] != cuentaId: raise AppError(404, 'NO_ENCONTRADO', 'Pedido no encontrado.')
    if p['estado'] != 'pendiente_pago' or p['expiraEn'] <= ahora():
        raise AppError(409, 'PEDIDO_NO_PAGABLE', 'El pedido está anulado, vencido o ya pagado.')
    return {'pedidoId': p['id'], 'total': p['total'], 'estado': p['estado'], 'expiraEn': p['expiraEn']}

def resp_i12(p):
    return {'pedidoId': p['id'], 'total': p['total'], 'cuentaId': p['cuentaId'], 'clienteNombre': p['clienteNombre'],
            'clienteCorreo': p['clienteCorreo'], 'pagadoEn': p['pagadoEn'], 'items': p['items']}

@app.post('/internal/orders/{pid}/payment-confirmation')
async def i12(pid: str, request: Request, ctx: Ctx = PAY):
    d = await json_de(request)
    if not isinstance(d.get('pagoId'), str) or not isinstance(d.get('monto'), int) or isinstance(d.get('monto'), bool):
        raise AppError(400, 'DATOS_INVALIDOS', 'Datos inválidos.')
    db = S['db']
    p = await db.pedidos.find_one({'id': pid})
    if not p: raise AppError(404, 'NO_ENCONTRADO', 'Pedido no encontrado.')
    if p.get('pagoId') == d['pagoId'] and p.get('pagadoEn'):
        return resp_i12(p)                                   # idempotente por pagoId
    if p['total'] != d['monto']:
        raise AppError(409, 'PEDIDO_NO_PAGABLE', 'El monto no coincide con el total del pedido.')
    ahora_ = ahora()
    u = await db.pedidos.update_one({'id': pid, 'estado': 'pendiente_pago', 'expiraEn': {'$gt': ahora_}},
                                    {'$set': {'estado': 'pagado', 'pagoId': d['pagoId'], 'pagadoEn': ahora_},
                                     '$push': {'historial': {'estado': 'pagado', 'fecha': ahora_, 'actor': 'sistema'}}})
    if u.modified_count == 0:
        raise AppError(409, 'PEDIDO_NO_PAGABLE', 'El pedido está anulado, vencido o ya pagado.')
    p = await db.pedidos.find_one({'id': pid})
    evento(log, 'orders-service', 'pedido_pagado', requestId=ctx.rid, pedidoId=pid, pagoId=d['pagoId'])
    try:
        r = await S['svc'].llamar('inventory-service', 'POST', f'/internal/stock/reservations/{pid}/confirm', ctx.rid, timeout=3.0)
        if r.status_code == 200: await db.pedidos.update_one({'id': pid}, {'$set': {'reservaConfirmada': True}})
        elif r.status_code in (404, 409): await db.pedidos.update_one({'id': pid}, {'$set': {'revisar': True}})
    except AppError:
        pass                                                 # la tarea de reintentos repite I09
    if await publicar(msg_despacho(p, 'nueva')):
        await db.pedidos.update_one({'id': pid}, {'$set': {'despachoPublicado': True}})
    return resp_i12(p)

if __name__ == '__main__':
    run(app)
