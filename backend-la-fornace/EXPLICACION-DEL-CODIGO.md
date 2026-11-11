# Explicación del código: qué había, qué se añadió, cómo funciona y por qué funciona

Pizzería La Fornace, Unidad 2. Cada sección compara una pieza del backend entregado con lo que ya existía en su repositorio (`unab-desarrollo-web-movil`).

Aclaración de partida: el código de `impl/` se escribió nuevo siguiendo la guía de la evaluación. No es una copia de sus laboratorios, pero usa las mismas ideas y tecnologías. Donde su laboratorio ya resolvía algo, se indica.

Alcance: la entrega es el **backend**, que se prueba por su API con los datos del frontend de la Evaluación 1 (los 12 productos de `data.js`). La sección 1 describe `impl/frontend/`, una demostración opcional que consume esa API; el backend no depende de ella.

## 0. Mapa general

```
Navegador (frontend, :8080)
   |  HTTPS, token Bearer
   v
API Gateway (:8443)  ----->  Auth Service        valida el token (introspección)
   |  añade identidad verificada + secreto propio de cada destino
   v
clients | inventory | orders | payments | dispatch | notifications      (red privada, sin puertos publicados)
                          |                |
                          v                v
                   GraphQL Gateway     Cola STOMP  --->  dispatch
   Cada sistema: su propia base MongoDB, sus secretos en Vault, TLS entre todos.
```

Una petición típica, "ver mi pedido":
1. El navegador envía `GET /api/v1/orders/ped_0001` con `Authorization: Bearer <token>`.
2. El gateway busca la ruta en `routes.json`, comprueba el límite de tasa, pregunta a Auth si el token es válido y qué rol tiene, y comprueba que el rol esté permitido para esa ruta.
3. El gateway borra cualquier identidad que traiga el navegador y reenvía a orders con la identidad verificada y el secreto `gateway-to-orders`.
4. Orders comprueba ese secreto contra Vault, y luego comprueba que el pedido pertenezca a esa cuenta. Si no, responde 404.

## 1. Frontend (`impl/frontend/`)

| | |
|---|---|
| **Lo que tenía** | `frontend-la-fornace` con 5 páginas, `data.js` con productos de mentira, carrito en `localStorage` y login "simulado" (`main.js` mostraba "Sesión iniciada (simulada) — sin backend"). |
| **Lo que se añadió** | `js/api.js` (cliente del API Gateway), `js/panel.js` (panel del personal) y 6 páginas nuevas: registro, confirmar correo, retorno de pago, mis pedidos, mi cuenta y panel. `main.js` y los HTML se modificaron para llamar al backend. El CSS y Bootstrap quedaron iguales. |
| **Cómo funciona** | Al iniciar sesión, `api.js` guarda el token en `sessionStorage` y lo envía en cada petición. El catálogo, el carrito, el pedido y el pago salen de las APIs. El carrito solo guarda `id` y `cantidad`; los precios los trae el servidor. |
| **Por qué funciona / es seguro** | El navegador nunca recibe secretos de servicios ni decide precios o pagos. `sessionStorage` se borra al cerrar la pestaña. Todo texto que viene del API se escapa con `esc()` antes de insertarse en la página, lo que evita inyectar HTML. El token de verificación de correo viaja después de `#`, que el navegador no envía al servidor. |

## 2. API Gateway (`services/api_gateway/main.py`)

| | |
|---|---|
| **Lo que tenía** | `lab-api-gateway/api-gateway/gateway.py`: valida el token llamando a `/introspect` de Auth, aplica una matriz de permisos por rol (`PERMISSIONS`) y reenvía a un backend con cabeceras `X-Authenticated-*` y `X-Gateway-Secret`. Tenía 3 rutas escritas a mano y un secreto por omisión incrustado en el código (`"PizzeriaSecret123"`). |
| **Lo que se añadió** | Rutas en una tabla (`common/fornace/routes.json`, 36 rutas) en lugar de una función por ruta; un secreto distinto por destino leído de Vault; límite de tasa por IP y por cuenta; límite de tamaño de cuerpo; cabeceras de seguridad y CORS restringido al frontend; si Auth no responde, falla cerrado con 503; y la ruta de webhook de pago sin token (se valida por firma). |
| **Cómo funciona** | `buscar()` compara el verbo y la ruta con la tabla (404 si no existe, 405 si el verbo no coincide). Si la ruta es autenticada, `introspeccionar()` pregunta a Auth. Después compara el rol con la lista de la ruta (403 si no coincide). Arma las cabeceras desde cero (`h = {...}`), de modo que lo que mande el navegador como identidad no pasa. Reenvía con `httpx` y devuelve la respuesta. |
| **Por qué funciona** | Es el único componente con puerto publicado, así que no hay otro camino hacia los sistemas. Los sistemas internos solo confían en el gateway porque exigen el secreto `gateway-to-<destino>` que solo el gateway y ese destino conocen. Como el gateway construye las cabeceras de identidad, un cliente no puede hacerse pasar por otro. |

Prueba relacionada: `T-AUT` y `GW-*` (módulo 10, secciones 10.9.1 y 10.9.6).

## 3. Auth Service (`services/auth/main.py`)

| | |
|---|---|
| **Lo que tenía** | `auth_service.py`: 3 usuarios escritos en una lista (`USERS_DB`) con contraseñas en texto plano (`"123"`, `"456"`, `"789"`), sesiones en un diccionario en memoria y un secreto por omisión incrustado. Tenía `/login`, `/introspect` y `/logout`. |
| **Lo que se añadió** | Cuentas en MongoDB; contraseñas con **bcrypt**; el token se guarda como hash SHA-256 (si se filtra la base, los tokens no sirven); sesiones en la base, que persisten y se pueden revocar; bloqueo tras 5 intentos fallidos (429 con `Retry-After`); registro, verificación de correo, reenvío, y administración de personal (crear, listar, editar, desactivar); estados de cuenta (`pendiente_verificacion`, `activo`, `inactivo`); y rutas `/internal/...` solo para otros sistemas. |
| **Cómo funciona** | `login()` cuenta los intentos fallidos recientes del correo; si hay demasiados, bloquea. Compara la contraseña con bcrypt y, si el correo no existe, compara contra un hash de relleno (`DUMMY`) para tardar lo mismo. Si todo está bien y la cuenta está activa, crea un token aleatorio de 256 bits, guarda su hash y su vencimiento y devuelve el token. `introspect()` busca el hash del token, comprueba que esté activa, que no haya vencido y que la cuenta siga activa. |
| **Por qué funciona** | bcrypt es lento a propósito y lleva sal, lo que frena ataques de fuerza bruta contra una base filtrada. El hash de relleno evita que alguien descubra qué correos existen midiendo tiempos. Como la sesión está en la base, `logout` la desactiva de verdad y un token vencido deja de servir. |

## 4. Código compartido (`common/fornace/`)

Su laboratorio repetía en cada archivo la comprobación `if x_gateway_secret != GATEWAY_SECRET`. Aquí esa lógica está en un solo lugar y la usan los 7 sistemas.

| Archivo | Qué hace y por qué funciona |
|---|---|
| `guard.py` | Cada ruta declara quién puede llamarla (`roles`, `pares`, `publica`). Verifica que la llamada venga del gateway (con su secreto) o de un sistema permitido (con el secreto de ese par) y construye el contexto con la cuenta y los roles. Reemplaza al `verify_gateway_secret` de su `auth_service.py`, pero añade el control de rol y el de llamador. |
| `topology.py` | Tabla de qué sistema puede llamar a cuál y con qué secreto (`PARES`), y qué secretos de Vault lee cada componente. Así ningún sistema puede llamar a uno al que no le toca. |
| `vault.py` | Lee secretos de Vault con un token de solo lectura, los guarda en memoria unos minutos y, si Vault cae, sigue con el valor en memoria durante una ventana y luego responde 503. Las comparaciones usan `hmac.compare_digest` (tiempo constante). Durante una rotación acepta el valor actual y el anterior. |
| `svc.py` | Cliente para llamadas entre sistemas: agrega el secreto del par, usa TLS con la CA del proyecto, tiene plazos y reintentos, y convierte un fallo de red en un 503 controlado. |
| `base.py` | Fábrica de cada sistema: errores con formato uniforme, registros en JSON con `requestId` (sin cuerpos, cabeceras ni datos personales), desactiva `/docs` y `/openapi.json`, y arranca con TLS. |
| `db.py` | Conexión a MongoDB; se conecta con el usuario de MongoDB del sistema, cuya clave se lee de Vault (`MONGO_AUTH=1`, activo en Docker Compose; en modo local `MONGO_AUTH=0`), y maneja contadores para los IDs. |
| `retencion.py` | Plazos de retención del Módulo 7 (7.9) y la fecha de corte. Cada sistema usa `corte(...)` en su tarea periódica para eliminar o anonimizar sus datos vencidos; `RETENCION_SEGUNDOS` define cada cuánto corre. |
| `util.py` | Validación del RUN con dígito verificador (módulo 11), paginación y rangos de fechas. |
| `routes.json` | Las 36 rutas, con verbo, sistema destino, roles, política de límite de tasa, tamaño máximo y plazo. |

## 5. Orders (`services/orders/main.py`)

| | |
|---|---|
| **Lo que tenía** | Su `backend_api.py` devolvía un menú fijo; su `graphql-pizzeria` tenía un modelo `Pedido` con `addPedido`, `confirmarPago` y `anularPedido` que cualquiera podía llamar sin autenticación. |
| **Lo que se añadió** | Creación de pedido con precio tomado de inventory; reserva de stock; verificación de cobertura de comuna; estados controlados (`pendiente_pago` a `pagado`, `en_preparacion`, `en_despacho`, `entregado`, `anulado`) con historial; anulación con motivo y devolución de stock; vencimiento automático de pedidos sin pago; publicación de la orden a la cola; y la regla de que solo un pago confirmado por payments pasa un pedido a `pagado`. |
| **Cómo funciona** | `crear_pedido()` pide el perfil a clients, valida la comuna, reserva stock en inventory (con reintento y liberación si falla) y calcula el total sumando `precioUnitario × cantidad` con los precios que devuelve inventory. El cliente solo envía `productoId` y `cantidad`. `propio_o_personal()` devuelve 404 si el pedido no es de esa cuenta. `i12` (confirmación de pago) comprueba que el pedido siga pendiente, que no haya vencido y que el monto coincida; solo entonces lo pasa a `pagado` y publica la orden. |
| **Por qué funciona** | Que el total salga del servidor elimina la manipulación de precios desde el navegador. El 404 idéntico para "ajeno" e "inexistente" no revela qué pedidos existen. La actualización de estado es condicional (`estado: 'pendiente_pago'`), así que un pago repetido no cambia nada. |

## 6. Inventory (`services/inventory/main.py`)

| | |
|---|---|
| **Lo que tenía** | Un menú fijo en memoria (`MENU_ITEMS`) y `fastapi-items`, un CRUD de ítems con MongoDB sin autorización. |
| **Lo que se añadió** | Catálogo público que oculta el stock; administración (crear, editar, retirar, ajustar stock) solo para administrador y dueño; reservas de stock por pedido con vencimiento; movimientos de stock; y una tarea que libera reservas vencidas cada minuto. |
| **Cómo funciona** | `reservar()` descuenta stock bajo un candado (`BLOQUEO`) y registra el movimiento. Un índice único sobre `pedidoId` evita reservar dos veces el mismo pedido. Si falla la creación del pedido o vence el plazo, la reserva se devuelve. |
| **Por qué funciona** | Inventory es la única autoridad de precio y stock. El candado y el índice único evitan vender más de lo que hay aunque lleguen pedidos simultáneos. La actualización condicional de MongoDB (`stock >= cantidad`) ya es atómica; el candado en el proceso es una defensa adicional que supone una sola instancia de inventory (declarado en la sección 10.11 del módulo 10). |

## 7. Clients (`services/clients/main.py`)

| | |
|---|---|
| **Lo que tenía** | Un modelo `Cliente` en `graphql-pizzeria` con campos como `run`, `nombre`, `correo`, `telefono`, accesible sin control. |
| **Lo que se añadió** | Registro de cliente que valida el RUN con dígito verificador, correo y teléfono; creación de la cuenta en Auth y compensación (borra la cuenta si falla guardar el perfil); perfil propio (`/clients/me`); administración de clientes; y una ruta interna que orders usa para obtener el perfil. |
| **Cómo funciona** | `POST /clients/register` llama a Auth para crear la cuenta pendiente y luego guarda el perfil. Si el guardado falla, llama a `DELETE /internal/accounts/{id}` para no dejar una cuenta sin perfil. |
| **Por qué funciona** | Como cada sistema tiene su propia base, no hay transacción entre ellos. La compensación mantiene consistente el resultado: nunca queda una cuenta sin perfil. |

## 8. Payments (`services/payments/main.py`) y el proveedor de pago de prueba

| | |
|---|---|
| **Lo que tenía** | La mutación `confirmarPago(id)` de su GraphQL, que marcaba un pedido como pagado sin ninguna verificación. |
| **Lo que se añadió** | Inicio del cobro; aviso de la plataforma (`/payments/webhook`) validado con firma HMAC-SHA256 y marca de tiempo; registro de ventas y número de boleta; boleta por correo; reporte de ventas; y una tarea de conciliación que repite la confirmación si falló. |
| **Cómo funciona** | La plataforma firma `timestamp + "." + cuerpo` con un secreto compartido. `s21()` rechaza el aviso si la hora está a más de 5 minutos o si la firma no coincide (401). Guarda cada `eventoId` con índice único para ignorar duplicados. Si el monto no coincide con el del pago, lo marca `observado` y no cambia el pedido. Solo un aviso `aprobado` y válido lleva a orders a marcar `pagado`. |
| **Por qué funciona** | Sin el secreto de Vault nadie puede fabricar un aviso válido, y la marca de tiempo evita reutilizar uno viejo. El navegador no participa en la decisión de si algo está pagado; solo ve el resultado. El pago del navegador al proveedor de prueba y el aviso firmado al gateway son canales separados. |

## 9. Dispatch (`services/dispatch/main.py`) y la cola

| | |
|---|---|
| **Lo que tenía** | `stomp/productor.py` y `consumidor.py`: envían y reciben mensajes por `/queue/cola_pedidos` (puerto 61613) en varios formatos (texto, ancho fijo, XML, JSON). |
| **Lo que se añadió** | Orders publica una orden de despacho en JSON al quedar pagado el pedido; dispatch la consume con confirmación manual (`ack: client`), valida el formato, guarda la orden sin precios y la expone al encargado de despachos; si el broker cae, reconecta; si llega un mensaje repetido, no duplica la orden. |
| **Cómo funciona** | `Oyente.on_message` valida el mensaje; solo cuando la orden quedó guardada envía `ack`. Un mensaje inválido se confirma y se registra para que no se reintente. Si el proceso cae a mitad, el mensaje sin confirmar se entrega otra vez. Orders republica cada 30 s las órdenes pendientes (`despachoPublicado` en falso). |
| **Por qué funciona** | La confirmación manual garantiza que ningún pedido pagado se pierde aunque dispatch o el broker caigan. La idempotencia por `pedidoId` garantiza que una orden repetida no se duplique. Se probó en F2 y F3. |

## 10. Notifications y simuladores (`services/notifications`, `pasarela_prueba`, `correo_prueba`)

| | |
|---|---|
| **Lo que se añadió** | Notifications envía los correos (verificación y boleta) al proveedor de correo con una clave de Vault; cada sistema solo puede usar su plantilla (auth la de verificación y payments la de boleta). La pasarela y el correo de prueba son adaptadores que conservan el contrato y la autenticación de un proveedor real. |
| **Por qué funciona** | Restringir qué sistema puede usar qué plantilla evita que un sistema comprometido envíe correos arbitrarios. Los simuladores permiten probar todo el flujo sin cobros ni envíos reales, como pide el paso 4 del Módulo 10 de la guía. |

## 11. GraphQL Gateway (`services/graphql_gateway/`, Node)

| | |
|---|---|
| **Lo que tenía** | `graphql-pizzeria/server.js`: Apollo con Mongoose directo a MongoDB. Su schema permitía crear, modificar y borrar usuarios, clientes, productos y pedidos. El tipo `Usuario` exponía el campo `pass`, y `getUsuarios` devolvía todos los usuarios. No había autenticación y CORS estaba abierto a cualquiera (`app.use(cors())`). |
| **Lo que se añadió** | Un schema **de solo lectura** con dos consultas: `resumenPedido` (combina orders e inventory) y `miCuenta` (clients y orders). No toca ninguna base: pide los datos a los sistemas por REST con su secreto propio. Solo se llega a él por el API Gateway. Antes de ejecutar valida la consulta contra límites de profundidad (5), costo (600), campos de primer nivel (3) y `limitePedidos` (1 a 20), y comprueba rol por operación y por campo. |
| **Cómo funciona** | `policy.js` analiza el documento y calcula profundidad y costo antes de llamar a ningún sistema. El resolver de `resumenPedido` pide el pedido a orders; para los productos de cada ítem usa un DataLoader, que junta todas las peticiones en una sola llamada a inventory. Si un subsistema falla, el campo devuelve `SUBSISTEMA_NO_DISPONIBLE` en lugar de un error genérico. |
| **Por qué funciona** | Sin mutaciones, GraphQL no puede alterar nada. Como los datos pasan por orders, la regla de propiedad de orders se aplica también aquí: otra cuenta recibe "no encontrado". Los límites impiden consultas abusivas que sobrecarguen los sistemas. El DataLoader evita el problema de N+1 llamadas. |

## 12. Secretos, certificados y Vault (`scripts/vault_init.py`, `certs.sh`, `bootstrap_compose.py`)

| | |
|---|---|
| **Lo que tenía** | `GATEWAY_SECRET = os.getenv("GATEWAY_SECRET", "PizzeriaSecret123")` en tres archivos: un mismo secreto para todos, con un valor por omisión visible en el código. Su informe del laboratorio sí usó Vault. |
| **Lo que se añadió** | `certs.sh` crea una CA del proyecto y un certificado por componente (con `subjectAltName` para el nombre del contenedor). `vault_init.py` genera al azar un secreto por par de sistemas y uno por destino del gateway, crea una política de solo lectura por componente según `topology.py` y entrega a cada uno un token que solo lee lo suyo. `bootstrap_compose.py` hace lo mismo dentro de Docker y deja en cada contenedor únicamente su certificado y su token; además `mongo_usuarios.py` crea en MongoDB un usuario por sistema (`<sistema>_user`, rol `readWrite` solo sobre `<sistema>_db`) con la clave que está en Vault, y MongoDB arranca con `--auth`. |
| **Por qué funciona** | Ningún secreto está en el repositorio: se crean al arrancar y viven en Vault. Si un componente se compromete, solo expone sus propios secretos, no los de los demás. TLS cifra el tráfico y, como cada cliente comprueba el nombre del servidor contra la CA, no se puede suplantar un servicio. |

## 13. Despliegue (`docker-compose.yml`, `Dockerfile.*`, `scripts/compose.py`)

| | |
|---|---|
| **Lo que tenía** | Docker para crear un segundo host (`docker network create` y un contenedor `python:3.12-slim`) en su laboratorio del gateway. |
| **Lo que se añadió** | Un `docker-compose.yml` con 15 contenedores y dos redes. La red `privada` es `internal: true` (sin salida a Internet y sin puertos publicados). Solo se publican, en `127.0.0.1`, el gateway (8443), el frontend (8080) y el proveedor de pago de prueba (9201). Los contenedores corren como usuario sin privilegios (uid 10001), con 512 MB y 1 CPU. `preparacion` genera certificados, secretos y tokens una sola vez. `compose.py` unifica los comandos (`up`, `semilla`, `bandeja`, `estado`, `down`). |
| **Por qué funciona** | Docker no crea ruta desde el exterior hacia una red interna, por eso orders, inventory y los demás son inalcanzables desde su equipo. La separación pública y privada que pide el Módulo 6 queda demostrada con `compose.py estado`. |

## 14. Datos de ejemplo (`scripts/seed.py`)

Crea 4 cuentas de personal (administrador, dueño, cajero, despachos), 2 clientes y 12 productos ficticios. Las contraseñas se generan al azar en cada equipo y se guardan en `.run/credenciales-demo.json`; los datos de su `data.js` original (por ejemplo, la Napolitana a 8.990) sirven de base para el catálogo.

## 15. Lo que debe poder explicar en la defensa

1. **Por qué un solo punto de entrada:** todo control (token, rol, límites) se aplica en un único lugar y los sistemas internos no son alcanzables desde afuera.
2. **Por qué un secreto distinto por par:** limita el daño si uno se filtra. En su laboratorio un solo secreto servía para todos.
3. **Por qué el servidor calcula el precio y decide el pago:** el navegador es controlado por el usuario y no es confiable.
4. **Por qué 404 y no 403 en un pedido ajeno:** no revela que el pedido existe.
5. **Por qué GraphQL es de solo lectura y pasa por orders:** hereda la autorización y reduce la superficie de ataque.
6. **Por qué dos formas de ejecución:** Docker Compose demuestra la separación pública y privada con redes de contenedores; el modo local (sin Docker) corre los mismos servicios contra MongoDB, Vault y ActiveMQ instalados en el equipo y permite ejecutar la batería de 193 pruebas. Los motores son los mismos en ambas.
7. **Qué no cubre:** usuarios de base de datos por sistema en modo local (`MONGO_AUTH=0`; en Docker Compose sí existen), la carga a escala completa, la batería completa dentro de contenedores, el aislamiento de red en modo local, y un token de sesión fuera de `sessionStorage` (10.11).
