"""Demostracion de los flujos principales contra el sistema real. Escribe evidencia/demo-flujos.md con cada llamada, su respuesta
(sin tokens ni contrasenas) y las lineas de registro que dejaron los sistemas con el mismo requestId."""
import sys, json, time, random, re, pathlib
from h import *

api = Api(); SAL = []
def md(t=''): SAL.append(t)
def resumen(r):
    try: j = r.json()
    except Exception: return r.text[:200]
    if isinstance(j, dict):
        j = {k: ('***' if k in ('access_token', 'token', 'password') else v) for k, v in j.items()}
    s = json.dumps(j, ensure_ascii=False)
    return s if len(s) < 420 else s[:420] + ' ...'
def llamar(titulo, metodo, ruta, token=None, regla=None, **kw):
    rid = f'demo-{random.randint(10**7, 10**8)}'
    r = api.req(metodo, ruta, token, headers={'X-Request-Id': rid}, **kw)
    md(f'**{titulo}**'); md(); md(f'`{metodo} /api/v1{ruta}` con requestId `{rid}`' + (f' · {regla}' if regla else '')); md()
    md(f'Respuesta {r.status_code}: `{resumen(r)}`'); md()
    time.sleep(0.3)
    lin = [(f, l) for f, l in lineas_log(rid) if '"acceso"' in l]
    if lin:
        md('Registros con el mismo requestId:'); md(); md('```')
        for f, l in sorted(lin):
            j = json.loads(l); md(f'{f.replace(".log", ""):18s} {j.get("verbo","")} {j.get("ruta","")} -> {j.get("estado")} ({j.get("ms")} ms) cuentaId={j.get("cuentaId")}')
        md('```'); md()
    return r

md('# Demostración de los flujos principales'); md()
md('Salida real de `tests/demo_flujos.py` contra el sistema en ejecución. Los datos son ficticios. Los tokens y las contraseñas no se imprimen.'); md()
md('## 1. Registro, verificación de correo e inicio de sesión (S03, S04, S01)'); md()
n = random.randint(10**5, 10**6); correo = f'demo{n}@ejemplo.cl'; clave = f'Clave{n}Demo'
llamar('Registro', 'POST', '/auth/register', json={'run': run_valido(random.randint(10**7, 24999999)), 'nombreCompleto': f'Cliente Demo {n}', 'correo': correo, 'password': clave, 'telefono': '+56912345678', 'fechaNacimiento': '1992-02-02', 'sexo': 'F',
        'direccion': {'calle': 'Calle Ficticia 321', 'comuna': 'Maipú', 'provincia': 'Santiago', 'region': 'Metropolitana'}})
asunto = bandeja(correo)[-1]['asunto']; md(f'Correo recibido en el servidor de correo de prueba, asunto: "{asunto}". El enlace de verificación no se muestra.'); md()
llamar('Verificación del correo', 'POST', '/auth/verify-email', json={'token': enlace_token(correo)})
tok = api.login(correo, clave); md('**Inicio de sesión**: respuesta 200 (el token no se muestra).'); md()
md('## 2. Catálogo y pedido (S06, S12)'); md()
llamar('Catálogo público (sin sesión; sin stock en la respuesta)', 'GET', '/products?categoria=combo')
r = llamar('Pedido: el precio y el total los fija el servidor, aunque el cliente envíe otros', 'POST', '/orders', tok, json={'items': [{'productoId': 'prod_002', 'cantidad': 2}], 'total': 1, 'estado': 'pagado'})
ped = r.json()['id']
md('## 3. Consulta protegida de un pedido: autorizada y denegada (S14, regla C1)'); md()
md('Las dos ejecuciones aplican la misma regla en `orders-service`: el pedido solo se devuelve si `pedido.cuentaId` es la cuenta de la identidad verificada por el gateway. La cuenta ajena recibe el mismo 404 que un pedido que no existe.'); md()
llamar('Autorizada: la dueña del pedido', 'GET', f'/orders/{ped}', tok, regla='C1 permite')
otro = nuevo_cliente(api, 'otro')
llamar('Denegada: otra cuenta con sesión válida', 'GET', f'/orders/{ped}', otro['token'], regla='C1 deniega')
llamar('Referencia: pedido que no existe', 'GET', '/orders/ped_9999', otro['token'], regla='C1')
md('## 4. Pago por la plataforma de prueba, aviso firmado, boleta y despacho (S20, S21, S23, S18, S19, S17)'); md()
r = llamar('Iniciar pago', 'POST', f'/orders/{ped}/payments', tok, json={'medio': 'servipag'}); pago = r.json()['pagoId']
md('La pasarela de prueba envía el aviso firmado con HMAC-SHA256 (la firma y el secreto no se muestran).'); md()
simular(pago, 'aprobado'); esperar(lambda: api.req('GET', f'/orders/{ped}', tok).json().get('estado') == 'pagado')
llamar('El pedido quedó pagado', 'GET', f'/orders/{ped}', tok)
llamar('Boleta del pedido', 'GET', f'/orders/{ped}/receipt', tok)
mails = esperar(lambda: [m for m in bandeja(correo) if 'oleta' in m['asunto']]); md(f'Correo de boleta en el servidor de prueba: {"sí" if mails else "no"}, asunto "{mails[-1]["asunto"] if mails else ""}".'); md()
desp = login_demo(api, 'despachos@ejemplo.cl')
esperar(lambda: any(o['pedidoId'] == ped for o in api.req('GET', '/admin/dispatch-orders?limit=100', desp).json()))
llamar('Cola de despacho (encargado de despachos)', 'GET', '/admin/dispatch-orders?limit=100', desp)
llamar('Imprimir la orden', 'GET', f'/admin/dispatch-orders/{ped}/print', desp)
for e in ('en_preparacion', 'en_despacho', 'entregado'): llamar(f'Estado {e}', 'PATCH', f'/admin/orders/{ped}/status', desp, json={'estado': e})
md('## 5. Reporte del dueño (S34)'); md()
dueno = login_demo(api, 'dueno@ejemplo.cl'); hoy = time.strftime('%Y-%m-%d', time.gmtime()); d0 = time.strftime('%Y-%m-%d', time.gmtime(time.time() - 7 * 86400))
llamar('Ventas de los últimos 7 días', 'GET', f'/admin/reports/sales?desde={d0}&hasta={hoy}', dueno)
md('## 6. Detalle por GraphQL en una sola llamada (R36)'); md()
llamar('resumenPedido (orders + inventory)', 'POST', '/graphql', tok, json={'query': 'query($id:ID!){resumenPedido(id:$id){id estado total items{nombre cantidad producto{id nombre precio disponible}}}}', 'variables': {'id': ped}})
open(pathlib.Path(__file__).resolve().parent / 'evidencia/demo-flujos.md', 'w').write('\n'.join(SAL) + '\n')
print('demo escrita:', len(SAL), 'lineas')
