"""SecretProvider: lee secretos de Vault con un token de solo lectura. Nunca devuelve valores a los registros."""
import os, time, threading, hmac
import httpx

class SecretUnavailable(Exception):
    pass

class SecretProvider:
    def __init__(self, token_file=None, addr=None, ca=None, ttl=300, grace=None):
        self.addr = (addr or os.environ['VAULT_ADDR']).rstrip('/')
        self.token_file = token_file or os.environ['VAULT_TOKEN_FILE']
        self.ca = ca if ca is not None else os.environ.get('CA_FILE') or True
        self.ttl = ttl
        self.grace = grace          # segundos que se acepta un valor viejo si Vault no responde (None = sin limite)
        self._cache = {}
        self._lock = threading.Lock()

    def _token(self):
        with open(self.token_file) as f:
            return f.read().strip()

    def _fetch(self, path):
        r = httpx.get(f'{self.addr}/v1/secret/data/{path}', headers={'X-Vault-Token': self._token()},
                      verify=self.ca, timeout=3.0)
        if r.status_code != 200:
            raise SecretUnavailable(f'vault {r.status_code}')
        return r.json()['data']['data']

    def get(self, path):
        now = time.time()
        with self._lock:
            hit = self._cache.get(path)
            if hit and now - hit[0] < self.ttl:
                return hit[1]
            try:
                val = self._fetch(path)
                self._cache[path] = (now, val)
                return val
            except Exception:
                if hit and (self.grace is None or now - hit[0] < self.grace):
                    return hit[1]
                raise SecretUnavailable(path)

    def candidatos(self, path):
        """Valores validos para verificar: el actual y, durante la ventana de rotacion, el anterior."""
        v = self.get(path)
        return [x for x in (v.get('actual'), v.get('anterior')) if x]

    def actual(self, path):
        return self.get(path)['actual']

def iguales(a, b):
    return hmac.compare_digest((a or '').encode(), (b or '').encode())
