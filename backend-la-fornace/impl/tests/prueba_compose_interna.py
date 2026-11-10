"""Pruebas del despliegue en Docker Compose que se ejecutan DENTRO de la red privada (contenedor 'herramientas'):
acceso directo a los sistemas sin identidad autorizada, GraphQL Gateway directo y un recorrido completo de compra a traves del API Gateway.
Uso: python scripts/compose.py probar   (lo lanza junto con tests/suite_compose.py)"""
import sys, json, random, time, os
sys.path.insert(0, os.path.dirname(__file__))
from h import *
from reg import Suite

S = Suite('compose_interna')
api = Api()
GQL_Q = 'query($id:ID!){resumenPedido(id:$id){id estado total items{productoId nombre cantidad producto{id nombre precio disponible}}}}'

def estado(metodo, url, **kw):
    with cli() as c:
        return c.request(metodo, url, **kw).status_code

# ---- acceso directo a los sistemas desde otro contenedor de la red privada (equivale a T-DAT-05, T-AUT-11, T-AUT-12 y T-GQL-13b y c)
o = base('orders') + '/orders/ped_0001'
s_otro = secreto('services/gateway-to-clients')['actual']
s_ord = secreto('services/gateway-to-orders')['actual']
r1 = estado('GET', o)
r2 = estado('GET', o, headers={'X-Gateway-Secret': s_otro})
r3 = estado('GET', o, headers={'X-Gateway-Secret': s_ord})
par_c = secreto('services/clients-to-auth')['actual']
r4 = estado('GET', o, headers={'X-Service-Id': 'clients-service', 'X-Service-Secret': par_c})
S.caso('CMP-RED-01', 'orders-service llamado desde otro contenedor sin secreto, con el secreto de otro destino, con el suyo pero sin identidad, y con un par de otro sistema: siempre rechazado',
       r1 == 401 and r2 == 401 and r3 == 401 and r4 in (401, 403), f'sin secreto={r1}, secreto de otro destino={r2}, secreto propio sin identidad={r3}, par de otro sistema={r4}')
g = base('graphql') + '/graphql'
q = {'query': '{__typename}'}
g1 = estado('POST', g, json=q)
g2 = estado('POST', g, json=q, headers={'X-Gateway-Secret': s_otro})
g3 = estado('POST', g, json=q, headers={'X-Gateway-Secret': s_ord})
S.caso('CMP-RED-02', 'GraphQL Gateway llamado directamente sin secreto, con el de otro destino y con el de orders: 401 en los tres', g1 == 401 and g2 == 401 and g3 == 401, f'{g1}, {g2}, {g3}')
i1 = estado('GET', base('gateway') + '/internal/introspect'); i2 = estado('GET', base('gateway') + '/docs'); i3 = estado('GET', base('gateway') + '/api/v1/internal/introspect')
S.caso('CMP-RED-03', 'El API Gateway no publica /internal, /docs ni la introspeccion de Auth', i1 in (404,) and i2 in (404,) and i3 in (404,), f'{i1}, {i2}, {i3}')

# ---- MongoDB con autenticacion: un usuario por sistema, solo sobre su base
import pymongo
from pymongo.errors import OperationFailure
SIST = ['auth', 'clients', 'inventory', 'orders', 'payments', 'dispatch', 'notifications']
try:
    pymongo.MongoClient('mongodb://mongo:27017', serverSelectionTimeoutMS=4000)['orders_db'].pedidos.find_one(); sin = 'permitido'
except OperationFailure as e:
    sin = f'rechazado (codigo {e.code})'
try:
    pymongo.MongoClient('mongodb://mongo:27017', serverSelectionTimeoutMS=4000)['orders_db'].list_collection_names(); sin2 = 'permitido'
except OperationFailure as e:
    sin2 = f'rechazado (codigo {e.code})'
S.caso('CMP-DB-01', 'MongoDB rechaza una conexion sin credenciales: no puede leer ni listar las colecciones de orders_db', sin.startswith('rechazado') and sin2.startswith('rechazado'), f'leer: {sin}; listar: {sin2}')
propias, ajenas_rechazadas, ajenas_total, detalle_db = 0, 0, 0, []
for s in SIST:
    c = secreto(f'{s}/db')
    u = pymongo.MongoClient('mongodb://mongo:27017', username=c['usuario'], password=c['clave'], authSource=f'{s}_db', serverSelectionTimeoutMS=4000)
    try:
        col = u[f'{s}_db']['_prueba_aislamiento']; col.insert_one({'_id': 'x', 'sistema': s}); ok_p = col.find_one({'_id': 'x'}) is not None; col.delete_one({'_id': 'x'})
    except OperationFailure:
        ok_p = False
    propias += ok_p
    for t in SIST:
        if t == s: continue
        ajenas_total += 1
        try:
            u[f'{t}_db'].list_collection_names(); u[f'{t}_db']['_x'].find_one()
        except OperationFailure as e:
            if e.code == 13: ajenas_rechazadas += 1
    detalle_db.append(f'{c["usuario"]}:{"propia ok" if ok_p else "propia FALLA"}')
S.caso('CMP-DB-02', 'Cada sistema, con su usuario de MongoDB, escribe y lee en su base y es rechazado (Unauthorized) en las de los otros seis',
       propias == len(SIST) and ajenas_rechazadas == ajenas_total == 42, f'bases propias accesibles={propias}/{len(SIST)}; bases ajenas rechazadas={ajenas_rechazadas}/{ajenas_total}')
root = pymongo.MongoClient(os.environ['MONGO_URL'], serverSelectionTimeoutMS=4000)
usuarios = {u['user']: u for u in root.admin.command('usersInfo', {'forAllDBs': True})['users']}
esperado = {f'{s}_user': (f'{s}_db', [{'role': 'readWrite', 'db': f'{s}_db'}]) for s in SIST}
cumple = all(k in usuarios and usuarios[k]['db'] == db and [{'role': r['role'], 'db': r['db']} for r in usuarios[k]['roles']] == roles for k, (db, roles) in esperado.items())
S.caso('CMP-DB-03', 'MongoDB tiene exactamente un usuario por sistema, definido en la base del sistema y con el unico rol readWrite sobre esa base', cumple and len([k for k in usuarios if k.endswith('_user')]) == len(SIST),
       '; '.join(f'{k}: {usuarios[k]["db"]} {[r["role"] + "@" + r["db"] for r in usuarios[k]["roles"]]}' for k in sorted(usuarios) if k.endswith('_user'))[:380])

# ---- recorrido completo a traves del API Gateway
p = api.req('GET', '/products')
S.caso('CMP-01', 'Catalogo publico sin sesion: 12 productos, sin stock', p.status_code == 200 and len(p.json()) == 12 and all('stock' not in x for x in p.json()), f'{p.status_code}, {len(p.json())} productos')
S.caso('CMP-02', 'Operacion protegida sin token: 401', api.req('GET', '/orders').status_code == 401, api.req('GET', '/orders').status_code)
A = nuevo_cliente(api, 'cmpa'); B = nuevo_cliente(api, 'cmpb')
S.caso('CMP-03', 'Registro (S03), correo con enlace en la bandeja de prueba, confirmacion (S04) e inicio de sesion (S01) de dos clientes', bool(A['token']) and bool(B['token']), f"clientes {A['clienteId']} y {B['clienteId']}")
inv0 = {x['id']: x['stock'] for x in api.req('GET', '/admin/products', login_demo(api, 'admin@ejemplo.cl')).json()}
ped, pago = pedido_pagado(api, A['token'], [{'productoId': 'prod_007', 'cantidad': 2}])
d = api.req('GET', f'/orders/{ped}', A['token']).json()
S.caso('CMP-04', 'Pedido con precio fijado por el servidor, pago por la pasarela de prueba con aviso firmado y pedido en estado pagado', d.get('estado') == 'pagado' and d.get('total', 0) > 0, f"{ped} estado={d.get('estado')} total={d.get('total')}")
inv1 = {x['id']: x['stock'] for x in api.req('GET', '/admin/products', login_demo(api, 'admin@ejemplo.cl')).json()}
S.caso('CMP-05', 'Stock descontado en inventory por el pedido pagado', inv1['prod_007'] == inv0['prod_007'] - 2, f"{inv0['prod_007']} -> {inv1['prod_007']}")
mail = esperar(lambda: [m for m in bandeja(A['correo']) if 'boleta' in m['asunto'].lower() or 'B-' in m['cuerpo']])
S.caso('CMP-06', 'Boleta enviada por correo (proveedor de prueba) y disponible por S23', bool(mail) and api.req('GET', f'/orders/{ped}/receipt', A['token']).status_code == 200, f"{len(mail)} correo(s) con la boleta")
desp = login_demo(api, 'despachos@ejemplo.cl')
cola = esperar(lambda: [x for x in api.req('GET', '/admin/dispatch-orders', desp).json() if x['pedidoId'] == ped])
S.caso('CMP-07', 'La orden de despacho llega por la cola STOMP y el encargado la ve sin precios', bool(cola) and 'precio' not in json.dumps(cola[0]).lower(), f"{len(cola)} orden(es)")
ajeno = api.req('GET', f'/orders/{ped}', B['token']); inexist = api.req('GET', '/orders/ped_999999', B['token']); propio = api.req('GET', f'/orders/{ped}', A['token'])
S.caso('CMP-08', 'Consulta autorizada (cuenta dueña) 200; cuenta distinta 404 identico al de un pedido inexistente (regla C1 en orders-service)',
       propio.status_code == 200 and ajeno.status_code == 404 and inexist.status_code == 404 and ajeno.json()['error']['codigo'] == inexist.json()['error']['codigo'], f'dueña={propio.status_code}, otra cuenta={ajeno.status_code} {ajeno.json()["error"]["codigo"]}, inexistente={inexist.status_code}')
rid = f'cmp-gql-{random.randint(10**5, 10**6)}'
ok = api.req('POST', '/graphql', A['token'], json={'query': GQL_Q, 'variables': {'id': ped}}, headers={'X-Request-Id': rid}).json()
no = api.req('POST', '/graphql', B['token'], json={'query': GQL_Q, 'variables': {'id': ped}}).json()
arch = sorted({f for f, _ in lineas_log(rid)})
S.caso('CMP-09', 'GraphQL: resumenPedido combina orders e inventory para la dueña; otra cuenta recibe NO_ENCONTRADO; el requestId aparece en los registros de cada sistema',
       ok.get('data', {}).get('resumenPedido', {}).get('items', [{}])[0].get('producto', {}).get('id') == 'prod_007' and no['errors'][0]['extensions']['code'] == 'NO_ENCONTRADO' and len(arch) >= 4, f'archivos con el requestId: {arch}')
body = json.dumps({'eventoId': f'cmp-{random.randint(10**6, 10**7)}', 'pagoId': pago, 'estado': 'aprobado', 'monto': 1}).encode()
inval = estado('POST', base('gateway') + '/api/v1/payments/webhook', content=body, headers={'Content-Type': 'application/json', 'X-Timestamp': str(int(time.time())), 'X-Signature': 'sha256=' + '0' * 64})
S.caso('CMP-10', 'Aviso de pago con firma invalida (como lo haria un navegador alterado): 401', inval == 401, inval)
dueno = login_demo(api, 'dueno@ejemplo.cl')
hoy = time.strftime('%Y-%m-%d', time.gmtime())
rep = api.req('GET', f'/admin/reports/sales?desde={hoy}&hasta={hoy}', dueno); repc = api.req('GET', f'/admin/reports/sales?desde={hoy}&hasta={hoy}', A['token'])
S.caso('CMP-11', 'Reporte de ventas: 200 para el dueño y 403 para un cliente', rep.status_code == 200 and repc.status_code == 403, f'{rep.status_code}, {repc.status_code}')
secretos = [A['password'], B['password'], A['correo'], A['calle']]
filtrados = [v for v in secretos if logs_con(v)]
S.caso('CMP-12', 'Los registros compartidos no contienen contraseñas, correos ni direcciones de las pruebas', not filtrados, f'{len(secretos)} valores buscados en /logs; coincidencias={len(filtrados)}')
sys.exit(0 if S.cerrar() else 1)
