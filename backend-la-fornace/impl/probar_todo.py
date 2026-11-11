#!/usr/bin/env python3
"""Prueba TODO con un solo comando: el modo local (sin Docker) y Docker Compose, y deja los resultados en un solo zip.

Uso (desde la carpeta que contiene este archivo):
    python probar_todo.py                    # local y Docker Compose, en ese orden
    python probar_todo.py --solo-local       # solo la bateria local
    python probar_todo.py --solo-compose     # solo Docker Compose
    python probar_todo.py --sin-carga        # la bateria local sin carga ni caidas (mucho mas corta)
    python probar_todo.py --instalar-infra   # descarga Vault 1.18.5 y ActiveMQ 6.2.0 a .herramientas si no los encuentra

Que hace:
  1. Crea .venv e instala las dependencias (una sola vez) y se vuelve a ejecutar con ese Python.
  2. Busca MongoDB (servicio en 127.0.0.1:27017), Vault, ActiveMQ, Java, Node y Docker.
  3. Modo local: scripts/run_tests.py (193 pruebas) y luego stack.py down --todo.
  4. Docker Compose: down --borrar, up, semilla, probar (28 pruebas) y estado; deja todo detenido.
  5. Escribe ENVIAR-RESULTADOS.zip con los resultados, las capturas, las salidas y las versiones del entorno.
Lo que no se puede instalar solo (MongoDB 7 como servicio, Java 17, Node, Docker Desktop) se informa con el comando de instalacion."""
import os, sys, re, json, time, shutil, socket, hashlib, zipfile, pathlib, platform, subprocess, urllib.request

RAIZ = pathlib.Path(__file__).resolve().parent
os.chdir(RAIZ)
EN_NT = os.name == 'nt'
ARGS = sys.argv[1:]
SOLO_LOCAL, SOLO_COMPOSE = '--solo-local' in ARGS, '--solo-compose' in ARGS
SIN_CARGA, INSTALAR = '--sin-carga' in ARGS, '--instalar-infra' in ARGS
SALIDA = RAIZ / 'salida-pruebas'
RES, EVID = RAIZ / 'tests' / 'resultados', RAIZ / 'tests' / 'evidencia'
VENV = RAIZ / '.venv'
VPY = VENV / ('Scripts/python.exe' if EN_NT else 'bin/python')
HERR = RAIZ / '.herramientas'
VAULT_SHA256 = {'nt': 'defd708e5db4c8ce989729d17a53bab78f0b730fde2fefc76b289e73c61dcdca',
                'posix': 'dfd8619affbc6449a2f8b23a04f1e8632a00e9b8010b49f7f5daf253d181129d'}
VAULT_URL = {'nt': 'https://releases.hashicorp.com/vault/1.18.5/vault_1.18.5_windows_amd64.zip',
             'posix': 'https://releases.hashicorp.com/vault/1.18.5/vault_1.18.5_linux_amd64.zip'}
AMQ_URLS = ['https://archive.apache.org/dist/activemq/6.2.0/apache-activemq-6.2.0-bin.zip', 'https://downloads.apache.org/activemq/6.2.0/apache-activemq-6.2.0-bin.zip']

if '--ayuda' in ARGS or '-h' in ARGS:
    print(__doc__); sys.exit(0)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

T0 = time.time()
def hora(): return time.strftime('%H:%M:%S')
def paso(t): print(f'\n[{hora()}] ===== {t} =====', flush=True)
def aviso(t): print(f'[{hora()}] AVISO: {t}', flush=True)
def info(t): print(f'[{hora()}] {t}', flush=True)

def ejecutar(cmd, log=None, env=None, cwd=None, mostrar=True):
    """Ejecuta mostrando la salida en vivo y copiandola a un archivo. Devuelve (codigo, texto)."""
    e = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
    if env: e.update({k: str(v) for k, v in env.items()})
    cabeza = '$ ' + ' '.join(str(c) for c in cmd)
    partes = [cabeza]
    try:
        p = subprocess.Popen([str(c) for c in cmd], cwd=str(cwd or RAIZ), env=e, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding='utf-8', errors='replace', bufsize=1)
    except OSError as ex:
        txt = f'{cabeza}\nNo se pudo ejecutar: {ex}'
        if log: pathlib.Path(log).write_text(txt, encoding='utf-8')
        print(txt); return 127, txt
    for linea in p.stdout:
        partes.append(linea.rstrip('\n'))
        if mostrar: print(linea.rstrip('\n'), flush=True)
    p.wait()
    texto = '\n'.join(partes) + '\n'
    if log:
        pathlib.Path(log).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(log).write_text(texto, encoding='utf-8')
    return p.returncode, texto

def captura(cmd, **kw):
    try:
        r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=kw.pop('timeout', 30), **kw)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as ex:
        return 127, str(ex)

# ---------------------------------------------------------------- 1. entorno virtual
def preparar_venv():
    paso('Entorno de Python (.venv)')
    if ' ' in str(RAIZ):
        aviso('la ruta del proyecto tiene espacios; el modo local puede fallar. Use una carpeta sin espacios.')
    if not VPY.exists():
        info('creando .venv ...')
        c, t = ejecutar([sys.executable, '-m', 'venv', VENV])
        if c: sys.exit('No se pudo crear .venv')
    firma = hashlib.sha256(b''.join((RAIZ / f).read_bytes() for f in ('requirements.txt', 'requirements-test.txt'))).hexdigest()
    marca = VENV / '.fornace-ok'
    if not (marca.exists() and marca.read_text() == firma):
        info('instalando dependencias (una sola vez) ...')
        for cmd in ([VPY, '-m', 'pip', 'install', '-q', '--disable-pip-version-check', '-r', 'requirements.txt', '-r', 'requirements-test.txt'],
                    [VPY, '-m', 'pip', 'install', '-q', '--disable-pip-version-check', '-e', 'common']):
            c, _ = ejecutar(cmd)
            if c: sys.exit('Fallo la instalacion de dependencias de Python (ver arriba).')
        c, _ = ejecutar([VPY, '-m', 'playwright', 'install', 'chromium'])
        if c: aviso('no se pudo instalar Chromium de Playwright: la prueba con navegador (e2e_frontend) puede fallar. Instale Google Chrome o defina CHROME_PATH.')
        marca.write_text(firma)
    gql = RAIZ / 'services' / 'graphql_gateway'
    if not (gql / 'node_modules').exists():
        npm = shutil.which('npm')
        if not npm: aviso('no se encontro npm: no se pueden instalar las dependencias del GraphQL Gateway (necesita Node 22 o superior).')
        else:
            info('instalando dependencias de Node del GraphQL Gateway ...')
            c, _ = ejecutar([npm, 'ci', '--omit=dev'], cwd=gql)
            if c: aviso('npm ci fallo.')

if os.environ.get('FORNACE_VENV') != '1':
    preparar_venv()
    r = subprocess.run([str(VPY), str(pathlib.Path(__file__).resolve())] + ARGS, env=dict(os.environ, FORNACE_VENV='1'))
    sys.exit(r.returncode)

# ---------------------------------------------------------------- 2. deteccion de infraestructura
def abierto(p):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', p)) == 0

def raices_busqueda():
    h = pathlib.Path.home()
    r = [(HERR, 4), (h / 'Desktop', 5), (h / 'Downloads', 5), (h / 'Documents', 5), (h, 2)]
    if EN_NT:
        r += [(pathlib.Path('C:/'), 2), (pathlib.Path('C:/tools'), 4), (pathlib.Path('C:/Program Files'), 3), (pathlib.Path('C:/Program Files (x86)'), 3), (pathlib.Path('D:/'), 2)]
    else:
        r += [(pathlib.Path('/opt'), 3), (pathlib.Path('/usr/local'), 2)]
    return [(p, d) for p, d in r if p.exists()]

SALTAR = {'node_modules', '.venv', '.git', 'windows', '$recycle.bin', 'appdata', 'system volume information', '__pycache__', 'site-packages'}
def buscar(pred, maximo=1):
    """Recorre las carpetas habituales (con profundidad limitada) y devuelve las rutas que cumplen pred(ruta_de_carpeta, nombres_de_archivos, nombres_de_carpetas)."""
    hallados = []
    for raiz, prof in raices_busqueda():
        base = len(raiz.parts)
        for d, carpetas, archivos in os.walk(raiz):
            if len(pathlib.Path(d).parts) - base >= prof: carpetas[:] = []
            carpetas[:] = [c for c in carpetas if c.lower() not in SALTAR]
            try:
                r = pred(pathlib.Path(d), archivos, carpetas)
            except Exception:
                r = None
            if r and r not in hallados:
                hallados.append(r)
                if len(hallados) >= maximo: return hallados
    return hallados

def buscar_vault():
    v = os.environ.get('VAULT_BIN')
    if v and pathlib.Path(v).exists(): return v
    w = shutil.which('vault')
    if w: return w
    nombre = 'vault.exe' if EN_NT else 'vault'
    h = buscar(lambda d, a, c: d / nombre if nombre in a else None)
    return str(h[0]) if h else None

def buscar_activemq():
    v = os.environ.get('ACTIVEMQ_HOME')
    sc = 'bin/activemq.bat' if EN_NT else 'bin/activemq'
    if v and (pathlib.Path(v) / sc).exists(): return v
    h = buscar(lambda d, a, c: d if d.name.lower().startswith('apache-activemq') and (d / sc).exists() else None)
    return str(h[0]) if h else None

def descargar(url, destino):
    info(f'descargando {url}')
    destino.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as r, open(destino, 'wb') as f:
        shutil.copyfileobj(r, f)

def instalar_vault():
    z = HERR / 'vault.zip'
    k = 'nt' if EN_NT else 'posix'
    descargar(VAULT_URL[k], z)
    if hashlib.sha256(z.read_bytes()).hexdigest() != VAULT_SHA256[k]:
        z.unlink(); raise RuntimeError('la suma SHA-256 de Vault no coincide con la publicada por HashiCorp')
    with zipfile.ZipFile(z) as f: f.extractall(HERR / 'vault')
    z.unlink()
    exe = HERR / 'vault' / ('vault.exe' if EN_NT else 'vault')
    if not EN_NT: exe.chmod(0o755)
    return str(exe)

def instalar_activemq():
    z = HERR / 'activemq.zip'
    for i, u in enumerate(AMQ_URLS):
        try:
            descargar(u, z); break
        except Exception as ex:
            if i == len(AMQ_URLS) - 1: raise
            aviso(f'fallo {u}: {ex}')
    with zipfile.ZipFile(z) as f: f.extractall(HERR)
    z.unlink()
    d = next(HERR.glob('apache-activemq-*'))
    if not EN_NT:
        for b in (d / 'bin').iterdir(): b.chmod(0o755)
    return str(d)

def comprobar_local():
    """Devuelve (lista_de_faltantes, entorno_extra)."""
    faltan, extra = [], {}
    if not abierto(27017):
        faltan.append('MongoDB 7 no responde en 127.0.0.1:27017. Windows (PowerShell como administrador): winget install MongoDB.Server ; luego Start-Service MongoDB')
    v = buscar_vault()
    if not v and INSTALAR:
        try: v = instalar_vault()
        except Exception as ex: aviso(f'no se pudo descargar Vault: {ex}')
    if v: extra['VAULT_BIN'] = v
    else: faltan.append('No se encontro Vault. Use --instalar-infra o descargue Vault 1.18.5 y defina $env:VAULT_BIN')
    a = buscar_activemq()
    if not a and INSTALAR:
        try: a = instalar_activemq()
        except Exception as ex: aviso(f'no se pudo descargar ActiveMQ: {ex}')
    if a: extra['ACTIVEMQ_HOME'] = a
    else: faltan.append('No se encontro Apache ActiveMQ Classic 6.2.0. Use --instalar-infra o descargue el zip y defina $env:ACTIVEMQ_HOME')
    if not (shutil.which('java') or os.environ.get('JAVA_HOME')):
        faltan.append('No se encontro Java 17 o superior. Windows: winget install EclipseAdoptium.Temurin.17.JDK (abra una consola nueva despues)')
    if not shutil.which('node'):
        faltan.append('No se encontro Node 22 o superior (GraphQL Gateway). Windows: winget install OpenJS.NodeJS')
    return faltan, extra

def comprobar_docker():
    c, t = captura(['docker', 'info', '--format', '{{.ServerVersion}}'], timeout=40)
    if c: return [f'Docker no responde ({t[:120]}). Abra Docker Desktop y espere a que diga "Engine running".']
    c, t = captura(['docker', 'compose', 'version'])
    return [] if not c else ['Falta el plugin docker compose.']

# ---------------------------------------------------------------- 3. ejecucion
ESTADO = {'local': 'no ejecutado', 'compose': 'no ejecutado'}
SALIDA.mkdir(exist_ok=True)

def puertos_ocupados():
    return [p for p in (8443, 8080, 9201) if abierto(p)]

def correr_local():
    paso('MODO LOCAL (sin Docker)')
    faltan, extra = comprobar_local()
    if faltan:
        ESTADO['local'] = 'omitido: ' + ' | '.join(faltan)
        for f in faltan: aviso(f)
        return
    for k, v in extra.items(): info(f'{k} = {v}')
    cmd = [sys.executable, 'scripts/run_tests.py'] + (['--sin-carga'] if SIN_CARGA else [])
    info('bateria completa desde cero: unos 25 minutos (con --sin-carga, bastante menos)')
    c, _ = ejecutar(cmd, log=SALIDA / 'local-run_tests.txt', env=extra)
    ESTADO['local'] = 'terminado' if c == 0 else f'terminado con codigo {c}'
    ejecutar([sys.executable, 'scripts/stack.py', 'down', '--todo'], log=SALIDA / 'local-down.txt', env=extra)
    time.sleep(3)
    if puertos_ocupados(): aviso(f'quedan puertos ocupados despues de detener el modo local: {puertos_ocupados()}')

def correr_compose():
    paso('DOCKER COMPOSE')
    faltan = comprobar_docker()
    if faltan:
        ESTADO['compose'] = 'omitido: ' + ' | '.join(faltan)
        for f in faltan: aviso(f)
        return
    if puertos_ocupados():
        ESTADO['compose'] = f'omitido: puertos {puertos_ocupados()} ocupados (detenga el modo local: python scripts/stack.py down --todo)'
        aviso(ESTADO['compose']); return
    py = sys.executable
    (RAIZ / '.run').mkdir(exist_ok=True)
    (RAIZ / '.run' / 'credenciales-demo.json').unlink(missing_ok=True)
    EVID.mkdir(parents=True, exist_ok=True); RES.mkdir(parents=True, exist_ok=True)
    ejecutar([py, 'scripts/compose.py', 'preparar'])
    ejecutar([py, 'scripts/compose.py', 'down', '--borrar'], log=SALIDA / 'compose-down.txt')
    info('construyendo e iniciando (la primera vez tarda varios minutos) ...')
    c, _ = ejecutar([py, 'scripts/compose.py', 'up'], log=SALIDA / 'compose-up.txt')
    if c:
        ESTADO['compose'] = 'fallo en up'
        ejecutar([py, 'scripts/compose.py', 'logs'], log=SALIDA / 'compose-logs.txt', mostrar=False)
        aviso('up fallo: los registros quedaron en salida-pruebas/compose-logs.txt')
        ejecutar([py, 'scripts/compose.py', 'down'], mostrar=False); return
    c, _ = ejecutar([py, 'scripts/compose.py', 'semilla'], log=SALIDA / 'compose-semilla.txt')
    if c:
        ESTADO['compose'] = 'fallo en semilla'; ejecutar([py, 'scripts/compose.py', 'down'], mostrar=False); return
    c, t = ejecutar([py, 'scripts/compose.py', 'estado'], mostrar=True)
    (EVID / 'compose-estado.txt').write_text(t, encoding='utf-8')
    c, t = ejecutar([py, 'scripts/compose.py', 'probar'], log=EVID / 'compose-probar-salida.txt')
    ESTADO['compose'] = 'terminado' if c == 0 else f'terminado con codigo {c}'
    ejecutar([py, 'scripts/compose.py', 'down'], log=SALIDA / 'compose-down-final.txt', mostrar=False)

if not SOLO_COMPOSE: correr_local()
if not SOLO_LOCAL: correr_compose()

# ---------------------------------------------------------------- 4. resumen y paquete
paso('RESUMEN')
filas, fallas = [], []
for f in sorted(RES.glob('*.json')):
    if f.name.endswith('_metricas.json') or f.name == 'resumen.json' or f.stat().st_mtime < T0: continue      # solo lo ejecutado ahora
    try: d = json.load(open(f, encoding='utf-8'))
    except Exception: continue
    if 'casos' not in d: continue
    filas.append((d['suite'], d['ok'], d['total']))
    fallas += [f"{d['suite']}: {c['id']} -> {c['observado'][:140]}" for c in d['casos'] if c['estado'] != 'OK']
loc = [(s, o, t) for s, o, t in filas if not s.startswith('compose_')]
cmp_ = [(s, o, t) for s, o, t in filas if s.startswith('compose_')]
L = []
def sub(titulo, g):
    L.append(titulo)
    for s, o, t in g: L.append(f'  {s:28s} {o}/{t}')
    L.append(f'  {"TOTAL":28s} {sum(o for _, o, _ in g)}/{sum(t for _, _, t in g)}' if g else '  (sin resultados)')
sub('Modo local (esperado 193 en la bateria completa)', loc); sub('Docker Compose (esperado 28)', cmp_)
L.append(''); L.append(f"Local: {ESTADO['local']}"); L.append(f"Compose: {ESTADO['compose']}")
L.append(f'Duracion: {int((time.time() - T0) // 60)} min')
if fallas: L += ['', 'Pruebas en FALLA:'] + ['  ' + x for x in fallas]
resumen = '\n'.join(L)
print(resumen)
(SALIDA / 'resumen-pruebas.txt').write_text(resumen + '\n', encoding='utf-8')

# versiones del entorno (para el informe)
def v(cmd):
    c, t = captura(cmd)
    lineas = [x for x in t.splitlines() if x.strip() and not x.startswith('Picked up')]
    return lineas[0] if lineas and not c else 'no disponible'
env_txt = [f'Fecha (UTC): {time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}', f'Sistema: {platform.platform()}', f'Python: {sys.version.split()[0]}',
           f'Node: {v(["node", "--version"])}', f'Java: {v(["java", "-version"])}', f'Docker: {v(["docker", "version", "--format", "{{.Server.Version}}"])}',
           f'Docker Compose: {v(["docker", "compose", "version", "--short"])}']
vb = buscar_vault() if not SOLO_COMPOSE else None
env_txt.append('Vault: ' + (v([vb, 'version']) if vb else 'no disponible'))
am = buscar_activemq() if not SOLO_COMPOSE else None
env_txt.append('ActiveMQ: ' + (pathlib.Path(am).name if am else 'no disponible'))
try:
    import pymongo
    env_txt.append('MongoDB (modo local): ' + pymongo.MongoClient('127.0.0.1', 27017, serverSelectionTimeoutMS=2000).server_info()['version'])
except Exception:
    env_txt.append('MongoDB (modo local): no disponible')
(SALIDA / 'entorno.txt').write_text('\n'.join(env_txt) + '\n', encoding='utf-8')

zip_ = RAIZ / 'ENVIAR-RESULTADOS.zip'
with zipfile.ZipFile(zip_, 'w', zipfile.ZIP_DEFLATED) as z:
    for carpeta in (RES, EVID, SALIDA):
        if carpeta.exists():
            for f in sorted(carpeta.rglob('*')):
                if f.is_file() and f.name != '.gitkeep' and (carpeta == SALIDA or f.stat().st_mtime >= T0): z.write(f, f.relative_to(RAIZ).as_posix())
paso('LISTO')
info(f'Envie este archivo: {zip_}')
ok_todo = not fallas and not ESTADO['local'].startswith(('omitido', 'terminado con')) and not ESTADO['compose'].startswith(('omitido', 'fallo', 'terminado con'))
sys.exit(0 if ok_todo else 1)
