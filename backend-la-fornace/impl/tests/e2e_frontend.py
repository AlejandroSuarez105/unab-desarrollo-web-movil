"""Recorrido de extremo a extremo con navegador real (Chrome headless): frontend -> API Gateway -> servicios.
Registra resultados y capturas en tests/resultados y tests/evidencia. Requiere el entorno levantado (scripts/stack.py up)."""
import re, random, time, json, pathlib, sys
from playwright.sync_api import sync_playwright
from h import *
from reg import Suite

FRONT = 'http://127.0.0.1:8080'
EV = pathlib.Path(__file__).resolve().parent / 'evidencia'
S = Suite('e2e_frontend')

def run_valido(cuerpo):
    suma, m = 0, 2
    for d in reversed(str(cuerpo)):
        suma += int(d) * m; m = 2 if m == 7 else m + 1
    r = 11 - suma % 11
    return f"{cuerpo}-{'0' if r == 11 else 'K' if r == 10 else r}"

def esperar_js(pg, expr, timeout=30):
    """Espera a que la expresion JavaScript sea verdadera. Se consulta con page.evaluate en vez de page.wait_for_function, porque este
    ultimo usa eval() dentro de la pagina y la Content-Security-Policy del frontend (sin 'unsafe-eval') lo bloquea."""
    fin = time.time() + timeout
    while time.time() < fin:
        if pg.evaluate('() => !!(' + expr + ')'): return
        pg.wait_for_timeout(150)
    raise TimeoutError('esperar_js: ' + expr)

def bandeja(para):
    k = secreto('notifications/mail')['actual']
    with cli() as c:
        return c.get(base('correo') + '/bandeja', params={'para': para}, headers={'X-API-Key': k}).json()

ts = int(time.time())
correo = f'cliente{ts}@ejemplo.cl'
pwd = 'ClaveDePrueba' + str(ts)[-4:]
run_c = run_valido(random.randint(10000000, 24999999))
reqs = []

with sync_playwright() as p:
    chrome = os.environ.get('CHROME_PATH') or ('/usr/bin/google-chrome' if os.path.exists('/usr/bin/google-chrome') else None)
    nav = p.chromium.launch(**({'executable_path': chrome} if chrome else {}), args=['--no-sandbox'])   # sin ruta: el Chromium que instala playwright
    ctx = nav.new_context(ignore_https_errors=True, viewport={'width': 1280, 'height': 900})
    pg = ctx.new_page()
    pg.on('request', lambda r: reqs.append((r.method, r.url)))
    pg.on('dialog', lambda d: d.accept('Me equivoqué de dirección'))

    # --- P01/P02 catalogo desde la API
    pg.goto(FRONT + '/index.html'); pg.wait_for_selector('#grilla-combos .card-combo'); pg.wait_for_selector('#grilla-destacados .card-producto')
    combos, dest = pg.locator('#grilla-combos .card-combo').count(), pg.locator('#grilla-destacados .card-producto').count()
    S.caso('E2E-01', 'Inicio muestra combos y destacados desde S06', combos == 4 and dest >= 2, f'{combos} combos, {dest} destacados')
    pg.screenshot(path=str(EV / 'e2e-01-inicio.png'))
    pg.goto(FRONT + '/menu.html'); pg.wait_for_selector('#grilla-productos .card-producto')
    n = pg.locator('#grilla-productos .card-producto').count()
    pg.click('[data-filtro-categoria="premium"]'); pg.wait_for_timeout(500)
    n2 = pg.locator('#grilla-productos .card-producto').count()
    S.caso('E2E-02', 'Menu filtra por categoria con datos del servidor', n == 8 and n2 == 3, f'todas={n}, premium={n2}')

    # --- P08 registro (S03) y P09 confirmacion (S04)
    pg.goto(FRONT + '/registro.html')
    f = '#form-registro '
    for k, v in dict(run=run_c, nombreCompleto='Cliente de Prueba', correo=correo, password=pwd, telefono='+56911110000', fechaNacimiento='1992-03-15', calle='Calle Ficticia 100').items():
        pg.fill(f + f'[name={k}]', v)
    pg.select_option(f + '[name=sexo]', 'F')
    pg.click(f + 'button[type=submit]'); pg.wait_for_selector('#registro-ok:not(.d-none)', timeout=15000)
    pg.screenshot(path=str(EV / 'e2e-03-registro.png'))
    S.caso('E2E-03', 'Registro de cliente (S03) deja la cuenta pendiente y envia correo', True, 'mensaje de confirmacion visible')
    # intento de login sin confirmar
    pg.goto(FRONT + '/index.html'); pg.click('button.icono-boton[data-bs-target="#modalLogin"]'); pg.wait_for_selector('#modalLogin.show')
    pg.fill('#modalLogin [name=correo]', correo); pg.fill('#modalLogin [name=password]', pwd); pg.click('#modalLogin button[type=submit]')
    pg.wait_for_selector('#login-error:not(.d-none)'); msg = pg.inner_text('#login-error')
    S.caso('E2E-04', 'Login con correo sin confirmar se rechaza (403)', 'Confirma tu correo' in msg, msg)
    # enlace del correo (en la bandeja del proveedor de prueba)
    msgs = bandeja(correo); enlace = re.search(r'(http\S+confirmar-correo\.html#token=\S+)', msgs[-1]['cuerpo']).group(1)
    pg.goto(enlace); pg.wait_for_selector('#form-confirmar:not(.d-none)'); pg.click('#form-confirmar button[type=submit]'); pg.wait_for_selector('#cc-ok:not(.d-none)')
    S.caso('E2E-05', 'Confirmar correo con el enlace de un solo uso (S04)', True, 'cuenta activa')
    pg.goto(enlace); 
    # el enlace ya se uso: el token ya no esta en la URL (fragmento limpiado), se prueba por API
    with cli() as c:
        tok = re.search(r'token=(\S+)', enlace).group(1)
        r = c.post(base('gateway') + '/api/v1/auth/verify-email', json={'token': tok})
    S.caso('E2E-06', 'El enlace de confirmacion no se puede reutilizar (410)', r.status_code == 410, f'{r.status_code} {r.json()["error"]["codigo"]}')

    # --- login real
    pg.goto(FRONT + '/index.html'); pg.click('button.icono-boton[data-bs-target="#modalLogin"]'); pg.wait_for_selector('#modalLogin.show')
    pg.fill('#modalLogin [name=correo]', correo); pg.fill('#modalLogin [name=password]', pwd); pg.click('#modalLogin button[type=submit]')
    pg.wait_for_selector('#zona-sesion button'); tok_guardado = pg.evaluate("sessionStorage.getItem('fornace_token')")
    en_local = pg.evaluate("JSON.stringify(Object.assign({}, localStorage))")
    S.caso('E2E-07', 'Login (S01): el token queda solo en sessionStorage, no en localStorage', bool(tok_guardado) and tok_guardado not in en_local, 'token en sessionStorage; localStorage solo tiene el carrito')

    # --- carrito, pedido y pago
    pg.goto(FRONT + '/menu.html'); pg.wait_for_selector('#grilla-productos .card-producto')
    pg.locator('#grilla-productos .card-producto').nth(0).locator('button').click(); pg.locator('#grilla-productos .card-producto').nth(6).locator('button').click()
    pg.goto(FRONT + '/carrito.html'); pg.wait_for_selector('#lista-carrito .item-carrito'); esperar_js(pg, "document.querySelector('#form-entrega [name=calle]').value !== ''")
    pre = pg.input_value('#form-entrega [name=calle]')
    total_ui = pg.inner_text('#carrito-total')
    S.caso('E2E-08', 'Carrito precarga la direccion del perfil (S24) y no cobra despacho', pre == 'Calle Ficticia 100' and 'Gratis' in pg.inner_text('#resumen-carrito'), f'calle={pre}, total={total_ui}')
    pg.screenshot(path=str(EV / 'e2e-08-carrito.png'))
    pg.click('#btn-confirmar'); pg.wait_for_url(re.compile(r'.*/pagar/.*'), timeout=20000)
    S.caso('E2E-09', 'Confirmar pedido (S12) + iniciar pago (S20) redirige a la plataforma de pago', True, pg.url.split('/pagar/')[0])
    pg.screenshot(path=str(EV / 'e2e-09-pasarela.png'))
    pg.click('button[value=aprobado]'); pg.wait_for_url(re.compile(r'.*pago-retorno\.html.*'), timeout=20000)
    pg.wait_for_selector('#pr-estado.alert-success', timeout=20000)
    txt = pg.inner_text('#pr-estado')
    S.caso('E2E-10', 'Retorno de pago: el estado "pagado" viene del servidor (S14) tras el aviso firmado', 'Pago confirmado' in txt, txt)
    pg.screenshot(path=str(EV / 'e2e-10-retorno.png'))

    # --- P11 detalle con una sola llamada GraphQL
    pg.goto(FRONT + '/mis-pedidos.html'); pg.wait_for_selector('#mp-lista .resumen-total')
    reqs.clear()
    pg.locator('#mp-lista button:has-text("Ver detalle")').first.click(); pg.wait_for_selector('#md-cuerpo img', timeout=15000)
    gqls = [r for r in reqs if r[0] == 'POST' and r[1].endswith('/api/v1/graphql')]
    otros = [r for r in reqs if '/api/v1/orders/' in r[1] or '/api/v1/products' in r[1]]
    S.caso('T-GQL-15', 'P11 usa una sola llamada POST /api/v1/graphql y ninguna a /orders/{id} ni /products', len(gqls) == 1 and not otros, f'graphql={len(gqls)}, otras={len(otros)}')
    pg.wait_for_timeout(900)      # espera a que termine la animacion del modal
    pg.screenshot(path=str(EV / 'e2e-11-detalle-graphql.png'))
    pg.click('#md-cuerpo button:has-text("Ver boleta")'); pg.wait_for_selector('#md-boleta .resumen-total')
    S.caso('E2E-12', 'Boleta digital del pedido pagado (S23)', 'B-' in pg.inner_text('#md-boleta'), pg.inner_text('#md-boleta').replace('\n', ' ')[:120])

    # --- P12 mi cuenta
    pg.goto(FRONT + '/mi-cuenta.html'); esperar_js(pg, "document.querySelector('#form-perfil [name=nombreCompleto]').value !== ''")
    esperar_js(pg, "!document.getElementById('mc-pedidos').textContent.includes('Cargando')")
    S.caso('E2E-13', 'Mi cuenta (miCuenta GraphQL + S24) muestra perfil y ultimos pedidos', 'ped_' in pg.inner_text('#mc-pedidos'), pg.inner_text('#mc-pedidos')[:80])
    pg.screenshot(path=str(EV / 'e2e-13-mi-cuenta.png'))

    # --- contacto S35
    pg.goto(FRONT + '/contacto.html')
    pg.fill('#form-contacto [name=nombre]', 'Pedro Soto'); pg.fill('#form-contacto [name=correo]', 'pedro@ejemplo.cl'); pg.fill('#form-contacto [name=telefono]', '+56955556666')
    pg.select_option('#form-contacto [name=motivo]', 'reserva_evento'); pg.fill('#form-contacto [name=mensaje]', 'Quisiera cotizar 20 pizzas para un cumpleaños.')
    pg.click('#form-contacto button[type=submit]'); pg.wait_for_selector('#contacto-confirmacion:not(.d-none)')
    S.caso('E2E-14', 'Formulario de contacto guarda el mensaje (S35)', True, 'confirmacion visible')

    # --- anular pedido propio (S15) con otro pedido
    pg.goto(FRONT + '/menu.html'); pg.wait_for_selector('#grilla-productos .card-producto'); pg.locator('#grilla-productos .card-producto').nth(1).locator('button').click()
    pg.goto(FRONT + '/carrito.html'); esperar_js(pg, "document.querySelector('#form-entrega [name=calle]').value !== ''"); pg.click('#btn-confirmar'); pg.wait_for_url(re.compile(r'.*/pagar/.*'))
    pg.goto(FRONT + '/mis-pedidos.html'); pg.wait_for_selector('#mp-lista .resumen-total')
    pg.locator('#mp-lista button:has-text("Anular")').first.click(); pg.wait_for_timeout(1500); pg.reload(); pg.wait_for_selector('#mp-lista .resumen-total')
    html = pg.inner_text('#mp-lista')
    S.caso('E2E-15', 'Anular un pedido pendiente propio (S15)', 'Anulado' in html, 'estado Anulado visible')

    # --- personal: despacho
    pg.evaluate("cerrarSesion()"); pg.wait_for_url(re.compile('.*index.html')); pg.wait_for_timeout(500)
    cr = cred()
    def entrar(usr):
        pg.goto(FRONT + '/index.html'); pg.click('button.icono-boton[data-bs-target="#modalLogin"]'); pg.wait_for_selector('#modalLogin.show')
        pg.fill('#modalLogin [name=correo]', usr); pg.fill('#modalLogin [name=password]', cr[usr]); pg.click('#modalLogin button[type=submit]'); pg.wait_for_selector('#zona-sesion button')
    entrar('despachos@ejemplo.cl'); pg.goto(FRONT + '/panel.html'); pg.wait_for_selector('#panel-tabs a')
    tabs = [t.strip() for t in pg.locator('#panel-tabs a').all_inner_texts()]
    S.caso('E2E-16', 'Panel del encargado de despachos muestra solo sus secciones', tabs == ['Pedidos y ventas', 'Despacho'], tabs)
    pg.click('#panel-tabs a[data-id=despacho]'); pg.wait_for_selector('#panel-contenido table')
    filas = pg.locator('#panel-contenido tbody tr').count()
    S.caso('E2E-17', 'Cola de despacho (S18) muestra ordenes pagadas', filas >= 1, f'{filas} ordenes en cola')
    pg.screenshot(path=str(EV / 'e2e-17-despacho.png'))
    with ctx.expect_page() as nueva:
        pg.locator('[data-print]').first.click()
    pn = nueva.value; pn.wait_for_load_state(); cont = pn.inner_text('body')
    S.caso('E2E-18', 'Imprimir orden (S19) abre el documento HTML con numero de orden', 'Orden OD-' in cont, cont.replace('\n', ' ')[:100])
    pn.close()
    # --- admin y dueno
    pg.evaluate("cerrarSesion()"); pg.wait_for_url(re.compile('.*index.html')); pg.wait_for_timeout(500)
    entrar('dueno@ejemplo.cl'); pg.goto(FRONT + '/panel.html'); pg.wait_for_selector('#panel-tabs a')
    tabs = [t.strip() for t in pg.locator('#panel-tabs a').all_inner_texts()]
    S.caso('E2E-19', 'Panel del dueno: productos y reporte', tabs == ['Productos', 'Reporte de ventas'], tabs)
    pg.click('#panel-tabs a[data-id=reporte]'); pg.click('#f-rep button'); pg.wait_for_selector('#rep table')
    S.caso('E2E-20', 'Reporte de ventas (S34) con total y productos mas vendidos', 'Total recaudado' in pg.inner_text('#rep'), pg.inner_text('#rep').replace('\n', ' ')[:120])
    pg.screenshot(path=str(EV / 'e2e-20-reporte.png'))
    # un cliente no entra al panel
    pg.evaluate("cerrarSesion()"); pg.wait_for_url(re.compile('.*index.html')); pg.wait_for_timeout(500); entrar('admin@ejemplo.cl'); pg.goto(FRONT + '/panel.html'); pg.wait_for_selector('#panel-tabs a')
    tabs = [t.strip() for t in pg.locator('#panel-tabs a').all_inner_texts()]
    S.caso('E2E-21', 'Panel del administrador muestra las seis secciones', len(tabs) == 6, tabs)
    pg.click('#panel-tabs a[data-id=usuarios]'); pg.wait_for_selector('#panel-contenido table')
    S.caso('E2E-22', 'Usuarios del personal (S31) sin contrasenas ni hashes', 'hash' not in pg.inner_text('#panel-contenido').lower(), f'{pg.locator("#panel-contenido tbody tr").count()} usuarios')
    # --- Vista de telefono (390 x 844): sin desplazamiento horizontal y con el menu plegable
    mov = nav.new_context(ignore_https_errors=True, viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
    pm = mov.new_page()
    for n_, (pag, sel) in enumerate((('index.html', '#grilla-combos .card-combo'), ('menu.html', '#grilla-productos .card-producto'), ('registro.html', 'form'), ('contacto.html', 'form'), ('sucursales.html', 'body')), 1):
        pm.goto(FRONT + '/' + pag); pm.wait_for_selector(sel); pm.wait_for_timeout(500)
        ancho = pm.evaluate('[document.documentElement.scrollWidth, window.innerWidth]')
        toggler = pm.locator('.navbar-toggler').is_visible()
        S.caso(f'E2E-M{n_}', f'Telefono 390 px: {pag} sin desplazamiento horizontal y con menu plegable', ancho[0] <= ancho[1] + 1 and toggler, f'scrollWidth={ancho[0]}, innerWidth={ancho[1]}, menu plegable={toggler}')
        if pag in ('index.html', 'menu.html'): pm.screenshot(path=str(EV / f'e2e-m{n_}-{pag.split(".")[0]}-movil.png'))
    nav.close()
ok = S.cerrar()
sys.exit(0 if ok else 1)
