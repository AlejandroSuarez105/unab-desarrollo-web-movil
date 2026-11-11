"""Muestra los correos de prueba enviados a un correo (proveedor de correo simulado). Solo laboratorio: lee la clave de la bandeja en Vault
con el token raiz del modo desarrollo. Uso: python scripts/bandeja.py <correo>   (dentro de la red privada: python scripts/compose.py bandeja <correo>)"""
import os, sys, json, pathlib, httpx

if len(sys.argv) < 2:
    sys.exit('Uso: bandeja.py <correo>')
RUN = pathlib.Path(os.environ.get('RUN_DIR', pathlib.Path(__file__).resolve().parents[1] / '.run'))
ca = os.environ.get('CA_FILE') or str(RUN / 'certs/ca.crt')
vault = os.environ.get('VAULT_ADDR', 'http://127.0.0.1:8200').rstrip('/')
raiz = open(os.environ.get('VAULT_ROOT_TOKEN_FILE', RUN / 'vault-root.token')).read().strip()
clave = httpx.get(f'{vault}/v1/secret/data/notifications/mail', headers={'X-Vault-Token': raiz}, timeout=5).json()['data']['data']['actual']
correo = os.environ.get('URL_CORREO', 'https://127.0.0.1:9202').rstrip('/')
r = httpx.get(correo + '/bandeja', params={'para': sys.argv[1]}, headers={'X-API-Key': clave}, verify=ca, timeout=5)
for m in r.json():
    print(json.dumps({k: m.get(k) for k in ('para', 'asunto', 'cuerpo')}, ensure_ascii=False, indent=1))
if not r.json():
    print('(sin correos para ese destino)')
