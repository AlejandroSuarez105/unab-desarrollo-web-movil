"""clients-service: perfil y domicilio del cliente y su alta (S03, S24-S29, I07). Autoridad de los datos personales."""
import os, re
from fastapi import Depends, Request, Response
from pymongo.errors import DuplicateKeyError
from fornace.base import make_app, run, AppError, evento
from fornace.vault import SecretProvider
from fornace.guard import Guard, Ctx
from fornace.svc import Servicios
from fornace.db import conectar, siguiente, ahora
from fornace.retencion import corte, INTERVALO
from fornace.util import EMAIL_RE, FONO_RE, run_valido, run_normal, fecha_pasada, paginar

SISTEMA = 'clients'
vault = SecretProvider()
guard = Guard(SISTEMA, vault)
S = {}

async def startup(app):
    S['cli'], S['db'] = await conectar(SISTEMA, vault)
    S['svc'] = Servicios('clients-service', vault, app.state.log)
    await S['db'].clientes.create_index('id', unique=True)
    await S['db'].clientes.create_index('run', unique=True)
    await S['db'].clientes.create_index('cuentaId', unique=True)

async def retencion():
    """7.9: 24 meses despues de la baja se anonimiza el perfil del cliente (RUN, nombre, telefono, fecha de nacimiento, sexo y direccion).
    El RUN se reemplaza por un valor unico para no romper el indice."""
    db, n = S['db'], 0
    async for c in db.clientes.find({'baja': True, 'anonimizado': {'$ne': True}, 'bajaEn': {'$lt': corte('cliente_baja')}}).limit(200):
        await db.clientes.update_one({'id': c['id']}, {'$set': {'run': 'ANON-' + c['id'], 'nombreCompleto': '[eliminado]', 'telefono': None,
                                                                'fechaNacimiento': None, 'sexo': None, 'direccion': None, 'anonimizado': True}})
        n += 1
    if n:
        evento(log, 'clients-service', 'retencion', clientesAnonimizados=n)

app = make_app('clients-service', startup=startup, tareas=[('retencion', INTERVALO, retencion)])
log = app.state.log
CLI = Depends(guard.dep(roles=['cliente']))
ADM = Depends(guard.dep(roles=['administrador']))

async def json_de(request):
    try: d = await request.json()
    except Exception: raise AppError(400, 'DATOS_INVALIDOS', 'El cuerpo debe ser JSON válido.')
    if not isinstance(d, dict): raise AppError(400, 'DATOS_INVALIDOS', 'El cuerpo debe ser un objeto JSON.')
    return d

def validar(d, completo):
    """completo=True: alta (incluye run y correo). Devuelve el documento limpio."""
    m = []
    def txt(o, k, a, b, ruta=None):
        v = o.get(k)
        if not isinstance(v, str) or not (a <= len(v.strip()) <= b): m.append(ruta or k)
    txt(d, 'nombreCompleto', 2, 100)
    if not isinstance(d.get('telefono'), str) or not FONO_RE.match(d['telefono']): m.append('telefono')
    f = d.get('fechaNacimiento')
    if not isinstance(f, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', f) or not fecha_pasada(f) or f < '1900-01-01': m.append('fechaNacimiento')
    if d.get('sexo') not in ('M', 'F', 'O'): m.append('sexo')
    dr = d.get('direccion')
    if not isinstance(dr, dict): m.append('direccion')
    else:
        for k, mx in (('calle', 120), ('comuna', 60), ('provincia', 60), ('region', 60)): txt(dr, k, 2, mx, 'direccion.' + k)
    if completo:
        if not isinstance(d.get('run'), str) or not run_valido(d['run']): m.append('run')
        if not isinstance(d.get('correo'), str) or not EMAIL_RE.match(d['correo'].strip()) or len(d['correo']) > 120: m.append('correo')
    if m: raise AppError(400, 'DATOS_INVALIDOS', 'Datos inválidos en: ' + ', '.join(m))
    out = {'nombreCompleto': d['nombreCompleto'].strip(), 'telefono': d['telefono'], 'fechaNacimiento': d['fechaNacimiento'], 'sexo': d['sexo'],
           'direccion': {k: dr[k].strip() for k in ('calle', 'comuna', 'provincia', 'region')}}
    if completo: out.update(run=run_normal(d['run']), correo=d['correo'].strip().lower())
    return out

def perfil(c, correo=None, estado=None):
    o = {'id': c['id'], 'run': c['run'], 'nombreCompleto': c['nombreCompleto'], 'correo': correo, 'telefono': c['telefono'],
         'fechaNacimiento': c['fechaNacimiento'], 'sexo': c['sexo'], 'direccion': c['direccion']}
    if estado: o['estado'] = estado
    return o

async def alta(request, ctx, con_password):
    d = await json_de(request)
    v = validar(d, True)
    pw = None
    if con_password:
        pw = d.get('password')
        if not isinstance(pw, str) or not (8 <= len(pw) <= 128): raise AppError(400, 'DATOS_INVALIDOS', 'Datos inválidos en: password')
    db = S['db']
    if await db.clientes.find_one({'run': v['run']}):
        raise AppError(409, 'RUN_DUPLICADO', 'Ese RUN ya está registrado.')
    r = await S['svc'].llamar('auth-service', 'POST', '/internal/accounts', ctx.rid,
                              json={'correo': v['correo'], 'rol': 'cliente', 'password': pw, 'nombre': v['nombreCompleto']}, timeout=8.0)
    if r.status_code != 201:
        e = r.json().get('error', {}) if r.headers.get('content-type', '').startswith('application/json') else {}
        if r.status_code in (409, 422): raise AppError(r.status_code, e.get('codigo', 'ERROR'), e.get('mensaje', 'No se pudo crear la cuenta.'))
        raise AppError(503, 'SERVICIO_NO_DISPONIBLE', 'Servicio no disponible. Intenta de nuevo en un momento.')
    cuenta = r.json()['cuentaId']
    kid = await siguiente(db, 'cli', 'cli_')
    try:
        doc = {k: x for k, x in v.items() if k != 'correo'}   # el correo es de auth
        await db.clientes.insert_one(dict(doc, id=kid, cuentaId=cuenta, baja=False, creadoEn=ahora()))
    except Exception as e:
        # compensacion de I03: sin perfil no debe quedar cuenta
        await S['svc'].llamar('auth-service', 'DELETE', f'/internal/accounts/{cuenta}', ctx.rid, timeout=5.0)
        if isinstance(e, DuplicateKeyError): raise AppError(409, 'RUN_DUPLICADO', 'Ese RUN ya está registrado.')
        raise AppError(500, 'ERROR_INTERNO', 'Error interno.')
    evento(log, 'clients-service', 'cliente_registrado', requestId=ctx.rid, id=kid, origen='web' if con_password else 'personal')
    return {'id': kid, 'correo': v['correo'], 'estado': 'pendiente_verificacion'}

# ---------- S03 ----------
@app.post('/clients/register', status_code=201)
async def s03(request: Request, ctx: Ctx = Depends(guard.dep(publica=True))):
    return await alta(request, ctx, True)

# ---------- S26 ----------
@app.post('/admin/clients', status_code=201)
async def s26(request: Request, ctx: Ctx = ADM):
    r = await alta(request, ctx, False)
    return {'id': r['id'], 'estado': r['estado']}

# ---------- S24 / S25 ----------
async def propio(ctx):
    c = await S['db'].clientes.find_one({'cuentaId': ctx.cuenta, 'baja': False})
    if not c: raise AppError(404, 'NO_ENCONTRADO', 'Perfil no encontrado.')
    return c

@app.get('/clients/me')
async def s24(ctx: Ctx = Depends(guard.dep(roles=['cliente'], pares=('graphql-gateway',), pares_solo_get=('graphql-gateway',)))):
    return perfil(await propio(ctx), ctx.email)

@app.put('/clients/me')
async def s25(request: Request, ctx: Ctx = CLI):
    v = validar(await json_de(request), False)
    c = await propio(ctx)
    await S['db'].clientes.update_one({'id': c['id']}, {'$set': v})
    return perfil(dict(c, **v), ctx.email)

# ---------- S27 ----------
@app.get('/admin/clients')
async def s27(q: str = None, limit: int = None, offset: int = None, ctx: Ctx = ADM):
    limit, offset = paginar(limit, offset)
    filtro = {}
    if q:
        if len(q) > 60: raise AppError(400, 'DATOS_INVALIDOS', 'Filtro inválido: q')
        esc = re.escape(q.strip())
        filtro = {'$or': [{'nombreCompleto': {'$regex': esc, '$options': 'i'}}, {'run': {'$regex': esc, '$options': 'i'}}]}
    lista = [c async for c in S['db'].clientes.find(filtro).sort('id', 1).skip(offset).limit(limit)]
    if not lista: return []
    r = await S['svc'].llamar('auth-service', 'GET', '/internal/accounts', ctx.rid, params={'ids': ','.join(c['cuentaId'] for c in lista)}, timeout=5.0)
    if r.status_code != 200: raise AppError(503, 'SERVICIO_NO_DISPONIBLE', 'Servicio no disponible. Intenta de nuevo en un momento.')
    cuentas = {x['cuentaId']: x for x in r.json()}
    return [perfil(c, cuentas.get(c['cuentaId'], {}).get('correo'), cuentas.get(c['cuentaId'], {}).get('estado')) for c in lista]

# ---------- S28 / S29 ----------
@app.put('/admin/clients/{kid}')
async def s28(kid: str, request: Request, ctx: Ctx = ADM):
    v = validar(await json_de(request), False)
    c = await S['db'].clientes.find_one({'id': kid})
    if not c: raise AppError(404, 'NO_ENCONTRADO', 'Cliente no encontrado.')
    await S['db'].clientes.update_one({'id': kid}, {'$set': v})
    r = await S['svc'].llamar('auth-service', 'GET', '/internal/accounts', ctx.rid, params={'ids': c['cuentaId']}, timeout=5.0)
    if r.status_code != 200: raise AppError(503, 'SERVICIO_NO_DISPONIBLE', 'Servicio no disponible. Intenta de nuevo en un momento.')
    a = r.json()[0] if r.json() else {}
    return perfil(dict(c, **v), a.get('correo'), a.get('estado'))

@app.delete('/admin/clients/{kid}', status_code=204)
async def s29(kid: str, ctx: Ctx = ADM):
    c = await S['db'].clientes.find_one({'id': kid})
    if not c: raise AppError(404, 'NO_ENCONTRADO', 'Cliente no encontrado.')
    r = await S['svc'].llamar('auth-service', 'PATCH', f'/internal/accounts/{c["cuentaId"]}', ctx.rid, json={'estado': 'inactivo'}, timeout=5.0)
    if r.status_code not in (200, 404): raise AppError(503, 'SERVICIO_NO_DISPONIBLE', 'Servicio no disponible. Intenta de nuevo en un momento.')
    await S['db'].clientes.update_one({'id': kid}, {'$set': {'baja': True, 'bajaEn': ahora()}})
    evento(log, 'clients-service', 'cliente_baja', requestId=ctx.rid, cuentaId=ctx.cuenta, id=kid)
    return Response(status_code=204)

# ---------- I07 ----------
@app.get('/internal/clients/by-account/{cuenta_id}')
async def i07(cuenta_id: str, ctx: Ctx = Depends(guard.dep(gateway=False, pares=('orders-service',)))):
    c = await S['db'].clientes.find_one({'cuentaId': cuenta_id})
    if not c: raise AppError(404, 'NO_ENCONTRADO', 'Perfil no encontrado.')
    return {'clienteId': c['id'], 'nombreCompleto': c['nombreCompleto'], 'telefono': c['telefono'], 'direccion': c['direccion']}

if __name__ == '__main__':
    run(app)
