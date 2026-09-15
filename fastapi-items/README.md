# Items API — FastAPI + MongoDB

API REST construida con FastAPI y conexión asíncrona a MongoDB (Motor).

## Instalación

```bash
pip install -r requirements.txt
```

Asegúrate de tener MongoDB corriendo localmente en `mongodb://localhost:27017`
(o edita la constante `MONGO_URI` en `main.py` si usas otra conexión, por ejemplo Atlas).

## Ejecución

```bash
uvicorn main:app --reload
```

El servidor queda en `http://127.0.0.1:8000`.

## Documentación interactiva

FastAPI genera automáticamente:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

Desde `/docs` puedes probar todos los endpoints sin necesitar Postman.

## Endpoints

| Método | Ruta              | Descripción                                      |
| ------ | ----------------- | ------------------------------------------------- |
| GET    | `/health`         | Estado del servicio                                |
| GET    | `/items`          | Lista items, con filtro `q`, `skip` y `limit`      |
| POST   | `/items`          | Crea un item (201)                                 |
| GET    | `/items/{id}`     | Obtiene un item por id (400 id inválido, 404 no existe) |
| PUT    | `/items/{id}`     | Actualiza un item por id                           |
| DELETE | `/items/{id}`     | Elimina un item por id (204)                       |

## Ejemplos con curl

**Crear un item**
```bash
curl -X POST http://127.0.0.1:8000/items \
  -H "Content-Type: application/json" \
  -d '{"nombre": "Pizza Napolitana", "precio": 8990, "tags": ["pizza"], "activo": true}'
```

**Listar items**
```bash
curl "http://127.0.0.1:8000/items?q=pizza&skip=0&limit=10"
```

**Obtener un item por id**
```bash
curl http://127.0.0.1:8000/items/ID_DEL_ITEM
```

**Actualizar un item**
```bash
curl -X PUT http://127.0.0.1:8000/items/ID_DEL_ITEM \
  -H "Content-Type: application/json" \
  -d '{"nombre": "Pizza Napolitana", "precio": 9990, "tags": ["pizza"], "activo": true}'
```

**Eliminar un item**
```bash
curl -X DELETE http://127.0.0.1:8000/items/ID_DEL_ITEM
```
