import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="OutService - Pizzería La Fornace (Auth & ZTA)",
    description="Servicio de autenticación e introspección de tokens para Pizzería La Fornace"
)

# Base de datos local de usuarios y roles de Pizzería La Fornace
USERS_DB = [
    {
        "user_id": "cli_001",
        "username": "manuel",
        "password": "123",
        "roles": ["cliente"]
    },
    {
        "user_id": "caj_002",
        "username": "alvaro",
        "password": "456",
        "roles": ["cajero"]
    },
    {
        "user_id": "adm_003",
        "username": "alejandro",
        "password": "789",
        "roles": ["admin"]
    }
]

# Sesiones activas en memoria
sessions = {}

TOKEN_LIFETIME_MINUTES = 15
GATEWAY_SECRET = os.getenv("GATEWAY_SECRET", "PizzeriaSecret123")


class LoginRequest(BaseModel):
    username: str
    password: str


class IntrospectRequest(BaseModel):
    token: str


def verify_gateway_secret(secret: Optional[str]):
    """Valida el secreto compartido con el API Gateway (Zero Trust Architecture)."""
    if not secret or not secrets.compare_digest(secret, GATEWAY_SECRET):
        raise HTTPException(status_code=403, detail="Acceso denegado: Gateway no autorizado")


@app.get("/health")
def health(x_gateway_secret: Optional[str] = Header(default=None)):
    verify_gateway_secret(x_gateway_secret)
    return {"status": "ok", "service": "auth-pizzeria-la-fornace"}


@app.post("/login")
def login(request: LoginRequest, x_gateway_secret: Optional[str] = Header(default=None)):
    verify_gateway_secret(x_gateway_secret)

    user = next((u for u in USERS_DB if u["username"] == request.username), None)
    if not user or not secrets.compare_digest(user["password"], request.password):
        raise HTTPException(status_code=401, detail="Credenciales inválidas en Pizzería La Fornace")

    access_token = secrets.token_urlsafe(32)
    expiration = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_LIFETIME_MINUTES)

    sessions[access_token] = {
        "user_id": user["user_id"],
        "username": user["username"],
        "roles": user["roles"],
        "expires_at": expiration
    }

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": TOKEN_LIFETIME_MINUTES * 60
    }


@app.post("/introspect")
def introspect(request: IntrospectRequest, x_gateway_secret: Optional[str] = Header(default=None)):
    verify_gateway_secret(x_gateway_secret)

    session = sessions.get(request.token)
    if not session:
        return {"active": False}

    now = datetime.now(timezone.utc)
    if now > session["expires_at"]:
        sessions.pop(request.token, None)
        return {"active": False}

    return {
        "active": True,
        "user_id": session["user_id"],
        "username": session["username"],
        "roles": session["roles"],
        "expires_at": session["expires_at"].isoformat()
    }


@app.post("/logout")
def logout(request: IntrospectRequest, x_gateway_secret: Optional[str] = Header(default=None)):
    verify_gateway_secret(x_gateway_secret)
    sessions.pop(request.token, None)
    return {"message": "Sesión en Pizzería La Fornace finalizada exitosamente"}
