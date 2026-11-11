# Evaluación Unidad 2 — Backend seguro completo
## Pizzería La Fornace (derivado del Caso 19)

---

# Módulo 4 — Stakeholders y permisos HTTP

Este módulo define quién necesita cada servicio, para qué lo usa y sobre qué recursos puede actuar. Usa los IDs S01 a S35 del Módulo 1 y los sistemas del Módulo 3. El detalle de cómo el gateway aplica estas reglas se diseña en el Módulo 5.

## 4.1 Cumplimiento de los pasos a seguir de la guía

| Paso de la guía | Dónde está |
| --- | --- |
| 1. Identificar stakeholders y su interés; separar partes interesadas, roles de usuario e identidades técnicas. | Registro 4.2 (columna "Clasificación"). |
| 2. Relacionar cada rol operativo con servicios concretos del Módulo 1. | Tabla 4.4 y matriz resumen 4.7. |
| 3. Indicar GET, POST, PUT y DELETE como permitido, denegado o no aplicable. Un verbo permitido no autoriza todas las rutas. | Tabla 4.9 (por recurso y verbo) y matriz detallada 4.8. |
| 4. Agregar condiciones (propiedad, ámbito, estado) y definir autenticación y responsable de verificar la autorización. | Condiciones 4.6, responsables 4.5 y columna "Se verifica en" de 4.8. |
| 5. Registrar los stakeholders sin acceso directo como "sin permisos operativos" y explicar cómo reciben su información. | Tabla 4.3. |
| Fundamentar los permisos de administración y las identidades de proveedores o sistemas. | Tablas 4.4 y 4.10. |
| Conservar el historial en las anulaciones. | 4.11. |

## 4.2 Registro de stakeholders

Se separan tres clases: **partes interesadas** (personas o grupos con interés en el sistema, tengan o no acceso), **roles de usuario** (los que tienen cuenta e invocan servicios) e **identidades técnicas** (sistemas que invocan servicios por sí mismos).

| Nombre o categoría | Clasificación | Interés | Rol asociado | Uso de información |
| --- | --- | --- | --- | --- |
| Visitante | Parte interesada sin sesión | Conocer la carta, contactar al local y registrarse. | Ninguno (anónimo) | Solo datos públicos del catálogo (S06). Entrega su nombre, correo, teléfono y mensaje al contactar (S35) y sus datos al registrarse (S03). |
| Cliente | Rol de usuario | Pedir, pagar, anular y recibir su boleta. | `cliente` | Lee y cambia solo sus datos y pedidos. Su RUN, dirección, correo e historial son restringidos. |
| Dueño del restaurante | Rol de usuario | Saber cuánto se vende y mantener la carta. | `dueno` | Cifras agregadas de ventas (S34) y administración del catálogo. No ve datos de clientes individuales ni pedidos. |
| Administrador | Rol de usuario | Administrar usuarios, clientes y productos, y atender pedidos. | `administrador` | Datos restringidos de clientes y pedidos para operar. No ve contraseñas ni hashes. |
| Cajero virtual | Rol de usuario | Controlar las ventas de la caja web y sus boletas. | `cajero_virtual` | Ventas, boletas y pedidos (lectura). |
| Encargado de despachos | Rol de usuario | Pasar las órdenes a cocina en orden de llegada y registrar el avance. | `encargado_despachos` | Cola de órdenes de despacho (sin precios) y estado del pedido. |
| Cocina | Parte interesada sin acceso | Preparar los pedidos en el orden en que llegan (RF13). | Sin rol. **Sin permisos operativos** | Recibe la orden impresa. |
| Repartidor | Parte interesada sin acceso (derivada del despacho a domicilio, RF1) | Saber qué entregar y a qué dirección. | Sin rol. **Sin permisos operativos** | Recibe la orden impresa con nombre, teléfono y dirección. |
| Contabilidad del local | Parte interesada sin acceso (derivada del reporte, RF9) | Revisar lo vendido en un período. | Sin rol. **Sin permisos operativos** | Recibe el reporte que el dueño o el administrador generan e imprimen. |
| Responsable de la infraestructura (el equipo) | Parte interesada sin acceso a la API | Arrancar los sistemas y custodiar los secretos. | Sin rol en la API. **Sin permisos operativos** | Administra Vault y los contenedores fuera de la API. No lee datos de negocio por la API. |
| Plataforma de pago | Identidad técnica externa | Informar el resultado de un cobro. | `plataforma-de-pago` (firma HMAC) | Recibe `pagoId` y monto al crear el cobro. Envía `eventoId`, `pagoId`, `estado` y `monto`. |
| Proveedor de correo | Identidad técnica externa | Validar correos y enviarlos. | Clave de API | Recibe correo de destino y el contenido del mensaje. |
| `api-gateway`, `graphql-gateway` y los siete sistemas de negocio | Identidades técnicas internas | Cumplir las integraciones del Módulo 3. | Par `X-Service-Id` y `X-Service-Secret` por cada camino | Reciben solo los datos mínimos de cada integración (3.7). |

## 4.3 Stakeholders sin permisos operativos

| Stakeholder | Cómo recibe la información que necesita | Por qué no tiene acceso directo |
| --- | --- | --- |
| Cocina | La orden impresa que entrega el encargado de despachos (S19). Trae número de orden, productos, cantidades, nombre, teléfono y dirección. No lleva precios, RUN ni correo. | Solo cumple el pedido. Cada acceso extra sería un dato restringido más expuesto. |
| Repartidor | La misma orden impresa. | Necesita la dirección del momento y no un acceso al sistema. |
| Contabilidad del local | El reporte de ventas del período (S34) que genera el dueño o el administrador. | Necesita cifras, no datos de clientes. Las boletas individuales llegan por correo al cliente. |
| Responsable de la infraestructura | Registros de los contenedores y estado de salud de cada sistema. Los secretos los gestiona en Vault. | Las operaciones de administración de la plataforma se hacen sobre la infraestructura y no con una cuenta de negocio. |

## 4.4 Roles operativos y servicios del Módulo 1

| Rol | Servicios | Detalle de los servicios | Fundamento de sus permisos |
| --- | --- | --- | --- |
| Visitante (sin rol) | 6 | S01, S03, S04, S05, S06, S35 | Solo necesita ver la carta, contactar y registrarse. No toca datos restringidos. |
| `cliente` | 15 | S01, S02, S03, S04, S05, S06, S12, S13, S14, S15, S20, S23, S24, S25, S35 | Opera únicamente sobre lo suyo: crea y paga sus pedidos, los anula mientras no estén en preparación, ve su boleta y mantiene su perfil. |
| `administrador` | 28 | S01, S02, S03, S04, S05, S06, S07, S08, S09, S10, S11, S14, S16, S17, S18, S19, S22, S23, S26, S27, S28, S29, S30, S31, S32, S33, S34, S35 | Es quien asigna perfiles (RF12) y administra usuarios, clientes y productos (RF10, RF7). Atiende pedidos y puede anular (RF3). No confirma pagos, no ve contraseñas y no puede dejar al sistema sin administrador. |
| `dueno` | 13 | S01, S02, S03, S04, S05, S06, S07, S08, S09, S10, S11, S34, S35 | Administra la carta (RF7, CU4) y consulta el reporte de ventas (RF9, CU8). No opera pedidos ni ve datos de clientes individuales, porque supervisa con cifras agregadas. |
| `cajero_virtual` | 11 | S01, S02, S03, S04, S05, S06, S14, S16, S22, S23, S35 | Controla las ventas de la caja web (RF4, CU6) y las boletas (RF8). Consulta pedidos para cotejar, pero no cambia su estado ni administra catálogo o usuarios. |
| `encargado_despachos` | 12 | S01, S02, S03, S04, S05, S06, S14, S16, S17, S18, S19, S35 | Prepara y despacha (RF13, CU9): ve la cola de órdenes, la imprime y avanza el estado un paso a la vez. No anula, no ve ventas y no ve precios en la orden. |

Los permisos de administración se justifican por el requisito que los origina: RF10 y RF12 (usuarios y perfiles), RF7 (catálogo), RF3 (anulación), RF4 y RF8 (ventas y boletas), RF9 (reporte) y RF13 (despacho). Ningún rol tiene más servicios de los que su función exige, y ninguno puede pasar un pedido a `pagado`.

## 4.5 Autenticación y responsable de verificar la autorización

La **identidad** responde quién es quien llama. La **autorización** responde qué puede hacer sobre ese recurso. Son dos comprobaciones distintas y las hace quien tiene el dato para decidirla.

| Pregunta | Quién la responde | Cómo |
| --- | --- | --- |
| ¿Quién es el usuario? (autenticación) | `auth-service`, consultado por `api-gateway` | Token Bearer (S01). El gateway lo valida en cada solicitud con I01. Si no está activo o venció, 401. |
| ¿Quién es el sistema que llama? | El sistema llamado | `X-Gateway-Secret` para el gateway y `X-Service-Id` con `X-Service-Secret` para los sistemas (3.8). |
| ¿Quién es la plataforma de pago? | `payments-service` | Firma HMAC y marca de tiempo (C8). |
| ¿El rol puede usar esta ruta y este verbo? (autorización gruesa) | `api-gateway` y luego el sistema destino | Primera barrera en el gateway, que corta antes de molestar a un sistema. Segunda barrera en el sistema, con `X-Authenticated-Roles`, por si se llama sin pasar por el gateway. |
| ¿El recurso es de esa persona o está en un estado que lo permite? (autorización fina) | Solo el sistema dueño del dato | Propiedad (C1), estado (C2) y ámbito (C3) las comprueba orders, payments o clients. El gateway no tiene esos datos y no puede decidirlas. |

Reglas comunes:
- El navegador no manda `cuentaId`, `rol` ni `estado` en el cuerpo. El gateway los toma del token y los entrega por cabeceras que él mismo escribe.
- Un 404 en lugar de 403 cuando el recurso es de otro cliente evita revelar que existe.
- Ocultar un botón en el frontend no sustituye ninguna de estas comprobaciones. Cada servicio se verifica en el backend aunque la pantalla no muestre la acción.

## 4.6 Condiciones de acceso

| ID | Condición | Regla | Quién la verifica |
| --- | --- | --- | --- |
| C1 | Propiedad del recurso | El pedido, la boleta o el perfil pertenece a la cuenta autenticada: `cuentaId` del recurso igual a `X-Authenticated-User`. La consulta siempre filtra por ese valor. Si no coincide, 404 sin revelar si el recurso existe. | orders, payments y clients |
| C2 | Estado del pedido | S15 solo desde `pendiente_pago` o `pagado` (409 desde `en_preparacion`). S20 solo si el pedido está `pendiente_pago`, no venció y no tiene pago aprobado. S23 solo desde `pagado`. | orders y payments |
| C3 | Ámbito de los datos | El personal recibe el DTO operativo (sin RUN, correo ni fecha de nacimiento). El cliente recibe solo su propio DTO. El dueño nunca recibe datos de pedidos ni de clientes individuales. | orders, payments y clients |
| C4 | Cuenta activa | La cuenta debe estar `activo`. Una cuenta `pendiente_verificacion` o `inactivo` no opera (403 `CUENTA_NO_ACTIVA`). | auth y orders |
| C5 | Integridad de la administración | No se puede dejar al sistema sin un administrador activo ni darse de baja a uno mismo (409). | auth |
| C6 | Período de consulta | Rango máximo de 92 días y `desde` menor o igual que `hasta` (400). | payments |
| C7 | Transición permitida según el rol | `encargado_despachos`: `pagado` → `en_preparacion` → `en_despacho` → `entregado`, de a un paso. `administrador`: las mismas más `anulado` desde `pendiente_pago`, `pagado` o `en_preparacion`, con motivo. Nadie pasa un pedido a `pagado` por esta ruta: solo lo hace el pago confirmado (409). | orders |
| C8 | Firma del proveedor | Firma HMAC-SHA256 y marca de tiempo de máximo 5 minutos. No se acepta token de usuario en esta ruta. | payments |
| C9 | Límite de solicitudes | Las rutas públicas con escritura tienen límite por origen (429). | api-gateway |
| C10 | Token de un solo uso | El token de verificación vence, solo se usa una vez y el reenvío invalida el anterior. | auth |
| C11 | Identidad del sistema llamador | `X-Service-Id` y `X-Service-Secret` del par llamador–llamado, y que esa ruta esté permitida para ese llamador. | sistema llamado |
| C12 | Solo campos públicos | El catálogo público devuelve únicamente nombre, categoría, descripción, precio, imagen, destacado y disponibilidad. Nunca `stock` ni productos retirados. | inventory |
| C13 | Baja lógica | DELETE no borra el registro: lo marca como retirado o inactivo y conserva el historial. | inventory, clients y auth |

## 4.7 Matriz resumen: rol por servicio

"Sí" significa permitido y "No" denegado. Entre paréntesis va la condición que además se debe cumplir. S21 no la usa ningún rol: solo la plataforma de pago con firma.

| ID | Servicio | Visitante | `cliente` | `administrador` | `dueno` | `cajero_virtual` | `encargado_despachos` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S01 | Iniciar sesión | Sí | Sí | Sí | Sí | Sí | Sí |
| S02 | Cerrar sesión e invalidar el token | No | Sí | Sí | Sí | Sí | Sí |
| S03 | Registrar un cliente desde la web | Sí | Sí | Sí | Sí | Sí | Sí |
| S04 | Confirmar el correo y, si corresponde, definir la contraseña | Sí | Sí | Sí | Sí | Sí | Sí |
| S05 | Reenviar el correo de confirmación | Sí | Sí | Sí | Sí | Sí | Sí |
| S06 | Consultar el catálogo | Sí | Sí | Sí | Sí | Sí | Sí |
| S07 | Listar productos con stock y retirados | No | No | Sí | Sí | No | No |
| S08 | Crear un producto | No | No | Sí | Sí | No | No |
| S09 | Reemplazar los datos de un producto | No | No | Sí | Sí | No | No |
| S10 | Retirar un producto (baja lógica, conserva el historial de pedidos) | No | No | Sí | Sí | No | No |
| S11 | Actualizar stock y disponibilidad de un producto | No | No | Sí | Sí | No | No |
| S12 | Crear un pedido | No | Sí | No | No | No | No |
| S13 | Listar los pedidos propios | No | Sí (C1) | No | No | No | No |
| S14 | Consultar el detalle de un pedido | No | Sí (C1) | Sí | No | Sí | Sí |
| S15 | Anular un pedido propio | No | Sí (C1, C2) | No | No | No | No |
| S16 | Listar todos los pedidos para el personal | No | No | Sí | No | Sí | Sí |
| S17 | Cambiar el estado de un pedido | No | No | Sí (C7) | No | No | Sí (C7) |
| S18 | Consultar la cola de órdenes de despacho en orden de llegada | No | No | Sí | No | No | Sí |
| S19 | Obtener la orden de despacho lista para imprimir | No | No | Sí | No | No | Sí |
| S20 | Iniciar el pago de un pedido en la plataforma externa | No | Sí (C1, C2) | No | No | No | No |
| S21 | Recibir el resultado del pago | No | No | No | No | No | No |
| S22 | Consultar las ventas de la caja virtual | No | No | Sí | No | Sí | No |
| S23 | Obtener la boleta digital de un pedido pagado | No | Sí (C1, C2) | Sí | No | Sí | No |
| S24 | Consultar mi perfil | No | Sí (C1) | No | No | No | No |
| S25 | Reemplazar mis datos de perfil | No | Sí (C1) | No | No | No | No |
| S26 | Registrar un cliente presencialmente | No | No | Sí | No | No | No |
| S27 | Listar clientes | No | No | Sí | No | No | No |
| S28 | Reemplazar los datos de un cliente | No | No | Sí | No | No | No |
| S29 | Dar de baja a un cliente (baja lógica) | No | No | Sí | No | No | No |
| S30 | Crear un usuario del personal | No | No | Sí | No | No | No |
| S31 | Listar usuarios del personal | No | No | Sí | No | No | No |
| S32 | Cambiar nombre, rol o estado de un usuario | No | No | Sí | No | No | No |
| S33 | Dar de baja a un usuario (baja lógica) | No | No | Sí | No | No | No |
| S34 | Reporte de ventas por período | No | No | Sí | Sí | No | No |
| S35 | Registrar un mensaje de contacto | Sí | Sí | Sí | Sí | Sí | Sí |

## 4.8 Matriz de permisos detallada

Cada servicio tiene una fila por regla de decisión. Las filas "Denegado" agrupan a los demás roles y al visitante. Hay 72 filas.

| Rol o identidad | ID | Ruta | Verbo | Decisión | Alcance y condición | Se verifica en |
| --- | --- | --- | --- | --- | --- | --- |
| visitante, cualquier rol | S01 | `/api/v1/auth/login` | POST | Permitido | Con correo y contraseña válidos y cuenta `activo` (C4). Límite de intentos y de tasa (C9). | `api-gateway`: ruta pública y límite de tasa. `auth-service`: credenciales y estado de la cuenta |
| `cliente`, `administrador`, `dueno`, `cajero_virtual`, `encargado_despachos` | S02 | `/api/v1/auth/logout` | POST | Permitido | Cierra solo la sesión del token enviado. No recibe `id` de otra sesión. | `api-gateway`: token (I01) y rol por ruta. `auth-service`: rol y sesión del token |
| Visitante (sin token) | S02 | `/api/v1/auth/logout` | POST | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `auth-service` (segunda barrera) |
| visitante, cualquier rol | S03 | `/api/v1/auth/register` | POST | Permitido | El `rol` es siempre `cliente` y el `estado` `pendiente_verificacion`; el cuerpo no puede traerlos. Límite de tasa (C9). | `api-gateway`: ruta pública y límite de tasa. `clients-service` y `auth-service`: validación y rol fijo |
| visitante, cualquier rol | S04 | `/api/v1/auth/verify-email` | POST | Permitido | Token de un solo uso y vigente (C10). | `api-gateway`: ruta pública. `auth-service`: token |
| visitante, cualquier rol | S05 | `/api/v1/auth/resend-verification` | POST | Permitido | Límite de tasa (C9). Cada reenvío invalida el token anterior (C10). | `api-gateway`: ruta pública y límite de tasa. `auth-service`: token |
| visitante, cualquier rol | S06 | `/api/v1/products` | GET | Permitido | Solo campos públicos (C12). | `api-gateway`: ruta pública. `inventory-service`: DTO público |
| `administrador`, `dueno` | S07 | `/api/v1/admin/products` | GET | Permitido | Ve `stock` y productos retirados. | `api-gateway`: token (I01) y rol por ruta. `inventory-service`: rol y ruta administrativa |
| Visitante (sin token), `cliente`, `cajero_virtual`, `encargado_despachos` | S07 | `/api/v1/admin/products` | GET | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `inventory-service` (segunda barrera) |
| `administrador`, `dueno` | S08 | `/api/v1/products` | POST | Permitido | Precio mayor que 0. `stock` inicial solo lo fija este rol. | `api-gateway`: token (I01) y rol por ruta. `inventory-service`: rol y validación |
| Visitante (sin token), `cliente`, `cajero_virtual`, `encargado_despachos` | S08 | `/api/v1/products` | POST | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `inventory-service` (segunda barrera) |
| `administrador`, `dueno` | S09 | `/api/v1/products/{id}` | PUT | Permitido | Reemplaza los datos del catálogo. No cambia `stock` (se hace con S11). | `api-gateway`: token (I01) y rol por ruta. `inventory-service`: rol y validación |
| Visitante (sin token), `cliente`, `cajero_virtual`, `encargado_despachos` | S09 | `/api/v1/products/{id}` | PUT | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `inventory-service` (segunda barrera) |
| `administrador`, `dueno` | S10 | `/api/v1/products/{id}` | DELETE | Permitido | Baja lógica (C13): el producto retirado sigue en los pedidos antiguos. | `api-gateway`: token (I01) y rol por ruta. `inventory-service`: rol y baja lógica |
| Visitante (sin token), `cliente`, `cajero_virtual`, `encargado_despachos` | S10 | `/api/v1/products/{id}` | DELETE | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `inventory-service` (segunda barrera) |
| `administrador`, `dueno` | S11 | `/api/v1/products/{id}/stock` | PUT | Permitido | Cambia `stock` y `disponible`. Queda un movimiento `ajuste`. | `api-gateway`: token (I01) y rol por ruta. `inventory-service`: rol y validación |
| Visitante (sin token), `cliente`, `cajero_virtual`, `encargado_despachos` | S11 | `/api/v1/products/{id}/stock` | PUT | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `inventory-service` (segunda barrera) |
| `cliente` | S12 | `/api/v1/orders` | POST | Permitido | Cuenta activa con perfil (C4). El `cuentaId` sale del token, nunca del cuerpo. Precios y total los calcula el servidor. | `api-gateway`: token (I01) y rol por ruta. `orders-service`: rol y cuenta activa (C4); `cuentaId` tomado de `X-Authenticated-User` |
| Visitante (sin token), `administrador`, `dueno`, `cajero_virtual`, `encargado_despachos` | S12 | `/api/v1/orders` | POST | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `orders-service` (segunda barrera) |
| `cliente` | S13 | `/api/v1/orders` | GET | Permitido | Solo los pedidos de su cuenta (C1). La consulta se filtra por el token y no acepta el id de otro cliente. | `api-gateway`: token (I01) y rol por ruta. `orders-service`: rol y filtro por `cuentaId` (C1) |
| Visitante (sin token), `administrador`, `dueno`, `cajero_virtual`, `encargado_despachos` | S13 | `/api/v1/orders` | GET | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `orders-service` (segunda barrera) |
| `cliente` | S14 | `/api/v1/orders/{id}` | GET | Permitido | Solo si el pedido es suyo (C1). | `api-gateway`: token (I01) y rol por ruta. `orders-service`: rol y propiedad (C1) |
| `administrador`, `cajero_virtual`, `encargado_despachos` | S14 | `/api/v1/orders/{id}` | GET | Permitido | Cualquier pedido, con el DTO operativo (C3). | `api-gateway`: token (I01) y rol por ruta. `orders-service`: rol y ámbito (C3) |
| cliente (de otra cuenta) | S14 | `/api/v1/orders/{id}` | GET | Denegado | 404, sin datos y sin revelar si el pedido existe. | `orders-service`: propiedad (C1) |
| Visitante (sin token), `dueno` | S14 | `/api/v1/orders/{id}` | GET | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `orders-service` (segunda barrera) |
| `cliente` | S15 | `/api/v1/orders/{id}/cancel` | POST | Permitido | Solo su pedido (C1) y solo desde `pendiente_pago` o `pagado` (C2). Motivo de 5 a 200 caracteres. Anular no borra el registro. | `api-gateway`: token (I01) y rol por ruta. `orders-service`: rol y propiedad (C1) y estado (C2) |
| cliente (de otra cuenta) | S15 | `/api/v1/orders/{id}/cancel` | POST | Denegado | 404, sin datos y sin revelar si el pedido existe. | `orders-service`: propiedad (C1) |
| Visitante (sin token), `administrador`, `dueno`, `cajero_virtual`, `encargado_despachos` | S15 | `/api/v1/orders/{id}/cancel` | POST | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `orders-service` (segunda barrera) |
| `administrador`, `cajero_virtual`, `encargado_despachos` | S16 | `/api/v1/admin/orders` | GET | Permitido | Todos los pedidos, con el DTO operativo (C3). | `api-gateway`: token (I01) y rol por ruta. `orders-service`: rol y ámbito (C3) |
| Visitante (sin token), `cliente`, `dueno` | S16 | `/api/v1/admin/orders` | GET | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `orders-service` (segunda barrera) |
| `encargado_despachos` | S17 | `/api/v1/admin/orders/{id}/status` | PATCH | Permitido | Solo avanzar un paso (C7). No puede anular. | `api-gateway`: token (I01) y rol por ruta. `orders-service`: rol y transición según rol (C7) |
| `administrador` | S17 | `/api/v1/admin/orders/{id}/status` | PATCH | Permitido | Avanzar y anular con motivo (C7). | `api-gateway`: token (I01) y rol por ruta. `orders-service`: rol y transición según rol (C7) |
| encargado_despachos (anular), cualquier rol (pasar a `pagado`) | S17 | `/api/v1/admin/orders/{id}/status` | PATCH | Denegado | Pasar a `pagado` por esta ruta: 409. Solo lo hace el pago confirmado. `encargado_despachos` que intenta `anulado`: 403. | `orders-service`: transición (C7) |
| Visitante (sin token), `cliente`, `dueno`, `cajero_virtual` | S17 | `/api/v1/admin/orders/{id}/status` | PATCH | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `orders-service` (segunda barrera) |
| `encargado_despachos`, `administrador` | S18 | `/api/v1/admin/dispatch-orders` | GET | Permitido | Cola en orden de llegada, sin precios, RUN ni correo. | `api-gateway`: token (I01) y rol por ruta. `dispatch-service`: rol y ruta administrativa |
| Visitante (sin token), `cliente`, `dueno`, `cajero_virtual` | S18 | `/api/v1/admin/dispatch-orders` | GET | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `dispatch-service` (segunda barrera) |
| `encargado_despachos`, `administrador` | S19 | `/api/v1/admin/dispatch-orders/{pedidoId}/print` | GET | Permitido | Marca la orden como impresa. Repetir no cambia el resultado. | `api-gateway`: token (I01) y rol por ruta. `dispatch-service`: rol y ruta administrativa |
| Visitante (sin token), `cliente`, `dueno`, `cajero_virtual` | S19 | `/api/v1/admin/dispatch-orders/{pedidoId}/print` | GET | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `dispatch-service` (segunda barrera) |
| `cliente` | S20 | `/api/v1/orders/{id}/payments` | POST | Permitido | Solo su pedido (C1), en `pendiente_pago` y no vencido (C2). El monto lo toma el servidor del pedido. | `api-gateway`: token (I01) y rol por ruta. `orders-service`: rol y propiedad y estado (C1, C2), consultados por `payments-service` en I11 |
| cliente (de otra cuenta) | S20 | `/api/v1/orders/{id}/payments` | POST | Denegado | 404, sin datos y sin revelar si el pedido existe. | `orders-service`: propiedad (C1), a pedido de `payments-service` |
| Visitante (sin token), `administrador`, `dueno`, `cajero_virtual`, `encargado_despachos` | S20 | `/api/v1/orders/{id}/payments` | POST | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `payments-service` (segunda barrera) |
| plataforma-de-pago | S21 | `/api/v1/payments/webhook` | POST | Permitido | Firma y marca de tiempo válidas (C8). Un `eventoId` repetido responde 200 sin procesar. Con monto distinto no se aprueba. | `api-gateway`: ruta pública con límite de tasa. `payments-service`: firma (C8), `eventoId` y monto |
| cualquier otro llamador, incluso con token de usuario | S21 | `/api/v1/payments/webhook` | POST | Denegado | 401. Un usuario no puede informar un pago. | `payments-service`: firma (C8) |
| `cajero_virtual`, `administrador` | S22 | `/api/v1/admin/sales` | GET | Permitido | Ventas de la caja virtual en un período (C6). | `api-gateway`: token (I01) y rol por ruta. `payments-service`: rol y período (C6) |
| Visitante (sin token), `cliente`, `dueno`, `encargado_despachos` | S22 | `/api/v1/admin/sales` | GET | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `payments-service` (segunda barrera) |
| `cliente` | S23 | `/api/v1/orders/{id}/receipt` | GET | Permitido | Solo su boleta (C1) y con el pedido pagado o posterior (C2). | `api-gateway`: token (I01) y rol por ruta. `payments-service`: rol y propiedad y estado (C1, C2) |
| `cajero_virtual`, `administrador` | S23 | `/api/v1/orders/{id}/receipt` | GET | Permitido | Cualquier boleta. | `api-gateway`: token (I01) y rol por ruta. `payments-service`: rol y ámbito |
| cliente (de otra cuenta) | S23 | `/api/v1/orders/{id}/receipt` | GET | Denegado | 404, sin datos y sin revelar si la boleta existe. | `payments-service`: propiedad (C1) |
| Visitante (sin token), `dueno`, `encargado_despachos` | S23 | `/api/v1/orders/{id}/receipt` | GET | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `payments-service` (segunda barrera) |
| `cliente` | S24 | `/api/v1/clients/me` | GET | Permitido | Solo su propio perfil (C1). La ruta no lleva `id`: la cuenta sale del token. | `api-gateway`: token (I01) y rol por ruta. `clients-service`: rol y cuenta del token (C1) |
| Visitante (sin token), `administrador`, `dueno`, `cajero_virtual`, `encargado_despachos` | S24 | `/api/v1/clients/me` | GET | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `clients-service` (segunda barrera) |
| `cliente` | S25 | `/api/v1/clients/me` | PUT | Permitido | Solo su propio perfil (C1). `run` y `correo` no se cambian. | `api-gateway`: token (I01) y rol por ruta. `clients-service`: rol y cuenta del token (C1) |
| Visitante (sin token), `administrador`, `dueno`, `cajero_virtual`, `encargado_despachos` | S25 | `/api/v1/clients/me` | PUT | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `clients-service` (segunda barrera) |
| `administrador` | S26 | `/api/v1/admin/clients` | POST | Permitido | El rol del nuevo usuario es siempre `cliente`. | `api-gateway`: token (I01) y rol por ruta. `clients-service`: rol y rol fijo; `auth-service` rechaza otro rol en I03 |
| Visitante (sin token), `cliente`, `dueno`, `cajero_virtual`, `encargado_despachos` | S26 | `/api/v1/admin/clients` | POST | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `clients-service` (segunda barrera) |
| `administrador` | S27 | `/api/v1/admin/clients` | GET | Permitido | Lista de clientes con perfil y `estado` (C3). | `api-gateway`: token (I01) y rol por ruta. `clients-service`: rol y ruta administrativa |
| Visitante (sin token), `cliente`, `dueno`, `cajero_virtual`, `encargado_despachos` | S27 | `/api/v1/admin/clients` | GET | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `clients-service` (segunda barrera) |
| `administrador` | S28 | `/api/v1/admin/clients/{id}` | PUT | Permitido | Reemplaza los datos personales. No cambia RUN ni correo. | `api-gateway`: token (I01) y rol por ruta. `clients-service`: rol y validación |
| Visitante (sin token), `cliente`, `dueno`, `cajero_virtual`, `encargado_despachos` | S28 | `/api/v1/admin/clients/{id}` | PUT | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `clients-service` (segunda barrera) |
| `administrador` | S29 | `/api/v1/admin/clients/{id}` | DELETE | Permitido | Baja lógica (C13): pedidos y ventas se conservan. | `api-gateway`: token (I01) y rol por ruta. `clients-service`: rol y baja lógica |
| Visitante (sin token), `cliente`, `dueno`, `cajero_virtual`, `encargado_despachos` | S29 | `/api/v1/admin/clients/{id}` | DELETE | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `clients-service` (segunda barrera) |
| `administrador` | S30 | `/api/v1/admin/users` | POST | Permitido | Crea personal con rol distinto de `cliente`. | `api-gateway`: token (I01) y rol por ruta. `auth-service`: rol y validación de rol |
| Visitante (sin token), `cliente`, `dueno`, `cajero_virtual`, `encargado_despachos` | S30 | `/api/v1/admin/users` | POST | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `auth-service` (segunda barrera) |
| `administrador` | S31 | `/api/v1/admin/users` | GET | Permitido | Nunca devuelve contraseñas ni hashes. | `api-gateway`: token (I01) y rol por ruta. `auth-service`: rol y ruta administrativa |
| Visitante (sin token), `cliente`, `dueno`, `cajero_virtual`, `encargado_despachos` | S31 | `/api/v1/admin/users` | GET | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `auth-service` (segunda barrera) |
| `administrador` | S32 | `/api/v1/admin/users/{id}` | PUT | Permitido | No puede dejar al sistema sin administrador activo (C5). | `api-gateway`: token (I01) y rol por ruta. `auth-service`: rol y integridad (C5) |
| Visitante (sin token), `cliente`, `dueno`, `cajero_virtual`, `encargado_despachos` | S32 | `/api/v1/admin/users/{id}` | PUT | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `auth-service` (segunda barrera) |
| `administrador` | S33 | `/api/v1/admin/users/{id}` | DELETE | Permitido | Baja lógica (C13). No a sí mismo ni al último administrador (C5). Invalida sus sesiones. | `api-gateway`: token (I01) y rol por ruta. `auth-service`: rol y integridad (C5) |
| Visitante (sin token), `cliente`, `dueno`, `cajero_virtual`, `encargado_despachos` | S33 | `/api/v1/admin/users/{id}` | DELETE | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `auth-service` (segunda barrera) |
| `dueno`, `administrador` | S34 | `/api/v1/admin/reports/sales` | GET | Permitido | Reporte agregado, sin datos de clientes individuales (C3). Rango de 92 días (C6). | `api-gateway`: token (I01) y rol por ruta. `payments-service`: rol y período (C6) |
| Visitante (sin token), `cliente`, `cajero_virtual`, `encargado_despachos` | S34 | `/api/v1/admin/reports/sales` | GET | Denegado | 401 sin token. 403 con un rol no permitido. Que el botón esté oculto no cambia esta regla. | `api-gateway` (primera barrera) y `payments-service` (segunda barrera) |
| visitante, cualquier rol | S35 | `/api/v1/contact-messages` | POST | Permitido | Límite de tasa (C9). Solo guarda el mensaje; no devuelve datos del negocio. | `api-gateway`: ruta pública y límite de tasa. `notifications-service`: validación |

## 4.9 Verbos por recurso

Cada recurso se muestra con sus cinco verbos. "Permitido" indica los roles que pueden usarlo, "Denegado" que los demás reciben 401 o 403, y "No aplicable" que la ruta no define ese verbo (405). Un verbo permitido en un recurso no autoriza otro: por ejemplo, GET es permitido para un cliente en `/api/v1/orders/{id}` solo sobre sus pedidos y denegado en `/api/v1/admin/orders`, y POST es permitido en `/api/v1/orders` para un cliente y denegado en `/api/v1/products`.

| Recurso | GET | POST | PUT | PATCH | DELETE |
| --- | --- | --- | --- | --- | --- |
| `/api/v1/auth/login` | No aplicable (405) | S01 · Permitido: todos | No aplicable (405) | No aplicable (405) | No aplicable (405) |
| `/api/v1/auth/logout` | No aplicable (405) | S02 · Permitido: `cliente`, `administrador`, `dueno`, `cajero_virtual`, `encargado_despachos`. Denegado: los demás | No aplicable (405) | No aplicable (405) | No aplicable (405) |
| `/api/v1/auth/register` | No aplicable (405) | S03 · Permitido: todos | No aplicable (405) | No aplicable (405) | No aplicable (405) |
| `/api/v1/auth/verify-email` | No aplicable (405) | S04 · Permitido: todos | No aplicable (405) | No aplicable (405) | No aplicable (405) |
| `/api/v1/auth/resend-verification` | No aplicable (405) | S05 · Permitido: todos | No aplicable (405) | No aplicable (405) | No aplicable (405) |
| `/api/v1/products` | S06 · Permitido: todos | S08 · Permitido: `administrador`, `dueno`. Denegado: los demás | No aplicable (405) | No aplicable (405) | No aplicable (405) |
| `/api/v1/admin/products` | S07 · Permitido: `administrador`, `dueno`. Denegado: los demás | No aplicable (405) | No aplicable (405) | No aplicable (405) | No aplicable (405) |
| `/api/v1/products/{id}` | No aplicable (405) | No aplicable (405) | S09 · Permitido: `administrador`, `dueno`. Denegado: los demás | No aplicable (405) | S10 · Permitido: `administrador`, `dueno`. Denegado: los demás |
| `/api/v1/products/{id}/stock` | No aplicable (405) | No aplicable (405) | S11 · Permitido: `administrador`, `dueno`. Denegado: los demás | No aplicable (405) | No aplicable (405) |
| `/api/v1/orders` | S13 · Permitido: `cliente` (solo lo propio, C1). Denegado: los demás | S12 · Permitido: `cliente`. Denegado: los demás | No aplicable (405) | No aplicable (405) | No aplicable (405) |
| `/api/v1/orders/{id}` | S14 · Permitido: `cliente` (solo lo propio, C1), `administrador`, `cajero_virtual`, `encargado_despachos`. Denegado: los demás | No aplicable (405) | No aplicable (405) | No aplicable (405) | No aplicable (405) |
| `/api/v1/orders/{id}/cancel` | No aplicable (405) | S15 · Permitido: `cliente` (solo lo propio, C1). Denegado: los demás | No aplicable (405) | No aplicable (405) | No aplicable (405) |
| `/api/v1/admin/orders` | S16 · Permitido: `administrador`, `cajero_virtual`, `encargado_despachos`. Denegado: los demás | No aplicable (405) | No aplicable (405) | No aplicable (405) | No aplicable (405) |
| `/api/v1/admin/orders/{id}/status` | No aplicable (405) | No aplicable (405) | No aplicable (405) | S17 · Permitido: `encargado_despachos`, `administrador`. Denegado: los demás | No aplicable (405) |
| `/api/v1/admin/dispatch-orders` | S18 · Permitido: `encargado_despachos`, `administrador`. Denegado: los demás | No aplicable (405) | No aplicable (405) | No aplicable (405) | No aplicable (405) |
| `/api/v1/admin/dispatch-orders/{pedidoId}/print` | S19 · Permitido: `encargado_despachos`, `administrador`. Denegado: los demás | No aplicable (405) | No aplicable (405) | No aplicable (405) | No aplicable (405) |
| `/api/v1/orders/{id}/payments` | No aplicable (405) | S20 · Permitido: `cliente` (solo lo propio, C1). Denegado: los demás | No aplicable (405) | No aplicable (405) | No aplicable (405) |
| `/api/v1/payments/webhook` | No aplicable (405) | S21 · Permitido: la plataforma de pago (firma). Denegado: los demás | No aplicable (405) | No aplicable (405) | No aplicable (405) |
| `/api/v1/admin/sales` | S22 · Permitido: `cajero_virtual`, `administrador`. Denegado: los demás | No aplicable (405) | No aplicable (405) | No aplicable (405) | No aplicable (405) |
| `/api/v1/orders/{id}/receipt` | S23 · Permitido: `cliente` (solo lo propio, C1), `cajero_virtual`, `administrador`. Denegado: los demás | No aplicable (405) | No aplicable (405) | No aplicable (405) | No aplicable (405) |
| `/api/v1/clients/me` | S24 · Permitido: `cliente` (solo lo propio, C1). Denegado: los demás | No aplicable (405) | S25 · Permitido: `cliente` (solo lo propio, C1). Denegado: los demás | No aplicable (405) | No aplicable (405) |
| `/api/v1/admin/clients` | S27 · Permitido: `administrador`. Denegado: los demás | S26 · Permitido: `administrador`. Denegado: los demás | No aplicable (405) | No aplicable (405) | No aplicable (405) |
| `/api/v1/admin/clients/{id}` | No aplicable (405) | No aplicable (405) | S28 · Permitido: `administrador`. Denegado: los demás | No aplicable (405) | S29 · Permitido: `administrador`. Denegado: los demás |
| `/api/v1/admin/users` | S31 · Permitido: `administrador`. Denegado: los demás | S30 · Permitido: `administrador`. Denegado: los demás | No aplicable (405) | No aplicable (405) | No aplicable (405) |
| `/api/v1/admin/users/{id}` | No aplicable (405) | No aplicable (405) | S32 · Permitido: `administrador`. Denegado: los demás | No aplicable (405) | S33 · Permitido: `administrador`. Denegado: los demás |
| `/api/v1/admin/reports/sales` | S34 · Permitido: `dueno`, `administrador`. Denegado: los demás | No aplicable (405) | No aplicable (405) | No aplicable (405) | No aplicable (405) |
| `/api/v1/contact-messages` | No aplicable (405) | S35 · Permitido: todos | No aplicable (405) | No aplicable (405) | No aplicable (405) |

Semántica de los verbos: GET consulta y no cambia nada (S19 solo marca la orden como impresa y es idempotente). POST crea un recurso o ejecuta una operación justificada (iniciar sesión, anular, pagar). PUT reemplaza la representación del recurso indicado. DELETE solicita una baja lógica. Se agrega PATCH solo en S17, y su semántica es cambiar únicamente el campo `estado` de un pedido sin reemplazar el resto.

## 4.10 Identidades técnicas: permisos entre sistemas

Las rutas `/internal/...` no se publican. Cada fila indica qué identidad puede llamar qué ruta y con qué límite. Lo que no aparece como permitido está denegado.

| Identidad | Integración | Destino | Ruta | Verbo | Decisión | Alcance y condición | Se verifica en |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `api-gateway` | I01 | `auth-service` | `/internal/introspect` | POST | Permitido | Solo para validar el token recibido. | `auth-service`: C11 |
| `api-gateway` | I02 | Cualquier sistema de negocio | `/internal/...` | Todos | Denegado | El gateway solo reenvía `/api/v1/...`. Las rutas internas no se publican. | `api-gateway`: tabla de rutas |
| `clients-service` | I03 | `auth-service` | `/internal/accounts` | POST | Permitido | Solo con `rol: cliente`. Si pide otro rol, 403. | `auth-service`: C11 y rol |
| `clients-service` | I03 | `auth-service` | `/internal/accounts/{cuentaId}` | DELETE | Permitido | Solo compensación: la cuenta debe seguir `pendiente_verificacion` y ser de rol `cliente`. | `auth-service`: C11 y estado |
| `clients-service` | I04 | `auth-service` | `/internal/accounts?ids=` | GET | Permitido | Devuelve solo `cuentaId`, `correo` y `estado`. | `auth-service`: C11 |
| `clients-service` | I05 | `auth-service` | `/internal/accounts/{cuentaId}` | PATCH | Permitido | Solo `estado: inactivo`, y solo sobre cuentas de rol `cliente`. | `auth-service`: C11 y rol de la cuenta |
| `clients-service` | — | `auth-service` | `/internal/accounts/{cuentaId}` | PUT | Denegado | No puede cambiar contraseñas ni roles de otra cuenta. | `auth-service`: C11 |
| `auth-service` | I06 | `notifications-service` | `/internal/emails` | POST | Permitido | Solo con plantilla `verificacion`. | `notifications-service`: C11 y plantilla |
| `orders-service` | I07 | `clients-service` | `/internal/clients/by-account/{cuentaId}` | GET | Permitido | Devuelve nombre, teléfono y domicilio. No devuelve RUN, fecha de nacimiento ni sexo. | `clients-service`: C11 |
| `orders-service` | I08, I09, I10 | `inventory-service` | `/internal/stock/reservations...` | POST | Permitido | Reservar, confirmar y liberar. No puede cambiar precio ni stock por otra vía. | `inventory-service`: C11 |
| `payments-service` | I11 | `orders-service` | `/internal/orders/{id}/payable` | GET | Permitido | Solo `pedidoId`, `total`, `estado` y `expiraEn`, para la cuenta indicada. | `orders-service`: C11 y propiedad (C1) |
| `payments-service` | I12 | `orders-service` | `/internal/orders/{id}/payment-confirmation` | POST | Permitido | Única identidad que puede llevar un pedido a `pagado`. Orders vuelve a comprobar estado, vencimiento y monto. | `orders-service`: C11 y reglas del pedido |
| `payments-service` | I13 | `notifications-service` | `/internal/emails` | POST | Permitido | Solo con plantilla `boleta`. | `notifications-service`: C11 y plantilla |
| `plataforma-de-pago` (externa) | I15 | `payments-service` | `/api/v1/payments/webhook` | POST | Permitido | Firma y marca de tiempo (C8). No tiene acceso a ninguna otra ruta. | `payments-service`: C8 |
| `notifications-service` | I17 | Proveedor de correo (externo) | API del proveedor | POST | Permitido | Clave del proveedor guardada en Vault, solo para enviar y validar correos. | Proveedor: clave de API |
| `orders-service` | I14 | ActiveMQ `/queue/cola_pedidos` | STOMP | SEND | Permitido | Usuario del broker solo de escritura. | ActiveMQ: usuario y permisos |
| `dispatch-service` | I14 | ActiveMQ `/queue/cola_pedidos` | STOMP | SUBSCRIBE | Permitido | Usuario del broker solo de lectura. | ActiveMQ: usuario y permisos |
| `inventory-service`, `dispatch-service`, `notifications-service` | — | Cualquier otro sistema | `/internal/...` | Todos | Denegado | No hacen llamadas hacia otros sistemas de negocio. No existe par de credenciales para ellos. | Sistema llamado: C11 |
| `clients-service` u otro sistema distinto de `payments-service` | — | `orders-service` | `/internal/orders/{id}/payment-confirmation` | POST | Denegado | El par de credenciales no está en la lista permitida de esa ruta. | `orders-service`: C11 |
| `orders-service` | — | `payments-service` | Cualquier ruta | Todos | Denegado | Orders nunca llama a payments. Evita el ciclo de dependencias (Módulo 3). | `payments-service`: C11 |
| `graphql-gateway` | — | `orders-service` | `/orders` y `/orders/{id}` | GET | Permitido | Solo lectura y con el contexto del usuario propagado. Orders sigue aplicando la propiedad (C1). | `orders-service`: C11 y C1 |
| `graphql-gateway` | — | `inventory-service` | `/products` | GET | Permitido | Solo campos públicos del catálogo (C12). | `inventory-service`: C11 |
| `graphql-gateway` | — | `clients-service` | `/clients/me` | GET | Permitido | Solo el perfil de la cuenta propagada (C1). | `clients-service`: C11 y C1 |
| `graphql-gateway` | — | Cualquier sistema | Cualquier ruta | POST, PUT, PATCH, DELETE | Denegado | No hay mutaciones: las reglas de negocio y las escrituras quedan en cada sistema. Tampoco puede llamar rutas `/internal/...`. | Sistema llamado: C11 |
| Navegador (cualquier rol) | — | Cualquier sistema | `/internal/...` | Todos | Denegado | No hay ruta publicada. El gateway responde 404. | `api-gateway`: tabla de rutas |

## 4.11 Anulación e historial

Anular un pedido no lo borra. No existe DELETE sobre pedidos, ventas ni boletas. La anulación (S15 o S17) cambia `estado` a `anulado`, agrega un registro `CambioEstado` con el motivo y quién lo pidió, y conserva el pedido, sus líneas y la dirección. Si ya estaba pagado, queda `reembolsoPendiente` y se conservan la venta y la boleta.

Las bajas de producto (S10), cliente (S29) y usuario (S33) también son lógicas: el registro queda marcado y los pedidos antiguos siguen mostrando los mismos datos porque cada línea guarda el nombre y el precio del momento de la compra.

## 4.12 Cómo la matriz impide que un cliente consulte pedidos de otro

Se comprueba con tres filas de la matriz 4.8:
1. S13: el cliente solo lista los pedidos de su `cuentaId`. La consulta se filtra con el valor de `X-Authenticated-User` y no existe parámetro para indicar otro cliente.
2. S14: el cliente puede leer un pedido solo si `Pedido.cuentaId` coincide con el suyo (C1). La búsqueda es `{id, cuentaId: <del token>}`. Si no coincide, devuelve 404, igual que un pedido inexistente.
3. S15, S20 y S23: aplican la misma regla C1 antes de mirar el estado, así que un cliente tampoco puede anular, pagar ni pedir la boleta de otro.

Regla aplicada por: `orders-service` (S13 a S15 y S20 a través de I11) y `payments-service` (S23). Las pruebas T-AUT-01 a T-AUT-04 (4.13) muestran la ejecución autorizada y la denegada de la misma regla.

## 4.13 Pruebas de autorización previstas

Se ejecutan en el Módulo 10, con la evidencia de cada resultado.

| ID | Regla | Caso | Resultado esperado | Servicio que la aplica |
| --- | --- | --- | --- | --- |
| T-AUT-01 | C1 | El cliente A consulta con su token un pedido de la cuenta B (S14). | 404, sin datos de B y sin diferencia visible con un pedido inexistente. | `orders-service` |
| T-AUT-02 | C1 | El cliente A consulta su propio pedido (S14). | 200 con el pedido. | `orders-service` |
| T-AUT-03 | C1, C2 | El cliente A anula un pedido de B (S15). Luego anula uno propio en `en_preparacion`. | 404. Luego 409. | `orders-service` |
| T-AUT-04 | C1 | El cliente A pide la boleta de un pedido de B (S23). | 404. | `payments-service` |
| T-AUT-05 | Rol | Un cliente intenta DELETE de un producto (S10) y POST de un producto (S08). | 403 en ambos. | `api-gateway` e `inventory-service` |
| T-AUT-06 | C12 | Un visitante consulta el catálogo (S06) y luego un pedido (S14). | 200 sin `stock`. Luego 401. | `inventory-service`, `api-gateway` |
| T-AUT-07 | C7 | `encargado_despachos` intenta anular (S17). Cualquier rol intenta pasar a `pagado`. | 403. 409. | `orders-service` |
| T-AUT-08 | C8 | Webhook con firma inválida y luego con firma válida (S21). | 401 y no cambia nada. Luego 200 y el pedido pasa a `pagado`. | `payments-service` |
| T-AUT-09 | Rol, C3 | El dueño pide la lista de pedidos (S16) y el reporte (S34). | 403 y 200. | `api-gateway` y `orders-service` |
| T-AUT-10 | Identidad | Un cliente envía `X-Authenticated-Roles: administrador` en su solicitud a S16. | El gateway borra la cabecera y la solicitud se evalúa con el rol real: 403. | `api-gateway` |
| T-AUT-11 | C11 | Llamada directa a `orders-service` sin `X-Gateway-Secret`. Luego con el secreto pero sin identidad. | 401 en ambas. | `orders-service` |
| T-AUT-12 | C11 | `clients-service` llama a `payment-confirmation` de orders. | 403. | `orders-service` |
| T-AUT-13 | Red | Se pide `/internal/introspect` por el gateway. | 404. | `api-gateway` |
| T-AUT-14 | C5 | El administrador se da de baja a sí mismo (S33). Se cambia el rol del último administrador (S32). | 409 en ambos. | `auth-service` |

## 4.14 Control antes de avanzar

| Pregunta | Respuesta |
| --- | --- |
| ¿Los permisos se expresan por servicio y recurso? | Sí. La matriz 4.8 tiene una fila por servicio y regla, con ruta y verbo, y la tabla 4.9 muestra cada recurso con sus verbos. |
| ¿Se distinguen identidad y autorización? | Sí. La tabla 4.5 separa quién es quien llama (token, secreto de sistema, firma) de lo que puede hacer (rol, propiedad, estado). |
| ¿La matriz permite comprobar que un usuario no consulta pedidos de otro? | Sí. La condición C1 se aplica en S13, S14, S15, S20 y S23, y las pruebas T-AUT-01 a T-AUT-04 la ejercitan. |
| ¿Hay stakeholders sin permisos operativos? | Sí. Cocina, repartidor, contabilidad y el responsable de la infraestructura figuran sin permisos y la tabla 4.3 explica cómo reciben su información. |
| ¿Se fundamentaron los permisos de administración y las identidades de sistemas? | Sí. Los permisos por rol se justifican en 4.4 y los de cada sistema en 4.10. |
