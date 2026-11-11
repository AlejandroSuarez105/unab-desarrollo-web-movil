"""Ejecuta TODAS las pruebas desde cero: detiene el sistema, borra datos y registros, levanta, siembra y corre cada suite.
Uso: python scripts/run_tests.py [--sin-carga] [--escala=completa]
Cada suite escribe tests/resultados/<suite>.json con lo realmente observado. Duracion: unos 20 minutos en escala reducida."""
import os, sys, time, json, shutil, subprocess, pathlib
BASE = pathlib.Path(__file__).resolve().parents[1]
RUN = pathlib.Path(os.environ.get('RUN_DIR', BASE / '.run'))
PY = sys.executable
ENV = dict(os.environ, RUN_DIR=str(RUN), PYTHONPATH=str(BASE / 'common'), PYTHONUTF8='1')
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(errors='replace')
RES = BASE / 'tests/resultados'
args = sys.argv[1:]

def paso(titulo): print(f'\n===== {titulo} =====', flush=True)
def correr(cmd, cwd, **extra):
    e = dict(ENV, **{k: str(v) for k, v in extra.items()})
    r = subprocess.run(cmd, cwd=cwd, env=e)
    return r.returncode

paso('Reinicio: detener, borrar datos y registros')
correr([PY, 'scripts/stack.py', 'down', '--todo'], BASE)
time.sleep(2)
shutil.rmtree(RUN / 'logs', ignore_errors=True); shutil.rmtree(RUN / 'tokens', ignore_errors=True)
(RUN / 'credenciales-demo.json').unlink(missing_ok=True)
for f in RES.glob('*.json'):
    f.unlink()
shutil.rmtree(RES.parent / 'evidencia', ignore_errors=True)
(RES.parent / 'evidencia').mkdir(exist_ok=True)
if (RUN / 'pids.json').exists(): (RUN / 'pids.json').unlink()

paso('Arranque (limites del gateway multiplicados por 50 para las pruebas funcionales)')
assert correr([PY, 'scripts/stack.py', 'up'], BASE, RL_FACTOR=50) == 0
paso('Datos de ejemplo (ficticios)')
assert correr([PY, 'scripts/seed.py'], BASE) == 0

codigos = {}
for nombre, archivo in (('seguridad', 'suite_seguridad.py'), ('negocio', 'suite_negocio.py'), ('graphql', 'suite_graphql.py'), ('e2e_frontend', 'e2e_frontend.py'), ('gateway', 'suite_gateway.py'), ('demo', 'demo_flujos.py'), ('retencion', 'suite_retencion.py')):
    paso(f'Suite {nombre}')
    codigos[nombre] = correr([PY, archivo], BASE / 'tests', RL_FACTOR=50)

if '--sin-carga' not in args:
    correr([PY, 'scripts/stack.py', 'restart', 'gateway'], BASE, RL_FACTOR=5000)
    paso('Carga C1-C9'); codigos['carga'] = correr([PY, 'carga.py'] + [a for a in args if a.startswith('--escala')], BASE / 'carga', RL_FACTOR=5000)
    paso('Fallos F1-F4, F6, F7'); codigos['fallos'] = correr([PY, 'fallos.py', 'F1', 'F2', 'F3', 'F4', 'F6', 'F7'], BASE / 'carga', RL_FACTOR=5000)
    paso('Fallo F5 (detiene Vault)'); codigos['fallos_f5'] = correr([PY, 'fallos.py', 'F5'], BASE / 'carga', RL_FACTOR=5000)

paso('Resumen')
total = ok = 0
for f in sorted(RES.glob('*.json')):
    if f.name.endswith('_metricas.json'): continue
    d = json.load(open(f)); total += d['total']; ok += d['ok']
    print(f'{d["suite"]:14s} {d["ok"]}/{d["total"]}')
print(f'TOTAL {ok}/{total}')
json.dump({'ejecutado': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'codigos_de_salida': codigos, 'ok': ok, 'total': total}, open(RES / 'resumen.json', 'w'), indent=1)
