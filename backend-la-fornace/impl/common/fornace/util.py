import re, datetime
from .base import AppError

EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$')
FONO_RE = re.compile(r'^[0-9+ ]{8,15}$')

def run_valido(run: str) -> bool:
    """Valida RUN chileno con digito verificador (modulo 11)."""
    s = re.sub(r'[.\-\s]', '', run or '').upper()
    if not re.fullmatch(r'\d{7,8}[0-9K]', s):
        return False
    cuerpo, dv = s[:-1], s[-1]
    suma, mult = 0, 2
    for d in reversed(cuerpo):
        suma += int(d) * mult
        mult = 2 if mult == 7 else mult + 1
    r = 11 - suma % 11
    esp = '0' if r == 11 else 'K' if r == 10 else str(r)
    return esp == dv

def run_normal(run: str) -> str:
    s = re.sub(r'[.\-\s]', '', run).upper()
    c = s[:-1]
    c = f'{int(c):,}'.replace(',', '.')
    return f'{c}-{s[-1]}'

def fecha_pasada(s: str) -> bool:
    try:
        return datetime.date.fromisoformat(s) < datetime.date.today()
    except Exception:
        return False

def paginar(limit, offset, maximo=100, defecto=50):
    limit = defecto if limit is None else limit
    offset = 0 if offset is None else offset
    if not (1 <= limit <= maximo) or offset < 0:
        raise AppError(400, 'DATOS_INVALIDOS', f'limit debe estar entre 1 y {maximo} y offset no puede ser negativo.')
    return limit, offset

def rango_fechas(desde, hasta, max_dias=None):
    try:
        d = datetime.date.fromisoformat(desde) if desde else None
        h = datetime.date.fromisoformat(hasta) if hasta else None
    except Exception:
        raise AppError(400, 'RANGO_INVALIDO', 'Las fechas deben tener formato AAAA-MM-DD.')
    if d and h and (h < d or (max_dias and (h - d).days > max_dias)):
        raise AppError(400, 'RANGO_INVALIDO', 'Rango de fechas inválido.')
    return d, h
