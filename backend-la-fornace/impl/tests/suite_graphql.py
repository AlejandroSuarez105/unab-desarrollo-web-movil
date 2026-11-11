"""Pruebas del GraphQL Gateway del Modulo 8 (T-GQL-01..17). T-GQL-15 se ejecuta en e2e_frontend.py."""
import sys, time, json, random
from h import *
from reg import Suite

S = Suite('graphql')
api = Api()
A = nuevo_cliente(api, 'ga'); B = nuevo_cliente(api, 'gb')
adm, dueno, caj, desp = (login_demo(api, u) for u in ('admin@ejemplo.cl', 'dueno@ejemplo.cl', 'cajero@ejemplo.cl', 'despachos@ejemplo.cl'))
ped, _ = pedido_pagado(api, A['token'], [{'productoId': 'prod_002', 'cantidad': 1}, {'productoId': 'prod_003', 'cantidad': 2}])

Q = 'query($id:ID!){resumenPedido(id:$id){id estado total items{productoId nombre cantidad precioUnitario producto{id nombre precio disponible}}}}'

def gql(tok, query, variables=None, rid=None):
    h = {'X-Request-Id': rid} if rid else {}
    return api.req('POST', '/graphql', tok, json={'query': query, 'variables': variables or {}}, headers=h)

def codigos(r):
    try: return [e['extensions']['code'] for e in r.json().get('errors', [])]
    except Exception: return []

def conteo(rid, archivo, texto):
    return sum(1 for f, l in lineas_log(rid) if f.startswith(archivo) and texto in l)

# T-GQL-01 / 02
rid = f'req-gql01-{random.randint(10**5, 10**6)}'
r = gql(A['token'], Q, {'id': ped}, rid); d = r.json()['data']['resumenPedido']
logs = lineas_log(rid)
arch = sorted({f for f, _ in logs})
S.caso('T-GQL-01', 'Agregacion autorizada: pedido con el producto vigente en cada item; mismo requestId en los registros de los tres sistemas',
       r.status_code == 200 and d['id'] == ped and all(i['producto'] and i['producto']['id'] == i['productoId'] for i in d['items']) and {'graphql-gateway.log', 'orders-service.log', 'inventory-service.log'} <= set(arch),
       f'{r.status_code}, {len(d["items"])} items con producto; registros con el requestId en {arch}')
llamadas_inv = sum(1 for f, l in logs if f.startswith('inventory-service') and '/products' in l)
S.caso('T-GQL-02', 'Una sola llamada a inventory (GET /products?ids=) para los 2 items', llamadas_inv == 1, f'llamadas a inventory con el requestId = {llamadas_inv}')

# T-GQL-03 / 04 (servicios detenidos)
stack('stop', 'inventory'); t0 = time.time()
r = gql(A['token'], Q, {'id': ped}); dt = time.time() - t0; j = r.json()
S.caso('T-GQL-03', 'Inventory detenido: pedido con producto null y SUBSISTEMA_NO_DISPONIBLE con path; menos de 15 s',
       r.status_code == 200 and j['data']['resumenPedido'] and all(i['producto'] is None for i in j['data']['resumenPedido']['items']) and 'SUBSISTEMA_NO_DISPONIBLE' in codigos(r) and all('path' in e for e in j['errors']) and dt < 15,
       f'{r.status_code}, errores={codigos(r)}, path={j["errors"][0].get("path")}, {dt:.1f} s')
stack('restart', 'inventory')
rid4 = f'req-gql04-{random.randint(10**5, 10**6)}'
stack('stop', 'orders'); r = gql(A['token'], Q, {'id': ped}, rid4); j = r.json()
S.caso('T-GQL-04', 'Orders detenido: resumenPedido null, SUBSISTEMA_NO_DISPONIBLE y ninguna llamada a inventory',
       j['data']['resumenPedido'] is None and 'SUBSISTEMA_NO_DISPONIBLE' in codigos(r) and conteo(rid4, 'inventory-service', 'products') == 0,
       f'{r.status_code}, errores={codigos(r)}, llamadas a inventory={conteo(rid4, "inventory-service", "products")}')
stack('restart', 'orders'); time.sleep(2)

# T-GQL-05
rid5 = f'req-gql05-{random.randint(10**5, 10**6)}'
r1 = gql(B['token'], Q, {'id': ped}, rid5); r2 = gql(B['token'], Q, {'id': 'ped_9999'})
S.caso('T-GQL-05', 'Pedido de otra cuenta e inexistente: NO_ENCONTRADO identico, sin datos de A ni llamada a inventory',
       codigos(r1) == codigos(r2) == ['NO_ENCONTRADO'] and r1.json()['data']['resumenPedido'] is None and r1.json()['errors'][0]['message'] == r2.json()['errors'][0]['message'] and A['nombre'] not in r1.text and conteo(rid5, 'inventory-service', 'products') == 0,
       f'ajeno={codigos(r1)}, inexistente={codigos(r2)}')

# T-GQL-06
rid6 = f'req-gql06-{random.randint(10**5, 10**6)}'
QN = 'query($id:ID!){resumenPedido(id:$id){id clienteNombre}}'
r1 = gql(A['token'], QN, {'id': ped}, rid6); r2 = gql(desp, QN, {'id': ped})
S.caso('T-GQL-06', 'clienteNombre con cliente: CAMPO_NO_AUTORIZADO sin llamadas a sistemas; con encargado_despachos si llega',
       codigos(r1) == ['CAMPO_NO_AUTORIZADO'] and conteo(rid6, 'orders-service', 'orders') == 0 and r2.json()['data']['resumenPedido']['clienteNombre'] == A['nombre'],
       f'cliente={codigos(r1)}, despachos nombre recibido={r2.json()["data"]["resumenPedido"]["clienteNombre"] == A["nombre"]}')

# T-GQL-07
r1 = gql(dueno, Q, {'id': ped}); r2 = gql(caj, 'query{miCuenta{perfil{nombreCompleto}}}')
S.caso('T-GQL-07', 'resumenPedido con dueno y miCuenta con cajero_virtual: OPERACION_NO_AUTORIZADA', codigos(r1) == codigos(r2) == ['OPERACION_NO_AUTORIZADA'], f'{codigos(r1)}, {codigos(r2)}')

# T-GQL-08 / 09 / 10 / 11
rid8 = f'req-gql08-{random.randint(10**5, 10**6)}'
# El schema publicado tiene como maximo 4 niveles, por eso el limite real (5) no se puede superar con una consulta valida.
# La prueba reinicia el GraphQL Gateway con GQL_PROFUNDIDAD=2 y envia una consulta de 4 niveles; despues restaura el valor 5.
stack('restart', 'graphql', GQL_PROFUNDIDAD=2, RL_FACTOR=50)
r = gql(A['token'], 'query($id:ID!){resumenPedido(id:$id){items{producto{id}}}}', {'id': ped}, rid8)
ok8 = 'LIMITE_PROFUNDIDAD' in codigos(r) and conteo(rid8, 'orders-service', 'orders') == 0
stack('restart', 'graphql', RL_FACTOR=50)
S.caso('T-GQL-08', 'Consulta mas profunda que el limite (configurado en 2 para la prueba): LIMITE_PROFUNDIDAD sin llamar a sistemas', r.status_code == 400 and ok8, f'{r.status_code} {codigos(r)}; limite real de produccion = 5 (el schema no admite más de 5 niveles)')
rid9 = f'req-gql09-{random.randint(10**5, 10**6)}'
completo = 'resumenPedido(id:"%s"){id estado estadoPago total creadoEn expiraEn boletaDisponible direccionEntrega{calle comuna referencia} historialEstados{estado fecha} items{productoId nombre cantidad precioUnitario producto{id nombre categoria descripcion precio imagen disponible}}}' % ped
r = gql(A['token'], 'query{a:%s b:%s c:%s}' % (completo, completo, completo), rid=rid9)
S.caso('T-GQL-09', 'Tres alias de resumenPedido completo superan el costo maximo: LIMITE_COSTO sin llamar a sistemas', 'LIMITE_COSTO' in codigos(r) and conteo(rid9, 'orders-service', 'orders') == 0, f'{r.status_code} {codigos(r)}')
r = gql(A['token'], 'query{miCuenta(limitePedidos:500){pedidos{id}}}')
S.caso('T-GQL-10', 'limitePedidos: 500 fuera de rango: CONSULTA_INVALIDA', codigos(r) == ['CONSULTA_INVALIDA'], f'{r.status_code} {codigos(r)}')
r1 = gql(A['token'], 'mutation{x}'); r2 = gql(A['token'], '{ __schema { types { name } } }')
S.caso('T-GQL-11', 'Mutation e introspeccion: CONSULTA_INVALIDA', codigos(r1) == ['CONSULTA_INVALIDA'] and codigos(r2) == ['CONSULTA_INVALIDA'] and 'Query' not in r2.text, f'{codigos(r1)}, {codigos(r2)}')

# T-GQL-12
r = api.req('POST', '/graphql', json={'query': '{miCuenta{perfil{nombreCompleto}}}'})
n_gql = len([1 for f, l in lineas_log(r.json()['error']['requestId']) if f.startswith('graphql-gateway')])
S.caso('T-GQL-12', 'Sin Authorization: 401 y la peticion no llega al GraphQL Gateway', r.status_code == 401 and n_gql == 0, f'{r.status_code}, registros de graphql-gateway con ese requestId={n_gql}')

# T-GQL-13 / 14 (acceso directo)
sec_otro = secreto('services/gateway-to-orders')['actual']
with cli() as c:
    u1 = c.post(base('graphql') + '/graphql', json={'query': '{miCuenta{perfil{nombreCompleto}}}'})
    u2 = c.post(base('graphql') + '/graphql', json={'query': '{miCuenta{perfil{nombreCompleto}}}'}, headers={'X-Gateway-Secret': sec_otro, 'X-Authenticated-User': 'cta_0001'})
S.caso('T-GQL-13', 'Acceso directo al GraphQL Gateway sin secreto y con el de otro destino: 401', u1.status_code == 401 and u2.status_code == 401,
       f'sin secreto={u1.status_code}, secreto de otro destino={u2.status_code}. La parte "conexion rechazada desde el host" NO se pudo verificar: en modo nativo todos los puertos escuchan en loopback del mismo equipo.')
w = [api.req('GET', f'/{s}-service/health', A['token']).status_code for s in ('orders', 'inventory', 'clients')]
w2 = [api.req('GET', f'/internal/{s}', A['token']).status_code for s in ('orders', 'products')]
S.caso('T-GQL-14', 'Subsistemas desde el navegador: el API Gateway no tiene ruta hacia orders-service, inventory-service ni clients-service ni hacia /internal (404)',
       all(x == 404 for x in w + w2), f'rutas por nombre de servicio={w}, rutas /internal={w2}. La parte "puerto no publicado" NO se pudo verificar en modo nativo (puertos en loopback).')

# T-GQL-16 / 17 (par de graphql)
with cli() as c: pass
r1 = par('graphql-gateway', 'orders-service', 'GET', f'/orders/{ped}', headers={'X-Authenticated-User': mongo()['auth_db'].cuentas.find_one({'correo': B['correo']})['id'], 'X-Authenticated-Roles': 'cliente'})
S.caso('T-GQL-16', 'Orders sigue decidiendo: par graphql-to-orders con la identidad de otra cuenta recibe 404', r1.status_code == 404, f'{r1.status_code} {r1.json()["error"]["codigo"]}')
r1 = par('graphql-gateway', 'orders-service', 'POST', '/orders', json={'items': [{'productoId': 'prod_002', 'cantidad': 1}]}, headers={'X-Authenticated-User': 'cta_0001', 'X-Authenticated-Roles': 'cliente'})
r2 = par('graphql-gateway', 'orders-service', 'PATCH', f'/admin/orders/{ped}/status', json={'estado': 'anulado', 'motivo': 'x'}, headers={'X-Authenticated-User': 'cta_0001', 'X-Authenticated-Roles': 'administrador'})
S.caso('T-GQL-17', 'GraphQL solo lee: POST /orders y PATCH de estado con el par graphql-to-orders: 403', r1.status_code == 403 and r2.status_code == 403, f'POST={r1.status_code}, PATCH={r2.status_code}')

sys.exit(0 if S.cerrar() else 1)
