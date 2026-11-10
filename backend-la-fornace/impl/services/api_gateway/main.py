"""api-gateway: unico punto de entrada. Valida el token (I01), borra identidades enviadas por el navegador, aplica politicas por ruta,
limites, plazos y reenvia (I02). Las rutas salen de la tabla R01-R36 del Modulo 6 (routes.json)."""
import os, re, json, time, collections, pathlib
import httpx
from fastapi import Request
from fastapi.responses import Response
from fornace.base import make_app, run, AppError, evento, err_body
from fornace.vault import SecretProvider
from fornace.topology import ref_gateway, ref_par

vault = SecretProvider(ttl=int(os.environ.get('VAULT_TTL_SEGUNDOS', '300')), grace=int(os.environ.get('VAULT_GRACIA_SEGUNDOS', '900')))
ORIGEN = os.environ.get('FRONTEND_ORIGIN', '')
RL = {'RL-SENSIBLE': 10, 'RL-CATALOGO': 120, 'RL-WEBHOOK': 60, 'RL-USUARIO': 120}
FACTOR = float(os.environ.get('RL_FACTOR', '1'))
S = {}

def cargar_rutas():
    rutas = json.load(open(pathlib.Path(__import__('fornace').__file__).parent / 'routes.json', encoding='utf-8'))
    for r in rutas:
        nombres = re.findall(r'\{(\w+)\}', r['externa'])
        r['_re'] = re.compile('^' + re.sub(r'\\\{\w+\\\}', '([^/]+)', re.escape(r['externa'])) + '$')
        r['_nombres'] = nombres
    return rutas

async def startup(app):
    S['rutas'] = cargar_rutas()
    # se cargan todos los secretos que el gateway usa: si Vault cae despues, sigue con estos valores hasta que venza la ventana (M6 6.10)
    from fornace.topology import lecturas
    for ruta in lecturas()['api-gateway']:
        try: vault.get(ruta)
        except Exception: evento(app.state.log, 'api-gateway', 'secreto_no_precargado', ruta=ruta)
    S['http'] = httpx.AsyncClient(verify=os.environ.get('CA_FILE') or True, limits=httpx.Limits(max_connections=200, max_keepalive_connections=50))

app = make_app('api-gateway', startup=startup)
log = app.state.log
VENTANAS = collections.defaultdict(collections.deque)

def limitar(politica, ident):
    tope = int(RL[politica] * FACTOR)
    q = VENTANAS[(politica, ident)]
    ahora = time.time()
    while q and q[0] < ahora - 60:
        q.popleft()
    if len(q) >= tope:
        raise AppError(429, 'DEMASIADAS_SOLICITUDES', 'Demasiadas solicitudes. Intenta de nuevo en un minuto.', {'Retry-After': str(max(1, int(60 - (ahora - q[0]))))})
    q.append(ahora)

def cabeceras_seguras(resp, request, cors):
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['Cache-Control'] = 'no-store'
    resp.headers['Strict-Transport-Security'] = 'max-age=31536000'
    resp.headers['Referrer-Policy'] = 'no-referrer'
    resp.headers['X-Frame-Options'] = 'DENY'
    resp.headers['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'"      # el API solo devuelve datos: no se interpreta como pagina
    o = request.headers.get('origin')
    if cors and o and o == ORIGEN:
        resp.headers['Access-Control-Allow-Origin'] = ORIGEN
        resp.headers['Vary'] = 'Origin'
    return resp

def buscar(verbo, path):
    parcial = False
    for r in S['rutas']:
        m = r['_re'].match(path)
        if m:
            if r['verbo'] == verbo:
                return r, m.groups()
            parcial = True
    if parcial:
        raise AppError(405, 'METODO_NO_PERMITIDO', 'Método no permitido.')
    raise AppError(404, 'NO_ENCONTRADO', 'Recurso no encontrado.')

async def introspeccionar(token, rid):
    try:
        r = await S['http'].post(os.environ['URL_AUTH'].rstrip('/') + '/internal/introspect', json={'token': token}, timeout=3.0,
                                 headers={'X-Service-Id': 'api-gateway', 'X-Service-Secret': vault.actual(ref_par('api-gateway', 'auth-service')), 'X-Request-Id': rid})
    except httpx.HTTPError:
        evento(log, 'api-gateway', 'auth_no_disponible', requestId=rid)
        raise AppError(503, 'AUTENTICACION_NO_DISPONIBLE', 'No pudimos verificar tu sesión. Intenta de nuevo.')   # falla cerrado
    if r.status_code != 200:
        raise AppError(503, 'AUTENTICACION_NO_DISPONIBLE', 'No pudimos verificar tu sesión. Intenta de nuevo.')
    d = r.json()
    if not d.get('active'):
        raise AppError(401, 'TOKEN_INVALIDO', 'Tu sesión venció o no es válida. Inicia sesión de nuevo.')
    return d

@app.api_route('/api/v1/{resto:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'])
async def entrada(request: Request, resto: str):
    rid = request.state.rid
    path = '/api/v1/' + resto
    cors = True
    if request.method == 'OPTIONS':
        resp = Response(status_code=204)
        if request.headers.get('origin') == ORIGEN:
            resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,PATCH,DELETE'
            resp.headers['Access-Control-Allow-Headers'] = 'Authorization,Content-Type,Idempotency-Key'
            resp.headers['Access-Control-Max-Age'] = '600'
        return cabeceras_seguras(resp, request, True)
    try:
        r, params = buscar(request.method, path)
        cors = r['acceso'] != 'firma'
        ip = request.client.host if request.client else 'desconocida'
        if r['rl'] != 'RL-USUARIO':
            limitar(r['rl'], ip)
        tam = int(request.headers.get('content-length') or 0)
        if tam > r['body_kb'] * 1024:
            raise AppError(413, 'CUERPO_DEMASIADO_GRANDE', 'El cuerpo de la solicitud es demasiado grande.')
        cuerpo = await request.body()
        if len(cuerpo) > r['body_kb'] * 1024:
            raise AppError(413, 'CUERPO_DEMASIADO_GRANDE', 'El cuerpo de la solicitud es demasiado grande.')
        sistema = r['sistema']
        h = {'X-Request-Id': rid, 'X-Gateway-Secret': vault.actual(ref_gateway(sistema))}     # nada del navegador pasa como identidad
        if r['acceso'] == 'autenticada':
            auth = request.headers.get('authorization', '')
            if not auth.lower().startswith('bearer ') or len(auth) < 15:
                raise AppError(401, 'NO_AUTENTICADO', 'Debes iniciar sesión.')
            ident = await introspeccionar(auth[7:].strip(), rid)
            if not (set(r['roles']) & set(ident['roles'])):
                evento(log, 'api-gateway', 'acceso_denegado', requestId=rid, cuentaId=ident['cuentaId'], ruta=r['id'])
                raise AppError(403, 'SIN_PERMISO', 'No tienes permiso para esta acción.')
            limitar('RL-USUARIO', ident['cuentaId'])
            request.state.cuenta = ident['cuentaId']
            h.update({'X-Authenticated-User': ident['cuentaId'], 'X-Authenticated-Email': ident['correo'],
                      'X-Authenticated-Roles': ','.join(ident['roles']), 'X-Authenticated-Session': ident.get('sesionId', '')})
        for k in ('content-type', 'accept') + tuple(r['passthrough']):
            if k in request.headers:
                h[k] = request.headers[k]
        interna = r['interna']
        for n, v in zip(r['_nombres'], params):
            interna = interna.replace('{' + n + '}', v)
        url = os.environ['URL_' + sistema.upper()].rstrip('/') + interna
        try:
            up = await S['http'].request(request.method, url, params=request.query_params.multi_items(), content=cuerpo or None, headers=h, timeout=r['timeout'])
        except httpx.ConnectError:
            raise AppError(503, 'SERVICIO_NO_DISPONIBLE', 'Servicio no disponible. Intenta de nuevo en un momento.')
        except httpx.TimeoutException:
            raise AppError(502, 'SERVICIO_NO_RESPONDE', 'El servicio tardó demasiado en responder.')
        except httpx.HTTPError:
            raise AppError(502, 'SERVICIO_NO_RESPONDE', 'El servicio no respondió correctamente.')
        resp = Response(content=up.content, status_code=up.status_code, media_type=up.headers.get('content-type'))
        if 'retry-after' in up.headers:
            resp.headers['Retry-After'] = up.headers['retry-after']
        return cabeceras_seguras(resp, request, cors)
    except AppError as e:
        resp = Response(content=json.dumps(err_body(e.codigo, e.mensaje, rid), ensure_ascii=False), status_code=e.status, media_type='application/json', headers=e.headers)
        return cabeceras_seguras(resp, request, cors)

if __name__ == '__main__':
    run(app)
