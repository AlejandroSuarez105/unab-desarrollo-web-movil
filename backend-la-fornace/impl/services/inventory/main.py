"""inventory-service: catalogo, precio, disponibilidad, stock y reservas (S06-S11, I08-I10). Autoridad de precio y stock."""
import os, re, asyncio
from fastapi import Depends, Request, Response
from pymongo.errors import DuplicateKeyError
from fornace.base import make_app, run, AppError, evento
from fornace.vault import SecretProvider
from fornace.guard import Guard, Ctx
from fornace.db import conectar, siguiente, ahora, en_segundos
from fornace.retencion import corte, INTERVALO
from fornace.util import paginar

SISTEMA = 'inventory'
CATEGORIAS = ('clasica', 'premium', 'acompanamiento', 'bebida', 'combo')
vault = SecretProvider()
guard = Guard(SISTEMA, vault)
S = {}
# Con una sola instancia de inventory-service, los cambios de stock se serializan en el proceso: no se depende de la atomicidad
# de cada actualizacion condicional frente a peticiones simultaneas (prueba C3: 30 pedidos simultaneos con stock 10 dan 10 creados).
BLOQUEO = asyncio.Lock()

async def startup(app):
    S['cli'], S['db'] = await conectar(SISTEMA, vault)
    db = S['db']
    await db.productos.create_index('id', unique=True)
    await db.productos.create_index('nombre', unique=True)
    await db.reservas.create_index('pedidoId', unique=True)
    await db.reservas.create_index([('estado', 1), ('expiraEn', 1)])

async def devolver(reserva):
    async with BLOQUEO:
        await _devolver(reserva)

async def _devolver(reserva):
    db = S['db']
    for it in reserva['items']:
        await db.productos.update_one({'id': it['productoId']}, {'$inc': {'stock': it['cantidad']}})
        await db.movimientos.insert_one({'productoId': it['productoId'], 'tipo': 'liberacion', 'cantidad': it['cantidad'], 'pedidoId': reserva['pedidoId'], 'fecha': ahora()})

async def liberar_vencidas():
    """Cada minuto: libera reservas sin confirmar cuyo plazo vencio (M3 3.9)."""
    db = S['db']
    async for r in db.reservas.find({'estado': 'reservada', 'expiraEn': {'$lte': ahora()}}):
        u = await db.reservas.update_one({'pedidoId': r['pedidoId'], 'estado': 'reservada'}, {'$set': {'estado': 'liberada', 'liberadaEn': ahora(), 'motivo': 'vencida'}})
        if u.modified_count:
            await devolver(r)
            evento(log, 'inventory-service', 'reserva_vencida_liberada', pedidoId=r['pedidoId'])

async def retencion():
    """7.9: los movimientos de stock se eliminan a los 12 meses."""
    r = await S['db'].movimientos.delete_many({'fecha': {'$lt': corte('movimiento_stock')}})
    if r.deleted_count:
        evento(log, 'inventory-service', 'retencion', movimientos=r.deleted_count)

app = make_app('inventory-service', startup=startup, tareas=[('reservas_vencidas', int(os.environ.get('RESERVAS_SEGUNDOS', '60')), liberar_vencidas),
                                                             ('retencion', INTERVALO, retencion)])
log = app.state.log

def publico(p):
    return {'id': p['id'], 'nombre': p['nombre'], 'categoria': p['categoria'], 'descripcion': p['descripcion'], 'precio': p['precio'],
            'imagen': p['imagen'], 'destacado': p['destacado'], 'disponible': bool(p['disponible'] and p['stock'] > 0 and not p['retirado'])}

def booleano(v, nombre):
    if v is None: return None
    if v.lower() in ('true', '1'): return True
    if v.lower() in ('false', '0'): return False
    raise AppError(400, 'DATOS_INVALIDOS', f'Filtro inválido: {nombre}')

# ---------- S06 ----------
@app.get('/products')
async def s06(categoria: str = None, disponible: str = None, destacado: str = None, ids: str = None, limit: int = None, offset: int = None,
              ctx: Ctx = Depends(guard.dep(publica=True, pares=('graphql-gateway',), pares_solo_get=('graphql-gateway',)))):
    limit, offset = paginar(limit, offset)
    q = {'retirado': False}
    if categoria:
        if categoria not in CATEGORIAS: raise AppError(400, 'DATOS_INVALIDOS', 'Filtro inválido: categoria')
        q['categoria'] = categoria
    d, f = booleano(disponible, 'disponible'), booleano(destacado, 'destacado')
    if d is True: q.update({'disponible': True, 'stock': {'$gt': 0}})
    if d is False: q['$or'] = [{'disponible': False}, {'stock': {'$lte': 0}}]
    if f is not None: q['destacado'] = f
    if ids:
        lista = [x for x in ids.split(',') if re.fullmatch(r'prod_\d{3,6}', x)][:100]
        q['id'] = {'$in': lista}
    cur = S['db'].productos.find(q).sort('id', 1).skip(offset).limit(limit)
    return [publico(p) async for p in cur]

# ---------- S07 ----------
ADM = Depends(guard.dep(roles=['administrador', 'dueno']))

@app.get('/admin/products')
async def s07(categoria: str = None, incluirRetirados: str = None, limit: int = None, offset: int = None, ctx: Ctx = ADM):
    limit, offset = paginar(limit, offset)
    q = {}
    if categoria:
        if categoria not in CATEGORIAS: raise AppError(400, 'DATOS_INVALIDOS', 'Filtro inválido: categoria')
        q['categoria'] = categoria
    if not booleano(incluirRetirados, 'incluirRetirados'): q['retirado'] = False
    cur = S['db'].productos.find(q).sort('id', 1).skip(offset).limit(limit)
    return [{'id': p['id'], 'nombre': p['nombre'], 'categoria': p['categoria'], 'precio': p['precio'], 'stock': p['stock'],
             'disponible': bool(p['disponible'] and p['stock'] > 0 and not p['retirado']), 'retirado': p['retirado']} async for p in cur]

async def leer(request, con_stock):
    try: d = await request.json()
    except Exception: raise AppError(400, 'DATOS_INVALIDOS', 'El cuerpo debe ser JSON válido.')
    if not isinstance(d, dict): raise AppError(400, 'DATOS_INVALIDOS', 'El cuerpo debe ser un objeto JSON.')
    m = []
    def txt(k, a, b):
        if not isinstance(d.get(k), str) or not (a <= len(d[k].strip()) <= b): m.append(k)
    txt('nombre', 2, 80); txt('descripcion', 0, 300)
    if d.get('categoria') not in CATEGORIAS: m.append('categoria')
    if not isinstance(d.get('precio'), int) or isinstance(d.get('precio'), bool) or not (0 < d['precio'] <= 10_000_000): m.append('precio')
    if not isinstance(d.get('imagen'), str) or not re.match(r'^https?://[^\s]{3,300}$', d['imagen']): m.append('imagen')
    if not isinstance(d.get('destacado'), bool): m.append('destacado')
    if con_stock and (not isinstance(d.get('stock'), int) or isinstance(d.get('stock'), bool) or not (0 <= d['stock'] <= 100000)): m.append('stock')
    if m: raise AppError(400, 'DATOS_INVALIDOS', 'Datos inválidos en: ' + ', '.join(m))
    out = {k: (d[k].strip() if isinstance(d[k], str) else d[k]) for k in ('nombre', 'categoria', 'descripcion', 'precio', 'imagen', 'destacado')}
    if con_stock: out['stock'] = d['stock']
    return out

# ---------- S08 ----------
@app.post('/products', status_code=201)
async def s08(request: Request, ctx: Ctx = ADM):
    d = await leer(request, True)
    pid = await siguiente(S['db'], 'prod', 'prod_', 3)
    doc = dict(d, id=pid, disponible=True, retirado=False, creadoEn=ahora())
    try: await S['db'].productos.insert_one(doc)
    except DuplicateKeyError: raise AppError(409, 'NOMBRE_DUPLICADO', 'Ya existe un producto con ese nombre.')
    await S['db'].movimientos.insert_one({'productoId': pid, 'tipo': 'alta', 'cantidad': d['stock'], 'fecha': ahora()})
    evento(log, 'inventory-service', 'producto_creado', requestId=ctx.rid, cuentaId=ctx.cuenta, id=pid)
    return publico(doc)

# ---------- S09 ----------
@app.put('/products/{pid}')
async def s09(pid: str, request: Request, ctx: Ctx = ADM):
    d = await leer(request, False)
    try:
        r = await S['db'].productos.update_one({'id': pid, 'retirado': False}, {'$set': d})
    except DuplicateKeyError:
        raise AppError(409, 'NOMBRE_DUPLICADO', 'Ya existe un producto con ese nombre.')
    if r.matched_count == 0: raise AppError(404, 'NO_ENCONTRADO', 'Producto no encontrado.')
    return publico(await S['db'].productos.find_one({'id': pid}))

# ---------- S10 (baja logica, C13) ----------
@app.delete('/products/{pid}', status_code=204)
async def s10(pid: str, ctx: Ctx = ADM):
    r = await S['db'].productos.update_one({'id': pid}, {'$set': {'retirado': True, 'disponible': False}})
    if r.matched_count == 0: raise AppError(404, 'NO_ENCONTRADO', 'Producto no encontrado.')
    evento(log, 'inventory-service', 'producto_retirado', requestId=ctx.rid, cuentaId=ctx.cuenta, id=pid)
    return Response(status_code=204)

# ---------- S11 ----------
@app.put('/products/{pid}/stock')
async def s11(pid: str, request: Request, ctx: Ctx = ADM):
    try: d = await request.json()
    except Exception: raise AppError(400, 'DATOS_INVALIDOS', 'El cuerpo debe ser JSON válido.')
    if not isinstance(d, dict) or not isinstance(d.get('stock'), int) or isinstance(d.get('stock'), bool) or not (0 <= d['stock'] <= 100000) or not isinstance(d.get('disponible'), bool):
        raise AppError(400, 'DATOS_INVALIDOS', 'Datos inválidos en: stock, disponible')
    async with BLOQUEO:
        p = await S['db'].productos.find_one_and_update({'id': pid, 'retirado': False}, {'$set': {'stock': d['stock'], 'disponible': d['disponible']}})
    if not p: raise AppError(404, 'NO_ENCONTRADO', 'Producto no encontrado.')
    await S['db'].movimientos.insert_one({'productoId': pid, 'tipo': 'ajuste', 'cantidad': d['stock'] - p['stock'], 'fecha': ahora()})
    evento(log, 'inventory-service', 'stock_ajustado', requestId=ctx.rid, cuentaId=ctx.cuenta, id=pid)
    return {'id': pid, 'stock': d['stock'], 'disponible': d['disponible'] and d['stock'] > 0}

# ---------- I08 reservar ----------
ORD = Depends(guard.dep(gateway=False, pares=('orders-service',)))

async def reservar(pedido_id, items, expira):
    """Todo o nada: descuento atomico por producto; si alguno falla se devuelve lo descontado."""
    db = S['db']
    hechos, nombres = [], {}
    for it in items:
        p = await db.productos.find_one({'id': it['productoId']})
        if not p or p['retirado']:
            await devolver_hechos(pedido_id, hechos)
            raise AppError(404, 'PRODUCTO_NO_ENCONTRADO', 'Producto no encontrado.')
        r = await db.productos.update_one({'id': p['id'], 'retirado': False, 'disponible': True, 'stock': {'$gte': it['cantidad']}}, {'$inc': {'stock': -it['cantidad']}})
        if r.modified_count == 0:
            await devolver_hechos(pedido_id, hechos)
            act = await db.productos.find_one({'id': p['id']})
            if not act['disponible']:
                raise AppError(409, 'PRODUCTO_NO_DISPONIBLE', f'{p["nombre"]} no está disponible.')
            e = AppError(409, 'SIN_STOCK', f'{p["nombre"]} no tiene stock suficiente.')
            e.extra = {'productos': [{'productoId': p['id'], 'disponible': max(act['stock'], 0)}]}
            raise e
        hechos.append(it)
        nombres[p['id']] = p
        await db.movimientos.insert_one({'productoId': p['id'], 'tipo': 'reserva', 'cantidad': -it['cantidad'], 'pedidoId': pedido_id, 'fecha': ahora()})
    return [{'productoId': it['productoId'], 'nombre': nombres[it['productoId']]['nombre'], 'precioUnitario': nombres[it['productoId']]['precio'], 'cantidad': it['cantidad']} for it in items]

async def devolver_hechos(pedido_id, hechos):
    if hechos:
        await _devolver({'pedidoId': pedido_id, 'items': hechos})

@app.post('/internal/stock/reservations', status_code=201)
async def i08(request: Request, ctx: Ctx = ORD):
    try: d = await request.json()
    except Exception: raise AppError(400, 'DATOS_INVALIDOS', 'El cuerpo debe ser JSON válido.')
    ok = isinstance(d, dict) and isinstance(d.get('pedidoId'), str) and isinstance(d.get('expiraEn'), str) and isinstance(d.get('items'), list) and 1 <= len(d['items']) <= 30
    if ok:
        vistos = set()
        for it in d['items']:
            if not (isinstance(it, dict) and isinstance(it.get('productoId'), str) and isinstance(it.get('cantidad'), int) and 1 <= it['cantidad'] <= 20) or it['productoId'] in vistos:
                ok = False; break
            vistos.add(it['productoId'])
    if not ok: raise AppError(400, 'DATOS_INVALIDOS', 'Datos inválidos.')
    db = S['db']
    # el indice unico sobre pedidoId reclama la reserva: una repeticion devuelve la respuesta anterior
    try:
        await db.reservas.insert_one({'pedidoId': d['pedidoId'], 'estado': 'procesando', 'expiraEn': d['expiraEn'], 'items': [], 'creadoEn': ahora()})
    except DuplicateKeyError:
        ex = await db.reservas.find_one({'pedidoId': d['pedidoId']})
        if ex['estado'] in ('reservada', 'confirmada'):
            return {'pedidoId': d['pedidoId'], 'items': ex['items']}
        raise AppError(409, 'RESERVA_NO_VIGENTE', 'La reserva de este pedido no está vigente.')
    try:
        async with BLOQUEO:
            res = await reservar(d['pedidoId'], d['items'], d['expiraEn'])
    except BaseException:
        await db.reservas.delete_one({'pedidoId': d['pedidoId'], 'estado': 'procesando'})
        raise
    await db.reservas.update_one({'pedidoId': d['pedidoId']}, {'$set': {'estado': 'reservada', 'items': res}})
    return {'pedidoId': d['pedidoId'], 'items': res}

# ---------- I09 confirmar ----------
@app.post('/internal/stock/reservations/{pedido_id}/confirm')
async def i09(pedido_id: str, ctx: Ctx = ORD):
    db = S['db']
    r = await db.reservas.find_one({'pedidoId': pedido_id})
    if not r: raise AppError(404, 'RESERVA_NO_ENCONTRADA', 'Reserva no encontrada.')
    if r['estado'] == 'confirmada': return {'pedidoId': pedido_id, 'estado': 'confirmada'}
    if r['estado'] == 'reservada':
        u = await db.reservas.update_one({'pedidoId': pedido_id, 'estado': 'reservada'}, {'$set': {'estado': 'confirmada', 'confirmadaEn': ahora()}})
        if u.modified_count: return {'pedidoId': pedido_id, 'estado': 'confirmada'}
        r = await db.reservas.find_one({'pedidoId': pedido_id})
        if r['estado'] == 'confirmada': return {'pedidoId': pedido_id, 'estado': 'confirmada'}
    # liberada (vencio): caso residual 3.9. Se intenta volver a reservar; si el stock ya se vendio, 409.
    hechos = []
    async with BLOQUEO:
        for it in r['items']:
            u = await db.productos.update_one({'id': it['productoId'], 'stock': {'$gte': it['cantidad']}}, {'$inc': {'stock': -it['cantidad']}})
            if u.modified_count == 0:
                for h in hechos: await db.productos.update_one({'id': h['productoId']}, {'$inc': {'stock': h['cantidad']}})
                raise AppError(409, 'RESERVA_VENCIDA', 'La reserva venció y el stock ya no está disponible.')
            hechos.append(it)
    await db.reservas.update_one({'pedidoId': pedido_id}, {'$set': {'estado': 'confirmada', 'confirmadaEn': ahora()}})
    return {'pedidoId': pedido_id, 'estado': 'confirmada'}

# ---------- I10 liberar ----------
@app.post('/internal/stock/reservations/{pedido_id}/release')
async def i10(pedido_id: str, ctx: Ctx = ORD):
    db = S['db']
    r = await db.reservas.find_one({'pedidoId': pedido_id})
    if not r: return {'pedidoId': pedido_id, 'liberada': False}
    u = await db.reservas.update_one({'pedidoId': pedido_id, 'estado': {'$in': ['reservada', 'confirmada']}}, {'$set': {'estado': 'liberada', 'liberadaEn': ahora(), 'motivo': 'anulacion'}})
    if u.modified_count: await devolver(r)
    return {'pedidoId': pedido_id, 'liberada': bool(u.modified_count)}

if __name__ == '__main__':
    run(app)
