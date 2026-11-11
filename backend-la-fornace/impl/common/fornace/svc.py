"""Cliente HTTP para llamadas sistema -> sistema (par de credenciales propio, CA del proyecto, plazos)."""
import os, httpx
from .base import AppError, evento
from .topology import ref_par

class Servicios:
    def __init__(self, yo: str, vault, log=None, ca=None):
        self.yo, self.vault, self.log = yo, vault, log
        self.http = httpx.AsyncClient(verify=ca or os.environ.get('CA_FILE') or True)

    def url(self, destino: str) -> str:
        return os.environ['URL_' + destino.split('-')[0].upper()].rstrip('/')

    async def llamar(self, destino, metodo, ruta, rid, *, json=None, params=None, timeout=3.0, usuario=None, reintentos=0):
        """destino: p.ej. 'inventory-service'. Devuelve httpx.Response. Si no hay respuesta: AppError 503."""
        headers = {'X-Service-Id': self.yo, 'X-Service-Secret': self.vault.actual(ref_par(self.yo, destino)),
                   'X-Request-Id': rid or ''}
        if usuario:
            headers['X-Authenticated-User'] = usuario
        ultimo = None
        for _ in range(reintentos + 1):
            try:
                return await self.http.request(metodo, self.url(destino) + ruta, json=json, params=params,
                                               headers=headers, timeout=timeout)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                ultimo = e
        if self.log:
            evento(self.log, self.yo, 'dependencia_sin_respuesta', destino=destino, ruta=ruta.split('?')[0],
                   tipo=type(ultimo).__name__, requestId=rid)
        raise AppError(503, 'SERVICIO_NO_DISPONIBLE', 'Servicio no disponible. Intenta de nuevo en un momento.')
