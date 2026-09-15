from contextlib import asynccontextmanager
from typing import List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import FastAPI, HTTPException, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

# --- Configuracion de conexion a MongoDB ---
MONGO_URI = "mongodb://localhost:27017"
DATABASE_NAME = "items_db"
COLLECTION_NAME = "items"


# --- Ciclo de vida de la aplicacion: abre y cierra el cliente de MongoDB ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.mongodb_client = AsyncIOMotorClient(MONGO_URI)
    app.mongodb = app.mongodb_client[DATABASE_NAME]
    print(f"[DB] Conectado a MongoDB -> {MONGO_URI}/{DATABASE_NAME}")
    yield
    app.mongodb_client.close()
    print("[DB] Conexion a MongoDB cerrada")


app = FastAPI(title="Items API", lifespan=lifespan)


# --- Modelos Pydantic ---
class ItemBase(BaseModel):
    nombre: str = Field(..., min_length=1)
    precio: float = Field(..., gt=0)
    tags: List[str] = Field(default_factory=list)
    activo: bool = True


class ItemIn(ItemBase):
    """Modelo usado para crear/actualizar un item (entrada de la API)."""
    pass


class ItemOut(ItemBase):
    """Modelo usado para devolver un item, con el id de Mongo como string."""
    id: str


def item_helper(doc: dict) -> dict:
    """Transforma el _id (ObjectId) de un documento de Mongo en un campo 'id' string."""
    return {
        "id": str(doc["_id"]),
        "nombre": doc["nombre"],
        "precio": doc["precio"],
        "tags": doc.get("tags", []),
        "activo": doc.get("activo", True),
    }


def parse_object_id(item_id: str) -> ObjectId:
    """Valida que el id recibido sea un ObjectId valido, o lanza 400."""
    try:
        return ObjectId(item_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ID invalido")


# --- Endpoints ---
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/items", response_model=List[ItemOut])
async def get_items(
    q: Optional[str] = Query(None, description="Filtro por nombre (busqueda parcial)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
):
    query = {}
    if q:
        query["nombre"] = {"$regex": q, "$options": "i"}

    cursor = app.mongodb[COLLECTION_NAME].find(query).skip(skip).limit(limit)
    items = [item_helper(doc) async for doc in cursor]
    return items


@app.post("/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def create_item(item: ItemIn):
    result = await app.mongodb[COLLECTION_NAME].insert_one(item.model_dump())
    nuevo = await app.mongodb[COLLECTION_NAME].find_one({"_id": result.inserted_id})
    return item_helper(nuevo)


@app.get("/items/{item_id}", response_model=ItemOut)
async def get_item(item_id: str):
    oid = parse_object_id(item_id)
    doc = await app.mongodb[COLLECTION_NAME].find_one({"_id": oid})
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item no encontrado")
    return item_helper(doc)


@app.put("/items/{item_id}", response_model=ItemOut)
async def update_item(item_id: str, item: ItemIn):
    oid = parse_object_id(item_id)

    existente = await app.mongodb[COLLECTION_NAME].find_one({"_id": oid})
    if existente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item no encontrado")

    await app.mongodb[COLLECTION_NAME].update_one({"_id": oid}, {"$set": item.model_dump()})
    actualizado = await app.mongodb[COLLECTION_NAME].find_one({"_id": oid})
    return item_helper(actualizado)


@app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: str):
    oid = parse_object_id(item_id)

    existente = await app.mongodb[COLLECTION_NAME].find_one({"_id": oid})
    if existente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item no encontrado")

    await app.mongodb[COLLECTION_NAME].delete_one({"_id": oid})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
