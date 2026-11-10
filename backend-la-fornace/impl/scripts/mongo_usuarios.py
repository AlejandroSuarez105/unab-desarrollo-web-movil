"""Crea en MongoDB (con autenticacion activada) un usuario por sistema con permiso de lectura y escritura SOLO sobre su base.
Las credenciales salen de Vault (secret/<sistema>/db, creadas por vault_init.py); si el usuario ya existe se le actualiza la contrasena para que
Vault y MongoDB coincidan (Vault en modo desarrollo genera valores nuevos cuando se reinicia). Corre en el contenedor 'preparacion', cada vez.
Variables: MONGO_HOST (mongo), MONGO_ROOT_PASSWORD, VAULT_ADDR, VAULT_ROOT_TOKEN_FILE."""
import os, sys, time, json, pathlib
import httpx, pymongo
from pymongo.errors import OperationFailure, PyMongoError
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'common'))
from fornace.topology import SISTEMAS

ADDR = os.environ['VAULT_ADDR'].rstrip('/')
ROOT = open(os.environ['VAULT_ROOT_TOKEN_FILE']).read().strip()
cli = pymongo.MongoClient(os.environ.get('MONGO_HOST', 'mongo'), 27017, username='root', password=os.environ['MONGO_ROOT_PASSWORD'],
                          authSource='admin', serverSelectionTimeoutMS=3000)

t0, fallo_auth = time.time(), 0
while True:
    try:
        cli.admin.command('ping'); break
    except OperationFailure as e:
        fallo_auth += 1
        if e.code in (18, 13) and fallo_auth >= 15:
            sys.exit('MongoDB rechaza el usuario root: el volumen de datos se creo con otra clave o sin usuarios (version anterior). '
                     'Ejecute: python scripts/compose.py down --borrar   y luego   python scripts/compose.py up')
    except PyMongoError:
        pass
    if time.time() - t0 > 150: sys.exit('MongoDB no responde')
    time.sleep(2)

creados, actualizados = [], []
for s in SISTEMAS:
    r = httpx.get(f'{ADDR}/v1/secret/data/{s}/db', headers={'X-Vault-Token': ROOT}, timeout=5)
    r.raise_for_status()
    c = r.json()['data']['data']
    base = f'{s}_db'
    roles = [{'role': 'readWrite', 'db': base}]
    if cli[base].command('usersInfo', c['usuario'])['users']:
        cli[base].command('updateUser', c['usuario'], pwd=c['clave'], roles=roles); actualizados.append(c['usuario'])
    else:
        cli[base].command('createUser', c['usuario'], pwd=c['clave'], roles=roles); creados.append(c['usuario'])
print(json.dumps({'usuarios_creados': creados, 'usuarios_actualizados': actualizados}), flush=True)
