"""Pruebas del API Gateway: limites de tasa, tamano de cuerpo, CORS, cabeceras de seguridad, TLS y health checks."""
import sys, time, ssl, socket, random
from h import *
from reg import Suite

S = Suite('gateway')
stack('restart', 'gateway', RL_FACTOR=1)
api = Api()
A = None
# El gateway recien reiniciado parte con contadores en cero. Para no gastar el limite de login se crea la sesion antes de medir.
r = api.req('POST', '/auth/login', json={'correo': 'admin@ejemplo.cl', 'password': cred()['admin@ejemplo.cl']}); tok = r.json()['access_token']

# RL-CATALOGO 120/min por IP
codes = [api.req('GET', '/products').status_code for _ in range(130)]
n429 = codes.count(429); primero = codes.index(429) + 1 if 429 in codes else None
S.caso('GW-RL-CATALOGO', 'Catalogo publico: 120 por minuto por IP; la peticion 121 recibe 429', codes[:120].count(200) >= 119 and n429 >= 5, f'200={codes.count(200)}, 429={n429}, primer 429 en la peticion {primero}')
rr = api.req('GET', '/products')
S.caso('GW-RL-RETRY', 'La respuesta 429 trae Retry-After y el formato de error con requestId', rr.status_code == 429 and 'retry-after' in rr.headers and set(rr.json()['error']) == {'codigo', 'mensaje', 'requestId'}, f'{rr.status_code} Retry-After={rr.headers.get("retry-after")} codigo={rr.json()["error"]["codigo"]}')
# RL-SENSIBLE 10/min por IP (login)
c = [api.req('POST', '/auth/login', json={'correo': f'inexistente{i}@ejemplo.cl', 'password': 'clave-incorrecta'}).status_code for i in range(13)]
S.caso('GW-RL-SENSIBLE', 'Rutas sensibles (login, registro): 10 por minuto por IP; desde la 11 hay 429', c[:9].count(401) >= 8 and c.count(429) >= 2, f'{c}')
# RL-WEBHOOK 60/min
w = [api.req('POST', '/payments/webhook', content=b'{}', headers={'Content-Type': 'application/json'}).status_code for _ in range(66)]
S.caso('GW-RL-WEBHOOK', 'Aviso de pago: 60 por minuto; los no firmados dan 401 y desde el 61 hay 429', w[:60].count(401) >= 59 and w.count(429) >= 3, f'401={w.count(401)}, 429={w.count(429)}')
# RL-USUARIO 120/min por cuenta (otra IP logica no existe: se mide con el token del administrador)
u = [api.req('GET', '/admin/users?limit=1', tok).status_code for _ in range(130)]
S.caso('GW-RL-USUARIO', 'Rutas autenticadas: 120 por minuto por cuenta; luego 429', u.count(200) >= 119 and u.count(429) >= 5, f'200={u.count(200)}, 429={u.count(429)}')

stack('restart', 'gateway', RL_FACTOR=50)
api = Api()
# tamano de cuerpo
r = api.req('POST', '/auth/login', content=b'{"correo":"' + b'a' * 70000 + b'"}', headers={'Content-Type': 'application/json'})
S.caso('GW-BODY', 'Cuerpo de mas de 64 KB en login: 413', r.status_code == 413, f'{r.status_code} {r.json().get("error", {}).get("codigo")}')
# ruta inexistente, metodo no permitido, JSON invalido
r1 = api.req('GET', '/ruta-que-no-existe'); r2 = api.req('DELETE', '/auth/login'); r3 = api.req('POST', '/auth/login', content=b'{no json', headers={'Content-Type': 'application/json'})
S.caso('GW-RUTAS', 'Ruta inexistente 404, metodo no permitido 404/405 y JSON invalido 400, todos con formato de error', r1.status_code == 404 and r2.status_code in (404, 405) and r3.status_code == 400 and all('requestId' in x.json().get('error', {}) for x in (r1, r2, r3)), f'{r1.status_code}, {r2.status_code}, {r3.status_code}')
# CORS
with cli() as c:
    ok = c.options(GW + '/products', headers={'Origin': 'http://127.0.0.1:8080', 'Access-Control-Request-Method': 'GET'})
    mal = c.options(GW + '/products', headers={'Origin': 'https://sitio-malo.example', 'Access-Control-Request-Method': 'GET'})
    mal2 = c.get(GW + '/products', headers={'Origin': 'https://sitio-malo.example'})
S.caso('GW-CORS', 'CORS: solo el origen del frontend; un origen ajeno no recibe Access-Control-Allow-Origin', ok.headers.get('access-control-allow-origin') == 'http://127.0.0.1:8080' and 'access-control-allow-origin' not in mal.headers and 'access-control-allow-origin' not in mal2.headers,
       f'frontend={ok.headers.get("access-control-allow-origin")}, ajeno={mal.headers.get("access-control-allow-origin")}/{mal2.headers.get("access-control-allow-origin")}')
# cabeceras de seguridad
h = api.req('GET', '/products').headers
req = ['x-content-type-options', 'cache-control', 'strict-transport-security', 'x-frame-options', 'referrer-policy', 'content-security-policy']
S.caso('GW-CABECERAS', 'Cabeceras de seguridad en las respuestas del API (incluida Content-Security-Policy)', all(k in h for k in req) and "frame-ancestors 'none'" in h['content-security-policy'], {k: h.get(k) for k in req})
# el servidor del frontend envia una politica que limita a donde puede hablar una pagina (un script inyectado no puede enviar el token fuera)
with httpx.Client(timeout=10) as _c:
    _f = _c.get(os.environ.get('URL_FRONTEND', 'http://127.0.0.1:8080').rstrip('/') + '/index.html')
_csp = _f.headers.get('content-security-policy', '')
S.caso('GW-CSP', 'El frontend envia Content-Security-Policy: conexiones solo al API Gateway, sin plugins, sin base ajena, sin ser incrustado y formularios solo al propio sitio',
       _f.status_code == 200 and "connect-src 'self' https://127.0.0.1:8443" in _csp and "object-src 'none'" in _csp and "base-uri 'self'" in _csp and "frame-ancestors 'none'" in _csp and "form-action 'self'" in _csp
       and _f.headers.get('x-content-type-options') == 'nosniff', _csp)
# TLS: HTTP plano rechazado, certificado verificado con la CA
try:
    with socket.create_connection(('127.0.0.1', 8443), timeout=3) as s:
        s.sendall(b'GET /api/v1/products HTTP/1.1\r\nHost: x\r\n\r\n'); data = s.recv(200)
    plano = data[:12]
except Exception as e: plano = type(e).__name__
ctx = ssl.create_default_context(cafile=str(RUN / 'certs/ca.crt'))
with socket.create_connection(('127.0.0.1', 8443)) as s, ctx.wrap_socket(s, server_hostname='localhost') as ss: ver = ss.version()
S.caso('GW-TLS', 'El gateway solo atiende por TLS 1.2+ y el certificado se verifica con la CA del proyecto', not str(plano).startswith(("b'HTTP", 'HTTP')) and ver in ('TLSv1.2', 'TLSv1.3'), f'HTTP plano -> {plano!r}; version={ver}')
# health checks
comp = {'auth': 9101, 'clients': 9102, 'inventory': 9103, 'orders': 9104, 'payments': 9105, 'dispatch': 9106, 'notifications': 9107, 'graphql': 9108, 'pasarela': 9201, 'correo': 9202, 'gateway': 8443}
res = {}
with cli() as c:
    for k, p in comp.items():
        try: x = c.get(f'https://127.0.0.1:{p}/health'); res[k] = x.status_code
        except Exception as e: res[k] = type(e).__name__
S.caso('GW-HEALTH', 'Las 11 piezas responden /health 200 por TLS', all(v == 200 for v in res.values()), res)
# formato de registro
ln = lineas_log('req_')
S.caso('GW-LOG', 'Los registros son JSON de una linea con requestId y sin cuerpos ni cabeceras', all(l.startswith('{') for f, l in ln[:200]) and not any('authorization' in l.lower() or 'bearer' in l.lower() for f, l in ln), f'{len(ln)} lineas revisadas')
sys.exit(0 if S.cerrar() else 1)
