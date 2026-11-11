# Evaluación Unidad 2 — Backend seguro completo
## Pizzería La Fornace (derivado del Caso 19)

---

# Portada

| Campo | Detalle |
| --- | --- |
| Caso elegido | **Caso 19 "Sistema de Ventas On-line"**, adaptado al negocio Pizzería La Fornace (Maipú) |
| Integrantes | Alejandro Suarez, Alvaro Asencios |
| Versión del frontend | Evaluación 1 (`frontend-la-fornace`, 5 páginas HTML + Bootstrap 5.3). Esta entrega es el **backend**: se prueba por su API con los datos de ese frontend (los 12 productos de `js/data.js`). Como demostración opcional, el mismo frontend se extendió a 11 páginas conectadas al backend (`impl/frontend`) |
| Qué entregamos | El **backend**. El profesor indicó que *la entrega de backend es con datos de frontend, no con el frontend integrado*: probamos la API con los datos y los flujos de la Evaluación 1 y dejamos el frontend integrado solo como demostración opcional (Módulo 10, 10.5). |
| Repositorio | github.com/AlejandroSuarez105/unab-desarrollo-web-movil |
| Fecha de entrega | 09 de noviembre de 2026 |

## Tecnologías (las del curso, con las versiones realmente usadas en la entrega)

| Componente | Tecnología | Origen en el repo |
| --- | --- | --- |
| Servicios REST | Python 3.13 + FastAPI (uvicorn, httpx, motor, bcrypt) | `fastapi-items`, `lab-api-gateway` |
| API Gateway y Auth Service | Python + FastAPI + httpx | `lab-api-gateway/api-gateway`, `auth_service` |
| GraphQL Gateway | Node.js 22 + Apollo Server 5.5.1 + GraphQL 16.11 + DataLoader | `graphql-pizzeria` |
| Base de datos | MongoDB 7 (una base por sistema; controlador `motor` en Python) | `fastapi-items`, `graphql-pizzeria` |
| Administrador de secretos | HashiCorp Vault 1.18 (modo desarrollo), API KV v2 | informe del lab de gateway |
| Mensajería de pedidos | Cola STOMP `/queue/cola_pedidos` en Apache ActiveMQ Classic 6.2.0 (persistente, confirmación manual) | `stomp/` |
| Entorno | Docker Compose con red privada interna y red pública (Módulo 6), o en local sin Docker con `scripts/stack.py` sobre MongoDB, Vault y ActiveMQ instalados en el equipo | informe del lab de gateway |

> **Desviación declarada del caso:** el RNF 3 y 4 del Caso 19 piden Oracle, procedimientos almacenados y .NET o J2EE. Usamos el stack de los laboratorios del curso (FastAPI, Node, MongoDB). El resto de los RNF se cumple (capas separadas, servicios web, API de correo, cifrado de clave, control de sesiones, validaciones, mensajes de error claros, diseño responsivo). Las demás diferencias con el diseño y las limitaciones de la ejecución se declaran en el Módulo 10 (sección 10.11).

---

# Módulo 1 — Servicios derivados del frontend

## 1.1 Pantallas del frontend actual

El frontend es HTML + JS plano. Hoy no tiene backend: productos, combos y sucursal viven en `js/data.js`, el carrito está en `localStorage` y el login y el pedido son simulados.

| ID | Pantalla | Acciones y datos que maneja |
| --- | --- | --- |
| P01 | Inicio (`index.html`) | Carrusel (contenido fijo), grilla de **combos**, grilla de **más pedidas**, "¿Cómo pedir?" (fijo). Botones "Pedir combo" y "Agregar". |
| P02 | Menú (`menu.html`) | Catálogo con filtro por categoría (clásica, premium, acompañamiento, bebida). Botón "Agregar". |
| P03 | Carrito (`carrito.html`) | Lista de ítems, cambiar cantidad, quitar, resumen y botón "Confirmar pedido". |
| P04 | Sucursales (`sucursales.html`) | Una sucursal: dirección, horario, mapa embebido, radio de despacho. Contenido informativo. |
| P05 | Contacto (`contacto.html`) | Formulario: nombre, correo, teléfono, motivo, mensaje. |
| P06 | Modal Iniciar sesión (todas las páginas) | Correo y contraseña. El enlace "Regístrate" no tiene destino (`href="#"`). |
| P07 | Modal "Pedido confirmado" (en P03) | Mensaje de éxito tras confirmar. |

Escritorio y móvil usan las mismas pantallas (Bootstrap responsivo). La diferencia es solo visual, así que **no genera servicios nuevos**.

## 1.2 Brechas detectadas y cómo se incorporan

El frontend actual no cubre varias funciones que exige el Caso 19. Las registramos como brechas y las resolvemos en la entrega final.

| ID | Brecha | Propuesta |
| --- | --- | --- |
| P08 | No existe registro de clientes (RF5). Faltan RUN, provincia, región, fecha de nacimiento y sexo. | Página "Crear cuenta" (`registro.html`) con todos los datos del caso. |
| P09 | No hay validación de correo (RF11). | Página "Confirmar correo" a la que llega el enlace del correo. Sirve también para definir la contraseña de cuentas creadas por el administrador. |
| P10 | El carrito no pide dirección de entrega ni permite pagar (RF2). | En P03 mostrar la dirección de entrega (precargada del perfil). Crear la pantalla de **pago y retorno** con las opciones del caso (Servipag o depósito bancario). |
| P11 | No hay historial de pedidos, estado, boleta ni anulación (RF3, RF8). | Pantalla "Mis pedidos". |
| P12 | No hay perfil del cliente. | Pantalla "Mi cuenta". |
| P13–P18 | No existe ninguna pantalla interna para el personal. | **Panel interno** (`panel.html`) con secciones por rol: P13 Productos (administrador, dueño), P14 Pedidos y ventas (cajero virtual, administrador), P15 Despacho (encargado de despachos), P16 Clientes (administrador), P17 Usuarios (administrador), P18 Reporte de ventas (dueño, administrador). |
| P03 / P04 | El frontend cobra despacho ($1.500) y da gratis desde $15.000. El caso dice que la entrega es **siempre gratuita**, solo dentro de 3 km. | Quitar el cobro y el umbral del carrito y del texto de ayuda. |

## 1.3 Requisitos y casos de uso (del Caso 19)

Mantenemos la numeración del caso para la trazabilidad.

| ID | Requisito del caso |
| --- | --- |
| RF1 | El cliente arma un pedido con los productos disponibles del menú. |
| RF2 | La orden se prepara una vez confirmado el pago. El pago se hace por una plataforma externa (Servipag o depósito bancario). |
| RF3 | Anulación de compra, indicando el motivo. |
| RF4 | Se realizan ventas solo a pedidos de clientes registrados. Las ventas web se asocian a una caja que pertenece a un cajero virtual. |
| RF5 | Registro de clientes con RUN, nombre completo, dirección, comuna, provincia, región, fecha de nacimiento, sexo, correo y teléfono. El cliente registrado puede comprar. |
| RF6 | El registro lo puede hacer el cliente en la web o el administrador en el restaurante. En ambos casos se valida el correo. |
| RF7 | Consultar y actualizar la disponibilidad de cada producto. |
| RF8 | Para cada venta se genera la boleta digital y se envía por correo al cliente. |
| RF9 | Reporte de ventas por período para el dueño. |
| RF10 | Mantenedores de productos, usuarios y clientes. |
| RF11 | Validar que el correo existe y está activo mediante una API de mensajería. |
| RF12 | Autenticación de usuarios y acceso según el perfil asignado por el administrador. |
| RF13 | El encargado de despacho obtiene e imprime las órdenes de despacho, que van a cocina en el orden en que llegan. |
| RF14 | *(Extra del frontend, no está en el caso)* Formulario de contacto de la página P05. |

| Caso de uso | Servicios que lo cubren |
| --- | --- |
| CU1 Autenticar usuarios | S01, S02 |
| CU2 Administrar usuarios | S30–S33 |
| CU3 Administrar clientes | S03–S05, S24–S29 |
| CU4 Administrar productos | S07–S11 |
| CU5 Genera pedido | S06, S12–S14, S20 |
| CU6 Realizar venta | Operación interna tras S21; consulta en S22 y S23 |
| CU7 Anular compra | S15, S17 |
| CU8 Reporte de ventas | S34 |
| CU9 Obtener orden de despacho | S18, S19 |

## 1.4 Actores y roles

| Actor | Tipo | Rol en el sistema (`rol`) |
| --- | --- | --- |
| Visitante | Sin sesión | — (anónimo) |
| Cliente | Usuario registrado | `cliente` |
| Administrador | Personal | `administrador` |
| Dueño | Personal | `dueno` |
| Cajero virtual | Personal | `cajero_virtual` |
| Encargado de despachos | Personal (el caso lo llama también "Encargado de Bodega" en CU9; los unificamos) | `encargado_despachos` |
| Plataforma de pago externa | Identidad externa | Notifica el resultado de un pago al backend |
| API de mensajería (correo) | Proveedor externo | Valida correos y envía correos |

## 1.5 Convenciones del catálogo de servicios

- Base de ruta: `/api/v1`. Las rutas `/admin/...` son de uso interno del personal.
- Autenticación: cabecera `Authorization: Bearer <token>`.
- Formato de error: `{"error": {"codigo": "...", "mensaje": "..."}}`, con mensajes claros para el usuario (RNF 13).
- Clasificación de datos: **Público**, **Restringido** (datos personales, historial de pedidos), **Credencial** (contraseñas, tokens), **Operativo** (stock, estados internos, ventas).
- Lo que el servidor siempre decide: precios, total, cobertura de despacho, estado del pedido, estado del pago, rol del usuario, número de boleta. El navegador no los envía como dato confiable.
- Despacho: siempre gratuito, solo dentro del radio de 3 km. Una dirección fuera de cobertura se rechaza al crear el pedido.
- Ciclo de vida del pedido: `pendiente_pago → pagado → en_preparacion → en_despacho → entregado`, y `anulado`.

## 1.6 Matriz de servicios

Acceso: **A** = anónimo. **Au** = autenticado, con los roles indicados.

| ID | Req. | Pantalla y acción | Propósito | Verbo y ruta | Entrada | Salida | Reglas y errores | Clasificación | Acceso |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S01 | RF12 | P06 · "Entrar" | Iniciar sesión | POST `/api/v1/auth/login` | Cuerpo: `correo` (email), `password` | 200 con `access_token`, `token_type`, `expires_in`, `rol`, `nombre` | 400 datos inválidos. 401 credenciales inválidas (mensaje genérico). 403 cuenta no activa (correo sin confirmar o dada de baja). 429 muchos intentos. | Credencial · Restringido | A |
| S02 | RF12 | Navbar · "Cerrar sesión" | Cerrar sesión e invalidar el token | POST `/api/v1/auth/logout` | Cabecera Bearer. Sin cuerpo. | 204 | 401 token inválido o vencido. | Credencial | Au (cualquier rol) |
| S03 | RF5, RF11 | P08 · "Crear cuenta" | Registrar un cliente desde la web | POST `/api/v1/auth/register` | Cuerpo: `run`, `nombreCompleto`, `correo`, `password` (mín. 8), `telefono`, `fechaNacimiento`, `sexo`, `direccion` con `calle`, `comuna`, `provincia`, `region` | 201 con `id`, `correo`, `estado: "pendiente_verificacion"` | 400 validación (RUN con dígito verificador inválido, fecha futura). 409 correo o RUN ya registrado. 422 la API de mensajería indica que el correo no existe. 429. 503 API de mensajería no disponible. El rol siempre es `cliente`. Se envía un correo de confirmación. | Restringido · Credencial | A |
| S04 | RF11, RF6 | P09 · abrir el enlace del correo | Confirmar el correo y, si corresponde, definir la contraseña | POST `/api/v1/auth/verify-email` | Cuerpo: `token`, `password` (obligatoria solo si la cuenta fue creada por el administrador) | 200 con `{estado: "activo"}` | 400 token inválido. 410 token vencido o ya usado. El token es de un solo uso y vence en 24 h. | Credencial | A |
| S05 | RF11 | P09 · "Reenviar correo" | Reenviar el correo de confirmación | POST `/api/v1/auth/resend-verification` | Cuerpo: `correo` | 202 siempre, exista o no la cuenta | 429. No revela si el correo está registrado. Cada reenvío invalida el token anterior. | Restringido | A |
| S06 | RF1, RF7 | P01 combos y destacados · P02 cargar y filtrar · P03 mostrar ítems | Consultar el catálogo | GET `/api/v1/products` | Consulta opcional: `categoria`, `disponible`, `destacado`, `ids` (lista), `limit` (1–100, def. 50), `offset` | 200 con lista de `{id, nombre, categoria, descripcion, precio, imagen, destacado, disponible}`; `[]` si no hay | 400 filtros inválidos. Solo campos públicos: **no** devuelve `stock`. Los combos son `categoria=combo`. | Público | A |
| S07 | RF7, RF10 | P13 · cargar lista | Listar productos con stock y retirados | GET `/api/v1/admin/products` | Consulta opcional: `categoria`, `incluirRetirados`, `limit`, `offset` | 200 con lista de `{id, nombre, categoria, precio, stock, disponible, retirado}` | 401. 403. 400 filtros inválidos. | Operativo | Au (administrador, dueno) |
| S08 | RF10 | P13 · "Nuevo producto" | Crear un producto | POST `/api/v1/products` | Cuerpo: `nombre`, `categoria`, `descripcion`, `precio` (entero CLP > 0), `imagen` (URL), `destacado`, `stock` (≥ 0) | 201 con el producto | 400 validación. 401. 403. 409 nombre duplicado. | Público (catálogo) · Operativo (`stock`) | Au (administrador, dueno) |
| S09 | RF10 | P13 · "Guardar cambios" | Reemplazar los datos de un producto | PUT `/api/v1/products/{id}` | Ruta: `id`. Cuerpo igual a S08 sin `stock`. | 200 con el producto | 400. 401. 403. 404. | Público (catálogo) | Au (administrador, dueno) |
| S10 | RF10 | P13 · "Retirar" | Retirar un producto (baja lógica, conserva el historial de pedidos) | DELETE `/api/v1/products/{id}` | Ruta: `id`. Sin cuerpo. | 204 | 401. 403. 404. Queda `retirado=true` y `disponible=false`. | Operativo | Au (administrador, dueno) |
| S11 | RF7 | P13 · "Disponibilidad y stock" | Actualizar stock y disponibilidad de un producto | PUT `/api/v1/products/{id}/stock` | Ruta: `id`. Cuerpo: `stock` (≥ 0), `disponible` (bool) | 200 con `{id, stock, disponible}` | 400. 401. 403. 404. Con `stock = 0` el producto queda no disponible aunque `disponible` sea verdadero. | Operativo | Au (administrador, dueno) |
| S12 | RF1 | P03 · "Confirmar pedido" | Crear un pedido | POST `/api/v1/orders` | Cabecera opcional `Idempotency-Key`. Cuerpo: `items[]` con `productoId` y `cantidad` (1–20); `direccionEntrega` opcional (`calle`, `comuna`, `referencia`). Si falta, se usa la del perfil. | 201 con `id`, `estado`, `items[]` con precio unitario, `total`, `direccionEntrega`, `creadoEn`, `expiraEn` | 400 validación. 401. 403 la cuenta no es de cliente activo. 404 producto inexistente. 409 producto no disponible o sin stock. 422 dirección fuera de la cobertura de 3 km. 503 inventario no responde. Se ignoran precios o totales enviados por el navegador. Si llega la misma `Idempotency-Key` del mismo cliente, devuelve el pedido ya creado en vez de crear otro. Estado inicial: `pendiente_pago`. Si no se paga antes de `expiraEn`, el pedido se anula y se devuelve el stock. | Restringido (dirección, pedido) | Au (cliente) |
| S13 | RF1 | P11 · cargar "Mis pedidos" | Listar los pedidos propios | GET `/api/v1/orders` | Consulta opcional: `estado`, `limit`, `offset` | 200 con lista de `{id, estado, total, creadoEn}`; `[]` si no hay | 401. 400 filtro inválido. Solo devuelve los del usuario. | Restringido | Au (cliente) |
| S14 | RF1, RF2 | P11 · "Ver detalle" · P10 retorno de pago | Consultar el detalle de un pedido | GET `/api/v1/orders/{id}` | Ruta: `id` | 200 con `id`, `estado`, `estadoPago`, `items[]`, `total`, `direccionEntrega`, `historialEstados[]`, `boletaDisponible`, `creadoEn` y `expiraEn` (este último solo mientras está en `pendiente_pago`). Si lo pide el personal, además `clienteNombre` | 401. 404 si no existe **o** no es del usuario (no se revela existencia). El personal autorizado puede consultar cualquier pedido. | Restringido | Au (cliente dueño; administrador, cajero_virtual, encargado_despachos) |
| S15 | RF3 | P11 · "Anular pedido" | Anular un pedido propio | POST `/api/v1/orders/{id}/cancel` | Ruta: `id`. Cuerpo: `motivo` (5–200) | 200 con `{id, estado: "anulado", motivo, reembolsoPendiente}` | 401. 404. 409 si el pedido ya está `en_preparacion` o más avanzado. Se devuelve el stock y el registro se conserva. Si ya estaba pagado, queda `reembolsoPendiente: true` (el reembolso es manual). | Restringido | Au (cliente dueño) |
| S16 | RF2, RF4 | P14 · cargar lista | Listar todos los pedidos para el personal | GET `/api/v1/admin/orders` | Consulta opcional: `estado`, `fecha`, `limit`, `offset` | 200 con lista de `{id, estado, total, creadoEn, clienteNombre, direccionEntrega}` | 401. 403. 400 filtro inválido. | Restringido | Au (administrador, cajero_virtual, encargado_despachos) |
| S17 | RF2, RF3 | P14 y P15 · "Avanzar estado" o "Anular" | Cambiar el estado de un pedido | PATCH `/api/v1/admin/orders/{id}/status` | Ruta: `id`. Cuerpo: `estado`, `motivo` (obligatorio si es `anulado`) | 200 con el pedido actualizado | 401. 403. 404. 409 transición inválida. 400 falta el motivo. Permitido: `pagado → en_preparacion → en_despacho → entregado` (encargado_despachos, administrador). `anulado` solo lo hace el administrador, desde `pendiente_pago`, `pagado` o `en_preparacion`. **Nunca** permite pasar a `pagado`: eso solo lo hace el pago confirmado (S21). | Operativo | Au (encargado_despachos, administrador) |
| S18 | RF13 | P15 · cargar cola | Consultar la cola de órdenes de despacho en orden de llegada | GET `/api/v1/admin/dispatch-orders` | Consulta opcional: `impresa` (def. `false`), `limit` | 200 con lista ordenada por `pagadoEn` ascendente de `{numeroOrden, pedidoId, pagadoEn, clienteNombre, telefono, direccionEntrega, items[], impresa}` | 401. 403. 400. Una orden aparece en la cola solo después de que el pago está confirmado. Una orden anulada deja de aparecer. | Restringido | Au (encargado_despachos, administrador) |
| S19 | RF13 | P15 · "Imprimir orden" | Obtener la orden de despacho lista para imprimir | GET `/api/v1/admin/dispatch-orders/{pedidoId}/print` | Ruta: `pedidoId` | 200 con documento HTML imprimible (`text/html`) | 401. 403. 404 la orden no existe en la cola de despacho. Marca la orden como `impresa`; repetir la llamada no cambia el resultado. | Restringido | Au (encargado_despachos, administrador) |
| S20 | RF2 | P10 · "Pagar" | Iniciar el pago de un pedido en la plataforma externa | POST `/api/v1/orders/{id}/payments` | Ruta: `id`. Cuerpo: `medio` (`servipag` o `deposito`). El monto **no** se envía: lo toma el servidor. | 201 con `pagoId`, `estado: "pendiente"`, `urlPago`, `expiraEn` | 401. 404. 409 si el pedido no está en `pendiente_pago`, está vencido o ya tiene un pago aprobado. 502/503 plataforma de pago no disponible. | Restringido · Operativo | Au (cliente dueño) |
| S21 | RF2, RF4, RF8 | Sin pantalla: lo invoca la plataforma de pago | Recibir el resultado del pago | POST `/api/v1/payments/webhook` | Cuerpo definido por la plataforma: `eventoId`, `pagoId`, `estado`, `monto`; cabecera de firma | 200 con `{recibido: true}` | 401 firma inválida. 400 cuerpo inválido. Si el `monto` no coincide con el pedido no se aprueba. Un `eventoId` repetido responde 200 sin procesar otra vez. Es la **única** vía para pasar un pedido a `pagado`. | Operativo | Identidad de la plataforma (firma) |
| S22 | RF4, RF8 | P14 · cargar "Ventas" | Consultar las ventas de la caja virtual | GET `/api/v1/admin/sales` | Consulta opcional: `desde`, `hasta`, `limit`, `offset` | 200 con lista de `{ventaId, pedidoId, numeroBoleta, total, fecha, correoEnviado}` | 401. 403. 400 rango inválido. | Operativo | Au (cajero_virtual, administrador) |
| S23 | RF8 | P11 · "Ver boleta" | Obtener la boleta digital de un pedido pagado | GET `/api/v1/orders/{id}/receipt` | Ruta: `id` | 200 con `numeroBoleta`, `fechaEmision`, `pedidoId`, `clienteNombre`, `items[]`, `total`, `ivaIncluido` | 401. 404 (no existe o no es del usuario). 409 el pedido aún no está pagado. | Restringido | Au (cliente dueño; cajero_virtual, administrador) |
| S24 | RF5 | P12 · cargar perfil · P03 precarga dirección | Consultar mi perfil | GET `/api/v1/clients/me` | Sin cuerpo | 200 con `id`, `run`, `nombreCompleto`, `correo`, `telefono`, `fechaNacimiento`, `sexo`, `direccion` | 401. 403 si no es cliente. | Restringido | Au (cliente) |
| S25 | RF5 | P12 · "Guardar" | Reemplazar mis datos de perfil | PUT `/api/v1/clients/me` | Cuerpo: `nombreCompleto`, `telefono`, `fechaNacimiento`, `sexo`, `direccion`. `run` y `correo` no se cambian aquí. | 200 con el perfil | 400. 401. 403. | Restringido | Au (cliente) |
| S26 | RF6, RF10, RF11 | P16 · "Registrar cliente" | Registrar un cliente presencialmente | POST `/api/v1/admin/clients` | Cuerpo igual a S03 sin `password` | 201 con `id`, `estado: "pendiente_verificacion"` | 400. 401. 403. 409. 422 correo inexistente. 503. El cliente recibe un correo para confirmar y definir su contraseña (S04). | Restringido | Au (administrador) |
| S27 | RF10 | P16 · cargar lista | Listar clientes | GET `/api/v1/admin/clients` | Consulta opcional: `q` (nombre o RUN), `limit`, `offset` | 200 con lista con los datos de perfil y `estado` | 401. 403. 400. | Restringido | Au (administrador) |
| S28 | RF10 | P16 · "Guardar cambios" | Reemplazar los datos de un cliente | PUT `/api/v1/admin/clients/{id}` | Ruta: `id`. Cuerpo: `nombreCompleto`, `telefono`, `fechaNacimiento`, `sexo`, `direccion` | 200 con el cliente | 400. 401. 403. 404. | Restringido | Au (administrador) |
| S29 | RF10 | P16 · "Dar de baja" | Dar de baja a un cliente (baja lógica) | DELETE `/api/v1/admin/clients/{id}` | Ruta: `id` | 204 | 401. 403. 404. Los pedidos y ventas se conservan. Los pedidos en curso continúan su flujo con los datos que ya guardan. | Restringido | Au (administrador) |
| S30 | RF10, RF12 | P17 · "Nuevo usuario" | Crear un usuario del personal | POST `/api/v1/admin/users` | Cuerpo: `nombreCompleto`, `correo`, `rol` (`administrador`, `dueno`, `cajero_virtual`, `encargado_despachos`) | 201 con `id`, `rol`, `estado: "pendiente_verificacion"` | 400. 401. 403. 409 correo duplicado. 422 correo inexistente. Recibe un correo para definir su contraseña (S04). | Restringido · Credencial | Au (administrador) |
| S31 | RF10 | P17 · cargar lista | Listar usuarios del personal | GET `/api/v1/admin/users` | Consulta opcional: `rol`, `estado`, `limit`, `offset` | 200 con lista de `{id, nombreCompleto, correo, rol, estado}` | 401. 403. 400. Nunca devuelve contraseñas ni hashes. | Restringido | Au (administrador) |
| S32 | RF10, RF12 | P17 · "Guardar" | Cambiar nombre, rol o estado de un usuario | PUT `/api/v1/admin/users/{id}` | Ruta: `id`. Cuerpo: `nombreCompleto`, `rol`, `activo` | 200 con el usuario | 400. 401. 403. 404. 409 si deja al sistema sin administrador activo. | Restringido | Au (administrador) |
| S33 | RF10 | P17 · "Dar de baja" | Dar de baja a un usuario (baja lógica) | DELETE `/api/v1/admin/users/{id}` | Ruta: `id` | 204 | 401. 403. 404. 409 si es el propio usuario o el último administrador. Sus sesiones se invalidan. | Restringido | Au (administrador) |
| S34 | RF9 | P18 · "Generar reporte" | Reporte de ventas por período | GET `/api/v1/admin/reports/sales` | Consulta: `desde`, `hasta` (rango máx. 92 días) | 200 con `totalVentas`, `cantidadVentas`, `porDia[]`, `topProductos[]` | 400 rango inválido. 401. 403. `totalVentas` es el monto recaudado en la caja virtual en el período. No descuenta reembolsos pendientes: la venta de un pedido anulado después de pagar sigue contando. | Operativo | Au (dueno, administrador) |
| S35 | RF14 | P05 · "Enviar mensaje" | Registrar un mensaje de contacto | POST `/api/v1/contact-messages` | Cuerpo: `nombre` (mín. 2), `correo`, `telefono` (8–15; dígitos, `+` y espacios), `motivo` (`consulta_pedido`, `reserva_evento`, `alianza_comercial` u `otro`), `mensaje` (10–1000) | 201 con `{id, recibido: true}` | 400 validación. 429 límite de solicitudes. | Restringido | A |

### Operaciones internas (sin ruta pública)

Las dispara el propio sistema, no un navegador. Se describen aquí porque el caso las exige.

| Operación | Disparador | Qué hace | Req. |
| --- | --- | --- | --- |
| Realizar venta | S21 con pago aprobado | Registra la venta en la caja del cajero virtual, solo si el cliente está registrado. Genera el número de boleta. | RF4 |
| Enviar boleta | Venta registrada | Pide a la API de mensajería enviar la boleta digital al correo del cliente. Si falla, se reintenta. | RF8 |
| Publicar orden de despacho | Pedido pasa a `pagado` | Publica la orden de despacho (tipo `nueva`) en la cola ActiveMQ `cola_pedidos`. El sistema de despacho la guarda y S18 la muestra en orden de llegada. Si el pedido se anula, publica una orden de tipo `anulada`. | RF13 |
| Expirar pedidos | Tarea periódica | Anula los pedidos `pendiente_pago` vencidos y devuelve el stock. | RF2 |
| Validar y enviar correos | S03, S05, S26, S30 | Llama a la API de mensajería para validar el correo y enviar el enlace de confirmación. | RF11 |

### Acciones sin servicio (con justificación)

| Pantalla y acción | Justificación |
| --- | --- |
| P01 carrusel y "¿Cómo pedir?" | Contenido fijo del sitio, sin datos del negocio. |
| P01 y P02 "Agregar" y "Pedir combo"; P03 cambiar cantidad y "Quitar" | El carrito vive en `localStorage` y guarda solo `id` y `cantidad`. El precio real se calcula al crear el pedido (S12). |
| P04 Sucursales | Hay una sola sucursal con datos informativos. La regla de cobertura de 3 km se aplica en S12. |
| P07 Modal "Pedido confirmado" | Se muestra con la respuesta de S12. |

### Servicios que no creamos a propósito

- No hay `DELETE` de pedidos, ventas ni boletas. Se anulan o se conservan para mantener el historial.
- No existe una operación para marcar un pedido como pagado desde un navegador. La mutation `confirmarPago` del repo actual se elimina.

## 1.7 Ejemplos de contratos (datos ficticios)

### S01 Iniciar sesión
```json
// POST /api/v1/auth/login
{ "correo": "camila@ejemplo.cl", "password": "ClaveFicticia123" }
// 200
{ "access_token": "tok_ficticio_abc123", "token_type": "bearer", "expires_in": 900, "rol": "cliente", "nombre": "Camila Rojas" }
// 403
{ "error": { "codigo": "CUENTA_NO_ACTIVA", "mensaje": "Confirma tu correo para activar la cuenta." } }
```

### S02 Cerrar sesión
```
POST /api/v1/auth/logout   (Authorization: Bearer tok_ficticio_abc123)
// 204 sin cuerpo
```

### S03 Registrar cliente (web)
```json
// POST /api/v1/auth/register
{ "run": "12.345.678-5", "nombreCompleto": "Camila Rojas Pérez", "correo": "camila@ejemplo.cl",
  "password": "ClaveFicticia123", "telefono": "+56911112222", "fechaNacimiento": "1995-04-20", "sexo": "F",
  "direccion": { "calle": "Av. Ejemplo 1234", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana" } }
// 201
{ "id": "cli_0001", "correo": "camila@ejemplo.cl", "estado": "pendiente_verificacion" }
// 422
{ "error": { "codigo": "CORREO_NO_VALIDO", "mensaje": "No pudimos comprobar que ese correo exista." } }
```

### S04 Confirmar correo
```json
// POST /api/v1/auth/verify-email
{ "token": "tok_verificacion_ficticio_xyz", "password": "ClaveFicticia123" }
// 200
{ "estado": "activo" }
// 410
{ "error": { "codigo": "TOKEN_VENCIDO", "mensaje": "El enlace venció o ya fue usado. Pide uno nuevo." } }
```

### S05 Reenviar confirmación
```json
// POST /api/v1/auth/resend-verification
{ "correo": "camila@ejemplo.cl" }
// 202 sin cuerpo (siempre, exista o no la cuenta)
```

### S06 Consultar catálogo
```json
// GET /api/v1/products?categoria=clasica&disponible=true
// 200
[ { "id": "prod_001", "nombre": "Napolitana", "categoria": "clasica",
    "descripcion": "Salsa de tomate, mozzarella, jamón, orégano fresco.",
    "precio": 8990, "imagen": "https://ejemplo.cl/napolitana.jpg", "destacado": true, "disponible": true } ]
// sin resultados -> []
```

### S07 Listar productos (administración)
```json
// GET /api/v1/admin/products?incluirRetirados=true
// 200
[ { "id": "prod_001", "nombre": "Napolitana", "categoria": "clasica", "precio": 8990,
    "stock": 40, "disponible": true, "retirado": false },
  { "id": "prod_009", "nombre": "Pizza Hawaiana", "categoria": "clasica", "precio": 9490,
    "stock": 0, "disponible": false, "retirado": true } ]
```

### S08 Crear producto
```json
// POST /api/v1/products
{ "nombre": "Pizza Hawaiana", "categoria": "clasica", "descripcion": "Jamón y piña.",
  "precio": 9290, "imagen": "https://ejemplo.cl/hawaiana.jpg", "destacado": false, "stock": 25 }
// 201
{ "id": "prod_009", "nombre": "Pizza Hawaiana", "categoria": "clasica", "descripcion": "Jamón y piña.",
  "precio": 9290, "imagen": "https://ejemplo.cl/hawaiana.jpg", "destacado": false, "disponible": true }
```

### S09 Modificar producto
```json
// PUT /api/v1/products/prod_009
{ "nombre": "Pizza Hawaiana", "categoria": "clasica", "descripcion": "Jamón, piña y mozzarella.",
  "precio": 9490, "imagen": "https://ejemplo.cl/hawaiana.jpg", "destacado": true }
// 200 -> el producto actualizado
```

### S10 Retirar producto
```
DELETE /api/v1/products/prod_009   // 204 sin cuerpo
```

### S11 Actualizar disponibilidad y stock
```json
// PUT /api/v1/products/prod_009/stock
{ "stock": 12, "disponible": true }
// 200
{ "id": "prod_009", "stock": 12, "disponible": true }
```

### S12 Crear pedido
```json
// POST /api/v1/orders   (Idempotency-Key: 7f3c-ficticia)
{ "items": [ { "productoId": "prod_001", "cantidad": 2 }, { "productoId": "prod_007", "cantidad": 1 } ],
  "direccionEntrega": { "calle": "Av. Ejemplo 1234", "comuna": "Maipú", "referencia": "Casa azul" } }
// 201
{ "id": "ped_0001", "estado": "pendiente_pago",
  "items": [ { "productoId": "prod_001", "nombre": "Napolitana", "cantidad": 2, "precioUnitario": 8990 },
             { "productoId": "prod_007", "nombre": "Bebida 500ml", "cantidad": 1, "precioUnitario": 1990 } ],
  "total": 19970,
  "direccionEntrega": { "calle": "Av. Ejemplo 1234", "comuna": "Maipú", "referencia": "Casa azul" },
  "creadoEn": "2026-11-07T18:30:00Z", "expiraEn": "2026-11-07T18:45:00Z" }
// 409
{ "error": { "codigo": "SIN_STOCK", "mensaje": "La Napolitana no tiene stock suficiente." } }
// 422
{ "error": { "codigo": "FUERA_DE_COBERTURA", "mensaje": "Solo despachamos dentro de 3 km del local." } }
```

### S13 Listar mis pedidos
```json
// GET /api/v1/orders?estado=pagado&limit=10
// 200
[ { "id": "ped_0001", "estado": "pagado", "total": 19970, "creadoEn": "2026-11-07T18:30:00Z" } ]
```

### S14 Detalle de pedido
```json
// GET /api/v1/orders/ped_0001
// 200
{ "id": "ped_0001", "estado": "pagado", "estadoPago": "aprobado",
  "items": [ { "productoId": "prod_001", "nombre": "Napolitana", "cantidad": 2, "precioUnitario": 8990 },
             { "productoId": "prod_007", "nombre": "Bebida 500ml", "cantidad": 1, "precioUnitario": 1990 } ],
  "total": 19970,
  "direccionEntrega": { "calle": "Av. Ejemplo 1234", "comuna": "Maipú", "referencia": "Casa azul" },
  "historialEstados": [ { "estado": "pendiente_pago", "fecha": "2026-11-07T18:30:00Z" },
                        { "estado": "pagado", "fecha": "2026-11-07T18:33:00Z" } ],
  "boletaDisponible": true }
// 404 (pedido ajeno o inexistente)
{ "error": { "codigo": "NO_ENCONTRADO", "mensaje": "Pedido no encontrado." } }
```

### S15 Anular pedido (cliente)
```json
// POST /api/v1/orders/ped_0002/cancel
{ "motivo": "Me equivoqué de dirección" }
// 200
{ "id": "ped_0002", "estado": "anulado", "motivo": "Me equivoqué de dirección", "reembolsoPendiente": false }
```

### S16 Listar pedidos (personal)
```json
// GET /api/v1/admin/orders?estado=pagado
// 200
[ { "id": "ped_0001", "estado": "pagado", "total": 19970, "creadoEn": "2026-11-07T18:30:00Z",
    "clienteNombre": "Camila Rojas Pérez", "direccionEntrega": { "calle": "Av. Ejemplo 1234", "comuna": "Maipú" } } ]
```

### S17 Cambiar estado de pedido
```json
// PATCH /api/v1/admin/orders/ped_0001/status
{ "estado": "en_preparacion" }
// 200 -> el pedido con estado "en_preparacion"
// 409
{ "error": { "codigo": "TRANSICION_INVALIDA", "mensaje": "No se puede pasar de pagado a entregado." } }
```

### S18 Cola de órdenes de despacho
```json
// GET /api/v1/admin/dispatch-orders
// 200 (más antigua primero)
[ { "numeroOrden": "OD-000045", "pedidoId": "ped_0001", "pagadoEn": "2026-11-07T18:33:00Z",
    "clienteNombre": "Camila Rojas Pérez", "telefono": "+56911112222",
    "direccionEntrega": { "calle": "Av. Ejemplo 1234", "comuna": "Maipú", "referencia": "Casa azul" },
    "items": [ { "nombre": "Napolitana", "cantidad": 2 }, { "nombre": "Bebida 500ml", "cantidad": 1 } ] } ]
```

### S19 Imprimir orden de despacho
```
GET /api/v1/admin/dispatch-orders/ped_0001/print
// 200 Content-Type: text/html (documento con número de orden, ítems y dirección)
```

### S20 Iniciar pago
```json
// POST /api/v1/orders/ped_0001/payments
{ "medio": "servipag" }
// 201
{ "pagoId": "pag_0001", "estado": "pendiente", "urlPago": "https://pagos-prueba.ejemplo.cl/pagar/ficticio123",
  "expiraEn": "2026-11-07T18:45:00Z" }
```

### S21 Notificación de la plataforma de pago
```json
// POST /api/v1/payments/webhook   (cabecera de firma de la plataforma)
{ "eventoId": "evt_ficticio_001", "pagoId": "pag_0001", "estado": "aprobado", "monto": 19970 }
// 200
{ "recibido": true }
```

### S22 Ventas de la caja virtual
```json
// GET /api/v1/admin/sales?desde=2026-11-07&hasta=2026-11-07
// 200
[ { "ventaId": "ven_0001", "pedidoId": "ped_0001", "numeroBoleta": "B-000123", "total": 19970,
    "fecha": "2026-11-07T18:33:10Z", "correoEnviado": true } ]
```

### S23 Obtener boleta
```json
// GET /api/v1/orders/ped_0001/receipt
// 200
{ "numeroBoleta": "B-000123", "fechaEmision": "2026-11-07T18:33:10Z", "pedidoId": "ped_0001",
  "clienteNombre": "Camila Rojas Pérez",
  "items": [ { "nombre": "Napolitana", "cantidad": 2, "precioUnitario": 8990 },
             { "nombre": "Bebida 500ml", "cantidad": 1, "precioUnitario": 1990 } ],
  "total": 19970, "ivaIncluido": 3188 }
```

### S24 Consultar mi perfil
```json
// GET /api/v1/clients/me
// 200
{ "id": "cli_0001", "run": "12.345.678-5", "nombreCompleto": "Camila Rojas Pérez", "correo": "camila@ejemplo.cl",
  "telefono": "+56911112222", "fechaNacimiento": "1995-04-20", "sexo": "F",
  "direccion": { "calle": "Av. Ejemplo 1234", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana" } }
```

### S25 Actualizar mi perfil
```json
// PUT /api/v1/clients/me
{ "nombreCompleto": "Camila Rojas Pérez", "telefono": "+56933334444", "fechaNacimiento": "1995-04-20", "sexo": "F",
  "direccion": { "calle": "Calle Falsa 456", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana" } }
// 200 -> el perfil actualizado
```

### S26 Registrar cliente (administrador)
```json
// POST /api/v1/admin/clients
{ "run": "11.111.111-1", "nombreCompleto": "Pedro Soto Díaz", "correo": "pedro@ejemplo.cl", "telefono": "+56955556666",
  "fechaNacimiento": "1988-09-02", "sexo": "M",
  "direccion": { "calle": "Pasaje Ficticio 78", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana" } }
// 201
{ "id": "cli_0002", "estado": "pendiente_verificacion" }
```

### S27 Listar clientes
```json
// GET /api/v1/admin/clients?q=soto
// 200
[ { "id": "cli_0002", "run": "11.111.111-1", "nombreCompleto": "Pedro Soto Díaz", "correo": "pedro@ejemplo.cl",
    "telefono": "+56955556666", "fechaNacimiento": "1988-09-02", "sexo": "M",
    "direccion": { "calle": "Pasaje Ficticio 78", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana" },
    "estado": "activo" } ]
```

### S28 Modificar cliente
```json
// PUT /api/v1/admin/clients/cli_0002
{ "nombreCompleto": "Pedro Soto Díaz", "telefono": "+56977778888", "fechaNacimiento": "1988-09-02", "sexo": "M",
  "direccion": { "calle": "Pasaje Ficticio 80", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana" } }
// 200 -> el cliente actualizado
```

### S29 Dar de baja cliente
```
DELETE /api/v1/admin/clients/cli_0002   // 204 sin cuerpo
```

### S30 Crear usuario del personal
```json
// POST /api/v1/admin/users
{ "nombreCompleto": "Luis Mena", "correo": "luis@ejemplo.cl", "rol": "cajero_virtual" }
// 201
{ "id": "usr_0003", "rol": "cajero_virtual", "estado": "pendiente_verificacion" }
```

### S31 Listar usuarios
```json
// GET /api/v1/admin/users?rol=cajero_virtual
// 200
[ { "id": "usr_0003", "nombreCompleto": "Luis Mena", "correo": "luis@ejemplo.cl", "rol": "cajero_virtual", "estado": "activo" } ]
```

### S32 Modificar usuario
```json
// PUT /api/v1/admin/users/usr_0003
{ "nombreCompleto": "Luis Mena", "rol": "encargado_despachos", "activo": true }
// 200 -> el usuario actualizado
// 409
{ "error": { "codigo": "ULTIMO_ADMINISTRADOR", "mensaje": "Debe quedar al menos un administrador activo." } }
```

### S33 Dar de baja usuario
```
DELETE /api/v1/admin/users/usr_0003   // 204 sin cuerpo
```

### S34 Reporte de ventas
```json
// GET /api/v1/admin/reports/sales?desde=2026-11-01&hasta=2026-11-07
// 200
{ "desde": "2026-11-01", "hasta": "2026-11-07", "totalVentas": 1250000, "cantidadVentas": 82,
  "porDia": [ { "fecha": "2026-11-07", "ventas": 14, "total": 210000 } ],
  "topProductos": [ { "productoId": "prod_001", "nombre": "Napolitana", "unidades": 40 } ] }
```

### S35 Mensaje de contacto
```json
// POST /api/v1/contact-messages
{ "nombre": "Pedro Soto", "correo": "pedro@ejemplo.cl", "telefono": "+56955556666",
  "motivo": "reserva_evento", "mensaje": "Quisiera cotizar 20 pizzas para un cumpleaños." }
// 201
{ "id": "msg_0001", "recibido": true }
```

> Los agregados GraphQL del Módulo 8 (por ejemplo `resumenPedido` para P11) usarán estos mismos servicios como base.

## 1.8 Trazabilidad de pantallas

Cada acción de cada pantalla, con el servicio que la atiende y el requisito del Caso 19.

| Pantalla | Acción | Servicio | Req. |
| --- | --- | --- | --- |
| P01 Inicio | Cargar combos | S06 (`categoria=combo`) | RF1, RF7 |
| P01 Inicio | Cargar "más pedidas" | S06 (`destacado=true`) | RF1, RF7 |
| P01 Inicio | "Pedir combo" y "Agregar"; carrusel; "¿Cómo pedir?" | Sin servicio (carrito local o contenido fijo) | — |
| P02 Menú | Cargar el catálogo y filtrar por categoría | S06 | RF1, RF7 |
| P02 Menú | "Agregar" | Sin servicio (carrito local) | — |
| P03 Carrito | Mostrar el detalle de los ítems | S06 (`ids`) | RF1 |
| P03 Carrito | Precargar la dirección de entrega | S24 | RF5 |
| P03 Carrito | "Confirmar pedido" | S12 | RF1 |
| P03 Carrito | Cambiar cantidad y "Quitar" | Sin servicio (carrito local) | — |
| P04 Sucursales | Ver ubicación, horario y mapa | Sin servicio (contenido informativo) | — |
| P05 Contacto | "Enviar mensaje" | S35 | RF14 |
| P06 Modal de sesión (y navbar) | "Entrar" | S01 | RF12 |
| P06 Modal de sesión (y navbar) | "Cerrar sesión" | S02 | RF12 |
| P07 Modal "Pedido confirmado" | Mostrar el resultado | Respuesta de S12 | RF1 |
| P08 Crear cuenta | "Crear cuenta" | S03 | RF5, RF11 |
| P09 Confirmar correo | Abrir el enlace y confirmar (o definir contraseña) | S04 | RF11, RF6 |
| P09 Confirmar correo | "Reenviar correo" | S05 | RF11 |
| P10 Pago y retorno | "Pagar" | S20 | RF2 |
| P10 Pago y retorno | Consultar el estado tras volver del proveedor | S14 | RF2 |
| P11 Mis pedidos | Cargar la lista | S13 | RF1 |
| P11 Mis pedidos | "Ver detalle" | S14 | RF1, RF2 |
| P11 Mis pedidos | "Anular pedido" | S15 | RF3 |
| P11 Mis pedidos | "Ver boleta" | S23 | RF8 |
| P12 Mi cuenta | Cargar y "Guardar" el perfil | S24, S25 | RF5 |
| P13 Panel · Productos | Listar con stock | S07 | RF7, RF10 |
| P13 Panel · Productos | "Nuevo producto", "Guardar cambios", "Retirar" | S08, S09, S10 | RF10 |
| P13 Panel · Productos | "Disponibilidad y stock" | S11 | RF7 |
| P14 Panel · Pedidos y ventas | Listar pedidos y ver detalle | S16, S14 | RF2, RF4 |
| P14 Panel · Pedidos y ventas | "Anular" (administrador) | S17 | RF3 |
| P14 Panel · Pedidos y ventas | Listar ventas de la caja virtual y ver boleta | S22, S23 | RF4, RF8 |
| P15 Panel · Despacho | Ver la cola de órdenes de despacho | S18 | RF13 |
| P15 Panel · Despacho | "Imprimir orden" | S19 | RF13 |
| P15 Panel · Despacho | "Avanzar estado" | S17 | RF2 |
| P16 Panel · Clientes | "Registrar cliente" | S26 | RF6, RF10, RF11 |
| P16 Panel · Clientes | Listar, "Guardar cambios" y "Dar de baja" | S27, S28, S29 | RF10 |
| P17 Panel · Usuarios | "Nuevo usuario", listar, "Guardar" y "Dar de baja" | S30, S31, S32, S33 | RF10, RF12 |
| P18 Panel · Reporte | "Generar reporte" | S34 | RF9 |
| Sin pantalla | La plataforma de pago avisa el resultado | S21 | RF2, RF4, RF8 |

Los 35 servicios aparecen en esta tabla. Los servicios sin pantalla propia (S21) y las operaciones internas (venta, boleta, orden de despacho, expiración y correos) están en 1.6.

## 1.9 Cumplimiento de los pasos a seguir de la guía

| Paso de la guía | Dónde está en este documento |
| --- | --- |
| 1. Recorrer cada pantalla y anotar acciones, formularios, listados y mensajes. Comparar escritorio y móvil. | 1.1 (pantallas P01–P07 y la nota de escritorio y móvil), 1.2 (brechas P08–P18) y 1.8 (trazabilidad por pantalla). |
| 2. Asignar un identificador a cada servicio y vincularlo con una pantalla y un requisito. Reutilizar servicios. | 1.6, columnas **ID**, **Req.** y **Pantalla y acción**. Reutilización: S06 lo usan P01, P02 y P03; S14 lo usan P10 y P11; S17 lo usan P14 y P15. |
| 3. Clasificar la operación (consultar, agregar, modificar, eliminar) y proponer el verbo. No inventar operaciones destructivas. | 1.10 (tipo de operación) y columna **Verbo y ruta** de 1.6. Los tres `DELETE` son bajas lógicas. |
| 4. Definir parámetros de ruta, consulta, cabeceras y cuerpo. Indicar campos, tipos, obligatoriedad, validación y clasificación de cada dato. | Columna **Entrada** de 1.6 y el diccionario de campos de 1.11. |
| 5. Definir respuesta, códigos de estado y errores. Diferenciar lo que envía el navegador de lo que valida el servidor. | Columnas **Salida** y **Reglas y errores** de 1.6, ejemplos de 1.7 y tabla de 1.12. |

## 1.10 Tipo de operación de cada servicio

| Tipo | Verbo | Servicios |
| --- | --- | --- |
| Consultar | GET | S06, S07, S13, S14, S16, S18, S19, S22, S23, S24, S27, S31, S34 |
| Agregar o ejecutar una operación justificada | POST | S01, S02, S03, S04, S05, S08, S12, S15, S20, S21, S26, S30, S35 |
| Modificar | PUT (reemplaza el recurso) o PATCH (solo el estado, S17) | S09, S11, S17, S25, S28, S32 |
| Eliminar | DELETE (baja lógica; conserva el historial) | S10, S29, S33 |

Los POST que no crean un recurso (S01, S02, S04, S05, S15, S20, S21) ejecutan una operación: iniciar o cerrar sesión, confirmar un correo, reenviar un correo, anular un pedido, iniciar un pago y recibir un aviso del proveedor.

## 1.11 Diccionario de campos

| Campo | Tipo | Obligatorio | Validación | Clasificación | Servicios |
| --- | --- | --- | --- | --- | --- |
| `correo` | Texto (email) | Sí | Formato válido, máx. 120. Debe existir según la API de mensajería. Único. | Restringido | S01, S03, S05, S26, S30, S35 |
| `password` | Texto | Sí en S01 y S03. En S04 solo si la cuenta no tiene contraseña. | Mín. 8, máx. 72. Nunca se devuelve. | Credencial | S01, S03, S04 |
| `token` (verificación) | Texto | Sí | De un solo uso. Vence en 24 h. | Credencial | S04 |
| `access_token` | Texto | Salida de S01. Va en la cabecera `Authorization`. | Vence a los 900 s. Se invalida en S02. | Credencial | S01, S02 y toda ruta autenticada |
| `run` | Texto (`12.345.678-5`) | Sí | Formato y dígito verificador. Único. No se puede modificar después. | Restringido | S03, S24, S26, S27 |
| `nombreCompleto` | Texto | Sí | 2–100 caracteres | Restringido | S03, S24–S28, S30–S32 |
| `telefono` | Texto | Sí (clientes) | 8–15; solo dígitos, `+` y espacios | Restringido | S03, S25, S26, S28, S35 |
| `fechaNacimiento` | Fecha ISO | Sí | No futura y posterior a 1900 | Restringido | S03, S25, S26, S28 |
| `sexo` | Enumerado | Sí | `F`, `M` u `O` | Restringido | S03, S25, S26, S28 |
| `direccion.calle` | Texto | Sí | 3–120 caracteres | Restringido | S03, S12, S25, S26, S28 |
| `direccion.comuna` | Texto | Sí | De una lista de comunas. Para entregar debe estar dentro de los 3 km. | Restringido | S03, S12, S25, S26, S28 |
| `direccion.provincia`, `direccion.region` | Texto | Sí en el registro | De una lista | Restringido | S03, S25, S26, S28 |
| `direccionEntrega.referencia` | Texto | No | Máx. 120 | Restringido | S12 |
| `rol` | Enumerado | Sí en S30 y S32 | `administrador`, `dueno`, `cajero_virtual` o `encargado_despachos`. El rol `cliente` solo se asigna al registrarse. | Operativo | S01 (salida), S30–S32 |
| `activo` | Booleano | Sí en S32 | — | Operativo | S32 |
| `categoria` | Enumerado | Sí al crear o editar | `clasica`, `premium`, `acompanamiento`, `bebida` o `combo` | Público | S06–S09 |
| `nombre` (producto) | Texto | Sí | 2–80 caracteres. Único. | Público | S08, S09 |
| `descripcion` | Texto | Sí | Máx. 300 | Público | S08, S09 |
| `precio` | Entero (CLP) | Sí | Mayor que 0 | Público | S08, S09 |
| `imagen` | URL | No | `https`, máx. 300 | Público | S08, S09 |
| `destacado` | Booleano | No (por defecto falso) | — | Público | S06, S08, S09 |
| `stock` | Entero | Sí en S08 y S11 | Mayor o igual que 0 | Operativo | S08, S11 |
| `disponible` | Booleano | Sí en S11 | — | Público (en el catálogo) | S06, S11 |
| `productoId` | Texto | Sí | Existe, no está retirado y está disponible | Público | S12 |
| `cantidad` | Entero | Sí | 1–20 por ítem | Operativo | S12 |
| `items` | Lista | Sí | 1–30 ítems | Operativo | S12 |
| `Idempotency-Key` (cabecera) | Texto | No | 8–64 caracteres | Operativo | S12 |
| `motivo` (anulación) | Texto | Sí en S15. En S17 solo si `estado` es `anulado`. | 5–200 caracteres | Restringido | S15, S17 |
| `estado` (pedido) | Enumerado | Sí en S17 | Solo transiciones permitidas | Operativo | S13, S14, S16, S17 |
| `impresa` | Booleano | No | Lo fija S19. Valor inicial `false`. | Operativo | S18, S19 |
| `medio` | Enumerado | Sí | `servipag` o `deposito` | Operativo | S20 |
| `eventoId`, `pagoId`, `monto` | Texto, texto, entero | Sí | Firma válida. `monto` igual al total del pedido. `eventoId` no repetido. | Operativo | S21 |
| `desde`, `hasta` | Fecha ISO | Sí en S34. Opcionales en S22. | `desde` menor o igual que `hasta`. Máx. 92 días. | Operativo | S22, S34 |
| `limit`, `offset` | Enteros | No | `limit` 1–100. `offset` mayor o igual que 0. | Público | Todas las listas |
| `q` (búsqueda) | Texto | No | Máx. 60 caracteres | Restringido | S27 |
| `motivo` (contacto) | Enumerado | Sí | `consulta_pedido`, `reserva_evento`, `alianza_comercial` u `otro` (el formulario muestra el texto y envía el valor) | Restringido | S35 |
| `mensaje` | Texto | Sí | 10–1000 caracteres | Restringido | S35 |

## 1.12 Qué envía el navegador y qué decide el servidor

| Dato | El navegador envía | El servidor decide |
| --- | --- | --- |
| Precios y total del pedido | Solo `productoId` y `cantidad` | Toma el precio vigente del catálogo y calcula el total. Ignora cualquier precio o total recibido. |
| Despacho | La dirección de entrega | Comprueba que esté dentro de los 3 km. La entrega es siempre gratuita. |
| Estado del pedido | La acción solicitada (anular, avanzar) | Valida la transición y quién la pide. |
| Estado del pago | Solo el `medio` de pago | Lo fija únicamente el aviso firmado del proveedor (S21), con el monto verificado. |
| Identidad y rol | El token en la cabecera | Verifica el token y obtiene usuario y rol. No acepta `clienteId` ni `rol` en el cuerpo. |
| Stock y disponibilidad | Nada (en el catálogo público) | El sistema de inventario descuenta, devuelve y calcula `disponible`. |
| Número de boleta, ids, fechas, vencimientos | Nada | Los genera el servidor. |
| Venta y caja virtual | Nada | Se registra automáticamente al aprobarse el pago. |

## 1.13 Hallazgos del código existente que afectan el diseño

Los encontramos al leer el repo. Se corrigen en la implementación final.

| Dónde | Hallazgo | Qué haremos |
| --- | --- | --- |
| `lab-api-gateway/auth_service` | Usuarios con contraseñas en texto plano (`"123"`, `"456"`, `"789"`) y secreto `PizzeriaSecret123` como valor por defecto en el código. Roles `cliente`, `cajero`, `admin`. | Contraseñas con hash adaptativo y sal. Secretos solo desde Vault o variables de entorno, sin valor por defecto. Roles del caso (5 roles). |
| `graphql-pizzeria/server.js` | Sin autenticación. `confirmarPago`, `delPedido`, `delCliente` y `delUsuario` están abiertas. `addPedido` no valida cantidades ni existencia del producto. El tipo `Usuario` expone `pass`. El modelo de cliente no tiene provincia, región, fecha de nacimiento ni sexo. | Se elimina `confirmarPago` y las mutations destructivas. El GraphQL queda privado, con identidad verificada. Se completa el modelo de cliente según RF5. |
| `apigateway/gateway.py` | Reenvía sin autenticación y con destinos fijos. | Se reemplaza por el gateway con autenticación y permisos del lab. |
| `frontend-la-fornace/js/data.js` y `carrito.html` | Precios y productos en el navegador. Cobro de despacho de $1.500 y umbral de $15.000. | El catálogo viene de S06. El despacho es gratis dentro de 3 km, como dice el caso. |
| `frontend-la-fornace/js/main.js` | Login y confirmación de pedido simulados, ids numéricos. | Se conectan a S01 y S12, con ids reales del backend. |
| `stomp/productor.py` | Ya publica pedidos en `/queue/cola_pedidos` con credenciales `demo/demo123` por defecto. | Se reutiliza la cola para las órdenes de despacho, con credenciales desde Vault. |

## 1.14 Control antes de avanzar

| Pregunta | Respuesta |
| --- | --- |
| ¿Cada acción tiene un servicio o una justificación? | Sí. Las acciones sin servicio están justificadas en 1.6. Las operaciones que exige el caso y no tienen pantalla están en "Operaciones internas". |
| ¿La matriz distingue campos públicos de datos restringidos? | Sí. Columna "Clasificación". El catálogo público no incluye `stock`. RUN, fecha de nacimiento, sexo, dirección, teléfono y correo son restringidos. |
| ¿Los contratos explican qué se transporta sin copiar el modelo de base de datos? | Sí. Solo viajan los campos que usa cada pantalla. |
| ¿Cada RF y CU del caso tiene servicios? | Sí. Ver 1.3. |
