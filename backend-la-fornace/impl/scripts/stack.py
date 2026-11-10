"""Arranca, detiene y consulta el entorno local completo (modo nativo: los servicios son procesos del equipo).
Uso: python stack.py up|down|status [--sin-infra]
Infraestructura: MongoDB, HashiCorp Vault y ActiveMQ reales instalados en el equipo (sin Docker). Variables:
  VAULT_BIN       ruta del ejecutable de Vault (vault.exe en Windows)
  ACTIVEMQ_HOME   carpeta de Apache ActiveMQ Classic 6.2.0
MongoDB debe estar en ejecucion en 127.0.0.1:27017 (en Windows, el servicio MongoDB). Vault y ActiveMQ los inicia este script.
Todo lo que no es secreto se define aqui; los secretos salen de Vault (ver vault_init.py)."""
import os, sys, time, json, signal, shutil, subprocess, pathlib, ssl, socket, urllib.request

BASE = pathlib.Path(__file__).resolve().parents[1]
RUN = pathlib.Path(os.environ.get('RUN_DIR', BASE / '.run'))
LOGS = RUN / 'logs'
EN_NT = os.name == 'nt'
VAULT_BIN = os.environ.get('VAULT_BIN', 'vault')
ACTIVEMQ_HOME = pathlib.Path(os.environ.get('ACTIVEMQ_HOME', '.'))
PY = sys.executable

PUERTOS = {'auth': 9101, 'clients': 9102, 'inventory': 9103, 'orders': 9104, 'payments': 9105, 'dispatch': 9106,
           'notifications': 9107, 'graphql': 9108, 'pasarela': 9201, 'correo': 9202, 'gateway': 8443, 'frontend': 8080}
INFRA = {'mongo': 27017, 'vault': 8200, 'broker': 61613}
TOKEN_RAIZ = 'root-dev-laboratorio'                      # solo para el Vault de desarrollo del laboratorio
NODOS = {  # nombre -> (directorio, comando, componente para certificado y token)
    'auth': ('auth', 'auth-service'), 'clients': ('clients', 'clients-service'), 'inventory': ('inventory', 'inventory-service'),
    'orders': ('orders', 'orders-service'), 'payments': ('payments', 'payments-service'), 'dispatch': ('dispatch', 'dispatch-service'),
    'notifications': ('notifications', 'notifications-service'), 'pasarela': ('pasarela_prueba', 'pasarela-prueba'),
    'correo': ('correo_prueba', 'correo-prueba'), 'gateway': ('api_gateway', 'api-gateway'), 'graphql': ('graphql_gateway', 'graphql-gateway'),
}
ORDEN = ['correo', 'pasarela', 'notifications', 'auth', 'inventory', 'dispatch', 'clients', 'orders', 'payments', 'graphql', 'gateway']

def entorno(nombre, comp):
    e = dict(os.environ)
    e.update({
        'PORT': str(PUERTOS[nombre]), 'HOST': '127.0.0.1', 'CA_FILE': str(RUN / 'certs/ca.crt'),
        'TLS_CERT': str(RUN / f'certs/{comp}.crt'), 'TLS_KEY': str(RUN / f'certs/{comp}.key'),
        'VAULT_ADDR': 'http://127.0.0.1:8200', 'VAULT_TOKEN_FILE': str(RUN / f'tokens/{comp}.token'),
        'MONGO_URL': 'mongodb://127.0.0.1:27017', 'MONGO_AUTH': os.environ.get('MONGO_AUTH', '0'),
        'STOMP_HOST': '127.0.0.1', 'STOMP_PORT': '61613', 'LOG_DIR': str(LOGS),
        'FRONTEND_URL': 'http://127.0.0.1:8080', 'FRONTEND_ORIGIN': 'http://127.0.0.1:8080',
        'COMUNAS_COBERTURA': 'Maipú,Cerrillos,Pudahuel,Estación Central',
        'PYTHONPATH': str(BASE / 'common'), 'PYTHONUTF8': '1',
    })
    for k, v in PUERTOS.items():
        e['URL_' + k.upper()] = f'https://127.0.0.1:{v}'
    e['RL_FACTOR'] = os.environ.get('RL_FACTOR', '1')
    e['PASARELA_PUBLICA'] = f'https://127.0.0.1:{PUERTOS["pasarela"]}'
    e['URL_GATEWAY'] = f'https://127.0.0.1:{PUERTOS["gateway"]}'
    if nombre == 'gateway' and os.environ.get('GATEWAY_HTTP') == '1':
        e.pop('TLS_CERT'); e.pop('TLS_KEY')
    return e

def esperar(puerto, seg=25):
    t0 = time.time()
    ctx = ssl.create_default_context(cafile=str(RUN / 'certs/ca.crt'))
    while time.time() - t0 < seg:
        try:
            with urllib.request.urlopen(f'https://127.0.0.1:{puerto}/health', context=ctx, timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.4)
    return False

def abierto(p):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(('127.0.0.1', p)) == 0

def _lanzar(cmd, log, env=None, cwd=None):
    """Proceso en segundo plano, desligado de esta consola; su salida va al archivo de registro."""
    kw = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if EN_NT else {'start_new_session': True}
    return subprocess.Popen(cmd, env=env, cwd=cwd, stdout=open(log, 'a'), stderr=subprocess.STDOUT, **kw)

def _infra_local():
    """MongoDB (ya en ejecucion en el equipo) y Vault en modo desarrollo. El broker se arranca despues de vault_init."""
    (RUN / 'infra').mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    raiz = RUN / 'vault-root.token'
    raiz.write_text(TOKEN_RAIZ); os.chmod(raiz, 0o600)
    if not abierto(27017):
        sys.exit('MongoDB no responde en 127.0.0.1:27017. En Windows: Start-Service MongoDB (PowerShell como administrador).')
    procs = {}
    if not abierto(8200):
        procs['vault'] = _lanzar([VAULT_BIN, 'server', '-dev', f'-dev-root-token-id={TOKEN_RAIZ}', '-dev-listen-address=127.0.0.1:8200'], LOGS / 'vault.log')
        _esperar('vault', lambda: urllib.request.urlopen('http://127.0.0.1:8200/v1/sys/health', timeout=2).status in (200, 429), seg=30)
    return procs

def broker_local():
    """ActiveMQ real con la configuracion generada por vault_init (.run/activemq.xml). Devuelve el proceso."""
    xml = RUN / 'activemq.xml'
    if not xml.exists(): sys.exit('Falta .run/activemq.xml: ejecute primero vault_init.py (stack.py up lo hace).')
    if abierto(61613): _liberar_puerto(61613)               # un broker de una ejecucion anterior tiene usuarios que ya no existen
    url = 'xbean:file:' + xml.as_posix()
    cmd = [str(ACTIVEMQ_HOME / 'bin' / 'activemq.bat'), 'start', url] if EN_NT else [str(ACTIVEMQ_HOME / 'bin' / 'activemq'), 'console', url]
    p = _lanzar(cmd, LOGS / 'activemq.log', cwd=str(ACTIVEMQ_HOME))
    _esperar('broker', lambda: abierto(61613) and p.poll() is None, seg=90)
    return p

def datos_broker():
    return (RUN / 'infra' / 'activemq-data').as_posix()

def _esperar(texto, fn, seg=60):
    t0 = time.time()
    while time.time() - t0 < seg:
        try:
            if fn(): return
        except Exception: pass
        time.sleep(0.5)
    sys.exit(f'{texto}: no responde en {seg} s')

def infra():
    return _infra_local()

def up(sin_infra=False):
    LOGS.mkdir(parents=True, exist_ok=True)
    pids = json.load(open(RUN / 'pids.json')) if (RUN / 'pids.json').exists() else {}
    if not sin_infra:
        for k, p in infra().items(): pids[k] = p.pid
    e0 = dict(os.environ, RUN_DIR=str(RUN), VAULT_ADDR='http://127.0.0.1:8200', VAULT_ROOT_TOKEN_FILE=str(RUN / 'vault-root.token'), PYTHONUTF8='1')
    e0['ACTIVEMQ_DATA'] = datos_broker()
    if EN_NT: generar_certs()
    else: subprocess.run(['bash', str(BASE / 'scripts/certs.sh')], check=True, env=e0, stdout=subprocess.DEVNULL)
    subprocess.run([PY, str(BASE / 'scripts/vault_init.py')], check=True, env=e0)
    if not sin_infra: pids['broker'] = broker_local().pid
    solo = os.environ.get('STACK_SOLO')
    for n in ORDEN:
        if solo and n not in solo.split(','): continue
        d, comp = NODOS[n]
        if n in pids and _vivo(pids[n]): continue
        _liberar_puerto(PUERTOS[n])                         # un proceso huerfano en el puerto haria pasar la espera sin ser el servicio que se arranca
        cmd = ['node', 'server.js'] if (BASE / 'services' / d / 'server.js').exists() else [PY, '-X', 'utf8', '-I', str(BASE / 'services' / d / 'main.py')]
        p = _lanzar(cmd, LOGS / f'{comp}.out', env=entorno(n, comp), cwd=str(BASE / 'services' / d))
        pids[n] = p.pid
        ok = esperar(PUERTOS[n]) and p.poll() is None
        print(f'{comp:22s} puerto {PUERTOS[n]}  {"OK" if ok else "NO RESPONDE"}')
        if not ok: break
    if not solo or 'frontend' in solo.split(','):
        if not abierto(8080):
            p = _lanzar([PY, str(BASE / 'scripts/serve_frontend.py')], LOGS / 'frontend.out', env=dict(os.environ, PORT='8080'))
            pids['frontend'] = p.pid
        print(f'{"frontend":22s} puerto 8080  OK')
    json.dump(pids, open(RUN / 'pids.json', 'w'))

def _vivo(pid):
    if EN_NT:                                               # os.kill(pid, 0) termina el proceso en Windows: se consulta con psutil
        import psutil
        return psutil.pid_exists(pid) and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    try: os.kill(pid, 0)
    except OSError: return False
    try:                                                    # un proceso zombi ya termino
        with open(f'/proc/{pid}/stat') as f: return f.read().rsplit(')', 1)[1].split()[0] != 'Z'
    except OSError: return True

def _matar(pid, espera=8):
    """Detiene el proceso y sus hijos. POSIX: SIGTERM al grupo y, si no termina, SIGKILL. Windows: terminacion del arbol.
    Evita que un servidor que cierra despacio siga ocupando el puerto cuando se arranca el siguiente."""
    if EN_NT:
        import psutil
        try: raiz = psutil.Process(pid); todos = raiz.children(recursive=True) + [raiz]
        except psutil.NoSuchProcess: return
        for q in todos:
            try: q.kill()
            except psutil.Error: pass
        psutil.wait_procs(todos, timeout=espera)
        return
    try: pgid = os.getpgid(pid)
    except OSError: return
    try: os.killpg(pgid, signal.SIGTERM)
    except OSError: return
    fin = time.time() + espera
    while time.time() < fin and _vivo(pid): time.sleep(0.1)
    if _vivo(pid):
        try: os.killpg(pgid, signal.SIGKILL)
        except OSError: pass
        for _ in range(30):
            if not _vivo(pid): break
            time.sleep(0.1)

def _liberar_puerto(puerto):
    """Detiene lo que escuche en el puerto (proceso de otra sesion o que quedo huerfano), para que el arranque
    cree el suyo con su registro de procesos."""
    try: import psutil
    except ImportError: return
    try: conexiones = psutil.net_connections(kind='tcp')
    except psutil.Error: return
    for c in conexiones:
        if c.status == 'LISTEN' and c.laddr.port == puerto and c.pid: _matar(c.pid, espera=2)
    for _ in range(50):
        if not abierto(puerto): return
        time.sleep(0.1)

def generar_certs():
    """CA del proyecto y un certificado por componente (equivale a certs.sh, sin depender de bash ni de openssl; se usa en Windows)."""
    import datetime, ipaddress
    from cryptography import x509
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    D = RUN / 'certs'; D.mkdir(parents=True, exist_ok=True)
    ahora = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)
    def guardar_llave(k, f): f.write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    def nombre(cn): return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    if not (D / 'ca.crt').exists() or not (D / 'ca.key').exists():
        ck = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cc = (x509.CertificateBuilder().subject_name(nombre('Fornace CA (desarrollo)')).issuer_name(nombre('Fornace CA (desarrollo)'))
              .public_key(ck.public_key()).serial_number(x509.random_serial_number()).not_valid_before(ahora).not_valid_after(ahora + datetime.timedelta(days=365))
              .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
              .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
              .add_extension(x509.SubjectKeyIdentifier.from_public_key(ck.public_key()), critical=False)
              .sign(ck, hashes.SHA256()))
        guardar_llave(ck, D / 'ca.key'); (D / 'ca.crt').write_bytes(cc.public_bytes(serialization.Encoding.PEM))
    ck = serialization.load_pem_private_key((D / 'ca.key').read_bytes(), None)
    cc = x509.load_pem_x509_certificate((D / 'ca.crt').read_bytes())
    for _, comp in NODOS.values():
        if (D / f'{comp}.crt').exists() and (D / f'{comp}.key').exists(): continue
        k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        c = (x509.CertificateBuilder().subject_name(nombre(comp)).issuer_name(cc.subject).public_key(k.public_key())
             .serial_number(x509.random_serial_number()).not_valid_before(ahora).not_valid_after(ahora + datetime.timedelta(days=365))
             .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'), x509.DNSName(comp), x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
             .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=False)
             .add_extension(x509.KeyUsage(True, False, True, False, False, False, False, False, False), critical=False)
             .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
             .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ck.public_key()), critical=False)
             .add_extension(x509.SubjectKeyIdentifier.from_public_key(k.public_key()), critical=False)
             .sign(ck, hashes.SHA256()))
        guardar_llave(k, D / f'{comp}.key'); (D / f'{comp}.crt').write_bytes(c.public_bytes(serialization.Encoding.PEM))
    print(f'certificados en {D}')

def _vaciar_mongo():
    """Elimina solo las bases del proyecto (terminan en _db) para empezar sin datos."""
    try:
        import pymongo
        c = pymongo.MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=3000)
        for n in c.list_database_names():
            if n.endswith('_db'): c.drop_database(n)
    except Exception as e:
        print(f'no se pudieron vaciar las bases: {e}')

def down(todo=False):
    if todo:
        for pto in (8200, 61613): _liberar_puerto(pto)          # MongoDB es un servicio del equipo: no se detiene, solo se vacian las bases del proyecto
        _vaciar_mongo()
        shutil.rmtree(RUN / 'infra' / 'activemq-data', ignore_errors=True)
    if not (RUN / 'pids.json').exists(): return
    pids = json.load(open(RUN / 'pids.json'))
    for n, pid in list(pids.items()):
        if n in ('mongo', 'vault', 'broker') and not todo: continue
        _matar(pid)
        pids.pop(n)
    for n in PUERTOS:                                       # nada que no este en pids.json debe quedar escuchando
        if n != 'frontend' or todo: _liberar_puerto(PUERTOS[n])
    json.dump(pids, open(RUN / 'pids.json', 'w'))
    print('detenido')

def stop(nombre):
    pids = json.load(open(RUN / 'pids.json'))
    if nombre in pids: _matar(pids[nombre], espera=2)       # una caida simulada es abrupta: no se espera a que se vacien las conexiones abiertas
    _liberar_puerto({**PUERTOS, **INFRA}[nombre])
    print(f'{nombre} detenido')

def restart(nombre):
    pids = json.load(open(RUN / 'pids.json'))
    if nombre in pids: _matar(pids[nombre], espera=2)
    _liberar_puerto(PUERTOS[nombre])
    d, comp = NODOS[nombre]
    cmd = ['node', 'server.js'] if (BASE / 'services' / d / 'server.js').exists() else [PY, '-X', 'utf8', '-I', str(BASE / 'services' / d / 'main.py')]
    p = _lanzar(cmd, LOGS / f'{comp}.out', env=entorno(nombre, comp), cwd=str(BASE / 'services' / d))
    pids[nombre] = p.pid
    json.dump(pids, open(RUN / 'pids.json', 'w'))
    print(f'{comp} reiniciado: {"OK" if esperar(PUERTOS[nombre]) and p.poll() is None else "NO RESPONDE"}')

def infra_arrancar():
    pids = json.load(open(RUN / 'pids.json'))
    for k, p in infra().items(): pids[k] = p.pid
    if (RUN / 'activemq.xml').exists() and not abierto(61613): pids['broker'] = broker_local().pid
    json.dump(pids, open(RUN / 'pids.json', 'w'))
    print('infraestructura activa')

def status():
    for n, p in PUERTOS.items():
        print(f'{n:14s} {p}  {"activo" if abierto(p) else "inactivo"}')
    for n, p in (('mongo', 27017), ('vault', 8200), ('broker', 61613)):
        print(f'{n:14s} {p}  {"activo" if abierto(p) else "inactivo"}')

if __name__ == '__main__':
    a = sys.argv[1] if len(sys.argv) > 1 else 'status'
    {'up': lambda: up('--sin-infra' in sys.argv), 'down': lambda: down('--todo' in sys.argv), 'status': status, 'restart': lambda: restart(sys.argv[2]), 'stop': lambda: stop(sys.argv[2]), 'infra': infra_arrancar}[a]()
