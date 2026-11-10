"""Errores controlados, registros sin secretos, identificador de correlacion y fabrica de aplicaciones."""
import json, os, re, sys, time, uuid, logging, asyncio
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

class AppError(Exception):
    def __init__(self, status, codigo, mensaje, headers=None):
        self.status, self.codigo, self.mensaje, self.headers = status, codigo, mensaje, headers or {}
        self.extra = None

def err_body(codigo, mensaje, rid=None):
    return {'error': {'codigo': codigo, 'mensaje': mensaje, 'requestId': rid}}

def setup_logger(name):
    lg = logging.getLogger(name)
    if lg.handlers:
        return lg
    lg.setLevel(logging.INFO)
    lg.propagate = False
    fmt = logging.Formatter('%(message)s')
    sh = logging.StreamHandler(sys.stdout); sh.setFormatter(fmt); lg.addHandler(sh)
    d = os.environ.get('LOG_DIR')
    if d:
        os.makedirs(d, exist_ok=True)
        fh = logging.FileHandler(os.path.join(d, f'{name}.log')); fh.setFormatter(fmt); lg.addHandler(fh)
    return lg

def evento(lg, servicio, tipo, /, **campos):
    """Registro de un evento. Solo se aceptan campos simples; nunca cuerpos, cabeceras ni datos personales."""
    r = {'ts': time.strftime('%Y-%m-%dT%H:%M:%S'), 'servicio': servicio, 'evento': tipo}
    r.update({k: v for k, v in campos.items() if isinstance(v, (str, int, float, bool, type(None)))})
    lg.info(json.dumps(r, ensure_ascii=False))

def make_app(name, startup=None, shutdown=None, tareas=()):
    """tareas: lista de (nombre, segundos, funcion_async)."""
    lg = setup_logger(name)
    bg = []

    async def runner(nombre, seg, fn):
        while True:
            await asyncio.sleep(seg)
            try:
                await fn()
            except Exception as e:  # una tarea nunca tumba el sistema
                evento(lg, name, 'tarea_error', tarea=nombre, tipo=type(e).__name__)

    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def lifespan(app):
        if startup:
            await startup(app)
        for n, s, fn in tareas:
            bg.append(asyncio.create_task(runner(n, s, fn)))
        yield
        for t in bg:
            t.cancel()
        if shutdown:
            await shutdown(app)

    app = FastAPI(title=name, docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.log = lg
    app.state.name = name

    @app.middleware('http')
    async def acceso(request: Request, call_next):
        t0 = time.time()
        rid = request.headers.get('x-request-id') or ''
        request.state.rid = rid if re.fullmatch(r'[A-Za-z0-9_\-]{8,64}', rid) else 'req_' + uuid.uuid4().hex[:12]
        request.state.cuenta = None
        try:
            resp = await call_next(request)
        except Exception as e:
            evento(lg, name, 'error_no_controlado', tipo=type(e).__name__, requestId=request.state.rid)
            if type(e).__name__ == 'SecretUnavailable':      # Vault no responde y no hay un valor vigente en memoria: falla controlada, no un error interno
                resp = JSONResponse(err_body('SERVICIO_NO_DISPONIBLE', 'Servicio no disponible. Intenta de nuevo en un momento.', request.state.rid), status_code=503)
            else:
                resp = JSONResponse(err_body('ERROR_INTERNO', 'Error interno.', request.state.rid), status_code=500)
        resp.headers['X-Request-Id'] = request.state.rid
        if request.url.path != '/health':
            evento(lg, name, 'acceso', requestId=request.state.rid, verbo=request.method, ruta=request.url.path,
                   estado=resp.status_code, ms=round((time.time() - t0) * 1000), cuentaId=request.state.cuenta)
        return resp

    @app.exception_handler(AppError)
    async def h_app(request, e):
        b = err_body(e.codigo, e.mensaje, request.state.rid)
        if e.extra:
            b['error'].update(e.extra)
        return JSONResponse(b, status_code=e.status, headers=e.headers)

    @app.exception_handler(RequestValidationError)
    async def h_val(request, e):
        campos = sorted({'.'.join(str(x) for x in er['loc'][1:]) for er in e.errors()})
        return JSONResponse(err_body('DATOS_INVALIDOS', 'Datos inválidos en: ' + ', '.join(campos), request.state.rid), status_code=400)

    @app.exception_handler(StarletteHTTPException)
    async def h_http(request, e):
        cod = {404: 'NO_ENCONTRADO', 405: 'METODO_NO_PERMITIDO'}.get(e.status_code, 'ERROR')
        return JSONResponse(err_body(cod, 'Recurso no disponible.', request.state.rid), status_code=e.status_code)

    @app.get('/health')
    async def health():
        return {'ok': True}

    return app

def run(app):
    import uvicorn
    kw = dict(host=os.environ.get('HOST', '127.0.0.1'), port=int(os.environ['PORT']), log_level='warning', access_log=False, server_header=False)
    if os.environ.get('TLS_CERT'):
        kw.update(ssl_certfile=os.environ['TLS_CERT'], ssl_keyfile=os.environ['TLS_KEY'])
    uvicorn.run(app, **kw)
