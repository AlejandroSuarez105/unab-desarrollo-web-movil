import os
from fastapi import FastAPI, Header, HTTPException

app = FastAPI(title="Backend Items - Pizzería La Fornace")

GATEWAY_SECRET = os.getenv("GATEWAY_SECRET", "PizzeriaSecret123")

MENU_ITEMS = {
    "1": {"id": "1", "name": "Pizza Margherita", "category": "pizzas", "price": 12000, "ingredients": ["mozzarella", "tomate", "albahaca"]},
    "2": {"id": "2", "name": "Pizza Quattro Formaggi", "category": "pizzas", "price": 14500, "ingredients": ["mozzarella", "gorgonzola", "parmesano", "provolone"]},
    "3": {"id": "3", "name": "Calzone Napolitano", "category": "calzones", "price": 13000, "ingredients": ["jamón", "mozzarella", "tomate"]},
    "4": {"id": "4", "name": "Fainá Tradicional", "category": "acompañamientos", "price": 3500, "ingredients": ["harina de garbanzo", "aceite de oliva"]}
}


@app.get("/items")
def get_all_items(
    x_gateway_secret: str = Header(default=None),
    x_authenticated_user: str = Header(default=None),
    x_authenticated_roles: str = Header(default=None),
    x_authenticated_client: str = Header(default=None)
):
    # Validar ZTA: Verificar que la llamada provenga del Gateway
    if x_gateway_secret != GATEWAY_SECRET:
        raise HTTPException(status_code=403, detail="Acceso no autorizado: requiere transmisión desde Gateway autorizado")

    return {
        "identity": {
            "client_id": x_authenticated_client,
            "username": x_authenticated_user,
            "roles": x_authenticated_roles.split(",") if x_authenticated_roles else []
        },
        "restaurant": "Pizzería La Fornace",
        "total_items": len(MENU_ITEMS),
        "items": list(MENU_ITEMS.values())
    }


@app.get("/items/{item_id}")
def get_item_by_id(
    item_id: str,
    x_gateway_secret: str = Header(default=None),
    x_authenticated_user: str = Header(default=None),
    x_authenticated_roles: str = Header(default=None),
    x_authenticated_client: str = Header(default=None)
):
    if x_gateway_secret != GATEWAY_SECRET:
        raise HTTPException(status_code=403, detail="Acceso no autorizado al backend de Pizzería La Fornace")

    item = MENU_ITEMS.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Ítem de menú no encontrado")

    return {
        "identity": {
            "client_id": x_authenticated_client,
            "username": x_authenticated_user,
            "roles": x_authenticated_roles.split(",") if x_authenticated_roles else []
        },
        "item": item
    }
