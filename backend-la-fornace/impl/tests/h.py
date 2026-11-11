"""Ayudas de prueba. Lee secretos de Vault con el token de administracion local (solo entorno de pruebas)."""
import os, json, pathlib, time, hmac, hashlib
import httpx

RUN = pathlib.Path(os.environ.get('RUN_DIR', pathlib.Path(__file__).resolve().parents[1] / '.run'))
# En modo nativo todo esta en 127.0.0.1. Dentro de la red de Docker Compose las mismas variables apuntan a los nombres de los contenedores.
CA = os.environ.get('CA_FILE') or str(RUN / 'certs/ca.crt')
VAULT = os.environ.get('VAULT_ADDR', 'http://127.0.0.1:8200')
ROOT = open(os.environ.get('VAULT_ROOT_TOKEN_FILE') or RUN / 'vault-root.token').read().strip()
LOGS = pathlib.Path(os.environ.get('LOG_DIR') or RUN / 'logs')
PUERTOS = {'auth': 9101, 'clients': 9102, 'inventory': 9103, 'orders': 9104, 'payments': 9105, 'dispatch': 9106,
           'notifications': 9107, 'graphql': 9108, 'pasarela': 9201, 'correo': 9202, 'gateway': 8443}

def secreto(path):
    r = httpx.get(f'{VAULT}/v1/secret/data/{path}', headers={'X-Vault-Token': ROOT})
    return r.json()['data']['data']

def cred():
    return json.load(open(RUN / 'credenciales-demo.json'))

def cli(**kw):
    return httpx.Client(verify=CA, timeout=15, **kw)

def base(n):
    return os.environ.get('URL_' + n.upper(), f'https://127.0.0.1:{PUERTOS[n]}').rstrip('/')

def directo(sistema, metodo, ruta, usuario=None, email=None, roles=None, **kw):
    """Llama a un sistema como si fuera el gateway (para probar al sistema solo)."""
    h = {'X-Gateway-Secret': secreto(f'services/gateway-to-{sistema}')['actual']}
    if usuario: h['X-Authenticated-User'] = usuario
    if email: h['X-Authenticated-Email'] = email
    if roles: h['X-Authenticated-Roles'] = ','.join(roles)
    h.update(kw.pop('headers', {}))
    with cli() as c:
        return c.request(metodo, base(sistema) + ruta, headers=h, **kw)

def par(llamador, destino, metodo, ruta, **kw):
    ref = {('api-gateway', 'auth-service'): 'gateway-introspect'}
    from fornace.topology import PARES
    r = secreto('services/' + PARES[(llamador, destino)])['actual']
    h = {'X-Service-Id': llamador, 'X-Service-Secret': r}
    h.update(kw.pop('headers', {}))
    with cli() as c:
        return c.request(metodo, base(destino.split('-')[0]) + ruta, headers=h, **kw)

def firmar(cuerpo: bytes, ts=None, secreto_hmac=None):
    ts = str(ts or int(time.time()))
    s = secreto_hmac or secreto('payments/webhook')['actual']
    sig = hmac.new(s.encode(), ts.encode() + b'.' + cuerpo, hashlib.sha256).hexdigest()
    return {'X-Timestamp': ts, 'X-Signature': 'sha256=' + sig, 'Content-Type': 'application/json'}

# ---------------- ayudas de alto nivel ----------------
import re, random, glob, subprocess, sys
BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
GW = base('gateway') + '/api/v1'

def run_valido(cuerpo):
    suma, m = 0, 2
    for d in reversed(str(cuerpo)):
        suma += int(d) * m; m = 2 if m == 7 else m + 1
    r = 11 - suma % 11
    return f"{cuerpo}-{'0' if r == 11 else 'K' if r == 10 else r}"

class Api:
    """Cliente del API Gateway. Cada llamada devuelve httpx.Response."""
    def __init__(self):
        self.c = cli()
    def req(self, metodo, ruta, token=None, **kw):
        h = kw.pop('headers', {})
        if token: h['Authorization'] = 'Bearer ' + token
        return self.c.request(metodo, GW + ruta, headers=h, **kw)
    def login(self, correo, password):
        r = self.req('POST', '/auth/login', json={'correo': correo, 'password': password})
        return r.json()['access_token'] if r.status_code == 200 else None

def bandeja(para):
    with cli() as c:
        return c.get(base('correo') + '/bandeja', params={'para': para}, headers={'X-API-Key': secreto('notifications/mail')['actual']}).json()

def enlace_token(para, indice=-1):
    return re.search(r'token=(\S+)', bandeja(para)[indice]['cuerpo']).group(1)

def nuevo_cliente(api, prefijo='cli', comuna='Maipú'):
    """Registra (S03), confirma (S04) e inicia sesion (S01). Devuelve un diccionario con los datos ficticios usados."""
    n = random.randint(100000, 999999)
    d = {'correo': f'{prefijo}{n}@ejemplo.cl', 'password': f'Clave{n}Prueba', 'run': run_valido(random.randint(10000000, 24999999)),
         'nombre': f'Cliente {prefijo} {n}', 'telefono': f'+5691{random.randint(1000000, 9999999)}', 'calle': f'Calle Ficticia {n}', 'comuna': comuna}
    r = api.req('POST', '/auth/register', json={'run': d['run'], 'nombreCompleto': d['nombre'], 'correo': d['correo'], 'password': d['password'], 'telefono': d['telefono'],
        'fechaNacimiento': '1990-05-20', 'sexo': 'F', 'direccion': {'calle': d['calle'], 'comuna': comuna, 'provincia': 'Santiago', 'region': 'Metropolitana'}})
    assert r.status_code == 201, r.text
    d['clienteId'] = r.json()['id']
    d['token_verificacion'] = enlace_token(d['correo'])
    assert api.req('POST', '/auth/verify-email', json={'token': d['token_verificacion']}).status_code == 200
    d['token'] = api.login(d['correo'], d['password'])
    assert d['token']
    return d

def login_demo(api, usuario):
    return api.login(usuario, cred()[usuario])

def pedido_pagado(api, tok, items=None, medio='servipag'):
    """Crea un pedido y lo paga mediante el aviso firmado de la pasarela de prueba. Devuelve (pedidoId, pagoId)."""
    items = items or [{'productoId': 'prod_002', 'cantidad': 1}]
    r = api.req('POST', '/orders', tok, json={'items': items}); assert r.status_code == 201, r.text
    ped = r.json()['id']
    r = api.req('POST', f'/orders/{ped}/payments', tok, json={'medio': medio}); assert r.status_code == 201, r.text
    pago = r.json()['pagoId']
    simular(pago, 'aprobado')
    esperar(lambda: api.req('GET', f'/orders/{ped}', tok).json().get('estado') == 'pagado')
    return ped, pago

def simular(pago, estado, **extra):
    with cli() as c:
        return c.post(base('pasarela') + '/simular', headers={'X-API-Key': secreto('payments/provider')['actual']}, json=dict(pagoId=pago, estado=estado, **extra)).json()

def esperar(fn, seg=20, paso=0.5):
    t0 = time.time()
    while time.time() - t0 < seg:
        v = fn()
        if v: return v
        time.sleep(paso)
    return fn()

def stack(*args, **env):
    e = dict(os.environ, RUN_DIR=str(RUN), **{k: str(v) for k, v in env.items()})
    return subprocess.run([sys.executable, str(BASE_DIR / 'scripts/stack.py'), *args], env=e, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)

def logs_con(valor):
    """Archivos de registro (y salida estandar) que contienen el valor."""
    hallados = []
    for f in glob.glob(str(LOGS / '*')):
        try:
            if valor in open(f, errors='ignore').read(): hallados.append(os.path.basename(f))
        except Exception: pass
    return hallados

def lineas_log(requestId):
    out = []
    for f in glob.glob(str(LOGS / '*.log')):
        for l in open(f, errors='ignore'):
            if requestId in l: out.append((os.path.basename(f), l.strip()))
    return out

def mongo():
    import pymongo
    return pymongo.MongoClient(os.environ.get('MONGO_URL', 'mongodb://127.0.0.1:27017'))
