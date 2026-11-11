"""Retencion y eliminacion (Modulo 7, 7.9). Se crean los datos con el sistema corriendo (compra, pago, entrega, baja), se les
retrocede la fecha en la base para simular el paso del tiempo y se comprueba que cada sistema elimina o anonimiza lo que
corresponde, conserva lo que debe conservar y no toca los datos recientes. Identificadores: RET-01 a RET-12."""
import sys, time, random, glob, os
from h import *
from reg import Suite
from fornace.util import run_normal

S = Suite('retencion')
api = Api()
adm, desp = login_demo(api, 'admin@ejemplo.cl'), login_demo(api, 'despachos@ejemplo.cl')
db = mongo()
n = random.randint(10**5, 10**6)

def hace(dias):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - dias * 86400))
def estado(ped): return api.req('GET', f'/orders/{ped}', C['token']).json().get('estado')

C = nuevo_cliente(api, 'ret')

# ---------- datos reales creados por el sistema ----------
# A: pedido pagado (con venta, pago, aviso de pago, movimiento de stock y orden de despacho) que se envejece 13 meses.
ped_a, pago_a = pedido_pagado(api, C['token'])
esperar(lambda: db['payments_db'].ventas.find_one({'pedidoId': ped_a}))
esperar(lambda: db['dispatch_db'].ordenes.find_one({'pedidoId': ped_a}))
# B: pedido que se anula sin haber sido pagado (con un pago iniciado que nunca se aprobo).
r = api.req('POST', '/orders', C['token'], json={'items': [{'productoId': 'prod_002', 'cantidad': 1}]}); ped_b = r.json()['id']
pago_b = api.req('POST', f'/orders/{ped_b}/payments', C['token'], json={'medio': 'servipag'}).json()['pagoId']
rb = api.req('PATCH', f'/admin/orders/{ped_b}/status', adm, json={'estado': 'anulado', 'motivo': 'Anulado para la prueba de retencion'})
# C: pedido pagado y entregado, que se envejece 13 meses desde la entrega.
ped_c, pago_c = pedido_pagado(api, C['token'])
sec = [api.req('PATCH', f'/admin/orders/{ped_c}/status', desp, json={'estado': e}).status_code for e in ('en_preparacion', 'en_despacho', 'entregado')]
esperar(lambda: db['dispatch_db'].ordenes.find_one({'pedidoId': ped_c}))
# D: pedido pagado y despues anulado (devolucion): tiene venta, se conserva aunque sea antiguo.
ped_d, pago_d = pedido_pagado(api, C['token'])
rd = api.req('PATCH', f'/admin/orders/{ped_d}/status', adm, json={'estado': 'anulado', 'motivo': 'Anulado para la prueba de retencion'})
# E: pedido pagado y entregado hace poco: conserva su direccion.
ped_e, pago_e = pedido_pagado(api, C['token'])
[api.req('PATCH', f'/admin/orders/{ped_e}/status', desp, json={'estado': e}) for e in ('en_preparacion', 'en_despacho', 'entregado')]
# F: orden de despacho reciente (llegada hace 10 dias).
dd = db['dispatch_db']
esperar(lambda: dd.ordenes.find_one({'pedidoId': ped_e}))

ok_previo = (rb.status_code == 200 and sec == [200, 200, 200] and rd.status_code == 200
             and db['payments_db'].ventas.find_one({'pedidoId': ped_a}) is not None and db['payments_db'].pagos.find_one({'id': pago_b}) is not None
             and db['payments_db'].eventos.count_documents({'pagoId': pago_a}) > 0)
S.caso('RET-00', 'Datos de partida creados por el sistema: pedido pagado con venta y orden de despacho, pedido anulado sin pago con un pago pendiente, pedido entregado y pedido pagado y anulado',
       ok_previo, f'anular={rb.status_code} entrega={sec} anular_pagado={rd.status_code}')

# ---------- envejecer los datos (simula el paso del tiempo) ----------
viejo13, viejo4m, viejo100d, viejo25m = hace(400), hace(120), hace(100), hace(800)
reciente = hace(10)
dd.ordenes.update_one({'pedidoId': ped_a}, {'$set': {'recibidaEn': viejo100d}}); dd.mensajes.update_many({'pedidoId': ped_a}, {'$set': {'recibidoEn': viejo100d}})
dd.ordenes.update_one({'pedidoId': ped_e}, {'$set': {'recibidaEn': reciente}}); dd.mensajes.update_many({'pedidoId': ped_e}, {'$set': {'recibidoEn': reciente}})
dd.ordenes.update_one({'pedidoId': ped_c}, {'$set': {'recibidaEn': viejo4m}}); dd.mensajes.update_many({'pedidoId': ped_c}, {'$set': {'recibidoEn': viejo4m}})  # 120 dias: tambien vencida
pay = db['payments_db']
pay.eventos.update_many({'pagoId': pago_a}, {'$set': {'recibidoEn': viejo13}}); pay.pagos.update_one({'id': pago_a}, {'$set': {'creadoEn': viejo13}})
pay.pagos.update_one({'id': pago_b}, {'$set': {'creadoEn': viejo13}})
pay.eventos.update_many({'pagoId': pago_e}, {'$set': {'recibidoEn': reciente}})
inv = db['inventory_db']
inv.movimientos.update_many({'pedidoId': ped_a}, {'$set': {'fecha': viejo13}}); inv.movimientos.update_many({'pedidoId': ped_e}, {'$set': {'fecha': reciente}})
od = db['orders_db']
od.pedidos.update_one({'id': ped_b}, {'$set': {'historial.$[].fecha': viejo13}})      # anulado sin pago, hace 13 meses
od.pedidos.update_one({'id': ped_d}, {'$set': {'historial.$[].fecha': viejo13}})      # pagado y anulado, hace 13 meses
od.pedidos.update_one({'id': ped_c}, {'$set': {'historial.$[].fecha': viejo13}})      # entregado hace 13 meses
od.pedidos.update_one({'id': ped_e}, {'$set': {'historial.$[].fecha': reciente}})
nt = db['notifications_db'].mensajes
nt.insert_one({'id': f'msg_ret_viejo_{n}', 'nombre': 'Contacto antiguo', 'correo': f'viejo{n}@ejemplo.cl', 'telefono': '+56911112222', 'motivo': 'consulta', 'mensaje': 'Mensaje de prueba', 'creadoEn': viejo13})
nt.insert_one({'id': f'msg_ret_nuevo_{n}', 'nombre': 'Contacto reciente', 'correo': f'nuevo{n}@ejemplo.cl', 'telefono': '+56911112222', 'motivo': 'consulta', 'mensaje': 'Mensaje de prueba', 'creadoEn': reciente})
# clientes dados de baja: uno hace 25 meses, otro hace 100 dias y otro activo
cc = db['clients_db'].clientes; ca = db['auth_db'].cuentas
V, R_, A_ = nuevo_cliente(api, 'retv'), nuevo_cliente(api, 'retr'), nuevo_cliente(api, 'reta')
bajas = [api.req('DELETE', f'/admin/clients/{x["clienteId"]}', adm).status_code for x in (V, R_)]
for x, f in ((V, viejo25m), (R_, viejo100d)):
    cc.update_one({'id': x['clienteId']}, {'$set': {'bajaEn': f}}); ca.update_one({'correo': x['correo']}, {'$set': {'bajaEn': f}})
S.caso('RET-00b', 'Dos clientes dados de baja (S29) guardan la fecha de baja en clients y en auth', bajas == [204, 204] and cc.find_one({'id': V['clienteId']}).get('baja') is True
       and ca.find_one({'correo': V['correo']}).get('estado') == 'inactivo', f'bajas={bajas}')

# ---------- ejecutar la retencion: cada sistema corre su tarea cada 2 segundos ----------
for s in ('dispatch', 'notifications', 'inventory', 'payments', 'orders', 'clients', 'auth'):
    stack('restart', s, RETENCION_SEGUNDOS=2)
time.sleep(8)

# ---------- verificaciones ----------
# RET-01 despacho: 90 dias desde la llegada
o_a, o_e, o_c = dd.ordenes.count_documents({'pedidoId': ped_a}), dd.ordenes.count_documents({'pedidoId': ped_e}), dd.ordenes.count_documents({'pedidoId': ped_c})
m_a, m_e = dd.mensajes.count_documents({'pedidoId': ped_a}), dd.mensajes.count_documents({'pedidoId': ped_e})
S.caso('RET-01', 'dispatch-service: la orden y el mensaje con mas de 90 dias se eliminan; los de menos de 90 dias se conservan', o_a == 0 and m_a == 0 and o_c == 0 and o_e == 1 and m_e >= 1,
       f'a(100 d): orden={o_a} mensajes={m_a}; c(120 d): orden={o_c}; e(10 d): orden={o_e} mensajes={m_e}')
# RET-02 contacto: 12 meses
v, nv = nt.count_documents({'id': f'msg_ret_viejo_{n}'}), nt.count_documents({'id': f'msg_ret_nuevo_{n}'})
S.caso('RET-02', 'notifications-service: el mensaje de contacto de hace 13 meses se elimina y el reciente se conserva', v == 0 and nv == 1, f'viejo={v} reciente={nv}')
# RET-03 avisos de pago y pagos sin venta
ev_a, ev_e = pay.eventos.count_documents({'pagoId': pago_a}), pay.eventos.count_documents({'pagoId': pago_e})
pg_a, pg_b, pg_e = pay.pagos.count_documents({'id': pago_a}), pay.pagos.count_documents({'id': pago_b}), pay.pagos.count_documents({'id': pago_e})
S.caso('RET-03', 'payments-service: los avisos de pago de hace 13 meses y el pago antiguo sin venta se eliminan; el reciente se conserva', ev_a == 0 and pg_b == 0 and ev_e >= 1 and pg_e == 1,
       f'avisos antiguos={ev_a}, pago antiguo sin venta={pg_b}, avisos recientes={ev_e}, pago reciente={pg_e}')
S.caso('RET-04', 'payments-service: el pago antiguo con venta y la venta con su boleta se conservan (6 anios)', pg_a == 1 and pay.ventas.count_documents({'pedidoId': ped_a}) == 1,
       f'pago con venta={pg_a} venta={pay.ventas.count_documents({"pedidoId": ped_a})}')
# RET-05 stock
mv_a, mv_e = inv.movimientos.count_documents({'pedidoId': ped_a}), inv.movimientos.count_documents({'pedidoId': ped_e})
S.caso('RET-05', 'inventory-service: los movimientos de stock de hace 13 meses se eliminan y los recientes se conservan', mv_a == 0 and mv_e >= 1, f'antiguos={mv_a} recientes={mv_e}')
# RET-06 pedido anulado sin pago
b, d = od.pedidos.count_documents({'id': ped_b}), od.pedidos.find_one({'id': ped_d})
S.caso('RET-06', 'orders-service: el pedido anulado sin pago de hace 13 meses se elimina', b == 0, f'pedido anulado sin pago: {b} documento(s)')
S.caso('RET-07', 'orders-service: el pedido que fue pagado y despues anulado se conserva aunque sea antiguo', d is not None and d['estado'] == 'anulado', f'{d and d["estado"]}')
# RET-08 direccion y telefono del pedido entregado
c_, e_ = od.pedidos.find_one({'id': ped_c}), od.pedidos.find_one({'id': ped_e})
S.caso('RET-08', 'orders-service: a los 12 meses de la entrega se borran calle, referencia y telefono, y se conservan comuna, lineas y total',
       c_ is not None and c_['direccionEntrega']['calle'] == '' and c_['direccionEntrega']['referencia'] == '' and c_['clienteTelefono'] is None
       and c_['direccionEntrega']['comuna'] and c_['total'] > 0 and len(c_['items']) >= 1,
       f'calle={c_ and c_["direccionEntrega"]["calle"]!r} telefono={c_ and c_["clienteTelefono"]!r} comuna={c_ and c_["direccionEntrega"]["comuna"]!r} total={c_ and c_["total"]}')
S.caso('RET-09', 'orders-service: el pedido entregado hace pocos dias conserva calle y telefono', e_ is not None and e_['direccionEntrega']['calle'] != '' and e_['clienteTelefono'],
       f'calle={e_ and e_["direccionEntrega"]["calle"]!r}')
# RET-10 clientes dados de baja
v_c, r_c, a_c = cc.find_one({'id': V['clienteId']}), cc.find_one({'id': R_['clienteId']}), cc.find_one({'id': A_['clienteId']})
S.caso('RET-10', 'clients-service: el cliente dado de baja hace 25 meses queda anonimizado; el de hace 100 dias y el activo conservan sus datos',
       v_c['anonimizado'] is True and v_c['nombreCompleto'] == '[eliminado]' and v_c['run'] == 'ANON-' + V['clienteId'] and v_c['telefono'] is None and v_c['fechaNacimiento'] is None
       and v_c['sexo'] is None and v_c['direccion'] is None and r_c['nombreCompleto'] == R_['nombre'] and r_c['run'] == run_normal(R_['run']) and a_c['nombreCompleto'] == A_['nombre'],
       f'baja 25 m: nombre={v_c["nombreCompleto"]!r} run={v_c["run"]!r}; baja 100 d: nombre={r_c["nombreCompleto"]!r}; activo: nombre={a_c["nombreCompleto"]!r}')
# RET-11 cuentas de auth
cv, cr = ca.find_one({'id': v_c['cuentaId']}), ca.find_one({'id': r_c['cuentaId']})
login_viejo = api.req('POST', '/auth/login', json={'correo': V['correo'], 'password': V['password']}).status_code
S.caso('RET-11', 'auth-service: la cuenta del cliente dado de baja hace 25 meses se anonimiza (correo, nombre y hash) y ya no permite iniciar sesion; la de hace 100 dias no cambia',
       cv['anonimizada'] is True and cv['correo'].endswith('@anonimo.invalid') and V['correo'] not in cv['correo'] and cv['nombre'] == '[eliminado]' and cv['hash'] is None
       and login_viejo == 401 and cr['correo'] == R_['correo'] and cr.get('anonimizada') is not True,
       f'correo={cv["correo"]} hash={cv["hash"]} login con el correo anterior={login_viejo}')
# RET-12 el sistema sigue respondiendo y los registros no tienen datos personales
lista = api.req('GET', '/admin/clients?limit=100', adm)
lineas = []
for f in glob.glob(str(LOGS / '*.log')):
    lineas += [l for l in open(f, errors='ignore') if '"evento": "retencion"' in l]
personales = [x for x in (V['correo'], V['nombre'], V['run'], R_['correo'], C['correo'], C['calle'], C['telefono']) if any(x in l for l in lineas)]
S.caso('RET-12', 'El listado de clientes responde con clientes anonimizados y los eventos de retencion del registro no contienen datos personales', lista.status_code == 200 and len(lineas) >= 6 and not personales,
       f'listado={lista.status_code} eventos de retencion={len(lineas)} datos personales en ellos={personales}')

# ---------- dejar el sistema como estaba ----------
for _ in range(10):      # el despachador imprime las ordenes que quedaron en la cola para no afectar a las pruebas siguientes
    pend = api.req('GET', '/admin/dispatch-orders?limit=100', desp).json()
    if not pend: break
    for o in pend: api.req('GET', f'/admin/dispatch-orders/{o["pedidoId"]}/print', desp)
for s in ('dispatch', 'notifications', 'inventory', 'payments', 'orders', 'clients', 'auth'):
    stack('restart', s)
time.sleep(2)
sys.exit(0 if S.cerrar() else 1)
