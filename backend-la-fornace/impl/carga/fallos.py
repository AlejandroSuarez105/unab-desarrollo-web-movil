"""Fallos y desconexiones F1..F7 del Modulo 9 (9.8) ejecutados sobre el sistema real. Resultados reales en ../tests/resultados/fallos.json.
F5 detiene Vault (modo desarrollo, en memoria): al terminar hay que levantar todo de nuevo con scripts/stack.py down y up."""
import os, sys, time, json, random, pathlib, psutil
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tests'))
from h import *
from reg import Suite
import stomp

SEL = [a.upper() for a in sys.argv[1:]]
S = Suite('fallos_' + '_'.join(SEL) if SEL else 'fallos')
def activo(i): return not SEL or i in SEL
def pids(): return json.load(open(RUN / 'pids.json'))
def err(r):
    try: j = r.json()
    except Exception: return None
    return j.get('error', {}).get('codigo') if isinstance(j, dict) else None
def estado_pedido(api, tok, ped): return api.req('GET', f'/orders/{ped}', tok).json().get('estado')

api = Api(); adm = login_demo(api, 'admin@ejemplo.cl'); desp = login_demo(api, 'despachos@ejemplo.cl')
A = nuevo_cliente(api, 'fa'); tk = A['token']
api.req('PUT', '/products/prod_010/stock', adm, json={'stock': 5000, 'disponible': True})
dd, io, ip = mongo()['dispatch_db'], mongo()['inventory_db'], mongo()['payments_db']
PED = {'items': [{'productoId': 'prod_010', 'cantidad': 1}]}

# ---------------- F1 inventory detenido durante la creacion de pedidos ----------------
if activo('F1'):
    resultados = []; t0 = time.time(); parado = reinicio = None; i = 0; lanzado = False
    while time.time() - t0 < 25:
        t = time.time() - t0
        if t > 5 and parado is None: stack('stop', 'inventory'); parado = time.time() - t0
        if parado and reinicio is None and t > 14: subprocess_t = time.time(); stack('restart', 'inventory', RL_FACTOR=5000); reinicio = time.time() - t0
        r = api.req('POST', '/orders', tk, json=PED, headers={'Idempotency-Key': f'f1-{os.getpid()}-{i}'}); resultados.append((round(time.time() - t0, 1), r.status_code, err(r))); i += 1
        time.sleep(0.5)
    durante = [x for x in resultados if parado and parado + 1 < x[0] < (reinicio or 99)]
    # recuperacion: primer 201 despues del reinicio
    primero_ok = next((x[0] for x in resultados if reinicio and x[0] >= reinicio and x[1] == 201), None)
    mios = [p['id'] for p in api.req('GET', '/orders', tk).json() if p['estado'] == 'pendiente_pago']
    sin_reserva = [p for p in mios if not io.reservas.find_one({'pedidoId': p, 'estado': {'$in': ['reservada', 'confirmada']}})]
    S.caso('F1', 'Inventory detenido durante la creacion de pedidos: 503 controlado, sin pedidos a medias, vuelve a 201', bool(durante) and all(x[1] == 503 for x in durante) and not sin_reserva and primero_ok is not None and primero_ok - reinicio < 30,
           json.dumps({'detenido_en_s': round(parado, 1), 'reiniciado_en_s': round(reinicio, 1), 'respuestas_durante_la_caida': sorted({(x[1], x[2]) for x in durante}), 'pedidos_sin_reserva': len(sin_reserva), 'segundos_hasta_el_primer_201': round(primero_ok - reinicio, 1) if primero_ok else None}))
    for p in mios: api.req('POST', f'/orders/{p}/cancel', tk, json={'motivo': 'Fin de la prueba F1'})

# ---------------- F2 broker detenido durante un pago ----------------
if activo('F2'):
    stack('stop', 'broker')
    ped, pago = pedido_pagado(api, tk, PED['items'])
    d0 = mongo()['orders_db'].pedidos.find_one({'id': ped})
    estado, pub_antes = estado_pedido(api, tk, ped), d0.get('despachoPublicado')
    en_cola_antes = dd.ordenes.count_documents({'pedidoId': ped})
    subprocess_ok = stack('infra'); t_b = time.time()
    llego = esperar(lambda: dd.ordenes.count_documents({'pedidoId': ped}) >= 1, 90)
    seg = round(time.time() - t_b, 1); n = dd.ordenes.count_documents({'pedidoId': ped}); pub_desp = mongo()['orders_db'].pedidos.find_one({'id': ped}).get('despachoPublicado')
    S.caso('F2', 'Broker detenido durante un pago: pedido pagado con despachoPublicado en falso; al reiniciar la orden llega una sola vez', estado == 'pagado' and pub_antes is False and en_cola_antes == 0 and n == 1 and pub_desp is True and seg < 60,
           json.dumps({'estado_con_broker_caido': estado, 'despachoPublicado_con_broker_caido': pub_antes, 'segundos_tras_reiniciar_hasta_dispatch': seg, 'ordenes_en_dispatch': n, 'despachoPublicado_final': pub_desp, 'objetivo_del_plan_s': 30}))

# ---------------- F3 dispatch reiniciado con mensajes pendientes ----------------
if activo('F3'):
    stack('stop', 'dispatch'); time.sleep(1)
    cr = secreto('orders/activemq'); conn = stomp.Connection10([('127.0.0.1', 61613)]); conn.connect(cr['usuario'], cr['clave'], wait=True)
    ids = [f'ped_f3{random.randint(10**5, 10**6)}_{i}' for i in range(20)]
    for pid in ids:
        time.sleep(0.05)       # pausa corta entre mensajes: no se envian tramas pegadas al broker
        conn.send('/queue/cola_pedidos', json.dumps({'tipo': 'nueva', 'pedidoId': pid, 'pagadoEn': '2026-11-08T12:00:00Z', 'clienteNombre': 'Cliente F3', 'telefono': '+56900000000', 'direccionEntrega': {'calle': 'Calle Ficticia 1', 'comuna': 'Maipú', 'referencia': ''}, 'items': [{'nombre': 'Pizza', 'cantidad': 1}]}))
    time.sleep(0.05); conn.send('/queue/cola_pedidos', json.dumps({'tipo': 'nueva', 'pedidoId': ids[0], 'pagadoEn': '2026-11-08T12:00:00Z', 'clienteNombre': 'Cliente F3', 'telefono': '+56900000000', 'direccionEntrega': {'calle': 'Calle Ficticia 1', 'comuna': 'Maipú', 'referencia': ''}, 'items': [{'nombre': 'Pizza', 'cantidad': 1}]}))   # un duplicado
    conn.disconnect(); antes = dd.ordenes.count_documents({'pedidoId': {'$in': ids}})
    stack('restart', 'dispatch'); t_r = time.time()
    esperar(lambda: dd.ordenes.count_documents({'pedidoId': {'$in': ids}}) >= 20, 60); seg = round(time.time() - t_r, 1); time.sleep(2)
    n = dd.ordenes.count_documents({'pedidoId': {'$in': ids}}); dups = n - len({o['pedidoId'] for o in dd.ordenes.find({'pedidoId': {'$in': ids}})})
    S.caso('F3', 'Dispatch reiniciado con 21 mensajes pendientes (uno repetido): reconecta, consume y no duplica ordenes', antes == 0 and n == 20 and dups == 0, json.dumps({'ordenes_antes_del_reinicio': antes, 'ordenes_despues': n, 'duplicadas': dups, 'segundos_hasta_consumir': seg}))

# ---------------- F4 orders lento durante un aviso de pago ----------------
if activo('F4'):
    r = api.req('POST', '/orders', tk, json=PED); ped = r.json()['id']
    pago = api.req('POST', f'/orders/{ped}/payments', tk, json={'medio': 'servipag'}).json()['pagoId']
    raiz_orders = psutil.Process(pids()['orders'])
    procs_orders = [raiz_orders] + raiz_orders.children(recursive=True)    # en Windows el entorno virtual lanza el interprete real como proceso hijo: se congela todo el arbol
    for q in procs_orders: q.suspend()
    t_s = time.time()
    try:
        res = simular(pago, 'aprobado'); time.sleep(7)             # orders no responde mas de 5 s (timeout de payments hacia orders)
        p1 = ip.pagos.find_one({'id': pago})
        estado_pago, conf = p1['estado'], p1['confirmadoEnPedidos']
    finally:
        for q in procs_orders: q.resume()
    t_c = time.time(); ok = esperar(lambda: estado_pedido(api, tk, ped) == 'pagado', 90); seg = round(time.time() - t_c, 1)
    S.caso('F4', 'Orders sin responder mas de 5 s durante el aviso: el aviso se registra, el pago queda aprobado sin confirmar y el pedido pasa a pagado al normalizarse', res['estado'] == 200 and estado_pago == 'aprobado' and conf is False and bool(ok),
           json.dumps({'respuesta_del_aviso': res['estado'], 'pago_durante_la_demora': estado_pago, 'confirmadoEnPedidos_durante_la_demora': conf, 'segundos_hasta_pagado_tras_reanudar_orders': seg}))

# ---------------- F6 auth detenido ----------------
if activo('F6'):
    ped = api.req('POST', '/orders', tk, json=PED).json()['id']; pago = api.req('POST', f'/orders/{ped}/payments', tk, json={'medio': 'servipag'}).json()['pagoId']
    stack('stop', 'auth')
    cat = api.req('GET', '/products'); ord_ = api.req('GET', '/orders', tk); w = simular(pago, 'aprobado')
    stack('restart', 'auth', RL_FACTOR=5000)
    pagado = esperar(lambda: estado_pedido(api, tk, ped) == 'pagado', 30)
    S.caso('F6', 'Auth detenido: el catalogo y el aviso de pago siguen; las rutas con token responden 503', cat.status_code == 200 and w['estado'] == 200 and ord_.status_code == 503 and bool(pagado), json.dumps({'catalogo': cat.status_code, 'aviso_de_pago': w['estado'], 'ruta_con_token': ord_.status_code, 'codigo': err(ord_), 'pedido_pagado_despues': bool(pagado)}))

# ---------------- F7 proveedor de pago y de correo sin respuesta ----------------
if activo('F7'):
    ped = api.req('POST', '/orders', tk, json=PED).json()['id']
    stack('stop', 'pasarela'); r = api.req('POST', f'/orders/{ped}/payments', tk, json={'medio': 'servipag'}); pend = ip.pagos.count_documents({'pedidoId': ped}); stack('restart', 'pasarela', RL_FACTOR=5000)
    stack('restart', 'payments', RL_FACTOR=5000, CORREO_REINTENTO_SEGUNDOS=10)
    stack('stop', 'correo'); ped2, _ = pedido_pagado(api, tk, PED['items'])
    v = esperar(lambda: ip.ventas.find_one({'pedidoId': ped2}), 20); sin_correo = v['correoEnviado'] if v else None
    stack('restart', 'correo', RL_FACTOR=5000); t_r = time.time()
    ok = esperar(lambda: ip.ventas.find_one({'pedidoId': ped2, 'correoEnviado': True}), 60); seg = round(time.time() - t_r, 1)
    S.caso('F7', 'Pasarela sin respuesta: S20 502/503 sin guardar pago. Correo sin respuesta: boleta con correoEnviado en falso y reintento', r.status_code in (502, 503) and pend == 0 and sin_correo is False and bool(ok),
           json.dumps({'S20_con_pasarela_caida': r.status_code, 'codigo': err(r), 'pagos_guardados': pend, 'correoEnviado_con_correo_caido': sin_correo, 'segundos_hasta_reintento_exitoso': seg, 'intervalo_de_reintento_de_la_prueba_s': 10, 'intervalo_del_plan_s': 300}))
    stack('restart', 'payments', RL_FACTOR=5000)

# ---------------- F5 vault detenido ----------------
if activo('F5'):
    stack('restart', 'gateway', RL_FACTOR=5000, VAULT_TTL_SEGUNDOS=5, VAULT_GRACIA_SEGUNDOS=25)
    a0 = api.req('GET', '/orders', tk).status_code; time.sleep(6)
    stack('stop', 'vault'); t0 = time.time(); time.sleep(1)
    antes = [api.req('GET', '/orders', tk).status_code, api.req('GET', '/products').status_code]           # el gateway usa el valor en memoria
    mid = []
    while time.time() - t0 < 14: mid.append(api.req('GET', '/orders', tk).status_code); time.sleep(3)
    time.sleep(max(0, 32 - (time.time() - t0)))
    despues = api.req('GET', '/orders', tk); cat = api.req('GET', '/products')
    S.caso('F5', 'Vault detenido: el gateway sigue con el secreto en memoria durante la ventana (25 s en la prueba, 15 min en produccion) y luego responde 503', a0 == 200 and antes == [200, 200] and all(x == 200 for x in mid) and despues.status_code == 503,
           json.dumps({'antes_de_la_ventana': antes, 'dentro_de_la_ventana': sorted(set(mid)), 'despues_de_la_ventana': despues.status_code, 'codigo': err(despues), 'catalogo_publico_despues': cat.status_code, 'ventana_prueba_s': 25, 'ventana_plan_s': 900}))

ok = S.cerrar()
sys.exit(0 if ok else 1)
