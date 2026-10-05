import os
import httpx
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

app = FastAPI(title="API Gateway - Pizzería La Fornace (ZTA & RBAC)")
security = HTTPBearer(auto_error=False)

BACKEND_ITEMS = os.getenv("BACKEND_ITEMS", "http://localhost:9000")
BACKEND_GRAPHQL = os.getenv("BACKEND_GRAPHQL", "http://localhost:8090")
OUTSERVICE_URL = os.getenv("OUTSERVICE_URL", "http://localhost:8100")
GATEWAY_SECRET = os.getenv("GATEWAY_SECRET", "PizzeriaSecret123")

# Matriz de Permisos por Rol en La Fornace
PERMISSIONS = {
    "cliente": {("GET", "items"), ("GET", "item_by_id")},
    "cajero": {("GET", "items"), ("GET", "item_by_id"), ("POST", "graphql")},
    "admin": {("GET", "items"), ("GET", "item_by_id"), ("POST", "graphql")}
}


class LoginBody(BaseModel):
    username: str
    password: str


async def authenticate_and_introspect(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Valida el Bearer Token comunicándose asíncronamente con outservice (/introspect)."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Bearer token requerido para Pizzería La Fornace")

    token = credentials.credentials
    headers = {"X-Gateway-Secret": GATEWAY_SECRET}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{OUTSERVICE_URL}/introspect",
                json={"token": token},
                headers=headers
            )
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Servicio de autenticación no disponible: {str(e)}")

        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Error en introspección de token")

        data = resp.json()
        if not data.get("active"):
            raise HTTPException(status_code=401, detail="Token inválido o expirado")

        return {
            "user_id": data["user_id"],
            "username": data["username"],
            "roles": data["roles"]
        }


@app.post("/api/login")
async def login(body: LoginBody):
    """Enruta el inicio de sesión hacia outservice."""
    headers = {"X-Gateway-Secret": GATEWAY_SECRET}
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{OUTSERVICE_URL}/login",
            json={"username": body.username, "password": body.password},
            headers=headers
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.json().get("detail", "Error al iniciar sesión"))
        return resp.json()


@app.get("/api/items")
async def items(auth=Depends(authenticate_and_introspect)):
    # Validar RBAC
    user_roles = auth["roles"]
    has_permission = any(("GET", "items") in PERMISSIONS.get(role, set()) for role in user_roles)
    if not has_permission:
        raise HTTPException(status_code=403, detail="Rol sin permiso para consultar el menú de ítems")

    headers = {
        "X-Gateway-Secret": GATEWAY_SECRET,
        "X-Authenticated-User": auth["username"],
        "X-Authenticated-Roles": ",".join(auth["roles"]),
        "X-Authenticated-Client": auth["user_id"]
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BACKEND_ITEMS}/items", headers=headers)
        return resp.json()


@app.get("/api/items/{item_id}")
async def item_by_id(item_id: str, auth=Depends(authenticate_and_introspect)):
    user_roles = auth["roles"]
    has_permission = any(("GET", "item_by_id") in PERMISSIONS.get(role, set()) for role in user_roles)
    if not has_permission:
        raise HTTPException(status_code=403, detail="Rol sin permiso para consultar este ítem")

    headers = {
        "X-Gateway-Secret": GATEWAY_SECRET,
        "X-Authenticated-User": auth["username"],
        "X-Authenticated-Roles": ",".join(auth["roles"]),
        "X-Authenticated-Client": auth["user_id"]
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BACKEND_ITEMS}/items/{item_id}", headers=headers)
        return resp.json()


@app.post("/api/graphql")
async def graphql(request: Request, auth=Depends(authenticate_and_introspect)):
    user_roles = auth["roles"]
    has_permission = any(("POST", "graphql") in PERMISSIONS.get(role, set()) for role in user_roles)
    if not has_permission:
        raise HTTPException(status_code=403, detail="Acceso denegado: GraphQL requiere rol cajero o admin")

    body = await request.json()
    headers = {
        "X-Gateway-Secret": GATEWAY_SECRET,
        "X-Authenticated-User": auth["username"],
        "X-Authenticated-Roles": ",".join(auth["roles"]),
        "X-Authenticated-Client": auth["user_id"]
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BACKEND_GRAPHQL}/graphql", json=body, headers=headers)
        return resp.json()
