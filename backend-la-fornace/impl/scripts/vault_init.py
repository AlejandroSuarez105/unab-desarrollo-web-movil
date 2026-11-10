"""Inicializa Vault: politicas de solo lectura por componente, un token por componente y los secretos del sistema.
Los valores se generan al azar en este momento; no existen en el repositorio. Los tokens se escriben en $RUN_DIR/tokens (600).
Uso: python vault_init.py [--rotar] ; requiere VAULT_ADDR y VAULT_ROOT_TOKEN_FILE."""
import os, sys, json, secrets, pathlib
import httpx
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'common'))
from fornace.topology import PARES, SISTEMAS, lecturas

ADDR = os.environ['VAULT_ADDR'].rstrip('/')
ROOT = open(os.environ['VAULT_ROOT_TOKEN_FILE']).read().strip()
RUN = pathlib.Path(os.environ.get('RUN_DIR', pathlib.Path(__file__).resolve().parents[1] / '.run'))
H = {'X-Vault-Token': ROOT}

def api(metodo, ruta, **kw):
    r = httpx.request(metodo, f'{ADDR}/v1/{ruta}', headers=H, timeout=5, **kw)
    return r

def existe(path):
    return api('GET', f'secret/data/{path}').status_code == 200

def escribir(path, datos):
    r = api('POST', f'secret/data/{path}', json={'data': datos})
    r.raise_for_status()

def rand():
    return secrets.token_urlsafe(32)

def main():
    rotar = '--rotar' in sys.argv
    # montaje KV v2 (en modo desarrollo ya existe en secret/)
    r = api('GET', 'sys/mounts')
    if 'secret/' not in r.json().get('data', r.json()):
        api('POST', 'sys/mounts/secret', json={'type': 'kv', 'options': {'version': '2'}}).raise_for_status()
    # secretos entre sistemas: par propio por llamador-llamado y uno por destino del gateway
    nuevos = []
    refs = [f'services/{ref}' for ref in PARES.values()] + [f'services/gateway-to-{d}' for d in SISTEMAS + ['graphql']]
    for p in refs:
        if rotar or not existe(p):
            ant = api('GET', f'secret/data/{p}')
            previo = ant.json()['data']['data']['actual'] if ant.status_code == 200 else None
            escribir(p, {'actual': rand(), 'anterior': previo or ''})
            nuevos.append(p)
    for p, campos in {
        'payments/webhook': ['actual'], 'payments/provider': ['actual'], 'notifications/mail': ['actual'],
    }.items():
        if rotar or not existe(p):
            escribir(p, {'actual': rand(), 'anterior': ''}); nuevos.append(p)
    for p in ('orders/activemq', 'dispatch/activemq'):
        if not existe(p):
            escribir(p, {'usuario': p.split('/')[0], 'clave': rand()}); nuevos.append(p)
    for s in SISTEMAS:
        p = f'{s}/db'
        if not existe(p):
            escribir(p, {'usuario': f'{s}_user', 'clave': rand()}); nuevos.append(p)
    # politicas y tokens por componente
    def _token_vigente(f):
        """Un token de una ejecucion anterior no sirve si Vault (modo desarrollo, en memoria) se reinicio: se vuelve a crear."""
        try:
            r = httpx.get(f'{ADDR}/v1/auth/token/lookup-self', headers={'X-Vault-Token': f.read_text().strip()}, timeout=3)
            return r.status_code == 200
        except Exception:
            return False
    (RUN / 'tokens').mkdir(parents=True, exist_ok=True)
    os.chmod(RUN / 'tokens', 0o700)
    lec = lecturas()
    for comp, rutas in lec.items():
        pol = ''.join(f'path "secret/data/{r}" {{ capabilities = ["read"] }}\n' for r in rutas)
        api('PUT', f'sys/policies/acl/{comp}', json={'policy': pol}).raise_for_status()
        f = RUN / 'tokens' / f'{comp}.token'
        if rotar or not f.exists() or not _token_vigente(f):
            t = api('POST', 'auth/token/create', json={'policies': [comp], 'ttl': '720h', 'no_parent': True, 'display_name': comp})
            t.raise_for_status()
            f.write_text(t.json()['auth']['client_token']); os.chmod(f, 0o600)
    # configuracion del broker (ActiveMQ): usuarios y permisos por cola, generada con los secretos de Vault
    o = api('GET', 'secret/data/orders/activemq').json()['data']['data']
    d = api('GET', 'secret/data/dispatch/activemq').json()['data']['data']
    from xml.sax.saxutils import escape
    xml = (pathlib.Path(__file__).resolve().parent / 'activemq.xml.plantilla').read_text(encoding='utf-8')
    for k, v in {'USUARIO_ORDERS': o['usuario'], 'CLAVE_ORDERS': o['clave'],
                 'USUARIO_DISPATCH': d['usuario'], 'CLAVE_DISPATCH': d['clave'],
                 'DIR_DATOS': os.environ.get('ACTIVEMQ_DATA', '/opt/apache-activemq/data')}.items():
        xml = xml.replace(f'@@{k}@@', escape(v, {'"': '&quot;'}))
    axml = RUN / 'activemq.xml'
    axml.write_text(xml, encoding='utf-8'); os.chmod(axml, 0o600)
    print(json.dumps({'secretos_creados_o_rotados': len(nuevos), 'componentes_con_token': len(lec)}))

main()
