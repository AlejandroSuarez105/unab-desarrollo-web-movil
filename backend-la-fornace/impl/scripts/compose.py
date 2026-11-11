"""Ayudante del despliegue en Docker Compose (funciona igual en Linux, macOS y Windows). Requiere Docker con el plugin compose.
Uso: python scripts/compose.py <orden>
  preparar      crea .env con un token de Vault de desarrollo y una clave root de MongoDB al azar (una sola vez)
  up            construye e inicia todo (espera a que los sistemas esten sanos)
  semilla       carga los datos de ejemplo; las contrasenas quedan en .run/credenciales-demo.json
  bandeja <correo>   muestra los correos de prueba enviados a ese correo (por ejemplo, el enlace de confirmacion)
  estado        muestra contenedores y puertos publicados
  probar        pruebas del despliegue: puertos publicados, red privada interna, acceso directo rechazado y compra completa dentro de la red privada (requiere up y semilla)
  logs [servicio]    registros de un servicio
  down          detiene todo (agregue --borrar para eliminar tambien los datos)
"""
import os, sys, secrets, pathlib, subprocess, time, json

RAIZ = pathlib.Path(__file__).resolve().parents[1]
os.chdir(RAIZ)
args = sys.argv[1:]
if not args:
    print(__doc__); sys.exit(0)
orden, resto = args[0], args[1:]
DC = ['docker', 'compose']

def run(cmd, **kw):
    return subprocess.run(cmd, cwd=RAIZ, **kw)

def herramienta(cmd, **kw):
    """Ejecuta un comando en el contenedor 'herramientas' (dentro de la red privada), reconstruyendo la imagen si cambio algo."""
    run(DC + ['--profile', 'herramientas', 'build', '-q', 'herramientas'], stdout=subprocess.DEVNULL)
    return run(DC + ['--profile', 'herramientas', 'run', '--rm', '-T', 'herramientas'] + cmd, **kw)

def preparar(silencioso=False):
    """Crea o completa .env: token raiz de Vault de desarrollo y clave root de MongoDB, ambos al azar (una sola vez)."""
    import re
    ruta = RAIZ / '.env'
    texto = ruta.read_text() if ruta.exists() else (RAIZ / '.env.example').read_text()
    cambios = []
    for clave, valor in (('VAULT_DEV_ROOT_TOKEN', f'bao-dev-{secrets.token_urlsafe(24)}'), ('MONGO_ROOT_PASSWORD', secrets.token_urlsafe(24))):
        m = re.search(rf'^{clave}=(.*)$', texto, re.M)
        if m and m.group(1).strip():
            continue
        texto = re.sub(rf'^{clave}=.*$', f'{clave}={valor}', texto, flags=re.M) if m else texto.rstrip('\n') + f'\n{clave}={valor}\n'
        cambios.append(clave)
    if not cambios:
        if not silencioso: print('.env ya existe')
        return
    ruta.write_text(texto); os.chmod(ruta, 0o600)
    print('.env creado o completado con valores al azar para: ' + ', '.join(cambios) + ' (no se versiona)')
    try:
        hay_volumen = 'MONGO_ROOT_PASSWORD' in cambios and run(DC + ['volume', 'inspect', 'fornace_mongo-datos'], capture_output=True).returncode == 0
    except OSError:
        hay_volumen = False
    if hay_volumen and not silencioso:
        print('AVISO: existe un volumen de datos creado sin autenticacion. Ejecute primero: python scripts/compose.py down --borrar')

def esperar_sano(seg=240):
    t0 = time.time()
    while time.time() - t0 < seg:
        r = run(DC + ['ps', '--format', 'json'], capture_output=True, text=True)
        filas = [json.loads(l) for l in r.stdout.splitlines() if l.strip().startswith('{')]
        faltan = [f['Service'] for f in filas if f.get('Health') in ('starting', 'unhealthy') or (f.get('State') != 'running' and f['Service'] != 'preparacion')] if filas else ['?']
        if filas and not faltan:
            print('todos los servicios estan sanos'); return True
        time.sleep(3)
    print('algunos servicios no quedaron sanos:', faltan); return False

if orden in ('estado', 'logs', 'down', 'semilla', 'bandeja'):
    preparar(silencioso=True)          # docker compose exige las variables de .env incluso para estado y down
if orden == 'preparar':
    preparar()
elif orden == 'up':
    preparar()
    if run(DC + ['up', '-d', '--build']).returncode: sys.exit(1)
    sys.exit(0 if esperar_sano() else 1)
elif orden == 'semilla':
    (RAIZ / '.run').mkdir(exist_ok=True)
    sys.exit(herramienta(['python', 'scripts/seed.py']).returncode)
elif orden == 'bandeja':
    sys.exit(herramienta(['python', 'scripts/bandeja.py'] + resto).returncode)
elif orden == 'estado':
    run(DC + ['ps', '--format', 'table {{.Service}}\t{{.State}}\t{{.Health}}\t{{.Ports}}'])
elif orden == 'probar':
    sys.exit(run([sys.executable, 'tests/suite_compose.py']).returncode)
elif orden == 'logs':
    run(DC + ['logs', '--tail', '100'] + resto)
elif orden == 'down':
    run(DC + ['down'] + (['-v'] if '--borrar' in resto else []))
else:
    print(__doc__)
