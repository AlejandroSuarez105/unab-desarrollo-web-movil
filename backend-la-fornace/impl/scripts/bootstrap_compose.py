"""Preparacion del entorno en Docker Compose (corre una vez, antes de los sistemas):
1) espera a Vault y a la base, 2) genera la CA y un certificado por componente, 3) crea los secretos en Vault con valores al azar
y un token de solo lectura por componente, y los usuarios de MongoDB (uno por sistema, solo sobre su base), 4) deja en el volumen 'pki' una carpeta por componente con SOLO lo suyo:
ca.crt, tls.crt, tls.key y vault.token (y para el broker, su configuracion con usuarios y permisos). Nada de esto queda en el repositorio."""
import os, sys, time, socket, shutil, subprocess, pathlib, urllib.request

VAULT = os.environ.get('VAULT_ADDR', 'http://vault:8200')
MONGO = os.environ.get('MONGO_HOST', 'mongo')
RAIZ_DEV = os.environ.get('VAULT_DEV_ROOT_TOKEN', '')
PKI = pathlib.Path('/pki')
TRABAJO = PKI / '_trabajo'      # dentro del volumen pero fuera de las carpetas que se montan en cada sistema: la CA sobrevive a un reinicio
COMPONENTES = ['api-gateway', 'graphql-gateway', 'auth-service', 'clients-service', 'inventory-service', 'orders-service',
               'payments-service', 'dispatch-service', 'notifications-service', 'pasarela-prueba', 'correo-prueba']
UID = 10001

def esperar(nombre, fn, seg=90):
    t0 = time.time()
    while time.time() - t0 < seg:
        try:
            if fn(): print(f'{nombre}: listo', flush=True); return
        except Exception: pass
        time.sleep(1)
    sys.exit(f'{nombre}: no responde')

if not RAIZ_DEV:
    sys.exit('Falta VAULT_DEV_ROOT_TOKEN (ejecute: python scripts/compose.py preparar)')
esperar('vault', lambda: urllib.request.urlopen(VAULT + '/v1/sys/health', timeout=2).status in (200, 429))
esperar('base de datos', lambda: socket.create_connection((MONGO, 27017), timeout=2).close() or True)

TRABAJO.mkdir(parents=True, exist_ok=True); os.chmod(TRABAJO, 0o700)
raiz = TRABAJO / 'vault-root.token'
raiz.write_text(RAIZ_DEV); os.chmod(raiz, 0o600)
env = dict(os.environ, RUN_DIR=str(TRABAJO), VAULT_ADDR=VAULT, VAULT_ROOT_TOKEN_FILE=str(raiz))
subprocess.run(['bash', '/app/scripts/certs.sh'], check=True, env=env, stdout=subprocess.DEVNULL)
subprocess.run([sys.executable, '/app/scripts/vault_init.py'], check=True, env=env)
# un usuario de MongoDB por sistema, solo con permiso sobre su base (las claves salen de Vault)
subprocess.run([sys.executable, '/app/scripts/mongo_usuarios.py'], check=True, env=env)

def entregar(carpeta, archivos):
    """Escribe los archivos de un componente SIN borrar su carpeta: los contenedores en ejecucion la tienen montada y deben seguir viendola."""
    d = PKI / carpeta
    d.mkdir(parents=True, exist_ok=True)
    for destino, origen, modo in archivos:
        shutil.copyfile(origen, d / destino); os.chmod(d / destino, modo); os.chown(d / destino, UID, UID)
    for extra in set(x.name for x in d.iterdir()) - {a[0] for a in archivos}:
        (d / extra).unlink()
    os.chmod(d, 0o500); os.chown(d, UID, UID)

ca = TRABAJO / 'certs/ca.crt'
for c in COMPONENTES:
    entregar(c, [('ca.crt', ca, 0o444), ('tls.crt', TRABAJO / f'certs/{c}.crt', 0o444), ('tls.key', TRABAJO / f'certs/{c}.key', 0o400),
                 ('vault.token', TRABAJO / f'tokens/{c}.token', 0o400)])
entregar('broker', [('activemq.xml', TRABAJO / 'activemq.xml', 0o400)])
# herramientas de laboratorio (semilla, bandeja de correo de prueba, pruebas): CA y token raiz del Vault de desarrollo
entregar('herramientas', [('ca.crt', ca, 0o444), ('vault-root.token', raiz, 0o400)])
salida = pathlib.Path('/salida')
if salida.exists():
    shutil.copyfile(ca, salida / 'ca.crt')       # certificado publico de la CA del laboratorio (no es secreto): para curl y el navegador
print('entorno preparado', flush=True)
