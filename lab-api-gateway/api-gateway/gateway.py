"""
API Gateway (HOST A) con HashiCorp Vault, token Bearer y roles.

Flujo:
    Cliente -> Bearer Token -> Gateway -> Vault -> validacion -> Backend

El Gateway:
  1. Autentica al cliente: busca su token entre los clientes guardados en
     Vault (401 si falta o es invalido).
  2. Autoriza segun el rol: revisa si el rol puede usar ese metodo y esa
     ruta (403 si no tiene permiso).
  3. Reenvia la solicitud al backend con el secreto interno
     (X-Gateway-Secret) y la identidad del cliente. El token del cliente
     NO se reenvia.

Variables de entorno:
    VAULT_ADDR   (por defecto http://127.0.0.1:8200)
    VAULT_TOKEN  (obligatoria)
    BACKEND_URL  (por defecto http://172.30.0.20:9000)

Ejecucion:
    uvicorn gateway:app --host 0.0.0.0 --port 8000
"""
import os
import json
import secrets
import httpx
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    Response
)
from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials
)

app = FastAPI(title="Secure Gateway con roles")
security = HTTPBearer(auto_error=False)

VAULT_ADDR = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
VAULT_TOKEN = os.getenv("VAULT_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://172.30.0.20:9000")

if not VAULT_TOKEN:
    raise RuntimeError("VAULT_TOKEN no configurado")

# Politica de autorizacion: rol -> (metodo, ruta) permitidos
PERMISSIONS = {
    "user": {("GET", "products")},
    "admin": {("GET", "products"), ("GET", "orders")},
}


async def get_gateway_secrets():
    url = f"{VAULT_ADDR}/v1/secret/data/gateway"
    headers = {"X-Vault-Token": VAULT_TOKEN}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers=headers)
    except httpx.RequestError:
        # Vault caido o sin respuesta: error controlado
        raise HTTPException(
            status_code=500,
            detail="No fue posible acceder a Vault"
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail="No fue posible acceder a Vault"
        )
    return response.json()["data"]["data"]


async def authenticate_client(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Bearer token requerido"
        )
    vault_secrets = await get_gateway_secrets()
    clients = json.loads(vault_secrets["clients"])
    received = credentials.credentials
    match = None
    for token, info in clients.items():
        if secrets.compare_digest(received, token):
            match = info
    if match is None:
        raise HTTPException(
            status_code=401,
            detail="Token invalido"
        )
    return {
        "client_id": match["client_id"],
        "role": match["role"],
        "backend_secret": vault_secrets["backend_shared_secret"]
    }


@app.get("/health")
def health():
    return {"status": "OK", "service": "API Gateway"}


@app.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"]
)
async def proxy(
    path: str,
    request: Request,
    auth=Depends(authenticate_client)
):
    allowed = PERMISSIONS.get(auth["role"], set())
    if (request.method, path) not in allowed:
        raise HTTPException(
            status_code=403,
            detail="Permiso insuficiente para este recurso"
        )
    target_url = f"{BACKEND_URL}/{path}"
    body = await request.body()
    gateway_headers = {
        "X-Gateway-Secret": auth["backend_secret"],
        "X-Authenticated-Client": auth["client_id"],
        "X-Client-Role": auth["role"]
    }
    content_type = request.headers.get("content-type")
    if content_type:
        gateway_headers["content-type"] = content_type
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            upstream = await client.request(
                method=request.method,
                url=target_url,
                params=request.query_params,
                content=body,
                headers=gateway_headers
            )
    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Backend no disponible"
        )
    response_headers = {}
    if "content-type" in upstream.headers:
        response_headers["content-type"] = upstream.headers["content-type"]
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers
    )
