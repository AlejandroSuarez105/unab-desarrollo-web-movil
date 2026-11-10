"""notifications-service: correos del sistema (I06, I13) y mensajes de contacto (S35)."""
import os, httpx
from fastapi import Depends, Request
from pymongo.errors import DuplicateKeyError
from fornace.base import make_app, run, AppError, evento
from fornace.vault import SecretProvider
from fornace.guard import Guard, Ctx
from fornace.db import conectar, siguiente, ahora
from fornace.retencion import corte, INTERVALO
from fornace.util import EMAIL_RE, FONO_RE

SISTEMA = 'notifications'
vault = SecretProvider()
guard = Guard(SISTEMA, vault)
S = {}

async def startup(app):
    S['cli'], S['db'] = await conectar(SISTEMA, vault)
    S['http'] = httpx.AsyncClient(verify=os.environ.get('CA_FILE') or True, timeout=5.0)
    await S['db'].mensajes.create_index('id', unique=True)

async def retencion():
    """7.9: los mensajes de contacto se eliminan a los 12 meses."""
    r = await S['db'].mensajes.delete_many({'creadoEn': {'$lt': corte('contacto')}})
    if r.deleted_count:
        evento(log, 'notifications-service', 'retencion', mensajes=r.deleted_count)

app = make_app('notifications-service', startup=startup, tareas=[('retencion', INTERVALO, retencion)])
log = app.state.log
PROV = lambda: os.environ['URL_CORREO'].rstrip('/')

def cab():
    return {'X-API-Key': vault.actual('notifications/mail')}

async def proveedor(ruta, datos):
    try:
        return await S['http'].post(PROV() + ruta, json=datos, headers=cab())
    except httpx.HTTPError:
        raise AppError(503, 'PROVEEDOR_NO_DISPONIBLE', 'El proveedor de correo no responde.')

def plantilla(d):
    if d['plantilla'] == 'verificacion':
        return 'Confirma tu correo - Pizzería La Fornace', f"Hola. Para activar tu cuenta abre este enlace (vence en 24 horas):\n{d['enlace']}\n"
    lineas = '\n'.join(f"- {i['nombre']} x{i['cantidad']}  ${i['precioUnitario']}" for i in d['items'])
    return f"Boleta {d['numeroBoleta']} - Pizzería La Fornace", f"Gracias por tu compra.\n{lineas}\nTotal: ${d['total']} (IVA incluido)\nBoleta: {d['numeroBoleta']}\n"

@app.post('/internal/emails')
async def emails(request: Request, ctx: Ctx = Depends(guard.dep(gateway=False, pares=('auth-service', 'payments-service')))):
    try:
        d = await request.json()
    except Exception:
        d = None
    if not isinstance(d, dict) or not isinstance(d.get('correo'), str) or not EMAIL_RE.match(d['correo']) or d.get('plantilla') not in ('verificacion', 'boleta'):
        raise AppError(400, 'DATOS_INVALIDOS', 'Datos inválidos.')
    # cada llamador solo puede usar su plantilla
    if (ctx.servicio, d['plantilla']) not in (('auth-service', 'verificacion'), ('payments-service', 'boleta')):
        raise AppError(403, 'LLAMADOR_NO_PERMITIDO', 'Operación no permitida.')
    if d['plantilla'] == 'verificacion' and not (isinstance(d.get('enlace'), str) and d['enlace'].startswith('http')):
        raise AppError(400, 'DATOS_INVALIDOS', 'Datos inválidos en: enlace')
    if d['plantilla'] == 'boleta' and not (d.get('numeroBoleta') and isinstance(d.get('total'), int) and isinstance(d.get('items'), list)):
        raise AppError(400, 'DATOS_INVALIDOS', 'Datos inválidos en: boleta')
    v = await proveedor('/validar', {'correo': d['correo']})
    if v.status_code != 200:
        raise AppError(503, 'PROVEEDOR_NO_DISPONIBLE', 'El proveedor de correo no responde.')
    if not v.json().get('existe'):
        raise AppError(422, 'CORREO_NO_VALIDO', 'No pudimos comprobar que ese correo exista.')
    asunto, cuerpo = plantilla(d)
    r = await proveedor('/enviar', {'para': d['correo'].lower(), 'asunto': asunto, 'cuerpo': cuerpo})
    if r.status_code != 200:
        raise AppError(503, 'PROVEEDOR_NO_DISPONIBLE', 'El proveedor de correo no responde.')
    evento(log, 'notifications-service', 'correo_enviado', requestId=ctx.rid, plantilla=d['plantilla'], origen=ctx.servicio)
    return {'enviado': True}

MOTIVOS = ('consulta_pedido', 'reserva_evento', 'alianza_comercial', 'otro')

@app.post('/contact-messages', status_code=201)
async def contacto(request: Request, ctx: Ctx = Depends(guard.dep(publica=True))):
    try:
        d = await request.json()
    except Exception:
        d = None
    malos = []
    if not isinstance(d, dict):
        raise AppError(400, 'DATOS_INVALIDOS', 'El cuerpo debe ser un objeto JSON.')
    def s(k, a, b): 
        v = d.get(k)
        if not isinstance(v, str) or not (a <= len(v.strip()) <= b): malos.append(k)
    s('nombre', 2, 100); s('mensaje', 10, 1000)
    if not isinstance(d.get('correo'), str) or not EMAIL_RE.match(d['correo'].strip()): malos.append('correo')
    if not isinstance(d.get('telefono'), str) or not FONO_RE.match(d['telefono']): malos.append('telefono')
    if d.get('motivo') not in MOTIVOS: malos.append('motivo')
    if malos:
        raise AppError(400, 'DATOS_INVALIDOS', 'Datos inválidos en: ' + ', '.join(malos))
    mid = await siguiente(S['db'], 'msg', 'msg_')
    await S['db'].mensajes.insert_one({'id': mid, 'nombre': d['nombre'].strip(), 'correo': d['correo'].strip().lower(), 'telefono': d['telefono'],
                                       'motivo': d['motivo'], 'mensaje': d['mensaje'].strip(), 'creadoEn': ahora()})
    evento(log, 'notifications-service', 'contacto_recibido', requestId=ctx.rid, id=mid)
    return {'id': mid, 'recibido': True}

if __name__ == '__main__':
    run(app)
