"""Control de acceso de cada sistema (M5 y M6): quien llama (gateway o sistema) y que usuario lo origino."""
from dataclasses import dataclass, field
from fastapi import Request
from .base import AppError
from .topology import PARES, ref_gateway, ref_par
from .vault import SecretProvider, iguales, SecretUnavailable

@dataclass
class Ctx:
    cuenta: str = None
    email: str = None
    roles: list = field(default_factory=list)
    sesion: str = None
    servicio: str = None      # id del sistema llamador cuando la llamada es sistema -> sistema
    rid: str = None

class Guard:
    def __init__(self, sistema: str, vault: SecretProvider):
        self.sistema = sistema
        self.me = f'{sistema}-service'
        self.vault = vault

    def _ok(self, recibido, ref):
        try:
            return any(iguales(recibido, c) for c in self.vault.candidatos(ref))
        except SecretUnavailable:
            raise AppError(503, 'SECRETOS_NO_DISPONIBLES', 'Servicio no disponible.')

    def dep(self, roles=None, publica=False, pares=(), gateway=True, pares_solo_get=()):
        """roles: roles de usuario permitidos (None = cualquiera autenticado).
        publica: no exige identidad de usuario (la llamada igual debe venir del gateway).
        pares: sistemas que pueden llamar a esta ruta. gateway=False: ruta /internal (solo pares)."""
        guard = self

        async def check(request: Request) -> Ctx:
            h = request.headers
            rid = getattr(request.state, 'rid', None)
            sid = h.get('x-service-id')
            if sid:
                if sid not in pares or (sid in pares_solo_get and request.method != 'GET'):
                    raise AppError(403, 'LLAMADOR_NO_PERMITIDO', 'Operación no permitida.')
                if (sid, guard.me) not in PARES or not guard._ok(h.get('x-service-secret'), ref_par(sid, guard.me)):
                    raise AppError(401, 'CREDENCIAL_INVALIDA', 'Credencial inválida.')
                c = Ctx(servicio=sid, rid=rid, cuenta=h.get('x-authenticated-user'),
                        email=h.get('x-authenticated-email'),
                        roles=[r for r in (h.get('x-authenticated-roles') or '').split(',') if r])
                request.state.cuenta = c.cuenta
                if roles is not None and not publica:
                    if not c.cuenta:
                        raise AppError(401, 'NO_AUTENTICADO', 'Debes iniciar sesión.')
                    if not (set(roles) & set(c.roles)):
                        raise AppError(403, 'SIN_PERMISO', 'No tienes permiso para esta acción.')
                return c
            if not gateway:
                raise AppError(401, 'CREDENCIAL_INVALIDA', 'Credencial inválida.')
            if not guard._ok(h.get('x-gateway-secret'), ref_gateway(guard.sistema)):
                raise AppError(401, 'CREDENCIAL_INVALIDA', 'Credencial inválida.')
            c = Ctx(cuenta=h.get('x-authenticated-user'), email=h.get('x-authenticated-email'),
                    roles=[r for r in (h.get('x-authenticated-roles') or '').split(',') if r],
                    sesion=h.get('x-authenticated-session'), rid=rid)
            request.state.cuenta = c.cuenta
            if publica:
                return c
            if not c.cuenta:
                raise AppError(401, 'NO_AUTENTICADO', 'Debes iniciar sesión.')
            if roles is not None and not (set(roles) & set(c.roles)):
                raise AppError(403, 'SIN_PERMISO', 'No tienes permiso para esta acción.')
            return c
        return check
