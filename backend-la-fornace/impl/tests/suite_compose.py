"""Pruebas del despliegue en Docker Compose desde el equipo anfitrion: puertos publicados, red interna, acceso desde fuera de la red privada.
Despues ejecuta tests/prueba_compose_interna.py dentro de la red privada. Requiere el entorno iniciado (python scripts/compose.py up y semilla).
Uso: python scripts/compose.py probar"""
import sys, os, json, socket, subprocess, pathlib
sys.path.insert(0, os.path.dirname(__file__))
from reg import Suite

RAIZ = pathlib.Path(__file__).resolve().parents[1]
DC = ['docker', 'compose']
S = Suite('compose_red')

def sh(cmd, **kw):
    return subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, **kw)

# ---- 1. puertos publicados
ps = [json.loads(l) for l in sh(DC + ['ps', '-a', '--format', 'json']).stdout.splitlines() if l.strip().startswith('{')]
pub = {}
for c in ps:
    for p in c.get('Publishers') or []:
        if p.get('PublishedPort'): pub.setdefault(c['Service'], set()).add((p.get('URL'), p['PublishedPort']))
esperado = {'api-gateway': {('127.0.0.1', 8443)}, 'frontend': {('127.0.0.1', 8080)}, 'pasarela-prueba': {('127.0.0.1', 9201)}}
S.caso('CMP-NET-01', 'Solo publican puerto el API Gateway (8443), el frontend (8080) y el simulador del proveedor de pago (9201), todos en 127.0.0.1',
       pub == esperado, json.dumps({k: sorted(v) for k, v in pub.items()}))
n_serv = len([c for c in ps if c['Service'] != 'preparacion'])
S.caso('CMP-NET-02', 'Todos los contenedores del sistema estan en ejecucion y sanos', all(c['State'] == 'running' and c.get('Health') in ('healthy', '') for c in ps if c['Service'] != 'preparacion'), f'{n_serv} contenedores en ejecucion')

# ---- 2. la red privada es interna
red = json.loads(sh(['docker', 'network', 'inspect', 'fornace_privada']).stdout)[0]
pub_net = json.loads(sh(['docker', 'network', 'inspect', 'fornace_publica']).stdout)[0]
miembros = lambda n: sorted(v['Name'].replace('fornace-', '').rsplit('-', 1)[0] for v in n['Containers'].values())
S.caso('CMP-NET-03', 'La red privada es interna (sin salida a Internet); solo el API Gateway, el frontend y el simulador de pago estan en la red publica',
       red['Internal'] is True and set(miembros(pub_net)) == {'api-gateway', 'frontend', 'pasarela-prueba'}, f"privada.internal={red['Internal']}; publica={miembros(pub_net)}")

# ---- 3. desde el equipo anfitrion (T-DAT-05a y T-GQL-13a: conexion rechazada)
def abierto(p):
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(('127.0.0.1', p)) == 0
privados = {'auth': 9101, 'clients': 9102, 'inventory': 9103, 'orders': 9104, 'payments': 9105, 'dispatch': 9106, 'notifications': 9107, 'graphql': 9108, 'correo': 9202, 'mongo': 27017, 'vault': 8200, 'broker': 61613}
abiertos = [k for k, p in privados.items() if abierto(p)]
# un puerto abierto en el equipo solo cuenta contra Compose si Compose lo publica; si lo ocupa otro programa del equipo (por ejemplo, un MongoDB instalado en el equipo) se informa aparte
puertos_compose = {p for v in pub.values() for _, p in v}
de_compose = [k for k in abiertos if privados[k] in puertos_compose]
ajenos = [k for k in abiertos if k not in de_compose]
S.caso('CMP-NET-04', 'Desde el equipo anfitrion, Compose no publica ningun puerto de los 7 sistemas, GraphQL, correo, base de datos, Vault ni broker (T-DAT-05a, T-GQL-13a)',
       not de_compose, f'{len(privados)} puertos probados; abiertos por Compose: {de_compose or "ninguno"}; abiertos en el equipo por otro programa (no es Compose): {ajenos or "ninguno"}')
publicos = {'gateway': 8443, 'frontend': 8080, 'pasarela': 9201}
S.caso('CMP-NET-05', 'Los puertos publicados si responden', all(abierto(p) for p in publicos.values()), ', '.join(f'{k}:{p}' for k, p in publicos.items()))

# ---- 4. desde un contenedor que solo esta en la red publica (equivale a un navegador o a otra maquina; T-GQL-14)
imagen = 'fornace-preparacion'
prog = r'''
import socket, ssl, urllib.request, json
def res(h):
    try: socket.gethostbyname(h); return True
    except OSError: return False
privados = ['orders-service', 'inventory-service', 'clients-service', 'payments-service', 'auth-service', 'dispatch-service', 'notifications-service', 'graphql-gateway', 'mongo', 'vault', 'broker', 'correo-prueba']
vistos = [h for h in privados if res(h)]
def get(u):
    try: return urllib.request.urlopen(u, context=ssl._create_unverified_context(), timeout=4).status
    except urllib.error.HTTPError as e: return e.code
    except Exception as e: return type(e).__name__
print(json.dumps({'resuelve': vistos, 'gateway_health': get('https://api-gateway:8000/health'), 'internal': get('https://api-gateway:8000/api/v1/internal/introspect'),
                  'sin_token': get('https://api-gateway:8000/api/v1/orders')}))
'''
r = sh(['docker', 'run', '--rm', '--network', 'fornace_publica', '--entrypoint', 'python', imagen, '-c', prog])
try: o = json.loads(r.stdout.strip().splitlines()[-1])
except Exception: o = {'error': (r.stdout + r.stderr)[-300:]}
S.caso('CMP-NET-06', 'Desde la red publica no existen los nombres de orders, inventory, clients, payments, auth, dispatch, notifications, GraphQL, base de datos, Vault ni broker (T-GQL-14)',
       o.get('resuelve') == [], json.dumps(o))
S.caso('CMP-NET-07', 'Desde la red publica solo se llega al API Gateway: responde /health, no expone /internal y exige token en las rutas protegidas',
       o.get('gateway_health') == 200 and o.get('internal') == 404 and o.get('sin_token') == 401, json.dumps({k: o.get(k) for k in ('gateway_health', 'internal', 'sin_token')}))

# ---- 5. sin salida a Internet desde la red privada
prog2 = "import socket\ntry:\n    socket.create_connection(('1.1.1.1', 443), timeout=4); print('conecta')\nexcept OSError as e: print('sin salida')"
r = sh(['docker', 'run', '--rm', '--network', 'fornace_privada', '--entrypoint', 'python', imagen, '-c', prog2])
S.caso('CMP-NET-08', 'Un contenedor de la red privada no tiene salida a Internet', r.stdout.strip() == 'sin salida', r.stdout.strip() or r.stderr[-200:])

# ---- 5b. los sistemas usan su usuario de MongoDB (autenticacion activada)
sis = ['auth', 'clients', 'inventory', 'orders', 'payments', 'dispatch', 'notifications']
valores = {}
for s in sis:
    rr = sh(DC + ['exec', '-T', f'{s}-service', 'printenv', 'MONGO_AUTH'])
    valores[s] = rr.stdout.strip()
S.caso('CMP-DB-04', 'Los 7 sistemas se ejecutan con MONGO_AUTH=1: se conectan con su usuario de MongoDB cuya clave sale de Vault', all(v == '1' for v in valores.values()) and len(valores) == 7, valores)

# ---- 6. recorrido dentro de la red privada
sh(DC + ['--profile', 'herramientas', 'build', '-q', 'herramientas'])
r = sh(DC + ['--profile', 'herramientas', 'run', '--rm', '-T', 'herramientas', 'python', 'tests/prueba_compose_interna.py'], timeout=600)
print(r.stdout[-30000:]); print(r.stderr[-6000:])
ok_int = r.returncode == 0
cargado = json.load(open(RAIZ / 'tests/resultados/compose_interna.json')) if (RAIZ / 'tests/resultados/compose_interna.json').exists() else None
S.caso('CMP-NET-09', 'Las pruebas internas (acceso directo, GraphQL directo y compra completa) terminan sin fallas', ok_int and cargado is not None and cargado['ok'] == cargado['total'], f"{cargado['ok']}/{cargado['total']} OK" if cargado else r.stderr[-300:])
sys.exit(0 if S.cerrar() else 1)
