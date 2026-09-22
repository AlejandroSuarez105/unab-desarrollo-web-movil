from fastapi import FastAPI, Request
import httpx

app = FastAPI(title="API Gateway - Pizzeria La Fornace")

BACKEND_ITEMS = "http://localhost:8000/"     
BACKEND_GRAPHQL = "http://localhost:8090/"   


@app.get("/api/items")
async def items():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BACKEND_ITEMS}/items")
    return response.json()


@app.get("/api/items/{item_id}")
async def item_by_id(item_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BACKEND_ITEMS}/items/{item_id}")
    return response.json()


@app.post("/api/graphql")
async def graphql(request: Request):
    body = await request.json()
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BACKEND_GRAPHQL}/graphql", json=body)
    return response.json()
