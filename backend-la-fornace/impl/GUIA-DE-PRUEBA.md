# Guía de prueba del backend por API

Pizzería La Fornace, Unidad 2. La entrega es el backend: esta guía lo prueba por su API, sin abrir el frontend, con los datos de la Evaluación 1 (catálogo de 12 productos de `frontend-la-fornace`). Cada paso indica qué hacer y qué resultado esperar.

## 0. Qué necesita

- Una de las dos formas de ejecutarlo (ver `README.md`): **A** Docker Desktop con `docker compose`, o **B** MongoDB, Vault y ActiveMQ instalados en el equipo.
- Python 3 y `curl` (en Windows PowerShell use `curl.exe`).
- Todos los comandos se ejecutan dentro de esta carpeta. En Windows use `py` si `python` no funciona.

Certificado: el sistema usa TLS con una CA propia. Para `curl` use `--cacert <CA>`, donde `<CA>` es `.run/ca.crt` en el modo A y `.run/certs/ca.crt` en el modo B.

## 1. Iniciar y cargar datos

Modo A:

```
python scripts/compose.py up
python scripts/compose.py semilla
python scripts/compose.py estado
```

`up` debe terminar con `todos los servicios estan sanos`. `estado` debe mostrar publicados solo `127.0.0.1:8443` (API Gateway), `127.0.0.1:8080` (frontend de demostración) y `127.0.0.1:9201` (proveedor de pago de prueba). Los 7 sistemas, GraphQL, MongoDB, Vault y ActiveMQ no tienen puerto publicado. La columna de salud de `mongo` queda vacía (no tiene healthcheck).

Modo B (con el entorno de `README.md` activo):

```
python scripts/stack.py up
python scripts/seed.py
python scripts/stack.py status
```

`up` debe mostrar los 11 servicios en `OK`.

La semilla debe mostrar `{"personal": 4, "clientes": 2, "productos": 12}`. Las contraseñas de las cuentas de ejemplo están en `.run/credenciales-demo.json`:

| Correo | Rol |
| --- | --- |
| admin@ejemplo.cl | administrador |
| dueno@ejemplo.cl | dueño |
| cajero@ejemplo.cl | cajero virtual |
| despachos@ejemplo.cl | encargado de despachos |
| camila@ejemplo.cl, pedro@ejemplo.cl | clientes |

Catálogo cargado (mismos nombres y precios que `js/data.js` de la Evaluación 1):

| Id | Producto | Precio | Id | Producto | Precio |
| --- | --- | --- | --- | --- | --- |
| prod_001 | Napolitana | 8.990 | prod_007 | Bebida 500ml | 1.990 |
| prod_002 | Margarita | 7.990 | prod_008 | Pan de Ajo | 3.490 |
| prod_003 | Cuatro Quesos | 10.990 | prod_009 | Combo Solo | 10.490 |
| prod_004 | Prosciutto e Funghi | 11.990 | prod_010 | Combo Dúo | 18.990 |
| prod_005 | Diávola | 10.490 | prod_011 | Combo Familiar | 28.990 |
| prod_006 | Vegetariana | 9.490 | prod_012 | Combo Noche Fornace | 34.990 |

## 2. Cómo enviar las peticiones

Todas pasan por el API Gateway: `https://127.0.0.1:8443/api/v1/...`. En PowerShell y cmd las comillas del JSON dentro de `-d '...'` se pierden: guarde el cuerpo en un archivo y use `-d @archivo.json`. Agregue `-w "\nHTTP %{http_code}\n"` para ver el código de estado.

## 3. Compra completa por API

1. **Catálogo anónimo (S06).**

   ```
   curl --cacert <CA> https://127.0.0.1:8443/api/v1/products
   ```

   Esperado: 200 con 12 productos, sin campo `stock`.

2. **Registro (S03).** Guarde `registro.json` (cambie el correo y el RUN si ya los usó; `11222333-9` es un RUN válido):

   ```
   {"run":"11222333-9","nombreCompleto":"Alumno Prueba","correo":"alumno@ejemplo.cl","password":"ClaveDePrueba2026","telefono":"+56912345678","fechaNacimiento":"1992-02-02","sexo":"F","direccion":{"calle":"Calle Ficticia 321","comuna":"Maipú","provincia":"Santiago","region":"Metropolitana"}}
   ```

   ```
   curl --cacert <CA> -H "Content-Type: application/json" -d @registro.json https://127.0.0.1:8443/api/v1/auth/register
   ```

   Esperado: 201 con la cuenta en `pendiente_verificacion`. Un RUN repetido da 409 y uno inválido 400.

3. **Correo de confirmación (S04).** El servidor de correo de prueba guarda el mensaje:

   ```
   python scripts/bandeja.py alumno@ejemplo.cl                 (modo B)
   python scripts/compose.py bandeja alumno@ejemplo.cl         (modo A)
   ```

   El cuerpo trae un enlace terminado en `token=<TOKEN>`. Copie solo el valor del token.

4. **Verificar el correo.** Guarde `verificar.json` con `{"token":"<TOKEN>"}`:

   ```
   curl --cacert <CA> -H "Content-Type: application/json" -d @verificar.json https://127.0.0.1:8443/api/v1/auth/verify-email
   ```

   Esperado: 200. Repetir con el mismo token da 410 `TOKEN_VENCIDO` (es de un solo uso).

5. **Iniciar sesión (S01).** Guarde `login.json` con `{"correo":"alumno@ejemplo.cl","password":"ClaveDePrueba2026"}`:

   ```
   curl --cacert <CA> -H "Content-Type: application/json" -d @login.json https://127.0.0.1:8443/api/v1/auth/login
   ```

   Esperado: 200 con `access_token`. Úselo como `TOKEN` en los pasos siguientes. Una contraseña incorrecta da 401 y desde el sexto intento fallido 429 con `Retry-After`.

6. **Crear el pedido (S12).** Guarde `pedido.json` (Napolitana y Bebida; la dirección sale del perfil, y el precio y el total los fija el servidor):

   ```
   {"items":[{"productoId":"prod_001","cantidad":1},{"productoId":"prod_007","cantidad":1}]}
   ```

   ```
   curl --cacert <CA> -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" -d @pedido.json https://127.0.0.1:8443/api/v1/orders
   ```

   Esperado: 201, estado `pendiente_pago`, total 10.980. Anote el `id` (`<PED>`). Una comuna fuera de la cobertura (Maipú, Cerrillos, Pudahuel, Estación Central) da 422.

7. **Iniciar el pago (S20).** Guarde `pago.json` con `{"medio":"servipag"}`:

   ```
   curl --cacert <CA> -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" -d @pago.json https://127.0.0.1:8443/api/v1/orders/<PED>/payments
   ```

   Esperado: 201 con `pagoId` y `urlPago`. Abra `urlPago` en el navegador (es la página del proveedor de pago de prueba, `https://127.0.0.1:9201/pagar/...`; acepte el certificado) y presione **Aprobar pago**. El proveedor envía el aviso firmado (HMAC-SHA256) al API Gateway.

8. **Estado, boleta y orden de despacho (S14, S23, S18).**

   ```
   curl --cacert <CA> -H "Authorization: Bearer <TOKEN>" https://127.0.0.1:8443/api/v1/orders/<PED>
   curl --cacert <CA> -H "Authorization: Bearer <TOKEN>" https://127.0.0.1:8443/api/v1/orders/<PED>/receipt
   ```

   Esperado: estado `pagado`; boleta con número `B-...`, total 10.980 e IVA incluido. La boleta también llega al correo de prueba (`bandeja`). Con la cuenta `despachos@ejemplo.cl`, `GET /api/v1/admin/dispatch-orders` lista la orden `OD-...` del pedido (llegó por ActiveMQ), sin precios ni datos de pago.

9. **Avance del pedido (S17).** Con el token de `despachos@ejemplo.cl`, `PATCH /api/v1/admin/orders/<PED>/status` con `{"estado":"en_preparacion"}`, luego `en_despacho` y `entregado`: 200 cada uno. Volver a un estado anterior da 409 `TRANSICION_INVALIDA`.

10. **Detalle por GraphQL (R36).** `POST /api/v1/graphql` con el token del cliente y este cuerpo:

    ```
    {"query":"query($id:ID!){resumenPedido(id:$id){id estado total items{nombre cantidad producto{id nombre precio disponible}}}}","variables":{"id":"<PED>"}}
    ```

    Esperado: 200 con el pedido y el producto vigente de cada ítem, armado con una sola llamada (orders e inventory).

11. **Reporte del dueño (S34).** Con el token de `dueno@ejemplo.cl`: `GET /api/v1/admin/reports/sales?desde=AAAA-MM-DD&hasta=AAAA-MM-DD` con el rango de hoy: 200 con totales, ventas por día y los diez productos más vendidos. Un rango de más de 92 días da 400; un cliente recibe 403.

## 4. Controles de seguridad

Reemplace `<CLAVE>` y `<CLAVE2>` por las contraseñas de `camila@ejemplo.cl` y `pedro@ejemplo.cl` de `.run/credenciales-demo.json`.

| Prueba | Comando | Resultado esperado |
| --- | --- | --- |
| Sin sesión | `curl -i --cacert <CA> https://127.0.0.1:8443/api/v1/orders` | 401 |
| Iniciar sesión | login de Camila como en el paso 5 | 200 con `access_token` (`TOKEN_C`) |
| Precio alterado | `POST /orders` con `{"items":[{"productoId":"prod_001","cantidad":1}],"total":1,"estado":"pagado"}` y `TOKEN_C` | 201, total 8.990 (del catálogo) y estado `pendiente_pago`. Anote el `id` (`<ID>`) |
| Pedido propio | `GET /orders/<ID>` con `TOKEN_C` | 200 |
| Pedido ajeno | `GET /orders/<ID>` con el token de Pedro (`TOKEN_P`) | 404, igual a la respuesta para un pedido inexistente |
| Rol insuficiente | `GET /admin/users` con `TOKEN_C` | 403 |
| Aviso de pago falso | `POST /payments/webhook` con `X-Timestamp: 1`, `X-Signature: sha256=00` y `{"pagoId":"pag_0001","estado":"aprobado","monto":1}` | 401 y el pedido no cambia |
| Sin rutas internas | `GET /internal/introspect` | 404 |
| Introspección GraphQL | consulta `{__schema{types{name}}}` en `/graphql` con `TOKEN_C` | Error `CONSULTA_INVALIDA`, sin esquema |
| Acceso directo a un sistema (solo modo A) | abrir `https://127.0.0.1:9104/health` (orders) | No conecta: el puerto no está publicado |
| Acceso directo sin secreto (modo A y B) | solo desde la red privada o con la batería del modo B (`T-DAT-05`, `T-AUT-11`) | 401 con secreto ausente, de otro destino o sin identidad |

## 5. Indisponibilidad de dependencias (modo A)

Con el sistema levantado y un pedido listo para pagar:

1. Detener el servicio de despacho: `docker compose -p fornace stop dispatch-service`. Pagar un pedido (paso 7). Esperado: el pedido queda `pagado`. `GET /admin/dispatch-orders` responde 503 "Servicio no disponible" con código de soporte. Reiniciar con `docker compose -p fornace start dispatch-service`: la orden `OD-...` aparece **una sola vez**.
2. Detener la cola: `docker compose -p fornace stop broker`. Pagar otro pedido. Esperado: queda `pagado` con `despachoPublicado` en falso; orders reintenta cada 30 s. Reiniciar con `docker compose -p fornace start broker`: la orden llega una sola vez.

En el modo B esos casos y otros cinco (F1 a F7) están automatizados en la batería.

## 6. Batería automática (modo B)

```
python scripts\run_tests.py
```

Ejecuta 193 pruebas desde cero: seguridad (32), negocio (73), GraphQL (16), retención (14), gateway (13), navegador real sobre el frontend de demostración (27), carga C1 a C9 (11) y fallos F1 a F7 (7). Dura unos 20 minutos y termina con `TOTAL 193/193`. Los resultados quedan en `tests/resultados/*.json`, las capturas en `tests/evidencia/` y la transcripción de los flujos por API (con el `requestId` de cada llamada y las líneas de registro que dejaron los sistemas) en `tests/evidencia/demo-flujos.md`. Para omitir la carga y las caídas: `--sin-carga` (dura bastante menos).

## 7. Registros con correlación

Modo A: `python scripts/compose.py logs`. Modo B: `.run/logs/*.log`. Cada línea es JSON y una misma petición lleva el mismo `requestId` en el API Gateway, auth, orders, inventory y GraphQL. No hay contraseñas, tokens ni datos personales. Para seguir una petición, busque su `requestId` (la respuesta de error lo trae como código de soporte, y el cliente puede enviar `X-Request-Id`).

## 8. Detener

```
python scripts/compose.py down              # modo A: detiene y conserva los datos
python scripts/compose.py down --borrar     # modo A: elimina también datos, certificados y secretos
python scripts\stack.py down --todo         # modo B: detiene todo y borra las bases del proyecto
```

## 9. Problemas frecuentes

| Síntoma | Causa y solución |
| --- | --- |
| `curl` falla por certificado | Falta `--cacert <CA>` o la CA cambió tras `down --borrar`: use la CA nueva |
| Registro desde un navegador dice "No pudimos conectarnos" | Acepte de nuevo `https://127.0.0.1:8443/health` y `https://127.0.0.1:9201/health` |
| `bandeja` no muestra correos | Use el correo exacto con que se registró; espere unos segundos |
| Puerto 8443, 8080 o 9201 ocupado | Detenga el otro modo (`compose.py down` o `stack.py down --todo`) |
| Modo B: `No module named 'fornace'` | Falta `pip install -e common` dentro del entorno virtual activo |
| Modo B: `MongoDB no responde en 127.0.0.1:27017` | Inicie el servicio: `Start-Service MongoDB` (PowerShell como administrador) |
| Modo B: `down --todo` no borra datos | MongoDB debe estar en ejecución; solo se eliminan las bases `*_db` |
| Olvidó una contraseña de ejemplo | Está en `.run/credenciales-demo.json` |
