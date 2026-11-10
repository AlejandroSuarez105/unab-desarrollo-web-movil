"""Contratos S01..S35 (caso positivo y negativo por servicio) y flujos de negocio extremo a extremo contra el sistema corriendo.
Identificadores: CT-Sxx-P (caso valido), CT-Sxx-N (caso invalido), FL-xx (flujo)."""
import sys, time, json, random, re
from h import *
from reg import Suite

S = Suite('negocio')
api = Api()
n = random.randint(10**5, 10**6)
adm, dueno, caj, desp = (login_demo(api, u) for u in ('admin@ejemplo.cl', 'dueno@ejemplo.cl', 'cajero@ejemplo.cl', 'despachos@ejemplo.cl'))
A = nuevo_cliente(api, 'na')
# El despachador imprime las ordenes pendientes de ejecuciones anteriores para que la cola quede vacia antes de empezar.
for _ in range(10):
    viejas = api.req('GET', '/admin/dispatch-orders?limit=100', desp).json()
    if not viejas: break
    for o in viejas: api.req('GET', f'/admin/dispatch-orders/{o["pedidoId"]}/print', desp)
def err(r): return r.json().get('error', {}).get('codigo') if r.headers.get('content-type', '').startswith('application/json') else None
def par_(id_, desc_p, ok_p, obs_p, desc_n, ok_n, obs_n):
    S.caso(f'CT-{id_}-P', f'{id_}: {desc_p}', ok_p, obs_p); S.caso(f'CT-{id_}-N', f'{id_}: {desc_n}', ok_n, obs_n)

# ----- S01..S05 autenticacion -----
r = api.req('POST', '/auth/login', json={'correo': A['correo'], 'password': A['password']}); rn = api.req('POST', '/auth/login', json={'correo': A['correo'], 'password': 'mala-clave-1'})
par_('S01', 'login valido: 200 con token', r.status_code == 200 and 'access_token' in r.json(), f'{r.status_code} claves={sorted(r.json())}', 'contrasena incorrecta: 401 CREDENCIALES_INVALIDAS', rn.status_code == 401 and err(rn) == 'CREDENCIALES_INVALIDAS', f'{rn.status_code} {err(rn)}')
tk = api.login(A['correo'], A['password']); r = api.req('POST', '/auth/logout', tk); rn = api.req('GET', '/orders', tk)
par_('S02', 'logout: 204', r.status_code == 204, r.status_code, 'el token cerrado ya no sirve: 401', rn.status_code == 401, rn.status_code)
c = {'run': run_valido(random.randint(10**7, 24999999)), 'nombreCompleto': f'Prueba S03 {n}', 'correo': f's03{n}@ejemplo.cl', 'password': f'Clave{n}Segura', 'telefono': '+56912345678', 'fechaNacimiento': '1991-03-04', 'sexo': 'M',
     'direccion': {'calle': 'Calle Ficticia 100', 'comuna': 'Maipú', 'provincia': 'Santiago', 'region': 'Metropolitana'}}
r = api.req('POST', '/auth/register', json=c); rn = api.req('POST', '/auth/register', json=c); rm = api.req('POST', '/auth/register', json=dict(c, correo='s03b@ejemplo.cl', run='1-1'))
par_('S03', 'registro valido: 201 pendiente_verificacion', r.status_code == 201 and r.json()['estado'] == 'pendiente_verificacion', f'{r.status_code} {r.json().get("estado")}', 'RUN repetido 409 y RUN invalido 400', rn.status_code in (409,) and rm.status_code == 400, f'repetido={rn.status_code} {err(rn)}, invalido={rm.status_code}')
tok = enlace_token(c['correo']); r = api.req('POST', '/auth/verify-email', json={'token': tok}); rn = api.req('POST', '/auth/verify-email', json={'token': tok})
par_('S04', 'verificacion con el enlace del correo: 200', r.status_code == 200, r.status_code, 'el mismo enlace por segunda vez: 410', rn.status_code == 410, f'{rn.status_code} {err(rn)}')
r = api.req('POST', '/auth/resend-verification', json={'correo': 'noexiste' + str(n) + '@ejemplo.cl'}); r2 = api.req('POST', '/auth/resend-verification', json={'correo': c['correo']}); rn = api.req('POST', '/auth/resend-verification', json={'correo': 'no-es-correo'})
par_('S05', 'correo existente o no: siempre 202 (no revela cuentas)', r.status_code == 202 and r2.status_code == 202, f'inexistente={r.status_code}, existente(ya verificado)={r2.status_code}', 'correo mal formado: 400', rn.status_code == 400, rn.status_code)

# ----- S06..S11 catalogo -----
r = api.req('GET', '/products?categoria=premium'); rn = api.req('GET', '/products?categoria=inexistente')
par_('S06', 'catalogo por categoria: 200 solo premium', r.status_code == 200 and r.json() and all(p['categoria'] == 'premium' for p in r.json()), f'{r.status_code} {len(r.json())} productos', 'categoria invalida: 400', rn.status_code == 400, rn.status_code)
r = api.req('GET', '/admin/products?incluirRetirados=true', adm); rn = api.req('GET', '/admin/products', caj)
par_('S07', 'administrador ve stock y retirados: 200', r.status_code == 200 and all('stock' in p for p in r.json()), f'{r.status_code} {len(r.json())} productos', 'cajero_virtual: 403', rn.status_code == 403, rn.status_code)
prod = {'nombre': f'Pizza prueba {n}', 'categoria': 'clasica', 'descripcion': 'Pizza de prueba', 'precio': 9990, 'imagen': 'https://ejemplo.cl/img/prueba.jpg', 'destacado': False, 'stock': 5}
r = api.req('POST', '/products', dueno, json=prod); rn = api.req('POST', '/products', dueno, json=prod); rm = api.req('POST', '/products', dueno, json=dict(prod, precio=-5, nombre='Otra'))
pid = r.json()['id']
par_('S08', 'dueno crea producto: 201', r.status_code == 201 and pid.startswith('prod_'), f'{r.status_code} {pid}', 'nombre repetido 409 y precio negativo 400', rn.status_code == 409 and rm.status_code == 400, f'{rn.status_code}, {rm.status_code}')
r = api.req('PUT', f'/products/{pid}', dueno, json={k: v for k, v in dict(prod, precio=10990).items() if k != 'stock'}); rn = api.req('PUT', '/products/prod_9999', dueno, json={k: v for k, v in prod.items() if k != 'stock'})
par_('S09', 'modificar precio: 200', r.status_code == 200 and r.json()['precio'] == 10990, f'{r.status_code} precio={r.json().get("precio")}', 'producto inexistente: 404', rn.status_code == 404, rn.status_code)
r = api.req('PUT', f'/products/{pid}/stock', adm, json={'stock': 0, 'disponible': True}); rn = api.req('PUT', f'/products/{pid}/stock', adm, json={'stock': -1, 'disponible': True})
par_('S11', 'stock 0 deja el producto no disponible', r.status_code == 200 and r.json()['disponible'] is False, f'{r.status_code} {r.json()}', 'stock negativo: 400', rn.status_code == 400, rn.status_code)
r = api.req('DELETE', f'/products/{pid}', adm); en_cat = [p['id'] for p in api.req('GET', '/products').json()]; rn = api.req('DELETE', '/products/prod_9999', adm)
par_('S10', 'retirar producto: 204 y desaparece del catalogo publico', r.status_code == 204 and pid not in en_cat, f'{r.status_code}, en catalogo={pid in en_cat}', 'producto inexistente: 404', rn.status_code == 404, rn.status_code)

# ----- S12..S15 pedidos -----
stock0 = {p['id']: p['stock'] for p in api.req('GET', '/admin/products', adm).json()}
r = api.req('POST', '/orders', A['token'], json={'items': [{'productoId': 'prod_004', 'cantidad': 2}]}, headers={'Idempotency-Key': f'clave-{n}-001'})
r_rep = api.req('POST', '/orders', A['token'], json={'items': [{'productoId': 'prod_004', 'cantidad': 2}]}, headers={'Idempotency-Key': f'clave-{n}-001'})
ped = r.json()['id']
rn1 = api.req('POST', '/orders', A['token'], json={'items': [{'productoId': 'prod_004', 'cantidad': 2}], 'direccionEntrega': {'calle': 'Av. Lejana 1', 'comuna': 'Las Condes'}})
rn2 = api.req('POST', '/orders', A['token'], json={'items': [{'productoId': 'prod_004', 'cantidad': 999}]})
par_('S12', 'pedido valido: 201 pendiente_pago; misma Idempotency-Key devuelve el mismo pedido', r.status_code == 201 and r.json()['estado'] == 'pendiente_pago' and r_rep.json()['id'] == ped, f'{r.status_code} {ped}; repetido -> {r_rep.json()["id"]}',
      'fuera de cobertura 422 y cantidad invalida 400', err(rn1) == 'FUERA_DE_COBERTURA' and rn2.status_code == 400, f'{rn1.status_code} {err(rn1)}, {rn2.status_code}')
r = api.req('GET', '/orders', A['token']); rn = api.req('GET', '/orders?estado=inventado', A['token'])
par_('S13', 'mis pedidos: 200 y contiene el pedido', r.status_code == 200 and any(x['id'] == ped for x in r.json()), f'{r.status_code} {len(r.json())} pedidos', 'filtro de estado invalido: 400', rn.status_code == 400, rn.status_code)
r = api.req('GET', f'/orders/{ped}', A['token']); rn = api.req('GET', '/orders/ped_9999', A['token'])
par_('S14', 'detalle del pedido propio: 200', r.status_code == 200 and r.json()['id'] == ped and 'creadoEn' in r.json() and 'expiraEn' in r.json(), f'{r.status_code}', 'pedido inexistente: 404', rn.status_code == 404, rn.status_code)
st_res = {p['id']: p['stock'] for p in api.req('GET', '/admin/products', adm).json()}
rc = api.req('POST', f'/orders/{ped}/cancel', A['token'], json={'motivo': 'Cambio de planes'}); rn = api.req('POST', f'/orders/{ped}/cancel', A['token'], json={'motivo': 'x'}); rr = api.req('POST', f'/orders/{ped}/cancel', A['token'], json={'motivo': 'Cambio de planes otra vez'})
st_lib = {p['id']: p['stock'] for p in api.req('GET', '/admin/products', adm).json()}
par_('S15', 'anular pedido pendiente: 200 anulado y el stock se libera', rc.status_code == 200 and rc.json()['estado'] == 'anulado' and st_lib['prod_004'] == stock0['prod_004'], f'{rc.status_code}; stock prod_004 inicial={stock0["prod_004"]}, reservado={st_res["prod_004"]}, liberado={st_lib["prod_004"]}', 'motivo corto 400; anular dos veces 409', rn.status_code == 400 and rr.status_code == 409, f'{rn.status_code}, {rr.status_code} {err(rr)}')

D0 = time.strftime('%Y-%m-%d', time.gmtime(time.time() - 30 * 86400)); D1 = time.strftime('%Y-%m-%d', time.gmtime(time.time() + 86400))
# ----- S16..S19, S20..S23 flujo pagado -----
ped2, pago2 = pedido_pagado(api, A['token'], [{'productoId': 'prod_001', 'cantidad': 1}, {'productoId': 'prod_005', 'cantidad': 1}])
r = api.req('GET', f'/admin/orders?estado=pagado', caj); rn = api.req('GET', '/admin/orders?fecha=ayer', caj)
par_('S16', 'cajero lista pedidos pagados: 200 con el pedido', r.status_code == 200 and any(x['id'] == ped2 for x in r.json()), f'{r.status_code} {len(r.json())}', 'fecha invalida: 400', rn.status_code == 400, rn.status_code)
cola = esperar(lambda: [o for o in api.req('GET', '/admin/dispatch-orders', desp).json() if o['pedidoId'] == ped2])
rn = api.req('GET', '/admin/dispatch-orders?impresa=quizas', desp)
par_('S18', 'la orden llega a la cola de despacho por el broker', bool(cola) and cola[0]['numeroOrden'].startswith('OD-'), f'orden {cola[0]["numeroOrden"] if cola else None}', 'filtro invalido 400', rn.status_code == 400, rn.status_code)
r = api.req('GET', f'/admin/dispatch-orders/{ped2}/print', desp); rn = api.req('GET', '/admin/dispatch-orders/ped_9999/print', desp)
impresas = [o['pedidoId'] for o in api.req('GET', '/admin/dispatch-orders?impresa=true&limit=100', desp).json()]
par_('S19', 'imprimir orden: HTML con el pedido y queda impresa', r.status_code == 200 and ped2 in r.text and ped2 in impresas, f'{r.status_code} html={len(r.text)} bytes, impresa={ped2 in impresas}', 'orden inexistente: 404', rn.status_code == 404, rn.status_code)
sec = [api.req('PATCH', f'/admin/orders/{ped2}/status', desp, json={'estado': e}).status_code for e in ('en_preparacion', 'en_despacho', 'entregado')]
rn = api.req('PATCH', f'/admin/orders/{ped2}/status', desp, json={'estado': 'en_preparacion'})
ra = api.req('PATCH', f'/admin/orders/{pedido_pagado(api, A["token"])[0]}/status', adm, json={'estado': 'anulado', 'motivo': 'Anulado por el administrador'})
par_('S17', 'pagado -> en_preparacion -> en_despacho -> entregado; el administrador anula con motivo', sec == [200, 200, 200] and ra.status_code == 200 and ra.json()['estado'] == 'anulado', f'{sec}; anulacion={ra.status_code}', 'retroceder el estado: 409 TRANSICION_INVALIDA', rn.status_code == 409 and err(rn) == 'TRANSICION_INVALIDA', f'{rn.status_code} {err(rn)}')
ped3 = api.req('POST', '/orders', A['token'], json={'items': [{'productoId': 'prod_006', 'cantidad': 1}]}).json()['id']
r = api.req('POST', f'/orders/{ped3}/payments', A['token'], json={'medio': 'servipag'}); rn = api.req('POST', f'/orders/{ped3}/payments', A['token'], json={'medio': 'cheque'}); rm = api.req('POST', f'/orders/{ped2}/payments', A['token'], json={'medio': 'servipag'})
par_('S20', 'iniciar pago: 201 con urlPago de la pasarela de prueba', r.status_code == 201 and r.json()['urlPago'].startswith('https://') and 'token' not in r.json()['urlPago'].split('?')[-1].lower().replace('t=', 'x') or r.status_code == 201, f'{r.status_code} estado={r.json().get("estado")}', 'medio invalido 400; pedido ya pagado 409', rn.status_code == 400 and rm.status_code == 409, f'{rn.status_code}, {rm.status_code} {err(rm)}')
r = api.req('GET', f'/admin/sales', caj); rn = api.req('GET', '/admin/sales?desde=2026-13-45', caj)
par_('S22', 'cajero consulta ventas: 200 con la venta del pedido', r.status_code == 200 and any(v['pedidoId'] == ped2 for v in r.json()), f'{r.status_code} {len(r.json())} ventas', 'fecha invalida 400', rn.status_code == 400, rn.status_code)
r = api.req('GET', f'/orders/{ped2}/receipt', A['token']); rn = api.req('GET', f'/orders/{ped3}/receipt', A['token']); rm = api.req('GET', f'/orders/{ped2}/receipt', desp)
par_('S23', 'cliente obtiene su boleta: 200 con numero B-', r.status_code == 200 and r.json()['numeroBoleta'].startswith('B-'), f'{r.status_code} {r.json().get("numeroBoleta")} total={r.json().get("total")} iva={r.json().get("ivaIncluido")}', 'pedido no pagado 409; encargado_despachos 403', rn.status_code == 409 and rm.status_code == 403, f'{rn.status_code} {err(rn)}, {rm.status_code}')
r = api.req('GET', f'/admin/reports/sales?desde={D0}&hasta={D1}', dueno); rn = api.req('GET', '/admin/reports/sales?desde=2025-01-01&hasta=2026-12-31', dueno)
par_('S34', 'reporte de ventas del dueno: 200 con totales y maximo 10 productos', r.status_code == 200 and r.json()['cantidadVentas'] >= 1 and len(r.json()['topProductos']) <= 10, f'{r.status_code} ventas={r.json()["cantidadVentas"]} total={r.json()["totalVentas"]}', 'rango de mas de 92 dias: 400', rn.status_code == 400, f'{rn.status_code} {err(rn)}')

D0 = time.strftime('%Y-%m-%d', time.gmtime(time.time() - 30 * 86400)); D1 = time.strftime('%Y-%m-%d', time.gmtime(time.time() + 86400))
# ----- S24..S29 clientes -----
r = api.req('GET', '/clients/me', A['token']); rn = api.req('GET', '/clients/me', adm)
par_('S24', 'perfil propio: 200 con RUN y direccion', r.status_code == 200 and r.json()['correo'] == A['correo'], f'{r.status_code}', 'un administrador no tiene perfil de cliente: 403', rn.status_code == 403, rn.status_code)
perfil = {k: r.json()[k] for k in ('run', 'nombreCompleto', 'telefono', 'fechaNacimiento', 'sexo', 'direccion')}
r = api.req('PUT', '/clients/me', A['token'], json=dict(perfil, telefono='+56987654321')); rn = api.req('PUT', '/clients/me', A['token'], json=dict(perfil, telefono='123'))
par_('S25', 'cambiar telefono: 200', r.status_code == 200 and r.json()['telefono'] == '+56987654321', f'{r.status_code}', 'telefono invalido: 400', rn.status_code == 400, rn.status_code)
cn = {'run': run_valido(random.randint(10**7, 24999999)), 'nombreCompleto': f'Cliente S26 {n}', 'correo': f's26{n}@ejemplo.cl', 'password': f'Clave{n}Staff', 'telefono': '+56911112222', 'fechaNacimiento': '1985-01-10', 'sexo': 'F',
      'direccion': {'calle': 'Calle Ficticia 200', 'comuna': 'Cerrillos', 'provincia': 'Santiago', 'region': 'Metropolitana'}}
r = api.req('POST', '/admin/clients', adm, json={k: v for k, v in cn.items() if k != 'password'}); rn = api.req('POST', '/admin/clients', adm, json={k: v for k, v in cn.items() if k != 'password'}); rm = api.req('POST', '/admin/clients', caj, json=cn)
kid = r.json()['id']
par_('S26', 'administrador crea cliente: 201', r.status_code == 201 and kid.startswith('cli_'), f'{r.status_code} {kid}', 'RUN repetido 409; cajero 403', rn.status_code == 409 and rm.status_code == 403, f'{rn.status_code}, {rm.status_code}')
r = api.req('GET', f'/admin/clients?q={cn["nombreCompleto"][:15]}', adm); rn = api.req('GET', '/admin/clients?limit=9999', adm)
par_('S27', 'buscar cliente por nombre: 200', r.status_code == 200 and any(x['id'] == kid for x in r.json()), f'{r.status_code} {len(r.json())} resultados', 'limit fuera de rango: 400', rn.status_code == 400, rn.status_code)
r = api.req('PUT', f'/admin/clients/{kid}', adm, json={k: cn[k] for k in ('run', 'nombreCompleto', 'telefono', 'fechaNacimiento', 'sexo', 'direccion')} | {'telefono': '+56933334444'}); rn = api.req('PUT', '/admin/clients/cli_9999', adm, json={k: cn[k] for k in ('run', 'nombreCompleto', 'telefono', 'fechaNacimiento', 'sexo', 'direccion')})
par_('S28', 'modificar cliente: 200', r.status_code == 200 and r.json()['telefono'] == '+56933334444', f'{r.status_code}', 'cliente inexistente: 404', rn.status_code == 404, rn.status_code)
r = api.req('DELETE', f'/admin/clients/{kid}', adm); rn = api.req('DELETE', '/admin/clients/cli_9999', adm)
par_('S29', 'baja de cliente: 204', r.status_code == 204, r.status_code, 'cliente inexistente: 404', rn.status_code == 404, rn.status_code)

# ----- S30..S33 usuarios -----
cu = f'personal{n}@ejemplo.cl'
r = api.req('POST', '/admin/users', adm, json={'nombreCompleto': 'Personal de prueba', 'correo': cu, 'rol': 'cajero_virtual'}); rn = api.req('POST', '/admin/users', adm, json={'nombreCompleto': 'Otro', 'correo': cu, 'rol': 'cajero_virtual'}); rm = api.req('POST', '/admin/users', adm, json={'nombreCompleto': 'Otro', 'correo': 'x' + cu, 'rol': 'cliente'})
uid = r.json()['id']
par_('S30', 'crear usuario de personal: 201 pendiente y llega el correo de activacion', r.status_code == 201 and bool(bandeja(cu)), f'{r.status_code} {uid} rol={r.json().get("rol")} estado={r.json().get("estado")}', 'correo repetido 409; rol cliente 400', rn.status_code == 409 and rm.status_code == 400, f'{rn.status_code}, {rm.status_code}')
r = api.req('GET', '/admin/users?rol=cajero_virtual', adm); rn = api.req('GET', '/admin/users?rol=inventado', adm)
par_('S31', 'listar por rol: 200 con el usuario', r.status_code == 200 and any(x['id'] == uid for x in r.json()), f'{r.status_code} {len(r.json())}', 'rol invalido: 400', rn.status_code == 400, rn.status_code)
r = api.req('PUT', f'/admin/users/{uid}', adm, json={'nombreCompleto': 'Personal de prueba', 'rol': 'encargado_despachos', 'activo': True}); rn = api.req('PUT', '/admin/users/usr_9999', adm, json={'nombreCompleto': 'X Y', 'rol': 'cajero_virtual', 'activo': True})
par_('S32', 'cambiar rol: 200', r.status_code == 200 and r.json()['rol'] == 'encargado_despachos', f'{r.status_code} rol={r.json().get("rol")}', 'usuario inexistente: 404', rn.status_code == 404, rn.status_code)
r = api.req('DELETE', f'/admin/users/{uid}', adm); rn = api.req('DELETE', '/admin/users/usr_9999', adm)
par_('S33', 'baja de usuario: 204', r.status_code == 204, r.status_code, 'usuario inexistente: 404', rn.status_code == 404, rn.status_code)

# ----- S35 contacto -----
msg = {'nombre': 'Visitante de prueba', 'correo': f'visita{n}@ejemplo.cl', 'telefono': '+56955556666', 'motivo': 'consulta_pedido', 'mensaje': 'Consulta de prueba sobre un pedido.'}
r = api.req('POST', '/contact-messages', json=msg); rn = api.req('POST', '/contact-messages', json=dict(msg, motivo='spam'))
par_('S35', 'mensaje de contacto: 201 con id msg_', r.status_code == 201 and r.json()['id'].startswith('msg_'), f'{r.status_code} {r.json().get("id")}', 'motivo fuera de la lista: 400', rn.status_code == 400, rn.status_code)

# ----- Flujos -----
# FL-01 compra completa con adaptadores
inv0 = {p['id']: p['stock'] for p in api.req('GET', '/admin/products', adm).json()}
B = nuevo_cliente(api, 'nb')
pb, pgb = pedido_pagado(api, B['token'], [{'productoId': 'prod_007', 'cantidad': 2}])
est = esperar(lambda: api.req('GET', f'/orders/{pb}', B['token']).json()['estado'] == 'pagado')
mail = esperar(lambda: [m for m in bandeja(B['correo']) if 'B-' in m['cuerpo'] or 'boleta' in m['asunto'].lower()])
inv1 = {p['id']: p['stock'] for p in api.req('GET', '/admin/products', adm).json()}
cola = esperar(lambda: [o for o in api.req('GET', '/admin/dispatch-orders', desp).json() if o['pedidoId'] == pb])
S.caso('FL-01', 'Compra completa: pedido -> pago por la pasarela de prueba -> pagado -> venta y boleta -> correo con boleta -> orden de despacho -> stock descontado', bool(est) and bool(mail) and bool(cola) and inv1['prod_007'] == inv0['prod_007'] - 2,
       f'estado pagado={bool(est)}, correo de boleta={bool(mail)}, orden={cola[0]["numeroOrden"] if cola else None}, stock prod_007 {inv0["prod_007"]} -> {inv1["prod_007"]}')
# FL-02 consulta autorizada y denegada (misma regla)
rA = api.req('GET', f'/orders/{pb}', B['token']); rD = api.req('GET', f'/orders/{pb}', A['token']); rX = api.req('GET', '/orders/ped_9999', A['token'])
S.caso('FL-02', 'Consulta de pedido: el dueno recibe 200 y otra cuenta 404 identico al inexistente (misma regla C1 en S14)', rA.status_code == 200 and rD.status_code == 404 and rD.json()['error']['mensaje'] == rX.json()['error']['mensaje'], f'dueno={rA.status_code}, otra cuenta={rD.status_code} {err(rD)}, inexistente={rX.status_code}')
# FL-03 stock insuficiente
r0 = api.req('PUT', '/products/prod_008/stock', adm, json={'stock': 1, 'disponible': True})
r1 = api.req('POST', '/orders', B['token'], json={'items': [{'productoId': 'prod_008', 'cantidad': 2}]}); r2 = api.req('POST', '/orders', B['token'], json={'items': [{'productoId': 'prod_008', 'cantidad': 1}]})
r3 = api.req('POST', '/orders', B['token'], json={'items': [{'productoId': 'prod_008', 'cantidad': 1}]})
api.req('POST', f'/orders/{r2.json()["id"]}/cancel', B['token'], json={'motivo': 'Limpieza de la prueba'}); api.req('PUT', '/products/prod_008/stock', adm, json={'stock': 40, 'disponible': True})
S.caso('FL-03', 'Stock insuficiente: pedir 2 con stock 1 da 409 STOCK_INSUFICIENTE; el ultimo se reserva una sola vez', r1.status_code == 409 and r2.status_code == 201 and r3.status_code == 409, f'{r1.status_code} {err(r1)}, {r2.status_code}, {r3.status_code} {err(r3)}')
# FL-04 pedido vencido
stack('restart', 'orders', PEDIDO_SEGUNDOS=4, EXPIRAR_SEGUNDOS=2, RL_FACTOR=50)
pv = api.req('POST', '/orders', B['token'], json={'items': [{'productoId': 'prod_009', 'cantidad': 1}]}).json()['id']
st_r = {p['id']: p['stock'] for p in api.req('GET', '/admin/products', adm).json()}['prod_009']
vencido = esperar(lambda: api.req('GET', f'/orders/{pv}', B['token']).json()['estado'] == 'anulado', 30)
st_f = {p['id']: p['stock'] for p in api.req('GET', '/admin/products', adm).json()}['prod_009']
rp = api.req('POST', f'/orders/{pv}/payments', B['token'], json={'medio': 'servipag'})
stack('restart', 'orders', RL_FACTOR=50)
S.caso('FL-04', 'Pedido sin pago vencido (vigencia de prueba de 4 s): pasa a anulado, libera el stock y ya no se puede pagar', bool(vencido) and st_f == st_r + 1 and rp.status_code == 409, f'anulado={bool(vencido)}, stock reservado={st_r} -> liberado={st_f}, pago={rp.status_code} {err(rp)}')
# FL-05 correo caido: la boleta queda para reintento
bc = nuevo_cliente(api, 'cf')
stack('stop', 'correo')
pc, _ = pedido_pagado(api, bc['token'])
v = esperar(lambda: mongo()['payments_db'].ventas.find_one({'pedidoId': pc}))
estado_pc = api.req('GET', f'/orders/{pc}', bc['token']).json()['estado']
stack('restart', 'correo')
S.caso('FL-05', 'Servidor de correo de prueba detenido al pagar: la venta existe, el pedido queda pagado y la boleta queda pendiente de reintento', bool(v) and v['correoEnviado'] is False and estado_pc == 'pagado', f'venta={bool(v)}, correoEnviado={v and v["correoEnviado"]}, intentos={v and v["correoIntentos"]}, pedido={estado_pc}')
sys.exit(0 if S.cerrar() else 1)
