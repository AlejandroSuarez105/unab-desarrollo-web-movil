"""dispatch-service: consume la cola de ordenes de despacho y las entrega para imprimir (S18, S19, I14)."""
import os, json, html, asyncio, threading, time
import stomp
from fastapi import Depends
from fastapi.responses import HTMLResponse
from pymongo.errors import DuplicateKeyError
from fornace.base import make_app, run, AppError, evento
from fornace.vault import SecretProvider
from fornace.guard import Guard, Ctx
from fornace.db import conectar, siguiente, ahora
from fornace.retencion import corte, INTERVALO
from fornace.util import paginar

SISTEMA = 'dispatch'
vault = SecretProvider()
guard = Guard(SISTEMA, vault)
S = {'loop': None, 'conectado': False}

async def startup(app):
    S['cli'], S['db'] = await conectar(SISTEMA, vault)
    S['loop'] = asyncio.get_running_loop()
    db = S['db']
    await db.mensajes.create_index([('pedidoId', 1), ('tipo', 1)], unique=True)
    await db.ordenes.create_index('pedidoId', unique=True)
    await db.ordenes.create_index('numeroOrden', unique=True)
    threading.Thread(target=consumidor, daemon=True).start()

async def retencion():
    """7.9: las ordenes de despacho y sus mensajes se eliminan 90 dias despues de su llegada."""
    db, c = S['db'], corte('orden_despacho')
    o = await db.ordenes.delete_many({'recibidaEn': {'$lt': c}})
    m = await db.mensajes.delete_many({'recibidoEn': {'$lt': c}})
    if o.deleted_count or m.deleted_count:
        evento(log, 'dispatch-service', 'retencion', ordenes=o.deleted_count, mensajes=m.deleted_count)

app = make_app('dispatch-service', startup=startup, tareas=[('retencion', INTERVALO, retencion)])
log = app.state.log

def valida(m):
    return (isinstance(m, dict) and m.get('tipo') in ('nueva', 'anulada') and isinstance(m.get('pedidoId'), str)
            and isinstance(m.get('items'), list) and all(isinstance(i, dict) and isinstance(i.get('nombre'), str) and isinstance(i.get('cantidad'), int) for i in m['items'])
            and isinstance(m.get('direccionEntrega'), dict) and isinstance(m.get('clienteNombre'), str))

async def procesar(m):
    """Idempotente: el indice unico (pedidoId, tipo) de `mensajes` hace que un mensaje repetido no cambie nada."""
    db = S['db']
    try:
        await db.mensajes.insert_one({'pedidoId': m['pedidoId'], 'tipo': m['tipo'], 'recibidoEn': ahora()})
    except DuplicateKeyError:
        evento(log, 'dispatch-service', 'mensaje_repetido', pedidoId=m['pedidoId'], tipo=m['tipo'])
        return
    if m['tipo'] == 'nueva':
        anulada = await db.mensajes.find_one({'pedidoId': m['pedidoId'], 'tipo': 'anulada'}) is not None   # llegada fuera de orden
        await db.ordenes.insert_one({'pedidoId': m['pedidoId'], 'numeroOrden': await siguiente(db, 'orden', 'OD-', 6), 'pagadoEn': m.get('pagadoEn'),
                                     'clienteNombre': m['clienteNombre'], 'telefono': m.get('telefono'), 'direccionEntrega': m['direccionEntrega'],
                                     'items': m['items'], 'impresa': False, 'activa': not anulada, 'recibidaEn': ahora()})
    else:
        await db.ordenes.update_one({'pedidoId': m['pedidoId']}, {'$set': {'activa': False}})
    evento(log, 'dispatch-service', 'orden_recibida', pedidoId=m['pedidoId'], tipo=m['tipo'])

class Oyente(stomp.ConnectionListener):
    """Confirmacion manual (ack client): el broker solo borra el mensaje cuando la orden quedo guardada.
    Si el proceso cae a mitad de camino, el mensaje sin confirmar vuelve a entregarse al reconectar."""
    def __init__(self, conn): self.conn = conn
    def on_message(self, frame):
        mid = frame.headers.get('message-id')
        try:
            m = json.loads(frame.body)
            if not valida(m): raise ValueError('formato')
        except Exception as e:
            evento(log, 'dispatch-service', 'mensaje_invalido', tipo=type(e).__name__)      # al registro de errores; el consumo sigue
            self.conn.ack(mid)                                                               # un mensaje invalido no se reintenta
            return
        try:
            asyncio.run_coroutine_threadsafe(procesar(m), S['loop']).result(10)
            self.conn.ack(mid)
        except Exception as e:
            evento(log, 'dispatch-service', 'orden_error', tipo=type(e).__name__)           # sin ack: el broker lo entrega de nuevo
    def on_disconnected(self):
        S['conectado'] = False

def consumidor():
    """Mantiene la suscripcion; si el broker cae, reconecta."""
    while True:
        try:
            c = vault.get('dispatch/activemq')
            conn = stomp.Connection10([(os.environ['STOMP_HOST'], int(os.environ['STOMP_PORT']))], timeout=4)
            conn.set_listener('', Oyente(conn))
            conn.connect(c['usuario'], c['clave'], wait=True)
            # sin cabecera id: compatible con STOMP 1.0 (la confirmacion manual por message-id funciona con ActiveMQ)
            conn.send_frame('SUBSCRIBE', {'destination': '/queue/cola_pedidos', 'ack': 'client'})
            S['conectado'] = True
            evento(log, 'dispatch-service', 'consumidor_conectado')
            while S['conectado'] and conn.is_connected():
                time.sleep(1)
        except Exception as e:
            evento(log, 'dispatch-service', 'consumidor_reintento', tipo=type(e).__name__)
        S['conectado'] = False
        time.sleep(3)

DES = Depends(guard.dep(roles=['administrador', 'encargado_despachos']))

def vista(o):
    return {'numeroOrden': o['numeroOrden'], 'pedidoId': o['pedidoId'], 'pagadoEn': o['pagadoEn'], 'clienteNombre': o['clienteNombre'],
            'telefono': o['telefono'], 'direccionEntrega': o['direccionEntrega'], 'items': o['items'], 'impresa': o['impresa']}

@app.get('/admin/dispatch-orders')
async def s18(impresa: str = 'false', limit: int = None, ctx: Ctx = DES):
    limit, _ = paginar(limit, None)
    if impresa.lower() not in ('true', 'false'): raise AppError(400, 'DATOS_INVALIDOS', 'Filtro inválido: impresa')
    cur = S['db'].ordenes.find({'activa': True, 'impresa': impresa.lower() == 'true'}).sort('pagadoEn', 1).limit(limit)
    return [vista(o) async for o in cur]

@app.get('/admin/dispatch-orders/{pedido_id}/print', response_class=HTMLResponse)
async def s19(pedido_id: str, ctx: Ctx = DES):
    db = S['db']
    o = await db.ordenes.find_one({'pedidoId': pedido_id, 'activa': True})
    if not o: raise AppError(404, 'NO_ENCONTRADO', 'La orden no existe en la cola de despacho.')
    await db.ordenes.update_one({'pedidoId': pedido_id}, {'$set': {'impresa': True}})       # repetir no cambia el resultado
    e = html.escape
    d = o['direccionEntrega']
    filas = ''.join(f'<tr><td>{e(i["nombre"])}</td><td>{i["cantidad"]}</td></tr>' for i in o['items'])
    cuerpo = (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Orden {e(o["numeroOrden"])}</title></head><body>'
              f'<h1>Orden {e(o["numeroOrden"])}</h1><p>Pedido {e(o["pedidoId"])} - pagado {e(str(o["pagadoEn"]))}</p>'
              f'<p>Cliente: {e(o["clienteNombre"])} - Tel. {e(str(o["telefono"]))}</p>'
              f'<p>Entrega: {e(d.get("calle", ""))}, {e(d.get("comuna", ""))} {e(d.get("referencia") or "")}</p>'
              f'<table border="1"><tr><th>Producto</th><th>Cantidad</th></tr>{filas}</table></body></html>')
    return HTMLResponse(cuerpo)

if __name__ == '__main__':
    run(app)
