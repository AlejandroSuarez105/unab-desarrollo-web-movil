"""payments-service: cobro, aviso de la plataforma, venta, boleta y reporte (S20-S23, S34, I11-I13, I15, I16)."""
import os, re, json, asyncio, hmac, hashlib, time, datetime
import httpx
from fastapi import Depends, Request
from pymongo.errors import DuplicateKeyError
from fornace.base import make_app, run, AppError, evento
from fornace.vault import SecretProvider, iguales
from fornace.guard import Guard, Ctx
from fornace.svc import Servicios
from fornace.db import conectar, siguiente, ahora, en_segundos
from fornace.retencion import corte, INTERVALO
from fornace.util import paginar, rango_fechas

SISTEMA = 'payments'
IVA = 1.19
vault = SecretProvider()
guard = Guard(SISTEMA, vault)
S = {}
SEGUNDO_PLANO = set()
CONFIRMACIONES = asyncio.Semaphore(2)     # a lo mas 2 confirmaciones a la vez para no quitarle la base de datos a los avisos nuevos

async def startup(app):
    S['cli'], S['db'] = await conectar(SISTEMA, vault)
    S['svc'] = Servicios('payments-service', vault, app.state.log)
    S['http'] = httpx.AsyncClient(verify=os.environ.get('CA_FILE') or True)
    db = S['db']
    await db.pagos.create_index('id', unique=True)
    await db.pagos.create_index('pedidoId')
    await db.eventos.create_index('eventoId', unique=True)
    await db.ventas.create_index('pedidoId', unique=True)
    await db.ventas.create_index('numeroBoleta', unique=True)
    await db.ventas.create_index('fecha')
    await db.ventas.create_index('enResumen')
    await db.resumen_dia.create_index('fecha', unique=True)
    await db.resumen_producto.create_index([('fecha', 1), ('productoId', 1)], unique=True)

async def conciliar():
    """Repite I12 para los pagos aprobados que orders todavia no confirmo (M3 3.5)."""
    db = S['db']
    async for p in db.pagos.find({'estado': 'aprobado', 'confirmadoEnPedidos': False}).limit(100):
        if p['aprobadoEn'] < en_segundos(-600):
            evento(log, 'payments-service', 'alerta_conciliacion', pagoId=p['id'], pedidoId=p['pedidoId'])
        await confirmar_en_pedidos(p, None)

async def reintentar_correos():
    db = S['db']
    async for v in db.ventas.find({'correoEnviado': False, 'correoIntentos': {'$lt': 5}}).limit(100):
        await enviar_boleta(v, None)

async def resumen_tarea():
    await pendientes_resumen()

async def retencion():
    """7.9: avisos de pago y pagos sin venta, a los 12 meses. Los pagos con venta se conservan con la venta (6 anios)."""
    db, c = S['db'], corte('evento_pago')
    ev = await db.eventos.delete_many({'recibidoEn': {'$lt': c}})
    pagos = 0
    async for p in db.pagos.find({'creadoEn': {'$lt': c}}, {'id': 1, 'pedidoId': 1}).limit(500):
        if await db.ventas.find_one({'pedidoId': p['pedidoId']}, {'_id': 1}) is None:
            pagos += (await db.pagos.delete_one({'id': p['id']})).deleted_count
    if ev.deleted_count or pagos:
        evento(log, 'payments-service', 'retencion', eventos=ev.deleted_count, pagos=pagos)

app = make_app('payments-service', startup=startup,
               tareas=[('resumen', int(os.environ.get('REINTENTO_SEGUNDOS', '30')), resumen_tarea), ('conciliar', int(os.environ.get('REINTENTO_SEGUNDOS', '30')), conciliar),
                       ('correos', int(os.environ.get('CORREO_REINTENTO_SEGUNDOS', '300')), reintentar_correos),
                       ('retencion', INTERVALO, retencion)])
log = app.state.log

async def json_de(request):
    try: d = await request.json()
    except Exception: raise AppError(400, 'DATOS_INVALIDOS', 'El cuerpo debe ser JSON válido.')
    if not isinstance(d, dict): raise AppError(400, 'DATOS_INVALIDOS', 'El cuerpo debe ser un objeto JSON.')
    return d

def ext(r):
    try: return r.json().get('error', {})
    except Exception: return {}

# ---------------- S20 ----------------
@app.post('/orders/{pid}/payments', status_code=201)
async def s20(pid: str, request: Request, ctx: Ctx = Depends(guard.dep(roles=['cliente']))):
    d = await json_de(request)
    if d.get('medio') not in ('servipag', 'deposito'): raise AppError(400, 'DATOS_INVALIDOS', 'Datos inválidos en: medio')
    db = S['db']
    r = await S['svc'].llamar('orders-service', 'GET', f'/internal/orders/{pid}/payable', ctx.rid, params={'cuentaId': ctx.cuenta}, timeout=5.0)
    if r.status_code == 404: raise AppError(404, 'NO_ENCONTRADO', 'Pedido no encontrado.')
    if r.status_code == 409: raise AppError(409, 'PEDIDO_NO_PAGABLE', 'El pedido está anulado, vencido o ya pagado.')
    if r.status_code != 200: raise AppError(503, 'SERVICIO_NO_DISPONIBLE', 'Servicio no disponible. Intenta de nuevo en un momento.')
    ped = r.json()
    if await db.pagos.find_one({'pedidoId': pid, 'estado': 'aprobado'}):
        raise AppError(409, 'PAGO_YA_APROBADO', 'El pedido ya tiene un pago aprobado.')
    pago_id = await siguiente(db, 'pag', 'pag_')
    try:
        c = await S['http'].post(os.environ['URL_PASARELA'].rstrip('/') + '/cobros', timeout=6.0, headers={'X-API-Key': vault.actual('payments/provider')},
                                 json={'pagoId': pago_id, 'monto': ped['total'], 'medio': d['medio'], 'retorno': pid})
    except httpx.HTTPError:
        raise AppError(503, 'PASARELA_NO_DISPONIBLE', 'La plataforma de pago no responde. Intenta de nuevo.')
    if c.status_code != 201: raise AppError(502, 'PASARELA_NO_DISPONIBLE', 'La plataforma de pago no respondió bien.')
    await db.pagos.update_many({'pedidoId': pid, 'estado': 'pendiente'}, {'$set': {'estado': 'expirado'}})
    await db.pagos.insert_one({'id': pago_id, 'pedidoId': pid, 'cuentaId': ctx.cuenta, 'monto': ped['total'], 'medio': d['medio'], 'estado': 'pendiente',
                               'urlPago': c.json()['urlPago'], 'expiraEn': ped['expiraEn'], 'creadoEn': ahora(), 'confirmadoEnPedidos': False})
    evento(log, 'payments-service', 'pago_iniciado', requestId=ctx.rid, cuentaId=ctx.cuenta, pagoId=pago_id, pedidoId=pid)
    return {'pagoId': pago_id, 'estado': 'pendiente', 'urlPago': c.json()['urlPago'], 'expiraEn': ped['expiraEn']}

# ---------------- S21 webhook ----------------
@app.post('/payments/webhook')
async def s21(request: Request, ctx: Ctx = Depends(guard.dep(publica=True))):
    raw = await request.body()
    ts, firma = request.headers.get('x-timestamp', ''), request.headers.get('x-signature', '')
    try:
        ok_ts = abs(time.time() - int(ts)) <= 300
    except ValueError:
        ok_ts = False
    valida = False
    if ok_ts and firma.startswith('sha256='):
        for sec in vault.candidatos('payments/webhook'):
            esperada = hmac.new(sec.encode(), ts.encode() + b'.' + raw, hashlib.sha256).hexdigest()
            valida = valida or iguales(firma[7:], esperada)
    if not valida:
        evento(log, 'payments-service', 'webhook_rechazado', requestId=ctx.rid, motivo='firma_o_fecha')
        raise AppError(401, 'FIRMA_INVALIDA', 'Firma inválida.')
    try:
        d = json.loads(raw)
    except Exception:
        raise AppError(400, 'DATOS_INVALIDOS', 'Cuerpo inválido.')
    if not (isinstance(d, dict) and isinstance(d.get('eventoId'), str) and 3 <= len(d['eventoId']) <= 80 and isinstance(d.get('pagoId'), str)
            and d.get('estado') in ('aprobado', 'rechazado', 'expirado') and isinstance(d.get('monto'), int) and not isinstance(d.get('monto'), bool)):
        raise AppError(400, 'DATOS_INVALIDOS', 'Cuerpo inválido.')
    db = S['db']
    pago = await db.pagos.find_one({'id': d['pagoId']})
    if not pago: raise AppError(400, 'DATOS_INVALIDOS', 'Pago desconocido.')
    try:
        await db.eventos.insert_one({'eventoId': d['eventoId'], 'pagoId': d['pagoId'], 'estado': d['estado'], 'monto': d['monto'], 'recibidoEn': ahora()})
    except DuplicateKeyError:
        return {'recibido': True}                                   # duplicado: no se procesa otra vez
    if pago['estado'] != 'pendiente' or d['monto'] != pago['monto']:
        if pago['estado'] == 'pendiente' or (pago['estado'] in ('rechazado', 'expirado') and d['estado'] == 'aprobado'):
            await db.pagos.update_one({'id': pago['id']}, {'$set': {'estado': 'observado', 'observacion': 'monto_distinto' if d['monto'] != pago['monto'] else 'pago_no_pendiente'}})
            evento(log, 'payments-service', 'pago_observado', requestId=ctx.rid, pagoId=pago['id'])
        return {'recibido': True}
    if d['estado'] in ('rechazado', 'expirado'):
        await db.pagos.update_one({'id': pago['id'], 'estado': 'pendiente'}, {'$set': {'estado': d['estado']}})
        return {'recibido': True}
    u = await db.pagos.update_one({'id': pago['id'], 'estado': 'pendiente'}, {'$set': {'estado': 'aprobado', 'aprobadoEn': ahora()}})
    if u.modified_count:
        # se responde de inmediato a la plataforma; la confirmacion en orders y la boleta siguen en segundo plano
        # (si el proceso cae, la tarea de conciliacion repite I12 porque confirmadoEnPedidos queda en falso)
        tarea = asyncio.create_task(confirmar_en_pedidos(await db.pagos.find_one({'id': pago['id']}), ctx.rid))
        SEGUNDO_PLANO.add(tarea); tarea.add_done_callback(SEGUNDO_PLANO.discard)
    return {'recibido': True}

async def aplicar_resumen(v):
    """Suma la venta a los resumenes diarios que lee el reporte S34. El indicador enResumen evita sumarla dos veces."""
    db = S['db']
    if v.get('enResumen'): return
    u = await db.ventas.update_one({'id': v['id'], 'enResumen': False}, {'$set': {'enResumen': True}})
    if not u.modified_count: return
    dia = v['fecha'][:10]
    await db.resumen_dia.update_one({'fecha': dia}, {'$inc': {'ventas': 1, 'total': v['total']}}, upsert=True)
    for i in v['items']:
        await db.resumen_producto.update_one({'fecha': dia, 'productoId': i['productoId']}, {'$inc': {'unidades': i['cantidad']}, '$set': {'nombre': i['nombre']}}, upsert=True)

async def pendientes_resumen():
    """Tarea periodica: si el servicio cayo entre guardar la venta y sumarla al resumen, la suma se completa."""
    async for v in S['db'].ventas.find({'enResumen': False}).limit(100):
        await aplicar_resumen(v)

async def confirmar_en_pedidos(pago, rid):
    async with CONFIRMACIONES:
        return await _confirmar_en_pedidos(pago, rid)

async def _confirmar_en_pedidos(pago, rid):
    """I12 + venta + boleta. Si orders no responde, el pago queda aprobado y la conciliacion lo repite."""
    db = S['db']
    try:
        r = await S['svc'].llamar('orders-service', 'POST', f'/internal/orders/{pago["pedidoId"]}/payment-confirmation', rid,
                                  json={'pagoId': pago['id'], 'monto': pago['monto']}, timeout=5.0)
    except AppError:
        return False
    if r.status_code == 409:
        await db.pagos.update_one({'id': pago['id']}, {'$set': {'estado': 'observado', 'observacion': 'pedido_no_pagable'}})
        evento(log, 'payments-service', 'pago_observado', requestId=rid, pagoId=pago['id'], motivo='pedido_no_pagable')
        return False
    if r.status_code != 200:
        return False
    c = r.json()
    v = await db.ventas.find_one({'pedidoId': c['pedidoId']})
    if not v:
        num = await siguiente(db, 'boleta', 'B-', 6)
        vid = await siguiente(db, 'ven', 'ven_')
        v = {'id': vid, 'pedidoId': c['pedidoId'], 'pagoId': pago['id'], 'cuentaId': c['cuentaId'], 'numeroBoleta': num, 'total': c['total'],
             'ivaIncluido': round(c['total'] - c['total'] / IVA), 'fecha': c['pagadoEn'], 'clienteNombre': c['clienteNombre'], 'clienteCorreo': c['clienteCorreo'],
             'items': c['items'], 'correoEnviado': False, 'correoIntentos': 0, 'creadoEn': ahora()}
        v['enResumen'] = False
        try:
            await db.ventas.insert_one(v)
        except DuplicateKeyError:
            v = await db.ventas.find_one({'pedidoId': c['pedidoId']})
        await aplicar_resumen(v)
    await db.pagos.update_one({'id': pago['id']}, {'$set': {'confirmadoEnPedidos': True}})
    evento(log, 'payments-service', 'venta_registrada', requestId=rid, pedidoId=c['pedidoId'], boleta=v['numeroBoleta'])
    if not v['correoEnviado']:
        await enviar_boleta(v, rid)
    return True

async def enviar_boleta(v, rid):
    db = S['db']
    try:
        r = await S['svc'].llamar('notifications-service', 'POST', '/internal/emails', rid, timeout=6.0,
                                  json={'plantilla': 'boleta', 'correo': v['clienteCorreo'], 'numeroBoleta': v['numeroBoleta'], 'total': v['total'],
                                        'items': v['items']})
        ok = r.status_code == 200
    except AppError:
        ok = False
    await db.ventas.update_one({'id': v['id']}, {'$set': {'correoEnviado': ok}, '$inc': {'correoIntentos': 1}})
    return ok

# ---------------- S22 ----------------
@app.get('/admin/sales')
async def s22(desde: str = None, hasta: str = None, limit: int = None, offset: int = None,
              ctx: Ctx = Depends(guard.dep(roles=['administrador', 'cajero_virtual']))):
    limit, offset = paginar(limit, offset)
    d, h = rango_fechas(desde, hasta)
    q = {}
    if d or h:
        q['fecha'] = {}
        if d: q['fecha']['$gte'] = d.isoformat() + 'T00:00:00Z'
        if h: q['fecha']['$lte'] = h.isoformat() + 'T23:59:59Z'
    cur = S['db'].ventas.find(q).sort('fecha', -1).skip(offset).limit(limit)
    return [{'ventaId': v['id'], 'pedidoId': v['pedidoId'], 'numeroBoleta': v['numeroBoleta'], 'total': v['total'], 'fecha': v['fecha'],
             'correoEnviado': v['correoEnviado']} async for v in cur]

# ---------------- S23 ----------------
@app.get('/orders/{pid}/receipt')
async def s23(pid: str, ctx: Ctx = Depends(guard.dep(roles=['administrador', 'cajero_virtual', 'cliente']))):
    db = S['db']
    v = await db.ventas.find_one({'pedidoId': pid})
    personal = bool({'administrador', 'cajero_virtual'} & set(ctx.roles))
    if v and (personal or v['cuentaId'] == ctx.cuenta):
        return {'numeroBoleta': v['numeroBoleta'], 'fechaEmision': v['fecha'], 'pedidoId': pid, 'clienteNombre': v['clienteNombre'],
                'items': [{'nombre': i['nombre'], 'cantidad': i['cantidad'], 'precioUnitario': i['precioUnitario']} for i in v['items']],
                'total': v['total'], 'ivaIncluido': v['ivaIncluido']}
    if not v and await db.pagos.find_one({'pedidoId': pid, 'cuentaId': ctx.cuenta}):
        raise AppError(409, 'PEDIDO_NO_PAGADO', 'El pedido aún no está pagado.')
    raise AppError(404, 'NO_ENCONTRADO', 'Boleta no encontrada.')

# ---------------- S34 ----------------
@app.get('/admin/reports/sales')
async def s34(desde: str = None, hasta: str = None, ctx: Ctx = Depends(guard.dep(roles=['administrador', 'dueno']))):
    if not desde or not hasta: raise AppError(400, 'RANGO_INVALIDO', 'Debes indicar desde y hasta (AAAA-MM-DD).')
    d, h = rango_fechas(desde, hasta, 92)
    # el reporte lee los resumenes diarios (a lo mas 92 dias) y no recorre las ventas
    f = {'fecha': {'$gte': d.isoformat(), '$lte': h.isoformat()}}
    total, cant, dias, prods = 0, 0, {}, {}
    async for x in S['db'].resumen_dia.find(f):
        total += x['total']; cant += x['ventas']; dias[x['fecha']] = {'fecha': x['fecha'], 'ventas': x['ventas'], 'total': x['total']}
    async for x in S['db'].resumen_producto.find(f):
        y = prods.setdefault(x['productoId'], {'productoId': x['productoId'], 'nombre': x['nombre'], 'unidades': 0})
        y['unidades'] += x['unidades']
    return {'desde': desde, 'hasta': hasta, 'totalVentas': total, 'cantidadVentas': cant, 'porDia': sorted(dias.values(), key=lambda z: z['fecha']),
            'topProductos': sorted(prods.values(), key=lambda z: -z['unidades'])[:10]}

if __name__ == '__main__':
    run(app)
