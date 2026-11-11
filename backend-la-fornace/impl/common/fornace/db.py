"""Conexion a MongoDB: una base y un usuario por sistema. Las credenciales salen de Vault, nunca del codigo."""
import os, time, asyncio
from motor.motor_asyncio import AsyncIOMotorClient

def ahora():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

def en_segundos(seg):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() + seg))

async def conectar(sistema, vault):
    kw = {}
    if os.environ.get('MONGO_AUTH', '1') == '1':
        c = vault.get(f'{sistema}/db')
        kw = dict(username=c['usuario'], password=c['clave'], authSource=f'{sistema}_db')
    cli = AsyncIOMotorClient(os.environ['MONGO_URL'], serverSelectionTimeoutMS=3000, **kw)
    return cli, cli[f'{sistema}_db']

_CONTADOR = None

async def siguiente(db, nombre, prefijo, ancho=4):
    # el contador se incrementa de a una peticion por proceso: no se depende de la atomicidad del motor (defensa adicional)
    global _CONTADOR
    if _CONTADOR is None: _CONTADOR = asyncio.Lock()
    async with _CONTADOR:
        r = await db.contadores.find_one_and_update({'_id': nombre}, {'$inc': {'n': 1}}, upsert=True, return_document=True)
    return f'{prefijo}{r["n"]:0{ancho}d}'

def limpio(doc, ocultar=()):
    if doc is None:
        return None
    d = {k: v for k, v in doc.items() if k != '_id' and k not in ocultar}
    return d
