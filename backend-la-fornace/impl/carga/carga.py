"""Pruebas de carga y de fallos del Modulo 9 (9.8), en escala reducida para el equipo de laboratorio.
Uso: python carga.py [--escala completa|reducida] [escenario ...]   (ver README). Resultados reales en ../tests/resultados/carga.json.
Mide con httpx asincrono: p50/p95/p99 en ms, rendimiento (peticiones/s), errores y CPU/memoria de los procesos del sistema (psutil)."""
import os, sys, time, json, asyncio, random, statistics, pathlib, subprocess
import httpx, psutil
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tests'))
from h import *
from reg import Suite

ESCALA = 'completa' if '--escala=completa' in sys.argv else 'reducida'
K = 1.0 if ESCALA == 'completa' else 0.25          # factor sobre las duraciones de 60 s o 120 s del plan
SEL = [a for a in sys.argv[1:] if not a.startswith('--')]
S = Suite('carga')
EXT = {}                                           # datos extra (metricas) por escenario

def q(v, p):
    if not v: return None
    v = sorted(v); return round(v[min(len(v) - 1, int(len(v) * p))] * 1000, 1)

class Medida:
    def __init__(self): self.lat, self.est, self.t0 = [], [], time.time()
    def add(self, dt, st): self.lat.append(dt); self.est.append(st)
    def resumen(self):
        d = time.time() - self.t0
        err = sum(1 for s in self.est if s >= 500 or s == 0)
        return {'peticiones': len(self.est), 'segundos': round(d, 1), 'rps': round(len(self.est) / d, 1), 'p50_ms': q(self.lat, .5), 'p95_ms': q(self.lat, .95), 'p99_ms': q(self.lat, .99),
                'errores_5xx': err, 'porcentaje_errores': round(100 * err / max(1, len(self.est)), 2), 'estados': {str(s): self.est.count(s) for s in sorted(set(self.est))}}

async def una(c, m, metodo, ruta, **kw):
    t = time.time()
    try:
        r = await c.request(metodo, GW + ruta, **kw); st = r.status_code
    except Exception: r, st = None, 0
    m.add(time.time() - t, st); return r

async def tasa(c, m, rps, seg, fn):
    """Lanza fn() a rps por segundo durante seg segundos (bucle abierto)."""
    t0 = time.time(); tareas = []; i = 0
    while time.time() - t0 < seg:
        tareas.append(asyncio.create_task(fn(i))); i += 1
        await asyncio.sleep(max(0, t0 + i / rps - time.time()))
    await asyncio.gather(*tareas)

def procesos():
    out = {}
    for p in psutil.process_iter(['pid', 'cmdline']):
        try:
            cl = ' '.join(p.info['cmdline'] or [])
            for nom in ('api_gateway', 'orders', 'inventory', 'payments', 'graphql_gateway', 'auth', 'clients', 'dispatch', 'mongod', 'vault', 'activemq'):
                if nom in cl and 'carga.py' not in cl and 'grep' not in cl: out[nom] = p
        except Exception: pass
    return out

async def muestrear(stop, res):
    ps = procesos(); mx = {}
    for p in ps.values():
        try: p.cpu_percent(None)
        except Exception: pass
    while not stop.is_set():
        await asyncio.sleep(1)
        for n, p in ps.items():
            try:
                c, mb = p.cpu_percent(None), p.memory_info().rss / 1e6
                x = mx.setdefault(n, {'cpu_max': 0, 'mem_max_mb': 0}); x['cpu_max'] = max(x['cpu_max'], round(c)); x['mem_max_mb'] = max(x['mem_max_mb'], round(mb))
            except Exception: pass
    res.update(mx)

def registrar(id_, descr, objetivo, ok, m, extra=None):
    r = m.resumen() if isinstance(m, Medida) else (m or {})
    if extra: r.update(extra)
    EXT[id_] = r
    S.caso(id_, f'{descr} | objetivo: {objetivo}', ok, json.dumps(r, ensure_ascii=False))

def borrar_semilla(pg, nv):
    # Borrar decenas de miles de documentos uno a uno es lento.
    # Se elimina la coleccion completa y payments-service la recrea con sus indices al reiniciar. Las ventas reales de las
    # pruebas anteriores ya quedaron registradas en los resultados, asi que esta limpieza se hace al final de C5 y C6.
    pg.ventas.drop(); pg.resumen_dia.drop(); pg.resumen_producto.drop(); stack('restart', 'payments', RL_FACTOR=5000)

def activo(id_): return not SEL or id_ in SEL or id_.split('-')[0] in SEL

async def principal():
    api = Api()
    adm = login_demo(api, 'admin@ejemplo.cl')
    # clientes para las pruebas (registrados antes de medir)
    cls = [nuevo_cliente(api, f'ld{i}') for i in range(3)]
    tk = cls[0]['token']
    limits = httpx.Limits(max_connections=200)
    async with httpx.AsyncClient(verify=str(RUN / 'certs/ca.crt'), limits=limits, timeout=20) as c:
        # ---------------- C1 catalogo ----------------
        if activo('C1'):
            for usuarios in (10, 50, 100):
                m = Medida(); fin = time.time() + 60 * K; res = {}; stop = asyncio.Event(); mu = asyncio.create_task(muestrear(stop, res))
                async def usuario():
                    while time.time() < fin:
                        await una(c, m, 'GET', '/products'); await asyncio.sleep(1.0)   # cada usuario consulta una vez por segundo: N usuarios = N por segundo
                await asyncio.gather(*[usuario() for _ in range(usuarios)])
                stop.set(); await mu
                s = m.resumen()
                obj = s['p95_ms'] <= 300 if usuarios <= 50 else True
                registrar(f'C1-{usuarios}u', f'Catalogo (S06), {usuarios} usuarios simultaneos, 1 consulta por segundo cada uno', 'p95 <= 300 ms hasta 50 por segundo; con 100 solo se informa; errores < 1 %', obj and s['porcentaje_errores'] < 1, m, {'recursos': res})
        # ---------------- C2 crear pedido ----------------
        if activo('C2'):
            await c.put(GW + '/products/prod_010/stock', json={'stock': 5000, 'disponible': True}, headers={'Authorization': 'Bearer ' + adm})
            m = Medida(); res = {}; stop = asyncio.Event(); mu = asyncio.create_task(muestrear(stop, res))
            async def pedido(i):
                await una(c, m, 'POST', '/orders', json={'items': [{'productoId': 'prod_010', 'cantidad': 1}]}, headers={'Authorization': 'Bearer ' + cls[i % 3]['token'], 'Idempotency-Key': f'carga-{os.getpid()}-{i}'})
            await tasa(c, m, 2, 120 * K, pedido)
            rafaga = Medida(); await asyncio.gather(*[una(c, rafaga, 'POST', '/orders', json={'items': [{'productoId': 'prod_010', 'cantidad': 1}]}, headers={'Authorization': 'Bearer ' + cls[0]['token']}) for _ in range(10)])
            stop.set(); await mu; s = m.resumen()
            registrar('C2', 'Crear pedido (S12), 2 por segundo y rafaga de 10', 'p95 <= 800 ms; errores < 1 %', s['p95_ms'] <= 800 and s['porcentaje_errores'] < 1 and rafaga.resumen()['errores_5xx'] == 0, m, {'rafaga_10': rafaga.resumen(), 'recursos': res})
            for cl in cls: pass
            # limpieza: los pedidos de la prueba se anulan para devolver el stock
            for cl in cls:
                lista = (await c.get(GW + '/orders', headers={'Authorization': 'Bearer ' + cl['token']})).json()
                for p in lista:
                    if p['estado'] == 'pendiente_pago': await c.post(GW + f'/orders/{p["id"]}/cancel', json={'motivo': 'Fin de la prueba de carga'}, headers={'Authorization': 'Bearer ' + cl['token']})
        # ---------------- C3 sin sobreventa ----------------
        if activo('C3'):
            await c.put(GW + '/products/prod_011/stock', json={'stock': 10, 'disponible': True}, headers={'Authorization': 'Bearer ' + adm})
            m = Medida()
            await asyncio.gather(*[una(c, m, 'POST', '/orders', json={'items': [{'productoId': 'prod_011', 'cantidad': 1}]}, headers={'Authorization': 'Bearer ' + cls[i % 3]['token']}) for i in range(30)])
            st = (await c.get(GW + '/admin/products?incluirRetirados=true', headers={'Authorization': 'Bearer ' + adm})).json()
            final = next(p['stock'] for p in st if p['id'] == 'prod_011')
            creados, rechazados = m.est.count(201), m.est.count(409)
            registrar('C3', 'Sin sobreventa: 30 pedidos simultaneos, stock 10', '10 creados, 20 con 409, stock final 0', creados == 10 and rechazados == 20 and final == 0, m, {'creados': creados, 'rechazados_409': rechazados, 'stock_final': final})
            for cl in cls:
                for p in (await c.get(GW + '/orders', headers={'Authorization': 'Bearer ' + cl['token']})).json():
                    if p['estado'] == 'pendiente_pago': await c.post(GW + f'/orders/{p["id"]}/cancel', json={'motivo': 'Fin de la prueba de carga'}, headers={'Authorization': 'Bearer ' + cl['token']})
            await c.put(GW + '/products/prod_011/stock', json={'stock': 100, 'disponible': True}, headers={'Authorization': 'Bearer ' + adm})
        # ---------------- C4 aviso de pago ----------------
        if activo('C4'):
            await c.put(GW + '/products/prod_012/stock', json={'stock': 1000, 'disponible': True}, headers={'Authorization': 'Bearer ' + adm})
            n_av = int(5 * 60 * K); pagos = []
            for i in range(n_av):
                cl = cls[i % 3]
                p = (await c.post(GW + '/orders', json={'items': [{'productoId': 'prod_012', 'cantidad': 1}]}, headers={'Authorization': 'Bearer ' + cl['token']})).json()['id']
                pagos.append((await c.post(GW + f'/orders/{p}/payments', json={'medio': 'servipag'}, headers={'Authorization': 'Bearer ' + cl['token']})).json()['pagoId'])
                if i % 40 == 39: await asyncio.sleep(0.2)
            monto = {x['id']: x['monto'] for x in mongo()['payments_db'].pagos.find({'id': {'$in': pagos}})}
            m = Medida(); res = {}; stop = asyncio.Event(); mu = asyncio.create_task(muestrear(stop, res))
            async def aviso(i):
                pid = pagos[i]; evt = f'evt_carga_{os.getpid()}_{i}'
                cuerpo = json.dumps({'eventoId': evt, 'pagoId': pid, 'estado': 'aprobado', 'monto': monto[pid]}).encode()
                await una(c, m, 'POST', '/payments/webhook', content=cuerpo, headers=firmar(cuerpo) | {'Content-Type': 'application/json'})
                if random.random() < 0.2: await una(c, m, 'POST', '/payments/webhook', content=cuerpo, headers=firmar(cuerpo) | {'Content-Type': 'application/json'})
            await tasa(c, m, 5, 60 * K, aviso)
            stop.set(); await mu; s = m.resumen()
            t_fin = time.time(); pgd = mongo()['payments_db']
            cuenta = lambda: pgd.ventas.count_documents({'pagoId': {'$in': pagos}})
            while cuenta() < len(pagos) and time.time() - t_fin < 90: await asyncio.sleep(1)
            ventas = cuenta(); aprob = pgd.pagos.count_documents({'id': {'$in': pagos}, 'estado': 'aprobado'}); espera_ventas = round(time.time() - t_fin, 1)
            enviados = min(len(pagos), int(5 * 60 * K))
            registrar('C4', 'Aviso de pago (S21), 5 por segundo con 20 % repetidos', 'p95 <= 500 ms; una venta por eventoId', s['p95_ms'] <= 500 and ventas == aprob and ventas <= enviados, s, {'avisos_unicos': enviados, 'pagos_aprobados': aprob, 'ventas': ventas, 'segundos_hasta_registrar_todas_las_ventas': espera_ventas, 'recursos': res})
        # ---------------- C5/C6 reporte ----------------
        for cid, nv in (('C5', 13800), ('C6', 138000)):
            if activo(cid):
                pg = mongo()['payments_db']; semilla = random.Random(42)
                borrar_semilla(pg, 138000)
                base_t = time.time(); docs = []
                for i in range(nv):
                    dia = time.strftime('%Y-%m-%d', time.gmtime(base_t - semilla.randint(0, 91) * 86400))
                    p1, p2 = semilla.sample(range(1, 13), 2)
                    docs.append({'id': f'ven_s{i}', 'pedidoId': f'ped_s{i}', 'pagoId': f'pag_s{i}', 'cuentaId': 'cta_semilla', 'numeroBoleta': f'B-S{i}', 'total': 8990 * 2, 'ivaIncluido': 2874, 'fecha': dia + 'T12:00:00Z',
                                 'clienteNombre': 'Cliente Semilla', 'clienteCorreo': 'semilla@ejemplo.cl', 'items': [{'productoId': f'prod_{p1:03d}', 'nombre': f'Producto {p1}', 'cantidad': 1, 'precioUnitario': 8990}, {'productoId': f'prod_{p2:03d}', 'nombre': f'Producto {p2}', 'cantidad': 1, 'precioUnitario': 8990}],
                                 'correoEnviado': True, 'correoIntentos': 1, 'semilla': 42, 'enResumen': True})
                for i in range(0, len(docs), 5000): pg.ventas.insert_many(docs[i:i + 5000])
                # los resumenes diarios que alimentan el reporte se calculan con las mismas ventas sembradas
                rd, rp = {}, {}
                for dct in docs:
                    f = dct['fecha'][:10]; x = rd.setdefault(f, {'fecha': f, 'ventas': 0, 'total': 0}); x['ventas'] += 1; x['total'] += dct['total']
                    for it in dct['items']:
                        y = rp.setdefault((f, it['productoId']), {'fecha': f, 'productoId': it['productoId'], 'nombre': it['nombre'], 'unidades': 0}); y['unidades'] += it['cantidad']
                for f, x in rd.items(): pg.resumen_dia.update_one({'fecha': f}, {'$inc': {'ventas': x['ventas'], 'total': x['total']}}, upsert=True)
                for k, y in rp.items(): pg.resumen_producto.update_one({'fecha': y['fecha'], 'productoId': y['productoId']}, {'$inc': {'unidades': y['unidades']}, '$set': {'nombre': y['nombre']}}, upsert=True)
                d0 = time.strftime('%Y-%m-%d', time.gmtime(base_t - 91 * 86400)); d1 = time.strftime('%Y-%m-%d', time.gmtime(base_t + 86400))
                m = Medida(); fin = time.time() + 60 * K; res = {}; stop = asyncio.Event(); mu = asyncio.create_task(muestrear(stop, res))
                async def lector():
                    while time.time() < fin:
                        await una(c, m, 'GET', f'/admin/reports/sales?desde={d0}&hasta={d1}', headers={'Authorization': 'Bearer ' + adm})
                await asyncio.gather(*[lector() for _ in range(5)])
                stop.set(); await mu; s = m.resumen()
                lim = 1500 if cid == 'C5' else 5000
                registrar(cid, f'Reporte de ventas (S34), 92 dias, {nv} ventas semilla 42, 5 consultas simultaneas', f'p95 <= {lim} ms; errores < 1 %', s['p95_ms'] <= lim and s['porcentaje_errores'] < 1, m, {'ventas_sembradas': nv, 'recursos': res})
                borrar_semilla(pg, nv)
        # ---------------- C7/C8 graphql ----------------
        if activo('C7') or activo('C8'):
            ped2 = (await c.post(GW + '/orders', json={'items': [{'productoId': 'prod_001', 'cantidad': 1}, {'productoId': 'prod_002', 'cantidad': 1}]}, headers={'Authorization': 'Bearer ' + cls[0]['token']})).json()['id']
            H = {'Authorization': 'Bearer ' + cls[0]['token']}
            Q = 'query($id:ID!){resumenPedido(id:$id){id estado total items{productoId nombre cantidad precioUnitario producto{id nombre precio disponible}}}}'
            if activo('C7'):
                m = Medida(); res = {}; stop = asyncio.Event(); mu = asyncio.create_task(muestrear(stop, res))
                async def g(i): await una(c, m, 'POST', '/graphql', json={'query': Q, 'variables': {'id': ped2}}, headers=H)
                rid = f'req-carga-c7-{random.randint(10**5, 10**6)}'
                await una(c, Medida(), 'POST', '/graphql', json={'query': Q, 'variables': {'id': ped2}}, headers=H | {'X-Request-Id': rid})
                await tasa(c, m, 10, 60 * K, g); stop.set(); await mu; s = m.resumen()
                inv = sum(1 for f, l in lineas_log(rid) if f.startswith('inventory-service') and '/products' in l)
                registrar('C7', 'Detalle por GraphQL (R36), 10 por segundo, pedido de 2 items', 'p95 <= 600 ms; una llamada a inventory por consulta', s['p95_ms'] <= 600 and inv == 1 and s['porcentaje_errores'] < 1, m, {'llamadas_inventory_por_consulta': inv, 'recursos': res})
            if activo('C8'):
                N = 100; mr, mg = Medida(), Medida(); ids = ','.join(['prod_001', 'prod_002'])
                for _ in range(N):
                    t = time.time(); r1 = await c.get(GW + f'/orders/{ped2}', headers=H); r2 = await c.get(GW + f'/products?ids={ids}', headers=H); mr.add(time.time() - t, max(r1.status_code, r2.status_code))
                    await una(c, mg, 'POST', '/graphql', json={'query': Q, 'variables': {'id': ped2}}, headers=H)
                a, b = mr.resumen(), mg.resumen()
                registrar('C8', 'Comparacion REST (S14 + S06) y GraphQL, 100 repeticiones secuenciales', 'se informa la diferencia; sin objetivo', True, {}, {'rest_2_llamadas_p95_ms': a['p95_ms'], 'rest_p50_ms': a['p50_ms'], 'graphql_1_llamada_p95_ms': b['p95_ms'], 'graphql_p50_ms': b['p50_ms'],
                          'diferencia_p95_ms': round(b['p95_ms'] - a['p95_ms'], 1), 'llamadas_del_navegador_rest': 2, 'llamadas_del_navegador_graphql': 1})
        # ---------------- C9 despacho ----------------
        if activo('C9'):
            import stomp
            vault_c = secreto('dispatch/activemq') if False else None
            total = 200; ids = [f'ped_c9{random.randint(10**5, 10**6)}_{i}' for i in range(total)]
            cr_ = secreto('orders/activemq'); conn = stomp.Connection10([('127.0.0.1', 61613)]); conn.connect(cr_['usuario'], cr_['clave'], wait=True)
            t0 = time.time()
            for i, pid in enumerate(ids):
                conn.send('/queue/cola_pedidos', json.dumps({'tipo': 'nueva', 'pedidoId': pid, 'pagadoEn': '2026-11-08T12:00:00Z', 'clienteNombre': 'Cliente Carga', 'telefono': '+56900000000',
                                                              'direccionEntrega': {'calle': 'Calle Ficticia 1', 'comuna': 'Maipú', 'referencia': ''}, 'items': [{'nombre': 'Pizza', 'cantidad': 1}]}))
                await asyncio.sleep(10 / total)
            envio = time.time() - t0
            dd = mongo()['dispatch_db']
            llegaron = lambda: dd.ordenes.count_documents({'pedidoId': {'$in': ids}})
            while llegaron() < total and time.time() - t0 < 60: await asyncio.sleep(0.5)
            dt = time.time() - t0; conn.disconnect()
            docs = list(dd.ordenes.find({'pedidoId': {'$in': ids}}).sort('numeroOrden', 1))
            orden_ok = [d['pedidoId'] for d in docs] == ids
            registrar('C9', 'Despacho (I14): rafaga de 200 ordenes en 10 s', '200 en orden, sin perdida ni duplicados, en menos de 30 s', len(docs) == total and orden_ok and dt < 30, {}, {'enviadas': total, 'recibidas': len(docs), 'en_orden_de_llegada': orden_ok, 'segundos_envio': round(envio, 1), 'segundos_hasta_ultima': round(dt, 1)})
            dd.ordenes.delete_many({'pedidoId': {'$in': ids}}); dd.mensajes.delete_many({'pedidoId': {'$in': ids}})

asyncio.run(principal())
json.dump(EXT, open(pathlib.Path(__file__).resolve().parents[1] / 'tests/resultados/carga_metricas.json', 'w'), ensure_ascii=False, indent=1)
sys.exit(0 if S.cerrar() else 1)
