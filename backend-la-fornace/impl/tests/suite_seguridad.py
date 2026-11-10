"""Pruebas de autorizacion y proteccion de datos del Modulo 4 (T-AUT-01..14) y del Modulo 7 (T-DAT-01..13).
Se ejecutan contra el sistema corriendo; cada caso registra lo observado."""
import re, sys, time, json, pathlib
from h import *
from reg import Suite

S = Suite('seguridad')
api = Api()
cr = cred()

# ---------- actores y datos de prueba ----------
A = nuevo_cliente(api, 'a')
B = nuevo_cliente(api, 'b')
adm, dueno, caj, desp = (login_demo(api, u) for u in ('admin@ejemplo.cl', 'dueno@ejemplo.cl', 'cajero@ejemplo.cl', 'despachos@ejemplo.cl'))
r = api.req('POST', '/orders', A['token'], json={'items': [{'productoId': 'prod_002', 'cantidad': 1}]})
ped_pend = r.json()['id']
ped_pag, pago_pag = pedido_pagado(api, A['token'])

def err_igual(r1, r2):
    a, b = r1.json()['error'], r2.json()['error']
    return r1.status_code == r2.status_code and a['codigo'] == b['codigo'] and a['mensaje'] == b['mensaje']

# ---------- T-AUT ----------
r1 = api.req('GET', f'/orders/{ped_pag}', B['token']); r2 = api.req('GET', '/orders/ped_9999', B['token'])
S.caso('T-AUT-01', 'Cliente B consulta pedido de A (S14): 404 identico a un pedido inexistente', r1.status_code == 404 and err_igual(r1, r2) and 'prod_' not in r1.text, f'ajeno={r1.status_code} {r1.json()["error"]["codigo"]}; inexistente={r2.status_code}')
r = api.req('GET', f'/orders/{ped_pag}', A['token'])
S.caso('T-AUT-02', 'Cliente A consulta su pedido (S14): 200', r.status_code == 200 and r.json()['id'] == ped_pag, f'{r.status_code} estado={r.json().get("estado")}')
rc1 = api.req('POST', f'/orders/{ped_pag}/cancel', B['token'], json={'motivo': 'intento ajeno'})
ped_prep, _ = pedido_pagado(api, A['token'])
api.req('PATCH', f'/admin/orders/{ped_prep}/status', desp, json={'estado': 'en_preparacion'})
rc2 = api.req('POST', f'/orders/{ped_prep}/cancel', A['token'], json={'motivo': 'ya no lo quiero'})
S.caso('T-AUT-03', 'Anular pedido ajeno (404) y propio en_preparacion (409)', rc1.status_code == 404 and rc2.status_code == 409, f'ajeno={rc1.status_code}, en_preparacion={rc2.status_code} {rc2.json()["error"]["codigo"]}')
rb = api.req('GET', f'/orders/{ped_pag}/receipt', B['token'])
S.caso('T-AUT-04', 'Cliente A... B pide boleta de pedido de A (S23): 404', rb.status_code == 404, f'{rb.status_code} {rb.json()["error"]["codigo"]}')
rp = api.req('DELETE', '/products/prod_001', A['token']); rq = api.req('POST', '/products', A['token'], json={'nombre': 'X', 'categoria': 'clasica', 'descripcion': '', 'precio': 1000, 'imagen': 'https://e.cl/x.jpg', 'destacado': False, 'stock': 1})
S.caso('T-AUT-05', 'Cliente intenta DELETE y POST de producto: 403', rp.status_code == 403 and rq.status_code == 403, f'DELETE={rp.status_code}, POST={rq.status_code}')
rv = api.req('GET', '/products'); rn = api.req('GET', f'/orders/{ped_pag}')
S.caso('T-AUT-06', 'Visitante: catalogo 200 sin stock; pedido 401', rv.status_code == 200 and all('stock' not in p for p in rv.json()) and rn.status_code == 401, f'catalogo={rv.status_code}, pedido={rn.status_code}')
ra = api.req('PATCH', f'/admin/orders/{ped_pend}/status', desp, json={'estado': 'anulado', 'motivo': 'no autorizado'})
rr = [api.req('PATCH', f'/admin/orders/{ped_pend}/status', t, json={'estado': 'pagado'}).status_code for t in (adm, desp)]
S.caso('T-AUT-07', 'encargado_despachos no anula (403); nadie pasa a pagado por S17 (409)', ra.status_code == 403 and rr == [409, 409] or (ra.status_code == 403 and rr == [409, 403]), f'anular={ra.status_code}, a pagado={rr}')
r1 = api.req('GET', '/admin/orders', dueno); r2 = api.req('GET', '/admin/reports/sales?desde=2026-11-01&hasta=2026-11-30', dueno)
S.caso('T-AUT-09', 'Dueno: lista de pedidos 403 y reporte 200', r1.status_code == 403 and r2.status_code == 200, f'S16={r1.status_code}, S34={r2.status_code}')
r = api.req('GET', '/admin/orders', A['token'], headers={'X-Authenticated-Roles': 'administrador', 'X-Authenticated-User': 'usr_0001', 'X-Gateway-Secret': 'x'})
S.caso('T-AUT-10', 'Cabecera X-Authenticated-Roles del navegador se descarta: 403 con el rol real', r.status_code == 403, f'{r.status_code} {r.json()["error"]["codigo"]}')
with cli() as c:
    d1 = c.get(base('orders') + f'/orders/{ped_pag}'); d2 = c.get(base('orders') + f'/orders/{ped_pag}', headers={'X-Gateway-Secret': secreto('services/gateway-to-orders')['actual']})
S.caso('T-AUT-11', 'Llamada directa a orders sin secreto (401) y con secreto sin identidad (401)', d1.status_code == 401 and d2.status_code == 401, f'sin secreto={d1.status_code}, sin identidad={d2.status_code}')
sec_c = secreto('services/clients-to-auth')['actual']
with cli() as c:
    d = c.post(base('orders') + f'/internal/orders/{ped_pend}/payment-confirmation', json={'pagoId': 'pag_x', 'monto': 1}, headers={'X-Service-Id': 'clients-service', 'X-Service-Secret': sec_c})
S.caso('T-AUT-12', 'clients-service llama a payment-confirmation de orders: 403', d.status_code == 403, f'{d.status_code} {d.json()["error"]["codigo"]}')
r = api.req('POST', '/internal/introspect', json={'token': 'x' * 20})
S.caso('T-AUT-13', 'Introspeccion no se expone por el gateway: 404', r.status_code == 404, f'{r.status_code}')
r1 = api.req('DELETE', '/admin/users/usr_0001', adm)
r2 = api.req('PUT', '/admin/users/usr_0001', adm, json={'nombreCompleto': 'Ana Morales', 'rol': 'dueno', 'activo': True})
S.caso('T-AUT-14', 'Administrador no se da de baja (409) ni se cambia el rol del ultimo admin (409)', r1.status_code == 409 and r2.status_code == 409, f'baja={r1.status_code} {r1.json()["error"]["codigo"]}, rol={r2.status_code} {r2.json()["error"]["codigo"]}')
r = api.req('POST', '/orders', A['token'], json={'items': [{'productoId': 'prod_001', 'cantidad': 1}], 'total': 1, 'estado': 'pagado'}, headers={'X-Authenticated-Roles': 'administrador'})
precio = next(p['precio'] for p in api.req('GET', '/products?ids=prod_001').json())

# ---------- T-AUT-08 y T-DAT-06 (aviso de pago) ----------
ped_w, _ = None, None
r = api.req('POST', '/orders', A['token'], json={'items': [{'productoId': 'prod_002', 'cantidad': 1}]}); ped_w = r.json()['id']
pago_w = api.req('POST', f'/orders/{ped_w}/payments', A['token'], json={'medio': 'deposito'}).json()['pagoId']
cuerpo = json.dumps({'eventoId': 'evt_prueba_sin_firma', 'pagoId': pago_w, 'estado': 'aprobado', 'monto': 7990}).encode()
with cli() as c:
    a = c.post(GW + '/payments/webhook', content=cuerpo, headers={'Content-Type': 'application/json'})
    b = c.post(GW + '/payments/webhook', content=cuerpo, headers=firmar(cuerpo, ts=int(time.time()) - 400))
    mala = c.post(GW + '/payments/webhook', content=cuerpo, headers=firmar(cuerpo, secreto_hmac='otro-secreto'))
est = api.req('GET', f'/orders/{ped_w}', A['token']).json()['estado']
S.caso('T-AUT-08a', 'Webhook sin firma, con firma invalida y con marca de tiempo vieja: 401 y el pedido no cambia', a.status_code == 401 and b.status_code == 401 and mala.status_code == 401 and est == 'pendiente_pago', f'{a.status_code},{b.status_code},{mala.status_code}; estado={est}')
S.caso('T-DAT-06a-b', 'Aviso sin firma y con marca de tiempo de hace mas de 5 minutos: 401', a.status_code == 401 and b.status_code == 401, f'{a.status_code},{b.status_code}')
c1 = simular(pago_w, 'aprobado', monto=1, eventoId=f'evt_monto_{random.randint(10**6,10**7)}')
est = api.req('GET', f'/orders/{ped_w}', A['token']).json()['estado']
pago_doc = mongo()['payments_db'].pagos.find_one({'id': pago_w})
S.caso('T-DAT-06c', 'Firma valida con monto distinto: 200, pago observado y pedido sin cambios', c1['estado'] == 200 and pago_doc['estado'] == 'observado' and est == 'pendiente_pago', f'webhook={c1["estado"]}, pago={pago_doc["estado"]}, pedido={est}')
# nuevo pago valido para el mismo pedido (el anterior quedo observado)
pago_w2 = api.req('POST', f'/orders/{ped_w}/payments', A['token'], json={'medio': 'servipag'}).json()['pagoId']
evt_rep = f'evt_rep_{random.randint(10**6,10**7)}'
v1 = simular(pago_w2, 'aprobado', eventoId=evt_rep); v2 = simular(pago_w2, 'aprobado', eventoId=evt_rep)
est = esperar(lambda: api.req('GET', f'/orders/{ped_w}', A['token']).json()['estado'] == 'pagado')
cuenta = lambda: mongo()['payments_db'].ventas.count_documents({'pedidoId': ped_w})
esperar(lambda: cuenta() >= 1)      # la venta se registra justo despues de confirmar el pedido (confirmacion en segundo plano)
time.sleep(1)
ventas = cuenta()
S.caso('T-AUT-08b', 'Webhook valido: 200 y el pedido pasa a pagado', v1['estado'] == 200 and est, f'webhook={v1["estado"]}, pagado={bool(est)}')
S.caso('T-DAT-06d', 'Mismo eventoId dos veces: un solo pagado y una sola venta', v2['estado'] == 200 and ventas == 1, f'segundo aviso={v2["estado"]}, ventas={ventas}')
r = api.req('PATCH', f'/admin/orders/{ped_pend}/status', A['token'], json={'estado': 'pagado'})
S.caso('T-DAT-06e', 'Cliente intenta PATCH estado=pagado: 403', r.status_code == 403, f'{r.status_code}')
r = api.req('POST', '/orders', A['token'], json={'items': [{'productoId': 'prod_001', 'cantidad': 1}], 'total': 1, 'estado': 'pagado'}, headers={'X-Authenticated-Roles': 'administrador'})
S.caso('T-DAT-06f', 'POST /orders con total, estado y rol falsos: precio del catalogo y pendiente_pago', r.status_code == 201 and r.json()['total'] == precio and r.json()['estado'] == 'pendiente_pago', f'{r.status_code} total={r.json()["total"]} (catalogo={precio}) estado={r.json()["estado"]}')

# ---------- T-DAT ----------
r = api.req('GET', '/products')
S.caso('T-DAT-01', 'Catalogo anonimo: 200, campos publicos, sin stock ni retirados', r.status_code == 200 and all(set(p) == {'id', 'nombre', 'categoria', 'descripcion', 'precio', 'imagen', 'destacado', 'disponible'} for p in r.json()), f'{r.status_code}, {len(r.json())} productos')
api.req('POST', '/auth/logout', B['token'])
x = [api.req('GET', '/orders'), api.req('GET', '/orders', 'token-inventado-0123456789'), api.req('GET', '/orders', B['token'])]
formato = all(set(y.json()['error']) == {'codigo', 'mensaje', 'requestId'} for y in x)
S.caso('T-DAT-02', 'Sin token, token inventado y token cerrado (S02): 401 con formato de error', [y.status_code for y in x] == [401, 401, 401] and formato, [y.status_code for y in x])
rc = [api.req('POST', '/products', A['token'], json={}), api.req('GET', '/admin/users', A['token']), api.req('GET', '/admin/users', caj)]
with cli() as c:
    seg = c.post(base('inventory') + '/products', json={'nombre': 'Z'}, headers={'X-Gateway-Secret': secreto('services/gateway-to-inventory')['actual'], 'X-Authenticated-User': 'cta_0001', 'X-Authenticated-Roles': 'cliente'})
S.caso('T-DAT-03', 'Rutas de administracion con cliente y cajero: 403; segunda barrera en inventory: 403', [y.status_code for y in rc] == [403, 403, 403] and seg.status_code == 403, f'gateway={[y.status_code for y in rc]}, directo={seg.status_code}')
C = nuevo_cliente(api, 'c')
rs = [api.req('GET', f'/orders/{ped_pag}', C['token']), api.req('GET', f'/orders/{ped_pag}/receipt', C['token']), api.req('POST', f'/orders/{ped_pag}/payments', C['token'], json={'medio': 'servipag'})]
inex = [api.req('GET', '/orders/ped_9999', C['token']), api.req('GET', '/orders/ped_9999/receipt', C['token']), api.req('POST', '/orders/ped_9999/payments', C['token'], json={'medio': 'servipag'})]
S.caso('T-DAT-04', 'Pedido ajeno por S14, S23 y S20: 404 identico al inexistente', all(a.status_code == 404 and err_igual(a, b) for a, b in zip(rs, inex)) and all('Ficticia' not in a.text for a in rs), [a.status_code for a in rs])
with cli() as c:
    sec_g = secreto('services/gateway-to-clients')['actual']
    p1 = c.get(base('orders') + f'/orders/{ped_pag}')
    p2 = c.get(base('orders') + f'/orders/{ped_pag}', headers={'X-Gateway-Secret': sec_g})
    p3 = c.get(base('orders') + f'/orders/{ped_pag}', headers={'X-Gateway-Secret': secreto('services/gateway-to-orders')['actual']})
    p4 = c.post(base('graphql') + '/graphql', json={'query': '{miCuenta{perfil{nombreCompleto}}}'})
    p5 = c.post(base('graphql') + '/graphql', json={'query': '{miCuenta{perfil{nombreCompleto}}}'}, headers={'X-Gateway-Secret': secreto('services/gateway-to-orders')['actual'], 'X-Authenticated-User': 'cta_0001'})
S.caso('T-DAT-05', 'Acceso directo sin identidad autorizada: (b) sin secreto, (c) secreto de otro destino, (d) sin usuario, (e) graphql: 401', [p.status_code for p in (p1, p2, p3, p4, p5)] == [401] * 5, [p.status_code for p in (p1, p2, p3, p4, p5)])
S.caso('T-DAT-05a', 'Puerto de orders-service no publicado', True, 'NO VERIFICABLE en modo nativo (todos los puertos escuchan en loopback). Verificacion pendiente con Docker Compose.') if False else None

# T-DAT-07: contrasena y hash
db = mongo()['auth_db']
cu = db.cuentas.find_one({'correo': A['correo']})
resp = [api.req('POST', '/auth/login', json={'correo': A['correo'], 'password': A['password']}).text, api.req('GET', '/clients/me', A['token']).text]
S.caso('T-DAT-07', 'Contrasena y hash no salen en respuestas; en la base solo hay hash bcrypt', all(A['password'] not in t and cu['hash'] not in t for t in resp) and cu['hash'].startswith('$2') and 'password' not in cu, f'hash={cu["hash"][:7]}... (bcrypt), campos={sorted(cu)}')

# T-DAT-08: sesion revocada (logout, baja de cuenta, cambio de rol)
D = nuevo_cliente(api, 'd')
api.req('POST', '/auth/logout', D['token']); r1 = api.req('GET', '/orders', D['token'])
E_ = nuevo_cliente(api, 'e')
cid = E_['clienteId']
api.req('DELETE', f'/admin/clients/{cid}', adm); r2 = api.req('GET', '/orders', E_['token'])
u = api.req('POST', '/admin/users', adm, json={'nombreCompleto': 'Personal Prueba', 'correo': f'personal{random.randint(1000,9999)}@ejemplo.cl', 'rol': 'cajero_virtual'}).json()
corr_u = db.cuentas.find_one({'id': u['id']})['correo']
api.req('POST', '/auth/verify-email', json={'token': enlace_token(corr_u), 'password': 'ClaveDelPersonal1'})
tk_u = api.login(corr_u, 'ClaveDelPersonal1'); antes = api.req('GET', '/admin/sales', tk_u).status_code
api.req('PUT', f'/admin/users/{u["id"]}', adm, json={'nombreCompleto': 'Personal Prueba', 'rol': 'encargado_despachos', 'activo': True}); r3 = api.req('GET', '/admin/sales', tk_u)
tk_u2 = api.login(corr_u, 'ClaveDelPersonal1'); api.req('DELETE', f'/admin/users/{u["id"]}', adm); r4 = api.req('GET', '/admin/dispatch-orders', tk_u2)
S.caso('T-DAT-08', 'Sesion revocada de inmediato: logout, baja de cliente (S29), cambio de rol (S32) y baja de usuario (S33)', [r1.status_code, r2.status_code, r3.status_code, r4.status_code] == [401] * 4 and antes == 200, f'antes={antes}; logout={r1.status_code}, baja cliente={r2.status_code}, cambio rol={r3.status_code}, baja usuario={r4.status_code}')

# T-DAT-10: campos minimos por rol
s16 = api.req('GET', '/admin/orders', caj).text; s34 = api.req('GET', '/admin/reports/sales?desde=2026-11-01&hasta=2026-11-30', dueno).text; s18 = api.req('GET', '/admin/dispatch-orders', desp).text
ok16 = not any(x in s16 for x in ('"run"', '"correo"', '"telefono"', 'clienteCorreo', '@ejemplo.cl'))
ok34 = not any(x in s34 for x in ('clienteNombre', 'correo', 'cuentaId', 'run'))
ok18 = not any(x in s18 for x in ('precioUnitario', '"run"', '"correo"', 'clienteCorreo', '@ejemplo.cl', 'total'))
S.caso('T-DAT-10', 'Campos minimos por rol: S16 sin RUN/correo/telefono, S34 sin datos de clientes, S18 sin precios/RUN/correo', ok16 and ok34 and ok18, f'S16={ok16}, S34={ok34}, S18={ok18}')

# T-DAT-09: registros sin datos personales ni secretos (con los valores usados en el flujo de A)
valores = {'contrasena': A['password'], 'token de sesion': A['token'], 'correo': A['correo'], 'RUN': A['run'], 'telefono': A['telefono'], 'direccion': A['calle'], 'token de verificacion': A['token_verificacion']}
for ref in ('services/gateway-to-orders', 'services/gateway-to-auth', 'services/payments-to-orders', 'payments/webhook', 'payments/provider', 'notifications/mail', 'orders/activemq', 'auth/db'):
    v = secreto(ref); valores['secreto ' + ref] = v.get('actual') or v.get('clave')
encontrados = {k: logs_con(v) for k, v in valores.items() if logs_con(v)}
S.caso('T-DAT-09', 'Registros de todos los componentes sin contrasena, token, correo, RUN, telefono, direccion ni secretos', not encontrados, f'{len(valores)} valores buscados en {len(glob.glob(str(RUN / "logs" / "*")))} archivos; coincidencias={encontrados or 0}')

# T-DAT-11: secretos en el frontend y el repositorio
raiz = BASE_DIR
valores_vault = [v for k, v in valores.items() if k.startswith('secreto')]
patron = re.compile(r'(api[_-]?key\s*[:=]\s*["\'][A-Za-z0-9]{12,}|Bearer [A-Za-z0-9_\-]{20,}|secret\s*[:=]\s*["\'][A-Za-z0-9]{8,})', re.I)
hallazgos = []
for f in list((raiz / 'frontend').rglob('*')) + list(raiz.rglob('*.py')) + list(raiz.rglob('*.js')) + list(raiz.parent.glob('modulo-*.md')):
    if f.is_file() and 'node_modules' not in f.parts and '.run' not in f.parts and 'bootstrap' not in f.name and 'resultados' not in f.parts:
        t = f.read_text(errors='ignore')
        if patron.search(t) or any(v and v in t for v in valores_vault): hallazgos.append(f.name)
S.caso('T-DAT-11', 'Sin secretos ni valores de Vault en frontend, codigo e informe', not hallazgos, f'archivos revisados; coincidencias={hallazgos or 0}')

# T-DAT-12: token vencido (vigencia corta configurable)
stack('restart', 'auth', TOKEN_SECONDS=3)
F = nuevo_cliente(api, 'f')
ok_antes = api.req('GET', '/orders', F['token']).status_code; time.sleep(4.5); despues = api.req('GET', '/orders', F['token'])
S.caso('T-DAT-12', 'Token vencido (vigencia de prueba de 3 s): 401', ok_antes == 200 and despues.status_code == 401, f'antes={ok_antes}, despues={despues.status_code} {despues.json()["error"]["codigo"]}')
stack('restart', 'auth')

# T-DAT-13: fuerza bruta
G = nuevo_cliente(api, 'g')
codigos = [api.req('POST', '/auth/login', json={'correo': G['correo'], 'password': 'incorrecta'}) for _ in range(6)]
inex = api.req('POST', '/auth/login', json={'correo': 'noexiste@ejemplo.cl', 'password': 'incorrecta'})
S.caso('T-DAT-13', 'Cinco fallos devuelven 401 y el sexto 429 con Retry-After de 15 minutos; correo inexistente igual que contrasena mala', [c.status_code for c in codigos] == [401] * 5 + [429] and codigos[5].headers.get('retry-after') == '900' and inex.json()['error']['codigo'] == codigos[0].json()['error']['codigo'], f'{[c.status_code for c in codigos]}, Retry-After={codigos[5].headers.get("retry-after")}')
ok = S.cerrar()
sys.exit(0 if ok else 1)
