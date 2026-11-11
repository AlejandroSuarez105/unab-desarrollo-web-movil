# Demostración de los flujos principales

Salida real de `tests/demo_flujos.py` contra el sistema en ejecución. Los datos son ficticios. Los tokens y las contraseñas no se imprimen.

## 1. Registro, verificación de correo e inicio de sesión (S03, S04, S01)

**Registro**

`POST /api/v1/auth/register` con requestId `demo-91279301`

Respuesta 201: `{"id": "cli_0018", "correo": "demo900206@ejemplo.cl", "estado": "pendiente_verificacion"}`

Registros con el mismo requestId:

```
api-gateway        POST /api/v1/auth/register -> 201 (401 ms) cuentaId=None
auth-service       POST /internal/accounts -> 201 (379 ms) cuentaId=None
clients-service    POST /clients/register -> 201 (393 ms) cuentaId=None
notifications-service POST /internal/emails -> 200 (15 ms) cuentaId=None
```

Correo recibido en el servidor de correo de prueba, asunto: "Confirma tu correo - Pizzería La Fornace". El enlace de verificación no se muestra.

**Verificación del correo**

`POST /api/v1/auth/verify-email` con requestId `demo-84097709`

Respuesta 200: `{"estado": "activo"}`

Registros con el mismo requestId:

```
api-gateway        POST /api/v1/auth/verify-email -> 200 (10 ms) cuentaId=None
auth-service       POST /auth/verify-email -> 200 (5 ms) cuentaId=None
```

**Inicio de sesión**: respuesta 200 (el token no se muestra).

## 2. Catálogo y pedido (S06, S12)

**Catálogo público (sin sesión; sin stock en la respuesta)**

`GET /api/v1/products?categoria=combo` con requestId `demo-36203968`

Respuesta 200: `[{"id": "prod_009", "nombre": "Combo Solo", "categoria": "combo", "descripcion": "1 pizza clásica + bebida 500ml", "precio": 10490, "imagen": "https://images.unsplash.com/photo-1513104890138-7c749659a591?w=600&q=80", "destacado": true, "disponible": true}, {"id": "prod_010", "nombre": "Combo Dúo", "categoria": "combo", "descripcion": "2 pizzas clásicas + pan de ajo", "precio": 18990, "imagen": "https://images.unsplas ...`

Registros con el mismo requestId:

```
api-gateway        GET /api/v1/products -> 200 (7 ms) cuentaId=None
inventory-service  GET /products -> 200 (2 ms) cuentaId=None
```

**Pedido: el precio y el total los fija el servidor, aunque el cliente envíe otros**

`POST /api/v1/orders` con requestId `demo-80581106`

Respuesta 201: `{"id": "ped_0020", "estado": "pendiente_pago", "items": [{"productoId": "prod_002", "nombre": "Margarita", "precioUnitario": 7990, "cantidad": 2}], "total": 15980, "direccionEntrega": {"calle": "Calle Ficticia 321", "comuna": "Maipú", "referencia": ""}, "creadoEn": "2026-11-08T21:59:10Z", "expiraEn": "2026-11-08T22:14:10Z"}`

Registros con el mismo requestId:

```
api-gateway        POST /api/v1/orders -> 201 (48 ms) cuentaId=cta_0018
auth-service       POST /internal/introspect -> 200 (3 ms) cuentaId=None
clients-service    GET /internal/clients/by-account/cta_0018 -> 200 (2 ms) cuentaId=None
inventory-service  POST /internal/stock/reservations -> 201 (6 ms) cuentaId=None
orders-service     POST /orders -> 201 (31 ms) cuentaId=cta_0018
```

## 3. Consulta protegida de un pedido: autorizada y denegada (S14, regla C1)

Las dos ejecuciones aplican la misma regla en `orders-service`: el pedido solo se devuelve si `pedido.cuentaId` es la cuenta de la identidad verificada por el gateway. La cuenta ajena recibe el mismo 404 que un pedido que no existe.

**Autorizada: la dueña del pedido**

`GET /api/v1/orders/ped_0020` con requestId `demo-99952522` · C1 permite

Respuesta 200: `{"id": "ped_0020", "estado": "pendiente_pago", "estadoPago": "pendiente", "items": [{"productoId": "prod_002", "nombre": "Margarita", "precioUnitario": 7990, "cantidad": 2}], "total": 15980, "direccionEntrega": {"calle": "Calle Ficticia 321", "comuna": "Maipú", "referencia": ""}, "historialEstados": [{"estado": "pendiente_pago", "fecha": "2026-11-08T21:59:10Z"}], "boletaDisponible": false, "creadoEn": "2026-11-08T21: ...`

Registros con el mismo requestId:

```
api-gateway        GET /api/v1/orders/ped_0020 -> 200 (15 ms) cuentaId=cta_0018
auth-service       POST /internal/introspect -> 200 (4 ms) cuentaId=None
orders-service     GET /orders/ped_0020 -> 200 (2 ms) cuentaId=cta_0018
```

**Denegada: otra cuenta con sesión válida**

`GET /api/v1/orders/ped_0020` con requestId `demo-91561857` · C1 deniega

Respuesta 404: `{"error": {"codigo": "NO_ENCONTRADO", "mensaje": "Pedido no encontrado.", "requestId": "demo-91561857"}}`

Registros con el mismo requestId:

```
api-gateway        GET /api/v1/orders/ped_0020 -> 404 (14 ms) cuentaId=cta_0019
auth-service       POST /internal/introspect -> 200 (3 ms) cuentaId=None
orders-service     GET /orders/ped_0020 -> 404 (2 ms) cuentaId=cta_0019
```

**Referencia: pedido que no existe**

`GET /api/v1/orders/ped_9999` con requestId `demo-15107439` · C1

Respuesta 404: `{"error": {"codigo": "NO_ENCONTRADO", "mensaje": "Pedido no encontrado.", "requestId": "demo-15107439"}}`

Registros con el mismo requestId:

```
api-gateway        GET /api/v1/orders/ped_9999 -> 404 (15 ms) cuentaId=cta_0019
auth-service       POST /internal/introspect -> 200 (4 ms) cuentaId=None
orders-service     GET /orders/ped_9999 -> 404 (2 ms) cuentaId=cta_0019
```

## 4. Pago por la plataforma de prueba, aviso firmado, boleta y despacho (S20, S21, S23, S18, S19, S17)

**Iniciar pago**

`POST /api/v1/orders/ped_0020/payments` con requestId `demo-19458123`

Respuesta 201: `{"pagoId": "pag_0013", "estado": "pendiente", "urlPago": "https://127.0.0.1:9201/pagar/YUGyJHy0_Ud2kMcBRhyLFw", "expiraEn": "2026-11-08T22:14:10Z"}`

Registros con el mismo requestId:

```
api-gateway        POST /api/v1/orders/ped_0020/payments -> 201 (44 ms) cuentaId=cta_0018
auth-service       POST /internal/introspect -> 200 (3 ms) cuentaId=None
orders-service     GET /internal/orders/ped_0020/payable -> 200 (2 ms) cuentaId=None
payments-service   POST /orders/ped_0020/payments -> 201 (27 ms) cuentaId=cta_0018
```

La pasarela de prueba envía el aviso firmado con HMAC-SHA256 (la firma y el secreto no se muestran).

**El pedido quedó pagado**

`GET /api/v1/orders/ped_0020` con requestId `demo-25636486`

Respuesta 200: `{"id": "ped_0020", "estado": "pagado", "estadoPago": "aprobado", "items": [{"productoId": "prod_002", "nombre": "Margarita", "precioUnitario": 7990, "cantidad": 2}], "total": 15980, "direccionEntrega": {"calle": "Calle Ficticia 321", "comuna": "Maipú", "referencia": ""}, "historialEstados": [{"estado": "pendiente_pago", "fecha": "2026-11-08T21:59:10Z"}, {"estado": "pagado", "fecha": "2026-11-08T21:59:13Z"}], "boletaD ...`

Registros con el mismo requestId:

```
api-gateway        GET /api/v1/orders/ped_0020 -> 200 (16 ms) cuentaId=cta_0018
auth-service       POST /internal/introspect -> 200 (4 ms) cuentaId=None
orders-service     GET /orders/ped_0020 -> 200 (2 ms) cuentaId=cta_0018
```

**Boleta del pedido**

`GET /api/v1/orders/ped_0020/receipt` con requestId `demo-30214401`

Respuesta 200: `{"numeroBoleta": "B-000010", "fechaEmision": "2026-11-08T21:59:13Z", "pedidoId": "ped_0020", "clienteNombre": "Cliente Demo 900206", "items": [{"nombre": "Margarita", "cantidad": 2, "precioUnitario": 7990}], "total": 15980, "ivaIncluido": 2551}`

Registros con el mismo requestId:

```
api-gateway        GET /api/v1/orders/ped_0020/receipt -> 200 (15 ms) cuentaId=cta_0018
auth-service       POST /internal/introspect -> 200 (3 ms) cuentaId=None
payments-service   GET /orders/ped_0020/receipt -> 200 (2 ms) cuentaId=cta_0018
```

Correo de boleta en el servidor de prueba: sí, asunto "Boleta B-000010 - Pizzería La Fornace".

**Cola de despacho (encargado de despachos)**

`GET /api/v1/admin/dispatch-orders?limit=100` con requestId `demo-35850934`

Respuesta 200: `[{"numeroOrden": "OD-000006", "pedidoId": "ped_0011", "pagadoEn": "2026-11-08T21:58:12Z", "clienteNombre": "Cliente nb 321322", "telefono": "+56919524555", "direccionEntrega": {"calle": "Calle Ficticia 321322", "comuna": "Maipú", "referencia": ""}, "items": [{"nombre": "Bebida 500ml", "cantidad": 2}], "impresa": false}, {"numeroOrden": "OD-000007", "pedidoId": "ped_0016", "pagadoEn": "2026-11-08T21:58:21Z", "clienteN ...`

Registros con el mismo requestId:

```
api-gateway        GET /api/v1/admin/dispatch-orders -> 200 (13 ms) cuentaId=usr_0004
auth-service       POST /internal/introspect -> 200 (3 ms) cuentaId=None
dispatch-service   GET /admin/dispatch-orders -> 200 (2 ms) cuentaId=usr_0004
```

**Imprimir la orden**

`GET /api/v1/admin/dispatch-orders/ped_0020/print` con requestId `demo-62966601`

Respuesta 200: `<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Orden OD-000010</title></head><body><h1>Orden OD-000010</h1><p>Pedido ped_0020 - pagado 2026-11-08T21:59:13Z</p><p>Cliente: Cliente De`

Registros con el mismo requestId:

```
api-gateway        GET /api/v1/admin/dispatch-orders/ped_0020/print -> 200 (15 ms) cuentaId=usr_0004
auth-service       POST /internal/introspect -> 200 (4 ms) cuentaId=None
dispatch-service   GET /admin/dispatch-orders/ped_0020/print -> 200 (3 ms) cuentaId=usr_0004
```

**Estado en_preparacion**

`PATCH /api/v1/admin/orders/ped_0020/status` con requestId `demo-91523377`

Respuesta 200: `{"id": "ped_0020", "estado": "en_preparacion", "estadoPago": "aprobado", "items": [{"productoId": "prod_002", "nombre": "Margarita", "precioUnitario": 7990, "cantidad": 2}], "total": 15980, "direccionEntrega": {"calle": "Calle Ficticia 321", "comuna": "Maipú", "referencia": ""}, "historialEstados": [{"estado": "pendiente_pago", "fecha": "2026-11-08T21:59:10Z"}, {"estado": "pagado", "fecha": "2026-11-08T21:59:13Z"}, { ...`

Registros con el mismo requestId:

```
api-gateway        PATCH /api/v1/admin/orders/ped_0020/status -> 200 (17 ms) cuentaId=usr_0004
auth-service       POST /internal/introspect -> 200 (3 ms) cuentaId=None
orders-service     PATCH /admin/orders/ped_0020/status -> 200 (4 ms) cuentaId=usr_0004
```

**Estado en_despacho**

`PATCH /api/v1/admin/orders/ped_0020/status` con requestId `demo-86578753`

Respuesta 200: `{"id": "ped_0020", "estado": "en_despacho", "estadoPago": "aprobado", "items": [{"productoId": "prod_002", "nombre": "Margarita", "precioUnitario": 7990, "cantidad": 2}], "total": 15980, "direccionEntrega": {"calle": "Calle Ficticia 321", "comuna": "Maipú", "referencia": ""}, "historialEstados": [{"estado": "pendiente_pago", "fecha": "2026-11-08T21:59:10Z"}, {"estado": "pagado", "fecha": "2026-11-08T21:59:13Z"}, {"es ...`

Registros con el mismo requestId:

```
api-gateway        PATCH /api/v1/admin/orders/ped_0020/status -> 200 (17 ms) cuentaId=usr_0004
auth-service       POST /internal/introspect -> 200 (3 ms) cuentaId=None
orders-service     PATCH /admin/orders/ped_0020/status -> 200 (5 ms) cuentaId=usr_0004
```

**Estado entregado**

`PATCH /api/v1/admin/orders/ped_0020/status` con requestId `demo-88341383`

Respuesta 200: `{"id": "ped_0020", "estado": "entregado", "estadoPago": "aprobado", "items": [{"productoId": "prod_002", "nombre": "Margarita", "precioUnitario": 7990, "cantidad": 2}], "total": 15980, "direccionEntrega": {"calle": "Calle Ficticia 321", "comuna": "Maipú", "referencia": ""}, "historialEstados": [{"estado": "pendiente_pago", "fecha": "2026-11-08T21:59:10Z"}, {"estado": "pagado", "fecha": "2026-11-08T21:59:13Z"}, {"esta ...`

Registros con el mismo requestId:

```
api-gateway        PATCH /api/v1/admin/orders/ped_0020/status -> 200 (16 ms) cuentaId=usr_0004
auth-service       POST /internal/introspect -> 200 (3 ms) cuentaId=None
orders-service     PATCH /admin/orders/ped_0020/status -> 200 (5 ms) cuentaId=usr_0004
```

## 5. Reporte del dueño (S34)

**Ventas de los últimos 7 días**

`GET /api/v1/admin/reports/sales?desde=2026-11-01&hasta=2026-11-08` con requestId `demo-62954688`

Respuesta 200: `{"desde": "2026-11-01", "hasta": "2026-11-08", "totalVentas": 120340, "cantidadVentas": 10, "porDia": [{"fecha": "2026-11-08", "ventas": 10, "total": 120340}], "topProductos": [{"productoId": "prod_002", "nombre": "Margarita", "unidades": 8}, {"productoId": "prod_007", "nombre": "Bebida 500ml", "unidades": 3}, {"productoId": "prod_001", "nombre": "Napolitana", "unidades": 2}, {"productoId": "prod_003", "nombre": "Cua ...`

Registros con el mismo requestId:

```
api-gateway        GET /api/v1/admin/reports/sales -> 200 (14 ms) cuentaId=usr_0002
auth-service       POST /internal/introspect -> 200 (3 ms) cuentaId=None
payments-service   GET /admin/reports/sales -> 200 (3 ms) cuentaId=usr_0002
```

## 6. Detalle por GraphQL en una sola llamada (R36)

**resumenPedido (orders + inventory)**

`POST /api/v1/graphql` con requestId `demo-37013854`

Respuesta 200: `{"data": {"resumenPedido": {"id": "ped_0020", "estado": "entregado", "total": 15980, "items": [{"nombre": "Margarita", "cantidad": 2, "producto": {"id": "prod_002", "nombre": "Margarita", "precio": 7990, "disponible": true}}]}}}`

Registros con el mismo requestId:

```
api-gateway        POST /api/v1/graphql -> 200 (35 ms) cuentaId=cta_0018
auth-service       POST /internal/introspect -> 200 (3 ms) cuentaId=None
graphql-gateway    POST /graphql -> 200 (19 ms) cuentaId=cta_0018
inventory-service  GET /products -> 200 (2 ms) cuentaId=cta_0018
orders-service     GET /orders/ped_0020 -> 200 (2 ms) cuentaId=cta_0018
```

