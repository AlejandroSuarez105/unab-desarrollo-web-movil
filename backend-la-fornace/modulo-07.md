# Evaluación Unidad 2 — Backend seguro completo
## Pizzería La Fornace (derivado del Caso 19)

---

# Módulo 7 — Datos sensibles y secretos del cliente

## 7.1 Cumplimiento de los pasos a seguir de la guía

| Paso de la guía | Dónde está |
| --- | --- |
| 1. Inventario de campos públicos, personales, sensibles según el contexto y credenciales, con su motivo. | 7.2 y 7.3. |
| 2. Decidir si hay que custodiar secretos del cliente, con fundamento. | 7.4. |
| 3. Quién consulta o modifica cada dato, qué devuelve cada servicio y cómo se limita el acceso a lo propio. | 7.3 (roles), 7.5 y 7.6. |
| 4. Almacenamiento, transporte, retención, eliminación y exclusión de logs. Hash adaptativo con sal. | 7.7, 7.8 y 7.9. |
| 5. Sesiones y tokens, expiración y revocación. Ninguna clave compartida en el navegador. | 7.10. |
| Matriz de datos y credenciales. | 7.3. |
| Recorrido de un dato restringido desde su captura hasta su eliminación. | 7.11. |
| Casos de validación. | 7.12. |

## 7.2 Qué se protege y cómo se clasifica

Se distinguen tres cosas que se suelen confundir:

| Tipo | Qué es | Ejemplos en La Fornace | Cómo se protege |
| --- | --- | --- | --- |
| Dato personal | Información sobre una persona identificable | RUN, nombre, correo, teléfono, fecha de nacimiento, sexo, dirección, historial de pedidos | Se limita quién lo ve, qué servicio lo devuelve y cuánto tiempo se guarda. No es una clave. |
| Credencial del usuario | Lo que prueba quién es el usuario | Contraseña, token de sesión, token de verificación | Se guarda solo como hash, vence y se revoca. Nunca se devuelve. |
| Secreto de integración | Lo que prueba quién es un sistema | Secretos del gateway, pares entre sistemas, clave del proveedor de pagos, credenciales de base de datos | Vault, permisos mínimos, rotación (Módulo 6). El navegador nunca lo recibe. |

La clasificación del Módulo 1 se mantiene: **Público**, **Operativo**, **Restringido** y **Credencial**. Se agrega **Secreto de integración** (Módulo 6). El rótulo "sensible según el contexto" no es una categoría legal nueva. Marca los datos restringidos que, por lo que revelan en esta aplicación, merecen cuidado extra:

- **Dirección de entrega y teléfono**: juntos, indican dónde vive una persona y cuándo pide comida a su casa.
- **RUN**: es el identificador que se usa para suplantar a alguien.
- **Historial de pedidos**: muestra hábitos y horarios.

No se recogen datos de salud, origen, creencias ni datos biométricos. `fechaNacimiento` y `sexo` son personales, y se piden porque el Caso 19 los incluye en el registro (RF5).

## 7.3 Matriz de datos y credenciales

Cada fila indica el sistema que custodia el dato y que puede cambiarlo. Las copias congeladas (M3 3.4) están en la columna del sistema.

| ID | Dato o credencial | Finalidad | Clasificación | Sistema custodio | Roles autorizados | Representación en el frontend | Protección | Retención |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D01 | `run` | Identificar de forma única al cliente (RF5). No se puede cambiar después del alta. | Restringido. Sensible según el contexto: se usa para suplantar identidades. | `clients-service` | Lee: `cliente` (el propio) y `administrador`. Modifica: nadie tras el alta. | Se muestra en "Mi perfil" (P12) y en administración de clientes (P16). No aparece en pedidos, boletas, despacho ni listas del personal. No se guarda en el navegador. | TLS. Solo viaja en S03, S24, S26 y S27. No sale de clients: I07 no lo incluye. Nunca en registros ni en mensajes de error. | Mientras exista el cliente. Se anonimiza 24 meses después de la baja. |
| D02 | `nombreCompleto` | Nombrar al cliente en el pedido, el despacho y la boleta (RF5, RF8, RF13). | Restringido | `clients-service`. Copias congeladas: `clienteNombre` en orders, payments y dispatch. | Lee: `cliente` (el propio), `administrador`; en las copias, el personal que atiende pedidos, ventas o despacho. Modifica: `cliente` (S25) y `administrador` (S28). | Perfil (P12, P16), detalle de pedido y boleta (P11, P14) y orden impresa (P15). | TLS. Las copias son solo lectura y no modifican al cliente. Fuera de los registros. | Perfil: como `run`. Copia en pedido: 12 meses desde la entrega. Copia en venta y boleta: 6 años. Copia en despacho: 90 días. |
| D03 | `correo` | Iniciar sesión, validar que existe, enviar el enlace de verificación y la boleta (RF5, RF8, RF11). | Restringido | `auth-service` (cuenta). Copias: `clienteCorreo` en orders (solo para la venta) y en payments (para la boleta). | Lee: `cliente` (el propio) y `administrador`. Modifica: nadie desde el perfil (S25 no lo cambia). Se fija en el alta (S03, S26). | Perfil, administración de clientes (P16), formulario de inicio de sesión (P06). No aparece en listas de pedidos ni de ventas. | TLS. No se devuelve en S13, S14, S16, S18, S22 ni S23. Fuera de los registros. No va en la URL. | Cuenta: como `run`. Copia en pedido: 12 meses desde la entrega. Copia en venta: 6 años. |
| D04 | `telefono` | Contactar para la entrega (RF1, RF13). | Restringido. Sensible según el contexto: junto con la dirección, ubica a una persona. | `clients-service`. Copias: `clienteTelefono` en orders y `telefono` en dispatch. | Lee: `cliente` (el propio), `administrador`, y `encargado_despachos` y `administrador` en la orden de despacho. Modifica: `cliente` (S25) y `administrador` (S28). | Perfil (P12, P16) y orden de despacho impresa (P15). No se devuelve en S16. | TLS. Fuera de los registros. En la cola ActiveMQ viaja solo dentro de la red privada. | Perfil: como `run`. Copia en pedido: 12 meses desde la entrega. Copia en despacho: 90 días. |
| D05 | `fechaNacimiento` y `sexo` | Datos de registro que pide el Caso 19 (RF5), para las promociones y ofertas. | Restringido | `clients-service` | Lee: `cliente` (el propio) y `administrador`. Modifica: `cliente` (S25) y `administrador` (S28). | Solo en el perfil (P12) y en administración de clientes (P16). | TLS. No viajan a orders, payments ni dispatch (I07 no los incluye). Fuera de los registros. | Como `run`. |
| D06 | `direccion` del perfil (`calle`, `comuna`, `provincia`, `region`) | Domicilio del cliente para precargar la entrega (RF5, RF1). | Restringido. Sensible según el contexto: es el domicilio de una persona. | `clients-service` | Lee: `cliente` (el propio) y `administrador`. Modifica: `cliente` (S25) y `administrador` (S28). | Perfil (P12) y precarga en el carrito (P03). | TLS. Se entrega a orders solo en I07, por cuenta. Fuera de los registros. | Como `run`. |
| D07 | `direccionEntrega` del pedido (`calle`, `comuna`, `referencia`) | Entregar el pedido y validar los 3 km (RF1). | Restringido. Sensible según el contexto. | `orders-service`. Copia: `direccionEntrega` en dispatch. | Lee: `cliente` dueño del pedido; `administrador`, `cajero_virtual` y `encargado_despachos` (el DTO operativo, C3). `dueno`: nunca. Modifica: nadie después de crear el pedido. | Formulario de pedido (P03), detalle (P11, P14) y orden impresa (P15). No hay en el catálogo público. | TLS. No va en el carrito ni en el almacenamiento del navegador. Dispatch la recibe sin precios, RUN ni correo (I14). | Pedido: 12 meses desde la entrega, luego se borran `calle` y `referencia`. Despacho: 90 días. |
| D08 | Pedido: ítems, total, estado, historial y `motivo` de anulación | Operar la venta (RF1 a RF3). El motivo puede contener texto libre del cliente. | Operativo. `motivo` es Restringido. | `orders-service` | Lee: `cliente` dueño (C1); personal según M4. Modifica: solo orders (S12, S15, S17, I12). | Mis pedidos y detalle (P11), administración de pedidos (P14). | TLS. El cliente solo ve lo suyo. El motivo no se registra. | Pagado: 6 años (respalda la venta). Vencido o anulado sin pago: 12 meses. |
| D09 | Pago: `medio`, `monto`, `estado`, `urlPago` | Cobrar en la plataforma externa (RF2). | Operativo. `urlPago` es de un solo uso (ver 7.5). | `payments-service` | Lee: cliente dueño (solo el resultado en S20); payments. Modifica: solo payments (S20, S21). | Página de pago (P10): redirige a `urlPago`. No se guarda. | TLS. No hay datos de tarjeta en ningún sistema. `urlPago` no se registra. | Pago y avisos (`EventoPago`): 12 meses. Si el pago aprobado origina una venta: 6 años. |
| D10 | Venta, líneas y boleta (`numeroBoleta`, total, ítems, `clienteNombre`, `clienteCorreo`) | Registro de la caja virtual y boleta digital (RF4, RF8). | Operativo. Nombre y correo: Restringido. | `payments-service` | Lee: `cajero_virtual` y `administrador` (S22, S23); `cliente` dueño (S23). `dueno`: solo cifras agregadas (S34). | Boleta (P11, P14) y ventas de la caja (P14). | TLS. S22 no devuelve el correo. S34 no devuelve datos de clientes individuales. | 6 años (plazo referencial por obligación tributaria, a confirmar con contabilidad). |
| D11 | Orden de despacho (`numeroOrden`, nombre, teléfono, dirección, ítems sin precio, `impresa`) | Armar y entregar el pedido en orden de llegada (RF13). | Restringido (nombre, teléfono, dirección). Operativo (el resto). | `dispatch-service` | Lee: `encargado_despachos` y `administrador`. Modifica: solo dispatch (I14, S19). | Cola de despacho y orden impresa (P15). | TLS. Sin precios, RUN ni correo. El usuario de dispatch en ActiveMQ es de solo lectura. | 90 días desde la llegada. Se borra con un índice TTL de MongoDB. |
| D12 | Mensaje de contacto (`nombre`, `correo`, `telefono`, `motivo`, `mensaje`) | Atender consultas del visitante (RF14). | Restringido. El `mensaje` es texto libre y puede traer datos de cualquier tipo. | `notifications-service` | Lee: nadie desde la API (es un extra del frontend, RF14, sin servicio de lectura). Escribe: el visitante (S35). | Formulario de contacto (P05). No se guarda en el navegador. | TLS. El `mensaje` no se registra. Límite de 10 solicitudes por minuto por IP. | 12 meses. Se borra con un índice TTL de MongoDB. |
| D13 | Catálogo: `nombre`, `categoria`, `descripcion`, `precio`, `imagen`, `destacado`, `disponible` | Mostrar la carta (RF1, RF7). | Público | `inventory-service` | Lee: cualquiera (S06). Modifica: `administrador` y `dueno` (S08 a S11). | Inicio, menú y carrito (P01 a P03). | Sin `stock` ni productos retirados en la respuesta pública (C12). Escritura solo con rol. | Sin límite. La baja es lógica (C13). |
| D14 | `stock` y movimientos de stock | Controlar el inventario y las reservas. | Operativo | `inventory-service` | Lee: `administrador` y `dueno` (S07). Modifica: `administrador` y `dueno` (S11) e `orders-service` por reservas (I08 a I10). | Panel de administración de productos (P13). | No se devuelve en S06. Solo orders puede reservar. | Movimientos: 12 meses. |
| D15 | `password` (entrada) y `passwordHash` | Autenticar al usuario (S01, S03, S04). | Credencial | `auth-service` | Lee: nadie. Ni el hash se devuelve (M4 4.8). Modifica: solo el propio usuario al activar la cuenta (S04). | Campo de contraseña en el inicio de sesión (P06) y en el registro (P08, P09). No se guarda en el navegador. El campo es de tipo contraseña. | Solo llega por TLS en el cuerpo. Se guarda un **hash adaptativo con sal** (bcrypt, costo 12, sal propia por contraseña), nunca la contraseña ni un cifrado reversible. No se devuelve, ni se registra, ni se envía a otro sistema. | Mientras exista la cuenta. Se elimina al anonimizar. |
| D16 | `access_token` (Bearer) y `Sesion.tokenHash` | Identificar al usuario en cada solicitud (S01, S02). | Credencial | `auth-service` | Lo recibe quien inicia sesión. Auth guarda solo el hash. Lo valida el gateway (I01). | `sessionStorage`, nunca `localStorage`. Se envía en `Authorization`. Se borra al cerrar sesión o la pestaña. | Valor aleatorio de 256 bits. Auth guarda solo su SHA-256. Vence a los 900 s. No se registra. | Documento de sesión: se borra 24 horas después de vencer (TTL). |
| D17 | Token de verificación del correo | Confirmar el correo o definir la contraseña (S04, S05). | Credencial | `auth-service`. Viaja en el correo (`enlace`). | Lo recibe el dueño del correo. | Llega en el enlace. La página lo lee, lo envía por POST (S04) y lo quita de la URL. | Aleatorio de 256 bits, un solo uso, vence en 24 h (C10). Se guarda solo su hash. El reenvío invalida el anterior. | Se borra 7 días después de vencer o usarse (TTL). |
| D18 | `intentosFallidos`, `estado` y `rol` de la cuenta | Bloquear la fuerza bruta (C9) y decidir el acceso (C4). | Operativo | `auth-service` | Lee: `administrador` (estado y rol, S31). Modifica: solo auth. | Lista de usuarios (P17): `estado` y `rol`. `intentosFallidos` no se muestra. | 5 intentos fallidos bloquean la cuenta 15 minutos. La respuesta de error no dice si el correo existe. | Mientras exista la cuenta. |
| D19 | Secretos de integración (claves de proveedores, secretos del gateway, pares entre sistemas, bases de datos, tokens de Vault) | Autenticar a los componentes entre sí y con los proveedores (Módulo 6). | Secreto de integración | Vault | Ningún rol de la API. Cada componente lee solo lo suyo. Los administra el responsable de infraestructura. | Nunca. No existen en el código, el HTML ni las capturas del frontend. | Módulo 6 (6.9 y 6.10): referencias simbólicas, permisos mínimos, rotación y revocación. | Hasta la rotación (Módulo 6). |

Lo que guarda el navegador, y nada más:

| Dónde | Qué | Por qué |
| --- | --- | --- |
| `localStorage` | El carrito: solo `id` y `cantidad` de cada producto | No tiene precio ni datos personales. El servidor vuelve a calcular todo al crear el pedido. |
| `sessionStorage` | El `access_token` y el rol y nombre que devuelve S01 | Se borra al cerrar la pestaña. El token vence a los 900 s. |
| En ningún lado | Contraseñas, RUN, dirección, perfil, claves o secretos | Se piden o se muestran, y se descartan. |

## 7.4 Decisión: ¿se custodian secretos del cliente?

**No.** Fundamento:

1. **No se guardan medios de pago.** El pago ocurre en la plataforma externa: el cliente es redirigido a `urlPago` y los datos de tarjeta o de cuenta no pasan por ningún sistema nuestro. No hay "guardar tarjeta".
2. **No hay claves, llaves de API ni credenciales de terceros del cliente.** Lo que el sistema le pide al cliente es su contraseña, y esa no se *custodia*: se *verifica*. Se guarda solo un hash que no permite recuperarla (D15).
3. **Los datos restringidos no son claves.** El RUN, la dirección o el teléfono se protegen controlando quién los ve y cuánto duran, no escondiéndolos como se hace con una clave.

Si en el futuro se quisiera recordar un medio de pago, la solución sería un token que entregue el proveedor, nunca los datos del medio.

**El token de pago.** `urlPago` identifica un solo cobro y vence en `expiraEn`. No permite operar la cuenta del comercio ni cobrar otros montos, así que se trata como dato de un solo uso y no como secreto: viaja al navegador y no se registra. La **clave del proveedor** (`payments-provider-key`) sí es un secreto de integración que permite crear cobros: está en Vault y solo la lee `payments-service`.

## 7.5 Qué devuelve cada servicio

El modelo interno no sale completo (M2 2.10). Cada servicio devuelve solo lo que su pantalla necesita.

| Servicio | DTO | Datos que devuelve | Datos que quedan dentro |
| --- | --- | --- | --- |
| S01 | `SesionDTO` | `access_token`, `token_type`, `expires_in`, `rol`, `nombre` | `passwordHash`, `intentosFallidos`, `tokenHash` |
| S06 | `ProductoPublicoDTO` | Campos públicos del catálogo | `stock`, `retirado` |
| S12, S14 | `PedidoDetalleDTO` | Pedido con ítems, total, `direccionEntrega`, historial y estado. Al cliente dueño o al personal | `clienteId`, `cuentaId`, `actorId`, banderas de reintento, correo, teléfono, RUN |
| S13 | `PedidoResumenDTO` | `id`, `estado`, `total`, `creadoEn` | Todo lo demás |
| S16 | `PedidoOperacionDTO` | `id`, `estado`, `total`, `creadoEn`, `clienteNombre`, `direccionEntrega` | `clienteTelefono`, `clienteCorreo`, `cuentaId`, RUN |
| S18, S19 | `OrdenDespachoDTO` y documento imprimible | `numeroOrden`, `pedidoId`, `pagadoEn`, `clienteNombre`, `telefono`, `direccionEntrega`, ítems sin precio | Precios, total, RUN y correo (la orden nunca los recibe) |
| S20 | `PagoIniciadoDTO` | `pagoId`, `estado`, `urlPago`, `expiraEn` | `pedidoId`, `monto`, banderas |
| S22 | `VentaResumenDTO` | `ventaId`, `pedidoId`, `numeroBoleta`, `total`, `fecha`, `correoEnviado` | `clienteCorreo`, `cuentaId`, `intentosEnvio` |
| S23 | `BoletaDTO` | `numeroBoleta`, `fechaEmision`, `pedidoId`, `clienteNombre`, `items`, `total`, `ivaIncluido` | `cuentaId`, `clienteCorreo` |
| S24, S25 | `PerfilClienteDTO` | `id`, `run`, `nombreCompleto`, `correo`, `telefono`, `fechaNacimiento`, `sexo`, `direccion` | `cuentaId`, `passwordHash`, `rol`, `intentosFallidos` |
| S27, S28 | `ClienteAdminDTO` | Los del perfil más `estado` | `cuentaId`, `passwordHash`, `intentosFallidos` |
| S31, S32 | `UsuarioDTO` | `id`, `nombreCompleto`, `correo`, `rol`, `estado` | `passwordHash`, `cuentaId`, `intentosFallidos` |
| S34 | `ReporteVentasDTO` | Totales, `porDia[]` y `topProductos[]` | Nombre, correo y cuenta de cualquier cliente |

Se aplican las reglas de ámbito del Módulo 4 (C3): el personal recibe el DTO operativo y el cliente su propio DTO. El dueño no recibe datos de pedidos ni de clientes individuales.

## 7.6 Cómo se limita el acceso a lo propio

| Regla | Cómo se cumple |
| --- | --- |
| La identidad sale del token, no de la solicitud. | `cuentaId` viene de `X-Authenticated-User`, que el gateway escribe a partir de I01. El cuerpo no puede traer `clienteId`, `cuentaId` ni `rol`. |
| Cada consulta filtra por dueño. | `orders-service`, `payments-service` y `clients-service` buscan siempre por el identificador del recurso **y** `cuentaId` (C1). |
| Un recurso ajeno no se distingue de uno inexistente. | Respuesta 404 idéntica (T-DAT-04). |
| El perfil no lleva identificador en la ruta. | S24 y S25 usan `/clients/me`. No hay manera de pedir el de otro. |
| Las listas propias no aceptan un `cuentaId`. | S13 devuelve solo los pedidos de la cuenta autenticada. |
| Los identificadores de recurso son opacos. | Los genera el servidor. Adivinar uno no da acceso, porque la propiedad se comprueba igualmente. |
| Ocultar un botón no protege. | Toda regla se aplica en el backend aunque la pantalla sea accesible desde Internet. |

## 7.7 Almacenamiento y transporte

| Tema | Decisión |
| --- | --- |
| Dónde se guardan los datos | Cada sistema en su propia base de MongoDB, con su usuario (`db-<sistema>`). Ningún otro componente la lee. |
| Contraseñas | **Hash adaptativo con sal: bcrypt, costo 12**, con sal propia por contraseña. El límite de 72 caracteres del Módulo 1 es el del algoritmo. Ni cifrado reversible ni hash simple. |
| Tokens de sesión y de verificación | Valores aleatorios de 256 bits. Se guarda solo su SHA-256. |
| Datos personales en la base | En texto, sin cifrado por campo. Razón: el acceso a la base está limitado al sistema dueño y cifrar por campo exige gestionar otra clave sin cambiar quién puede leer el dato. Se declara como límite: no protege contra quien tenga acceso al disco del servidor. |
| Transporte | TLS entre navegador, gateway, sistemas y Vault (M6 6.12). Excepción declarada de MongoDB y ActiveMQ dentro de la red privada. |
| Datos en la URL | Ninguno restringido, salvo el filtro `q` de S27, que no se registra (7.8). El token de verificación llega en el enlace del correo: la página lo envía por POST, lo quita de la URL con `history.replaceState` y usa `Referrer-Policy: no-referrer`. |
| Copias de respaldo | Heredan las mismas reglas. No se incluyen en el repositorio. |
| Datos de ejemplo | Siempre ficticios (por ejemplo, `ClaveFicticia123` y `tok_ficticio_abc123`). |

## 7.8 Qué no se registra

El registro de cada solicitud guarda `requestId`, verbo, ruta **sin la cadena de consulta**, estado, duración, `cuentaId` y la decisión (permitido o denegado, con el código de error). Nunca guarda:

| Dato | Tipo |
| --- | --- |
| Contraseñas, tokens (Bearer y de verificación), hashes y cabecera `Authorization` | Credenciales |
| `X-Gateway-Secret`, `X-Service-Secret`, `X-Signature` y cualquier valor de Vault | Secretos de integración |
| RUN, correo, teléfono, fecha de nacimiento, sexo, dirección y nombre | Datos personales |
| Cuerpos de solicitudes y respuestas, `motivo` de anulación y `mensaje` de contacto | Texto libre del cliente |
| La cadena de consulta de la URL (por ejemplo, `?q=` en S27, que es texto de búsqueda) | Datos personales en la URL |
| `urlPago` y la clave del proveedor | Datos de pago |

Los mensajes de error no repiten el valor recibido (dicen "correo inválido", no el correo). Las capturas del informe se toman con las cabeceras de credenciales ocultas.

## 7.9 Retención y eliminación

| Dato | Retención | Mecanismo | Estado |
| --- | --- | --- | --- |
| Sesión (`Sesion`) | Token: 900 s. Documento: 1 h después de vencer | Purga periódica de `auth-service` (cada 5 minutos) | Implementado |
| Token de verificación | 24 h de vigencia. Documento: 24 h después de vencer | Purga periódica de `auth-service` (cada 5 minutos) | Implementado |
| Orden de despacho | 90 días desde la llegada | Purga periódica de `dispatch-service` | Implementado y probado (RET-01) |
| Mensaje de contacto | 12 meses | Purga periódica de `notifications-service` | Implementado y probado (RET-02) |
| Aviso de pago (`EventoPago`) y pago sin venta | 12 meses | Purga periódica de `payments-service` | Implementado y probado (RET-03). El pago con venta se conserva (RET-04) |
| Movimiento de stock | 12 meses | Purga periódica de `inventory-service` | Implementado y probado (RET-05) |
| Pedido pagado, líneas e historial | 6 años | Sin borrado automático. Respalda la venta | Política |
| Pedido vencido o anulado sin pago | 12 meses desde el cambio de estado | Purga periódica de `orders-service` | Implementado y probado (RET-06). Si el pedido llegó a pagarse se conserva (RET-07) |
| Dirección y teléfono copiados en el pedido | 12 meses desde la entrega. Después se borran `calle`, `referencia` y `clienteTelefono` | Purga periódica de `orders-service` | Implementado y probado (RET-08 y RET-09) |
| Venta, líneas y boleta | 6 años (plazo referencial, a confirmar con contabilidad) | Sin borrado automático | Política |
| Cliente dado de baja | 24 meses desde la baja. Después se anonimiza `run`, `nombreCompleto`, `telefono`, `fechaNacimiento`, `sexo` y `direccion` en clients; en auth se reemplazan `correo` y `nombre` y se elimina el hash de la contraseña | Purga periódica de `clients-service` y de `auth-service` | Implementado y probado (RET-10 y RET-11) |
| Solicitud de eliminación de un cliente | Se atiende con la baja (S29) y la anonimización de su perfil. Se conserva lo que la obligación tributaria exige (venta y boleta) | Procedimiento del administrador y del responsable de infraestructura | Política |
| Secretos de integración | Hasta su rotación (Módulo 6) | Vault | Módulo 6 |

"Implementado" significa que cada sistema ejecuta una tarea periódica propia (se eligieron tareas del propio sistema en lugar de índices TTL), con los plazos en `common/fornace/retencion.py` y un intervalo de una hora. Las pruebas RET-01 a RET-12 (10.9.12) crean los datos, les retroceden las fechas en la base y comprueban qué se elimina, qué se anonimiza y qué se conserva; no se esperó el paso real del tiempo (10.11). Los pedidos pagados y las ventas siguen siendo política: se conservan 6 años sin borrado automático. Los plazos son decisiones de diseño del equipo. El de 6 años de ventas es referencial por obligación tributaria y debe confirmarse con la contabilidad del local.

## 7.10 Sesiones y tokens

| Tema | Decisión |
| --- | --- |
| Tipo de token | Opaco y aleatorio de 256 bits, sin datos dentro. Por eso su validez se consulta a auth en cada solicitud (I01). |
| Expiración | 900 s desde que se emite (M1). No hay token de renovación en esta entrega. Si vence, el frontend recibe 401 y vuelve al inicio de sesión. Consecuencia: quien tarde más de 15 minutos en la página de pago debe iniciar sesión otra vez al volver. |
| Revocación | Inmediata: S02 cierra la sesión, y la baja de una cuenta (S29, S33) y el cambio de rol (S32) invalidan sus sesiones. Como el gateway consulta a auth en cada solicitud, un token revocado deja de servir en la siguiente. |
| Almacenamiento en el servidor | Solo el hash del token. Si alguien lee la base de auth, no obtiene tokens válidos. |
| Almacenamiento en el navegador | `sessionStorage`. Riesgo: un script inyectado (XSS) podría leerlo. Se reduce con escape de todo texto mostrado y con una `Content-Security-Policy` en el servidor del frontend que solo deja conectarse al API Gateway (`connect-src`), bloquea plugins, base ajena, marcos y formularios hacia otros sitios. La política permite scripts en línea (`unsafe-inline`) porque las páginas los usan, así que no impide que un script inyectado se ejecute: solo limita adónde puede enviar el token (GW-CSP, 10.9.6). No se usan cookies, así que no hay riesgo de CSRF. |
| Fuerza bruta | 5 intentos fallidos bloquean la cuenta 15 minutos (C9), más `RL-SENSIBLE` por IP. La respuesta de S01 es la misma si el correo no existe o la contraseña es incorrecta. |
| Token de verificación | Un solo uso, 24 horas, y el reenvío invalida el anterior (C10). |
| **Claves en el navegador** | El frontend **no contiene ninguna clave compartida**: un valor puesto en JavaScript lo puede leer cualquiera que abra la página. La única credencial del navegador es el token del usuario, que es personal, vence y se puede revocar. Los secretos de integración y la clave del proveedor de pagos solo existen en el backend (D19). |

## 7.11 Recorrido de un dato restringido: la dirección de entrega

| Etapa | Qué ocurre con el dato | Dónde | Quién puede verlo | Protección |
| --- | --- | --- | --- | --- |
| 1. Captura | El cliente la escribe en el pedido (P03) o se precarga desde su perfil (S24) | Navegador | El propio cliente | No se guarda en el navegador. El carrito solo tiene `id` y `cantidad`. |
| 2. Transporte | `POST /api/v1/orders` (S12) | Navegador → gateway | Nadie en el camino | TLS. El gateway no registra el cuerpo. |
| 3. Reenvío | El gateway agrega la identidad verificada y pasa el cuerpo | Gateway → orders | Solo orders | TLS y `gateway-to-orders`. |
| 4. Validación y guardado | Orders comprueba que esté dentro de los 3 km y guarda una copia congelada en el pedido | `orders-service` | Cliente dueño y personal que atiende (C1, C3) | Base propia. Fuera de los registros. |
| 5. Publicación | Tras el pago, orders la envía en la orden de despacho, sin precios, RUN ni correo (I14) | ActiveMQ → `dispatch-service` | Solo dispatch lee la cola | Usuarios de escritura y lectura separados (M6). |
| 6. Uso | El encargado la imprime (S19) y entrega la orden impresa a cocina y al repartidor | Panel (P15) | `encargado_despachos` y `administrador` | El rol se verifica en el gateway y en dispatch. La hoja impresa sale de la API. |
| 7. Eliminación en despacho | La orden se borra a los 90 días | `dispatch-service` | — | Purga periódica (RET-01). |
| 8. Conservación en el pedido | Se conserva con el pedido mientras sirve para atender reclamos | `orders-service` | Como en la etapa 4 | 12 meses desde la entrega. |
| 9. Eliminación | Se borran `calle`, `referencia` y el teléfono del pedido. Se conserva el resto, necesario para la venta | `orders-service` | — | Purga periódica (RET-08). |

## 7.12 Casos de validación

Cada caso se ejecuta contra el backend implementado en el Módulo 10. La columna de resultado se completa con la salida real de esa ejecución (estado HTTP y registro), no con lo esperado.

| ID | Caso | Entrada | Identidad | Resultado esperado | Componente que verifica | Resultado registrado |
| --- | --- | --- | --- | --- | --- | --- |
| T-DAT-01 | Acceso anónimo al catálogo | `GET /api/v1/products` sin `Authorization` | Visitante | 200 con `ProductoPublicoDTO`. Sin `stock` ni productos retirados. | API Gateway (ruta anónima y límite de tasa). `inventory-service` (C12) | OK. 200, 12 productos |
| T-DAT-02 | Operación protegida sin sesión válida | `GET /api/v1/orders` (a) sin token, (b) con un token inventado, (c) con un token vencido o cerrado en S02 | Ninguna | 401 con `{ error: { codigo, mensaje, requestId } }` en los tres casos. No llega a orders. | API Gateway (I01) | OK. [401, 401, 401] |
| T-DAT-03 | Administración desde un rol sin permiso | `POST /api/v1/products` y `GET /api/v1/admin/users` con la sesión de un `cliente`. `GET /api/v1/admin/users` también con `cajero_virtual` | `cliente` y `cajero_virtual` | 403 en todos. Sin cambios en la base. | API Gateway (política de roles). `inventory-service` y `auth-service` (segunda barrera, probada llamando directamente con el secreto del gateway y el rol `cliente`) | OK. gateway=[403, 403, 403], directo=403 |
| T-DAT-04 | Consulta de un pedido ajeno | El cliente B pide `GET /api/v1/orders/{id}`, `GET /api/v1/orders/{id}/receipt` y `POST /api/v1/orders/{id}/payments` sobre un pedido del cliente A | `cliente` B | 404 idéntico al de un pedido inexistente, sin dato alguno de A. | `orders-service` y `payments-service` (C1) | OK. [404, 404, 404] |
| T-DAT-05 | Acceso directo al backend sin identidad autorizada | (a) Conectarse desde el host al puerto de `orders-service`. (b) Desde otro contenedor, `GET /orders/{id}` sin `X-Gateway-Secret`. (c) Con el secreto de `gateway-to-clients`. (d) Con el secreto correcto pero sin `X-Authenticated-User`. (e) Igual para `graphql-gateway` | Ninguna | (a) Conexión rechazada, no hay puerto publicado (Docker Compose: CMP-NET-04 probó 12 puertos y Compose no abrió ninguno, 10.9.11.1). (b), (c) y (d) 401 en Compose (CMP-RED-01, 10.9.11.2) y en modo local (T-DAT-05). Un par de secretos de otro sistema recibe 403 (CMP-RED-01). | Red de Docker. `InternalAccessGuard` de cada sistema | OK. [401, 401, 401, 401, 401] (modo local). CMP-RED-01: sin secreto=401, secreto de otro destino=401, secreto propio sin identidad=401, par de otro sistema=403 (Compose). |
| T-DAT-06 | Confirmar un pago con datos alterados del frontend | (a) `POST /api/v1/payments/webhook` con `estado: aprobado` y sin firma. (b) Con firma válida y marca de tiempo de hace más de 5 minutos. (c) Con firma válida y `monto` distinto del total. (d) El mismo `eventoId` dos veces. (e) Un cliente envía `PATCH /api/v1/admin/orders/{id}/status` con `estado: pagado`. (f) Un cliente envía `POST /api/v1/orders` con `total` y `estado: pagado`, y `X-Authenticated-Roles: administrador` | Plataforma de pago o `cliente` | (a) y (b) 401, el pedido sigue en `pendiente_pago`. (c) Pago `observado`, pedido sin cambios. (d) Un solo `pagado`, una sola venta. (e) 403. (f) Pedido creado con el precio del catálogo y `pendiente_pago`. El rol se toma del token. | `payments-service` (C8). `orders-service` (I12 y C7). API Gateway (descarte de cabeceras) | OK. (c) webhook=200, pago=observado, pedido=pendiente_pago; (d) segundo aviso=200, ventas=1; (e) 403; (f) 201 total=8990 (catalogo=8990) estado=pendiente_pago |
| T-DAT-07 | La contraseña y su hash no salen | Iniciar sesión, registrar y consultar el perfil. Revisar las respuestas, la base y los registros de todos los contenedores | `cliente` | La contraseña no aparece en ninguna respuesta ni registro. En la base solo hay un hash bcrypt. | `auth-service`. Revisión con `grep` | OK. hash=$2b$12$... (bcrypt), campos=['_id', 'correo', 'creadoEn', 'estado', 'hash', 'id', 'nombre', 'rol'] |
| T-DAT-08 | Sesión revocada | Cerrar sesión (S02) y repetir `GET /api/v1/orders` con el mismo token. Lo mismo tras dar de baja la cuenta (S29 o S33) y tras cambiar el rol (S32) | `cliente`, `administrador` | 401 de inmediato. | `auth-service` y API Gateway (I01) | OK. antes=200; logout=401, baja cliente=401, cambio rol=401, baja usuario=401 |
| T-DAT-09 | Registros sin secretos ni datos personales | Ejecutar el flujo completo (registro, pedido, pago, boleta, despacho) y buscar en los registros de todos los contenedores los valores usados: contraseña, token, correo, RUN, teléfono, dirección, secretos | — | Cero coincidencias. | `AccessLogger` del gateway y de cada sistema. Revisión con `grep` | OK. 15 valores buscados en 26 archivos; coincidencias=0 |
| T-DAT-10 | Campos mínimos por rol | `GET /api/v1/admin/orders`, `GET /api/v1/admin/reports/sales` y `GET /api/v1/admin/dispatch-orders` | `cajero_virtual`, `dueno`, `encargado_despachos` | S16 sin RUN, correo ni teléfono. S34 sin datos de clientes individuales. S18 sin precios, RUN ni correo. | `orders-service`, `payments-service` y `dispatch-service` (C3) | OK. S16=True, S34=True, S18=True |
| T-DAT-11 | Sin secretos en el frontend | Buscar en el código HTML, JavaScript y CSS, en las capturas y en los ejemplos del informe cadenas como `secret`, `api_key`, `Bearer ` seguido de un valor, y cualquier valor generado para Vault | — | Sin coincidencias. Los valores de ejemplo son ficticios. | Revisión con `grep` sobre el repositorio y el informe | OK. archivos revisados; coincidencias=0 |
| T-DAT-12 | Token vencido | Esperar los 900 s (en la prueba, con una vigencia corta configurable) y llamar | `cliente` | 401. | `auth-service` (I01) | OK. antes=200, despues=401 TOKEN_INVALIDO |
| T-DAT-13 | Fuerza bruta de contraseñas | Seis inicios de sesión fallidos seguidos para la misma cuenta | Visitante | Cinco intentos fallidos devuelven 401 y el sexto, 429 con `Retry-After` de 15 minutos. La respuesta no revela si el correo existe. | `auth-service` (C9) y API Gateway (`RL-SENSIBLE`) | OK. [401, 401, 401, 401, 401, 429], Retry-After=900 |

Los seis casos que pide la guía son T-DAT-01 a T-DAT-06. Los demás cubren contraseñas, sesiones, registros, campos mínimos y secretos en el frontend.

## 7.13 Riesgos aceptados

| Riesgo | Por qué se acepta | Medida |
| --- | --- | --- |
| Token en `sessionStorage` expuesto a XSS | El token vence en 15 minutos y se revoca. Guardarlo solo en memoria obligaría a iniciar sesión en cada recarga. | Escape de salida y CSP que limita adónde puede enviar datos un script inyectado (con `unsafe-inline`, no impide su ejecución). El riesgo queda declarado en 10.11. |
| S03 revela si un correo ya está registrado (409) | Es necesario para que el usuario sepa qué hacer | `RL-SENSIBLE` de 10 por minuto por IP. S01 no revela si el correo existe. |
| Datos personales sin cifrado por campo | Ver 7.7 | Acceso limitado a la base del sistema dueño, retención corta y anonimización. |
| MongoDB y ActiveMQ sin TLS en la red privada | Ver M6 6.12 | Red aislada, usuarios de mínimo permiso y consola sin publicar. |
| Sin token de renovación | Simplifica el diseño | Se documenta el efecto en la página de pago (7.10). |

## 7.14 Control antes de entregar

| Pregunta | Respuesta |
| --- | --- |
| ¿Existe algún secreto en JavaScript, HTML, capturas o ejemplos? | No. El navegador solo guarda el token del usuario y el carrito. Los ejemplos del informe usan valores ficticios y el caso T-DAT-11 lo comprueba en el repositorio y el informe. |
| ¿Los datos retornados son los mínimos necesarios? | Sí. 7.5 lista por servicio lo que sale y lo que queda dentro, y T-DAT-10 lo comprueba por rol. |
| ¿La propuesta protege información del cliente aunque la pantalla sea accesible por Internet? | Sí. Cada regla se aplica en el backend (7.6) y el navegador no tiene secretos. Ocultar un botón no cambia lo que el servidor permite. |
