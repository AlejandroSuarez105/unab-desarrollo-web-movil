"""pasarela-prueba: adaptador de prueba de la plataforma de pago externa (I15, I16). No mueve dinero.
Crea cobros, muestra una pagina de pago de ejemplo y envia el aviso firmado (HMAC-SHA256) al gateway."""
import os, json, time, hmac, hashlib, secrets, html
import httpx
from fastapi import Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fornace.base import make_app, run, AppError, evento
from fornace.vault import SecretProvider, iguales

vault = SecretProvider()
COBROS = {}
S = {}

async def startup(app):
    S['http'] = httpx.AsyncClient(verify=os.environ.get('CA_FILE') or True, timeout=8.0)

app = make_app('pasarela-prueba', startup=startup)
log = app.state.log

async def clave(request: Request):
    if not iguales(request.headers.get('x-api-key'), vault.actual('payments/provider')):
        raise AppError(401, 'CREDENCIAL_INVALIDA', 'Clave inválida.')

async def enviar_aviso(cobro, estado, monto=None, evento_id=None, ts=None, firma_invalida=False):
    cuerpo = json.dumps({'eventoId': evento_id or 'evt_' + secrets.token_hex(6), 'pagoId': cobro['pagoId'], 'estado': estado,
                         'monto': cobro['monto'] if monto is None else monto}).encode()
    ts = str(ts or int(time.time()))
    sec = 'secreto-incorrecto' if firma_invalida else vault.actual('payments/webhook')
    sig = hmac.new(sec.encode(), ts.encode() + b'.' + cuerpo, hashlib.sha256).hexdigest()
    r = await S['http'].post(os.environ['URL_GATEWAY'].rstrip('/') + '/api/v1/payments/webhook', content=cuerpo,
                             headers={'Content-Type': 'application/json', 'X-Timestamp': ts, 'X-Signature': 'sha256=' + sig})
    return r

@app.post('/cobros', status_code=201, dependencies=[Depends(clave)])
async def crear(request: Request):
    d = await request.json()
    if not (isinstance(d.get('pagoId'), str) and isinstance(d.get('monto'), int) and d.get('medio') in ('servipag', 'deposito')):
        raise AppError(400, 'DATOS_INVALIDOS', 'Datos inválidos.')
    t = secrets.token_urlsafe(16)
    COBROS[t] = {'pagoId': d['pagoId'], 'monto': d['monto'], 'medio': d['medio'], 'retorno': d.get('retorno')}
    return {'urlPago': f'{os.environ["PASARELA_PUBLICA"]}/pagar/{t}', 'cobroId': t}

@app.get('/pagar/{t}', response_class=HTMLResponse)
async def pagina(t: str):
    c = COBROS.get(t)
    if not c: raise AppError(404, 'NO_ENCONTRADO', 'Cobro no encontrado.')
    e = html.escape
    return HTMLResponse(f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Pago de prueba</title></head><body style="font-family:sans-serif;max-width:480px;margin:3rem auto">
<h1>Plataforma de pago (prueba)</h1><p>Medio: {e(c["medio"])}<br>Monto: ${c["monto"]:,}</p><p>Esta página simula la plataforma externa. No se cobra dinero.</p>
<form method="post" action="/pagar/{e(t)}/resultado"><button name="estado" value="aprobado">Aprobar pago</button>
<button name="estado" value="rechazado">Rechazar pago</button></form></body></html>'''.replace(',', '.'))

@app.post('/pagar/{t}/resultado')
async def resultado(t: str, estado: str = Form(...)):
    c = COBROS.get(t)
    if not c or estado not in ('aprobado', 'rechazado'): raise AppError(400, 'DATOS_INVALIDOS', 'Solicitud inválida.')
    r = await enviar_aviso(c, estado)
    evento(log, 'pasarela-prueba', 'aviso_enviado', estado=estado, respuesta=r.status_code)
    destino = f'{os.environ["FRONTEND_URL"]}/pago-retorno.html?pedido={c.get("retorno") or ""}'
    return RedirectResponse(destino, status_code=303)

@app.post('/simular', dependencies=[Depends(clave)])
async def simular(request: Request):
    """Solo para pruebas: envia un aviso con los datos pedidos (monto distinto, evento repetido, firma o fecha incorrectas)."""
    d = await request.json()
    c = next((v for v in COBROS.values() if v['pagoId'] == d.get('pagoId')), None)
    if not c: raise AppError(404, 'NO_ENCONTRADO', 'Cobro no encontrado.')
    r = await enviar_aviso(c, d['estado'], d.get('monto'), d.get('eventoId'), d.get('timestamp'), bool(d.get('firmaInvalida')))
    return {'estado': r.status_code, 'cuerpo': r.json() if r.headers.get('content-type', '').startswith('application/json') else None}

if __name__ == '__main__':
    run(app)
