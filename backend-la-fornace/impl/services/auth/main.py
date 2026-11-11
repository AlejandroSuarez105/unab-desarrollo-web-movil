"""auth-service: cuentas, contrasenas con hash, sesiones y tokens, verificacion de correo y personal (S01 S02 S04 S05 S30-S33, I01 I03-I05)."""
import os, re, hashlib, secrets, time
import bcrypt
from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse
from pymongo.errors import DuplicateKeyError
from fornace.base import make_app, run, AppError, evento
from fornace.vault import SecretProvider
from fornace.guard import Guard, Ctx
from fornace.svc import Servicios
from fornace.db import conectar, siguiente, ahora, en_segundos
from fornace.retencion import corte, INTERVALO
from fornace.util import EMAIL_RE, paginar
from fornace.topology import ROLES_TODOS

SISTEMA = 'auth'
ROLES_PERSONAL = ['administrador', 'dueno', 'cajero_virtual', 'encargado_despachos']
TOKEN_SEG = int(os.environ.get('TOKEN_SECONDS', '900'))
VERIF_SEG = 24 * 3600
MAX_FALLOS, VENTANA = 5, 900
FRONT = os.environ.get('FRONTEND_URL', 'https://localhost:8443')

vault = SecretProvider()
guard = Guard(SISTEMA, vault)
S = {}

async def startup(app):
    S['cli'], S['db'] = await conectar(SISTEMA, vault)
    S['svc'] = Servicios('auth-service', vault, app.state.log)
    db = S['db']
    await db.cuentas.create_index('id', unique=True)
    await db.cuentas.create_index('correo', unique=True)
    await db.sesiones.create_index('hash', unique=True)
    await db.tokens.create_index('hash', unique=True)
    await db.intentos.create_index('correo')

async def purga():
    """Retencion: borra sesiones, tokens e intentos vencidos (reemplaza al indice TTL)."""
    db = S['db']
    await db.sesiones.delete_many({'expiraEn': {'$lt': en_segundos(-3600)}})
    await db.tokens.delete_many({'expiraEn': {'$lt': en_segundos(-86400)}})
    await db.intentos.delete_many({'ts': {'$lt': time.time() - VENTANA}})

async def retencion():
    """7.9: 24 meses despues de la baja de un cliente se anonimiza su cuenta: el correo pasa a un valor unico sin significado,
    se borra el nombre y se elimina el hash de la contrasena."""
    db, n = S['db'], 0
    async for c in db.cuentas.find({'rol': 'cliente', 'estado': 'inactivo', 'anonimizada': {'$ne': True}, 'bajaEn': {'$lt': corte('cliente_baja')}}).limit(200):
        await db.cuentas.update_one({'id': c['id']}, {'$set': {'correo': f'eliminado-{c["id"]}@anonimo.invalid', 'nombre': '[eliminado]', 'hash': None, 'anonimizada': True}})
        await db.sesiones.delete_many({'cuentaId': c['id']})
        await db.tokens.delete_many({'cuentaId': c['id']})
        n += 1
    if n:
        evento(log, 'auth-service', 'retencion', cuentasAnonimizadas=n)

app = make_app('auth-service', startup=startup, tareas=[('purga', 300, purga), ('retencion', INTERVALO, retencion)])
log = app.state.log

def sha(x): return hashlib.sha256(x.encode()).hexdigest()
def hash_pw(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt(rounds=int(os.environ.get('BCRYPT_ROUNDS', '12')))).decode()
def check_pw(p, h): return bcrypt.checkpw(p.encode(), h.encode())
DUMMY = bcrypt.hashpw(b'relleno', bcrypt.gensalt(rounds=int(os.environ.get('BCRYPT_ROUNDS', '12')))).decode()

def vistaUsuario(c):
    return {'id': c['id'], 'nombreCompleto': c.get('nombre'), 'correo': c['correo'], 'rol': c['rol'], 'estado': c['estado']}

async def body(request, campos):
    try:
        d = await request.json()
    except Exception:
        raise AppError(400, 'DATOS_INVALIDOS', 'El cuerpo debe ser JSON válido.')
    if not isinstance(d, dict):
        raise AppError(400, 'DATOS_INVALIDOS', 'El cuerpo debe ser un objeto JSON.')
    return d

def texto(d, k, mn, mx):
    v = d.get(k)
    if not isinstance(v, str) or not (mn <= len(v.strip()) <= mx):
        raise AppError(400, 'DATOS_INVALIDOS', f'Datos inválidos en: {k}')
    return v.strip()

def correo_de(d, k='correo'):
    v = d.get(k)
    if not isinstance(v, str) or len(v) > 120 or not EMAIL_RE.match(v.strip()):
        raise AppError(400, 'DATOS_INVALIDOS', f'Datos inválidos en: {k}')
    return v.strip().lower()

async def enviar_verificacion(rid, correo, token):
    enlace = f'{FRONT}/confirmar-correo.html#token={token}'
    r = await S['svc'].llamar('notifications-service', 'POST', '/internal/emails', rid,
                              json={'plantilla': 'verificacion', 'correo': correo, 'enlace': enlace}, timeout=5.0)
    if r.status_code == 422:
        raise AppError(422, 'CORREO_NO_VALIDO', 'No pudimos comprobar que ese correo exista.')
    if r.status_code != 200:
        raise AppError(503, 'MENSAJERIA_NO_DISPONIBLE', 'No pudimos enviar el correo de confirmación. Intenta más tarde.')

async def crear_token(cuenta_id):
    db = S['db']
    await db.tokens.update_many({'cuentaId': cuenta_id, 'usado': False}, {'$set': {'usado': True}})
    t = secrets.token_urlsafe(32)
    return t, {'hash': sha(t), 'cuentaId': cuenta_id, 'expiraEn': en_segundos(VERIF_SEG), 'usado': False, 'creadoEn': ahora()}

# ---------------- S01 login ----------------
@app.post('/auth/login')
async def login(request: Request, ctx: Ctx = Depends(guard.dep(publica=True))):
    d = await body(request, None)
    correo = correo_de(d)
    pw = d.get('password')
    if not isinstance(pw, str) or not (1 <= len(pw) <= 128):
        raise AppError(400, 'DATOS_INVALIDOS', 'Datos inválidos en: password')
    db = S['db']
    desde = time.time() - VENTANA
    fallos = await db.intentos.count_documents({'correo': correo, 'ts': {'$gt': desde}})
    if fallos >= MAX_FALLOS:
        evento(log, 'auth-service', 'login_bloqueado', requestId=ctx.rid)
        raise AppError(429, 'DEMASIADOS_INTENTOS', 'Demasiados intentos. Espera 15 minutos e intenta de nuevo.', {'Retry-After': '900'})
    c = await db.cuentas.find_one({'correo': correo})
    ok = check_pw(pw, c['hash']) if c and c.get('hash') else (check_pw(pw, DUMMY) and False)
    if not ok:
        await db.intentos.insert_one({'correo': correo, 'ts': time.time()})
        evento(log, 'auth-service', 'login_fallido', requestId=ctx.rid)
        raise AppError(401, 'CREDENCIALES_INVALIDAS', 'Correo o contraseña incorrectos.')
    if c['estado'] != 'activo':
        raise AppError(403, 'CUENTA_NO_ACTIVA', 'Confirma tu correo para activar la cuenta.' if c['estado'] == 'pendiente_verificacion' else 'La cuenta no está activa.')
    await db.intentos.delete_many({'correo': correo})
    tok = secrets.token_urlsafe(32)
    await db.sesiones.insert_one({'hash': sha(tok), 'cuentaId': c['id'], 'creadoEn': ahora(), 'expiraEn': en_segundos(TOKEN_SEG), 'activa': True})
    evento(log, 'auth-service', 'login_ok', requestId=ctx.rid, cuentaId=c['id'])
    return {'access_token': tok, 'token_type': 'bearer', 'expires_in': TOKEN_SEG, 'rol': c['rol'], 'nombre': c.get('nombre')}

# ---------------- S02 logout ----------------
@app.post('/auth/logout', status_code=204)
async def logout(ctx: Ctx = Depends(guard.dep(roles=ROLES_TODOS))):
    if ctx.sesion:
        await S['db'].sesiones.update_one({'hash': ctx.sesion}, {'$set': {'activa': False}})
    return Response(status_code=204)

# ---------------- I01 introspect ----------------
@app.post('/internal/introspect')
async def introspect(request: Request, ctx: Ctx = Depends(guard.dep(gateway=False, pares=('api-gateway',)))):
    d = await body(request, None)
    t = d.get('token')
    if not isinstance(t, str) or not (10 <= len(t) <= 200):
        return {'active': False}
    db = S['db']
    h = sha(t)
    s = await db.sesiones.find_one({'hash': h, 'activa': True})
    if not s or s['expiraEn'] <= ahora():
        return {'active': False}
    c = await db.cuentas.find_one({'id': s['cuentaId']})
    if not c or c['estado'] != 'activo':
        return {'active': False}
    return {'active': True, 'cuentaId': c['id'], 'correo': c['correo'], 'roles': [c['rol']], 'sesionId': h}

# ---------------- S04 verify-email ----------------
@app.post('/auth/verify-email')
async def verify(request: Request, ctx: Ctx = Depends(guard.dep(publica=True))):
    d = await body(request, None)
    t = d.get('token')
    if not isinstance(t, str) or not (10 <= len(t) <= 200):
        raise AppError(400, 'TOKEN_INVALIDO', 'El enlace no es válido.')
    db = S['db']
    tk = await db.tokens.find_one({'hash': sha(t)})
    if not tk:
        raise AppError(400, 'TOKEN_INVALIDO', 'El enlace no es válido.')
    if tk['usado'] or tk['expiraEn'] <= ahora():
        raise AppError(410, 'TOKEN_VENCIDO', 'El enlace venció o ya fue usado. Pide uno nuevo.')
    c = await db.cuentas.find_one({'id': tk['cuentaId']})
    if not c or c['estado'] == 'inactivo':
        raise AppError(410, 'TOKEN_VENCIDO', 'El enlace venció o ya fue usado. Pide uno nuevo.')
    upd = {'estado': 'activo'}
    pw = d.get('password')
    if not c.get('hash'):
        if not isinstance(pw, str) or not (8 <= len(pw) <= 128):
            raise AppError(400, 'DATOS_INVALIDOS', 'Debes definir una contraseña de al menos 8 caracteres.')
        upd['hash'] = hash_pw(pw)
    # el token se consume con una actualizacion condicional: solo uno gana si llegan dos a la vez
    r = await db.tokens.update_one({'hash': sha(t), 'usado': False}, {'$set': {'usado': True}})
    if r.modified_count != 1:
        raise AppError(410, 'TOKEN_VENCIDO', 'El enlace venció o ya fue usado. Pide uno nuevo.')
    await db.cuentas.update_one({'id': c['id']}, {'$set': upd})
    evento(log, 'auth-service', 'correo_confirmado', requestId=ctx.rid, cuentaId=c['id'])
    return {'estado': 'activo'}

# ---------------- S05 resend ----------------
@app.post('/auth/resend-verification', status_code=202)
async def resend(request: Request, ctx: Ctx = Depends(guard.dep(publica=True))):
    d = await body(request, None)
    correo = correo_de(d)
    db = S['db']
    c = await db.cuentas.find_one({'correo': correo, 'estado': 'pendiente_verificacion'})
    if c:
        try:
            t, doc = await crear_token(c['id'])
            await enviar_verificacion(ctx.rid, correo, t)
            await db.tokens.insert_one(doc)
        except AppError as e:
            evento(log, 'auth-service', 'reenvio_fallido', requestId=ctx.rid, codigo=e.codigo)
    return Response(status_code=202)

# ---------------- I03 crear cuenta / compensar ----------------
async def crear_cuenta(rid, correo, rol, nombre, password, prefijo):
    db = S['db']
    if await db.cuentas.find_one({'correo': correo}):
        raise AppError(409, 'CORREO_DUPLICADO', 'Ese correo ya está registrado.')
    cid = await siguiente(db, prefijo, prefijo + '_')
    t, tok = await crear_token(cid)
    await enviar_verificacion(rid, correo, t)         # si falla no se crea nada (M3 I06)
    doc = {'id': cid, 'correo': correo, 'rol': rol, 'nombre': nombre, 'estado': 'pendiente_verificacion',
           'hash': hash_pw(password) if password else None, 'creadoEn': ahora()}
    try:
        await db.cuentas.insert_one(doc)
    except DuplicateKeyError:
        raise AppError(409, 'CORREO_DUPLICADO', 'Ese correo ya está registrado.')
    await db.tokens.insert_one(tok)
    return doc

@app.post('/internal/accounts', status_code=201)
async def i03_crear(request: Request, ctx: Ctx = Depends(guard.dep(gateway=False, pares=('clients-service',)))):
    d = await body(request, None)
    correo = correo_de(d)
    if d.get('rol') != 'cliente':
        raise AppError(400, 'DATOS_INVALIDOS', 'Datos inválidos en: rol')
    pw = d.get('password')
    if pw is not None and (not isinstance(pw, str) or not (8 <= len(pw) <= 128)):
        raise AppError(400, 'DATOS_INVALIDOS', 'Datos inválidos en: password')
    nombre = d.get('nombre') if isinstance(d.get('nombre'), str) else None
    c = await crear_cuenta(ctx.rid, correo, 'cliente', nombre, pw, 'cta')
    return {'cuentaId': c['id'], 'estado': c['estado']}

@app.delete('/internal/accounts/{cuenta_id}', status_code=204)
async def i03_compensar(cuenta_id: str, ctx: Ctx = Depends(guard.dep(gateway=False, pares=('clients-service',)))):
    db = S['db']
    r = await db.cuentas.delete_one({'id': cuenta_id, 'estado': 'pendiente_verificacion', 'rol': 'cliente'})
    if r.deleted_count:
        await db.tokens.delete_many({'cuentaId': cuenta_id})
    return Response(status_code=204)

# ---------------- I04 consultar cuentas ----------------
@app.get('/internal/accounts')
async def i04(ids: str = '', ctx: Ctx = Depends(guard.dep(gateway=False, pares=('clients-service',)))):
    lista = [x for x in ids.split(',') if x][:100]
    cur = S['db'].cuentas.find({'id': {'$in': lista}})
    return [{'cuentaId': c['id'], 'correo': c['correo'], 'estado': c['estado']} async for c in cur]

# ---------------- I05 cambiar estado ----------------
@app.patch('/internal/accounts/{cuenta_id}')
async def i05(cuenta_id: str, request: Request, ctx: Ctx = Depends(guard.dep(gateway=False, pares=('clients-service',)))):
    d = await body(request, None)
    if d.get('estado') != 'inactivo':
        raise AppError(400, 'DATOS_INVALIDOS', 'Datos inválidos en: estado')
    db = S['db']
    c = await db.cuentas.find_one({'id': cuenta_id, 'rol': 'cliente'})
    if not c:
        raise AppError(404, 'NO_ENCONTRADO', 'Cuenta no encontrada.')
    await db.cuentas.update_one({'id': cuenta_id}, {'$set': {'estado': 'inactivo', 'bajaEn': ahora()}})
    await db.sesiones.update_many({'cuentaId': cuenta_id}, {'$set': {'activa': False}})
    return {'cuentaId': cuenta_id, 'estado': 'inactivo'}

# ---------------- S30-S33 personal ----------------
ADMIN = Depends(guard.dep(roles=['administrador']))

@app.post('/admin/users', status_code=201)
async def s30(request: Request, ctx: Ctx = ADMIN):
    d = await body(request, None)
    nombre = texto(d, 'nombreCompleto', 2, 100)
    correo = correo_de(d)
    if d.get('rol') not in ROLES_PERSONAL:
        raise AppError(400, 'DATOS_INVALIDOS', 'Datos inválidos en: rol')
    c = await crear_cuenta(ctx.rid, correo, d['rol'], nombre, None, 'usr')
    evento(log, 'auth-service', 'usuario_creado', requestId=ctx.rid, cuentaId=ctx.cuenta, rol=d['rol'])
    return {'id': c['id'], 'rol': c['rol'], 'estado': c['estado']}

@app.get('/admin/users')
async def s31(rol: str = None, estado: str = None, limit: int = None, offset: int = None, ctx: Ctx = ADMIN):
    limit, offset = paginar(limit, offset)
    q = {'rol': {'$in': ROLES_PERSONAL}}
    if rol:
        if rol not in ROLES_PERSONAL: raise AppError(400, 'DATOS_INVALIDOS', 'Filtro rol inválido.')
        q['rol'] = rol
    if estado:
        if estado not in ('activo', 'inactivo', 'pendiente_verificacion'): raise AppError(400, 'DATOS_INVALIDOS', 'Filtro estado inválido.')
        q['estado'] = estado
    cur = S['db'].cuentas.find(q).sort('id', 1).skip(offset).limit(limit)
    return [vistaUsuario(c) async for c in cur]

async def admins_activos_excluyendo(uid):
    return await S['db'].cuentas.count_documents({'rol': 'administrador', 'estado': 'activo', 'id': {'$ne': uid}})

@app.put('/admin/users/{uid}')
async def s32(uid: str, request: Request, ctx: Ctx = ADMIN):
    d = await body(request, None)
    nombre = texto(d, 'nombreCompleto', 2, 100)
    if d.get('rol') not in ROLES_PERSONAL or not isinstance(d.get('activo'), bool):
        raise AppError(400, 'DATOS_INVALIDOS', 'Datos inválidos en: rol, activo')
    db = S['db']
    c = await db.cuentas.find_one({'id': uid, 'rol': {'$in': ROLES_PERSONAL}})
    if not c:
        raise AppError(404, 'NO_ENCONTRADO', 'Usuario no encontrado.')
    estado = c['estado']
    if d['activo'] is False:
        estado = 'inactivo'
    elif estado == 'inactivo':
        estado = 'activo' if c.get('hash') else 'pendiente_verificacion'
    deja_admin = d['rol'] == 'administrador' and estado == 'activo'
    if c['rol'] == 'administrador' and c['estado'] == 'activo' and not deja_admin and await admins_activos_excluyendo(uid) == 0:
        raise AppError(409, 'ULTIMO_ADMINISTRADOR', 'Debe quedar al menos un administrador activo.')
    await db.cuentas.update_one({'id': uid}, {'$set': {'nombre': nombre, 'rol': d['rol'], 'estado': estado}})
    if estado == 'inactivo' or d['rol'] != c['rol']:      # baja o cambio de rol: las sesiones abiertas dejan de servir de inmediato
        await db.sesiones.update_many({'cuentaId': uid}, {'$set': {'activa': False}})
    evento(log, 'auth-service', 'usuario_modificado', requestId=ctx.rid, cuentaId=ctx.cuenta, objetivo=uid)
    return vistaUsuario(await db.cuentas.find_one({'id': uid}))

@app.delete('/admin/users/{uid}', status_code=204)
async def s33(uid: str, ctx: Ctx = ADMIN):
    db = S['db']
    c = await db.cuentas.find_one({'id': uid, 'rol': {'$in': ROLES_PERSONAL}})
    if not c:
        raise AppError(404, 'NO_ENCONTRADO', 'Usuario no encontrado.')
    if uid == ctx.cuenta:
        raise AppError(409, 'NO_PUEDE_ELIMINARSE', 'No puedes dar de baja tu propio usuario.')
    if c['rol'] == 'administrador' and c['estado'] == 'activo' and await admins_activos_excluyendo(uid) == 0:
        raise AppError(409, 'ULTIMO_ADMINISTRADOR', 'Debe quedar al menos un administrador activo.')
    await db.cuentas.update_one({'id': uid}, {'$set': {'estado': 'inactivo'}})
    await db.sesiones.update_many({'cuentaId': uid}, {'$set': {'activa': False}})
    evento(log, 'auth-service', 'usuario_baja', requestId=ctx.rid, cuentaId=ctx.cuenta, objetivo=uid)
    return Response(status_code=204)

if __name__ == '__main__':
    run(app)
