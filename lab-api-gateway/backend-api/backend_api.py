"""
Backend API (HOST B)

API de negocio protegida: solo acepta solicitudes que traigan el header
X-Gateway-Secret con el secreto compartido con el API Gateway.

El secreto se entrega por la variable de entorno INTERNAL_GATEWAY_SECRET.
Si la variable no existe, la aplicacion se niega a arrancar.

Ejecucion:
    INTERNAL_GATEWAY_SECRET="gateway-api-secret-456" \
    uvicorn backend_api:app --host 0.0.0.0 --port 9000
"""
import os
import secrets
from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    Depends
)

app = FastAPI(title="Protected Backend API")

INTERNAL_GATEWAY_SECRET = os.getenv(
    "INTERNAL_GATEWAY_SECRET"
)

if not INTERNAL_GATEWAY_SECRET:
    raise RuntimeError(
        "INTERNAL_GATEWAY_SECRET no esta configurado"
    )


def verify_gateway(
    x_gateway_secret: str = Header(default="")
):
    # compare_digest compara en tiempo constante
    valid = secrets.compare_digest(
        x_gateway_secret,
        INTERNAL_GATEWAY_SECRET
    )
    if not valid:
        raise HTTPException(
            status_code=403,
            detail="Solicitud no autorizada desde Gateway"
        )


@app.get("/health")
def health():
    return {"status": "OK"}


@app.get(
    "/products",
    dependencies=[Depends(verify_gateway)]
)
def products(
    x_authenticated_client: str | None = Header(default=None)
):
    return {
        "authenticated_client": x_authenticated_client,
        "products": [
            {"id": 1, "name": "Notebook", "price": 900000},
            {"id": 2, "name": "Monitor", "price": 250000}
        ]
    }


@app.get(
    "/orders",
    dependencies=[Depends(verify_gateway)]
)
def orders(
    x_authenticated_client: str | None = Header(default=None)
):
    return {
        "authenticated_client": x_authenticated_client,
        "orders": [
            {"id": 1001, "status": "paid"},
            {"id": 1002, "status": "pending"}
        ]
    }
