"""correo-prueba: adaptador de prueba del proveedor externo de correo (I17). No envia nada a internet.
Valida correos (un dominio reservado se declara inexistente) y guarda los mensajes en una bandeja consultable con la clave."""
import os
from fastapi import Depends, Request
from fornace.base import make_app, run, AppError
from fornace.vault import SecretProvider, iguales

vault = SecretProvider()
BANDEJA = []

async def clave(request: Request):
    if not iguales(request.headers.get('x-api-key'), vault.actual('notifications/mail')):
        raise AppError(401, 'CREDENCIAL_INVALIDA', 'Clave inválida.')

app = make_app('correo-prueba')

@app.post('/validar', dependencies=[Depends(clave)])
async def validar(request: Request):
    d = await request.json()
    c = (d.get('correo') or '').lower()
    existe = not (c.endswith('@noexiste.invalid') or c.startswith('noexiste'))
    return {'existe': existe}

@app.post('/enviar', dependencies=[Depends(clave)])
async def enviar(request: Request):
    d = await request.json()
    if (d.get('para') or '').lower().startswith('falla'):
        raise AppError(503, 'PROVEEDOR_CAIDO', 'Proveedor no disponible.')
    BANDEJA.append({'para': d.get('para'), 'asunto': d.get('asunto'), 'cuerpo': d.get('cuerpo')})
    del BANDEJA[:-500]
    return {'enviado': True}

@app.get('/bandeja', dependencies=[Depends(clave)])
async def bandeja(para: str = None):
    return [m for m in BANDEJA if not para or m['para'] == para.lower()]

if __name__ == '__main__':
    run(app)
