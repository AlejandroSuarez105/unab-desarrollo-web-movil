# Evaluación Unidad 2 — Backend seguro completo
## Pizzería La Fornace (derivado del Caso 19)

---

# Módulo 9 — Analítica y comunicación gRPC cuando corresponden

Este módulo decide con una **proyección** de la carga si hacen falta un servicio de analítica y comunicación gRPC. La decisión es que **no**, y se compromete a demostrar con una prueba de carga reproducible que la alternativa implementada cumple los objetivos. Las mediciones se registran en el Módulo 10: la sección 9.9 queda con la tabla vacía hasta entonces y no contiene valores supuestos.

## 9.1 Cumplimiento de los pasos a seguir de la guía

| Paso de la guía | Dónde está |
| --- | --- |
| 1. Caracterizar volumen, concurrencia, tamaño, frecuencia, latencia y streaming, y declarar si es proyección o medición. | 9.2 (proyección). |
| 2. Decidir si hay analítica y gRPC, con un ADR de contexto, alternativas, elección y consecuencias. | 9.3 a 9.6. |
| 3. Si hay analítica: origen de datos, actualización, retraso, agregaciones, permisos y datos personales. | No aplica. 9.4 lo fundamenta y 9.7 define la alternativa implementada. |
| 4. Si hay gRPC: contratos, autenticación, deadlines y errores. | No aplica. 9.5 lo fundamenta. |
| 5. Si hay streaming: control de flujo, límites y recuperación. | No aplica. 9.6 lo fundamenta. Los fallos y desconexiones de lo que sí existe se prueban en 9.8. |
| 6. Prueba de carga con entorno, datos, concurrencia, duración, p95, throughput, errores y consumo. | Plan en 9.8 y resultados en 9.9. |
| Matriz de necesidades y ADR. | 9.3 y 9.4 a 9.6. |
| Justificar la ausencia de cada componente con los requisitos y la carga prevista. | 9.4 a 9.6. |

## 9.2 Caracterización de la carga

**Esto es una proyección, no una medición.** El Caso 19 describe un solo restaurante y no entrega volúmenes. Se declaran supuestos explícitos y se calcula a partir de ellos.

| ID | Supuesto | Valor | Origen |
| --- | --- | --- | --- |
| S1 | Pedidos por día | 80 en un día normal y 150 en viernes y sábado | Proyección del equipo. El Caso 19 no entrega volúmenes: describe un solo restaurante. |
| S2 | Concentración | 50 % de los pedidos del día en 2 horas | Proyección. Almuerzo o cena. |
| S3 | Ítems por pedido | 3 en promedio (máximo permitido: 30) | Proyección. El máximo es del Módulo 1. |
| S4 | Visitantes simultáneos del catálogo | 100 durante una promoción, con una consulta cada 10 s | Proyección. Es un escenario pesimista para un solo local. |
| S5 | Período máximo del reporte | 92 días | Dato del diseño (Módulo 1, C6). |
| S6 | Tamaño de una venta con sus líneas | 0.6 KB | Estimación por el tamaño de los contratos del Módulo 1. |

| Magnitud derivada | Cálculo | Resultado |
| --- | --- | --- |
| Pedidos por segundo en la hora punta | 150 × 0.5 ÷ (2 × 3600) | 0.0104 por segundo (unos 38 por hora) |
| Consultas de catálogo por segundo | 100 ÷ 10 | 10 por segundo |
| Ventas por año en el escenario pico | 150 × 365 | 54.750 |
| Ventas dentro de un reporte de 92 días | 150 × 92 | 13.800 ventas y 41.400 líneas |
| Tamaño de esos datos | 13.800 × 0.6 KB | unos 8 MB |

| ID | Necesidad | Volumen y frecuencia | Concurrencia | Tamaño de los mensajes | Carácter | Latencia objetivo | Streaming |
| --- | --- | --- | --- | --- | --- | --- | --- |
| N1 | Consultar el catálogo (S06) | 10 consultas por segundo en promoción | Hasta 100 visitantes | Respuesta de 2 a 20 KB (hasta 100 productos) | Frecuente y de solo lectura | p95 de 300 ms | No |
| N2 | Crear un pedido (S12) | 0.01 por segundo en la hora punta | Pocos simultáneos | Menos de 2 KB | Rara | p95 de 800 ms | No |
| N3 | Aviso de pago (S21) | Igual al de pedidos pagados | 1 a 2 simultáneos | Menos de 1 KB | Rara, con repeticiones posibles | p95 de 500 ms | No |
| N4 | Reporte de ventas (S34) | 1 a 2 consultas por día. Hasta 13.800 ventas por consulta | 1 a 2 usuarios (dueño y administrador) | Respuesta de menos de 5 KB | Baja | p95 de 1,5 s con los datos de 92 días | No |
| N5 | Orden de despacho a cocina (I14) | 0.01 por segundo | Un consumidor | Cerca de 1 KB por mensaje | Rara, y debe ser durable | Llega en menos de 5 s si el broker está activo | No. Es asíncrono |
| N6 | Agregación GraphQL (R36) | Una consulta por detalle de pedido o por cuenta | Pocos simultáneos | Hasta 15 KB con 30 ítems | Baja | p95 de 600 ms | No |
| N7 | Llamadas entre sistemas (I01, I03 a I13) | Como máximo el de pedidos más el de autenticación: una por solicitud autenticada | Igual que la concurrencia de cada flujo | Menos de 2 KB | Una por solicitud | Plazos de 3 s y 5 s (M3) | No |
| N8 | Estado del pedido en el navegador | Una consulta cada 15 s por pantalla abierta | Hasta 100 pantallas | Menos de 2 KB | Baja | El cambio se ve en 15 s | No hace falta |

Lectura de la tabla: lo más exigente es el catálogo con 10 consultas por segundo y el reporte de 92 días con 13.800 ventas (unos 8 MB). Un pedido nuevo llega cada 96 segundos en la hora punta. Los objetivos de latencia son decisiones del equipo, y la prueba de 9.8 los compara con lo que se mida.

## 9.3 Matriz de necesidades

| Necesidad | ¿Procesamiento intensivo? | ¿Streaming? | ¿Justifica gRPC o un servicio aparte? | Mecanismo elegido |
| --- | --- | --- | --- | --- |
| N1 a N3, N6 | No. Operaciones por solicitud con pocos datos | No | No: mensajes pequeños, tasa baja | REST (S06, S12, S21) y GraphQL (R36) |
| N4 Reporte de ventas | No: unos 14 mil documentos por consulta. Una agregación de la base lo resuelve | No | No: un solo sistema (payments) lo calcula | Agregación de MongoDB dentro de `payments-service` (9.7) |
| N5 Orden de despacho | No | No: un mensaje por pedido, sin flujo continuo | No: ya está resuelto con una cola durable y reintentos | ActiveMQ (I14) |
| N7 Entre sistemas | No | No | No: ver ADR-02 | REST con JSON y plazos (M3) |
| N8 Estado en el navegador | No | No: no hay eventos continuos que justifiquen mantener una conexión | No: gRPC no lo habla el navegador | Consulta periódica de S14 (ADR-03) |

## 9.4 ADR-01 — No crear un servicio de analítica

| | |
| --- | --- |
| **Estado** | Aceptado. Se revisa con las condiciones de 9.10. |
| **Contexto** | El caso pide un reporte de ventas por período para el dueño (RF9, S34). Es un solo local, con a lo sumo 13.800 ventas por consulta en 92 días (proyección 9.2). El reporte tiene totales, ventas por día y los diez productos más vendidos, sin datos de clientes individuales (M7, C3). |
| **Alternativas** | **A.** Servicio de analítica privado con copia de las ventas y actualización periódica. **B.** Colección de totales por día mantenida al registrar cada venta. **C.** Agregación de MongoDB bajo demanda, dentro de `payments-service`, con un índice por fecha. **D.** Una solución de big data. |
| **Decisión** | **C.** `payments-service` calcula el reporte con sus propios datos (9.7). Ajuste hecho en la implementación (Módulo 10): el reporte lee resúmenes diarios que el mismo servicio mantiene a partir de las ventas (parte de la opción B, dentro de `payments_db`), no recorre las ventas en cada consulta. |
| **Por qué** | Las ventas ya están en `payments_db`, que es su autoridad (M3 3.4). La carga proyectada es de unos 8 MB por consulta y una o dos consultas por día. La opción A agrega retraso, otra base y una copia de datos de ventas sin que el volumen lo pida. La B agrega una segunda fuente de verdad que mantener. La D es desproporcionada para este volumen. |
| **Consecuencias** | Menos piezas que operar y ningún dato personal fuera de payments. El costo del reporte crece con el período, por eso el rango está limitado a 92 días (C6). La consulta no es en tiempo real para períodos muy largos: no se ofrecen. La medición C5 y C6 (9.8) verifica que la decisión alcanza. Resultado en el Módulo 10: con el reporte leyendo los resúmenes diarios, C5 (13.800 ventas) y C6 (138.000) cumplen con holgura sobre MongoDB 7 (p95 de 40,5 ms y 39,3 ms frente a objetivos de 1.500 y 5.000 ms). No se midió la agregación directa sobre las ventas en esa ejecución, así que no se afirma cuánto habría costado; el resumen diario se mantiene porque su costo no crece con el volumen de ventas. La fuente de verdad sigue siendo `ventas`; los resúmenes son derivados y se pueden reconstruir. |
| **Qué se pierde** | Análisis históricos de más de 92 días y comparaciones entre locales. No están en el caso. |
| **Permisos y datos personales** | S34 es solo para `dueno` y `administrador`, y no devuelve nombre, correo ni cuenta de ningún cliente (M4, M7 7.5). |

## 9.5 ADR-02 — No usar gRPC entre sistemas

| | |
| --- | --- |
| **Estado** | Aceptado. Se revisa con las condiciones de 9.10. |
| **Contexto** | Los sistemas se llaman entre sí en I01 y de I03 a I13 con mensajes de menos de 2 KB y no más de una llamada por solicitud autenticada (9.2, N7). La frecuencia total es de 0.01 pedidos por segundo en la hora punta. Ya existen plazos por llamada (3 s y 5 s), reintento controlado e idempotencia (M3). |
| **Alternativas** | **A.** gRPC unary para todas las llamadas entre sistemas. **B.** gRPC solo para la reserva de stock (I08 a I10). **C.** Mantener REST con JSON entre sistemas. |
| **Decisión** | **C.** |
| **Por qué** | gRPC aporta contratos tipados y modos de streaming, pero con mensajes pequeños y una tasa baja el costo de serializar JSON no se nota y no hay nada que medir. Cambiar a gRPC obliga a mantener archivos `.proto`, generar código en Python y en Node, definir TLS, autenticación y autorización por método, y probarlo, para resolver un problema que el caso no tiene. Los contratos ya están definidos y probados como REST (Módulos 1 y 3). El stack del curso es REST con FastAPI. |
| **Consecuencias** | Una sola tecnología de comunicación síncrona y la misma identidad de servicio (M6). No hay tipado generado por `.proto`: se compensa con validación de esquemas en cada sistema. |
| **Qué cambiaría la decisión** | Llamadas muy frecuentes o mensajes grandes entre dos sistemas, o una operación con flujo continuo (9.10). |

## 9.6 ADR-03 — Despacho por cola y sin streaming hacia el navegador

| | |
| --- | --- |
| **Estado** | Aceptado. Se revisa con las condiciones de 9.10. |
| **Contexto** | La cocina debe recibir las órdenes en el orden de llegada (RF13). El Módulo 3 ya envía cada orden por `/queue/cola_pedidos` de ActiveMQ (I14). El frontend necesita ver el cambio de estado de un pedido, sin que el caso pida actualización en vivo. La guía menciona como ejemplo un monitoreo de despacho con streaming de servidor. |
| **Alternativas** | **A.** gRPC con streaming de servidor desde dispatch hacia un consumidor privado. **B.** Mantener la cola ActiveMQ y consultar el estado con S14 (y la cola de despacho con S18) cada 15 s. **C.** SSE o WebSocket desde el API Gateway hacia el navegador. |
| **Decisión** | **B.** |
| **Por qué** | Hay un mensaje por pedido (0.01 por segundo), no un flujo continuo. Una cola durable ya tolera caídas del consumidor y del broker, que un stream gRPC hay que reconstruir: puntos de reanudación, deduplicación y control de flujo. gRPC tampoco lo habla el navegador sin un adaptador. Consultar cada 15 s con 100 pantallas abiertas son unas 7 consultas por segundo, dentro de lo que el sistema soporta (C1). |
| **Consecuencias** | El cambio de estado se ve con hasta 15 s de retraso. El límite por cuenta (`RL-USUARIO`, 120 por minuto) cubre la consulta periódica (4 por minuto). |
| **Recuperación sin duplicar efectos** | Dispatch ignora una orden repetida (por `pedidoId`) y reconecta tras una desconexión. Orders republica las órdenes pendientes cada 30 s (M3). Se prueba en F2 y F3 (9.8). |

## 9.7 Alternativa implementada: el reporte de ventas en `payments-service`

| Elemento | Decisión |
| --- | --- |
| Almacenamiento | Colección `ventas` en `payments_db`. Cada venta lleva sus líneas embebidas (`lineas[]`) para no unir colecciones al agregar. |
| Índice | `ventas.fecha` ascendente. Los resúmenes tienen índice único por `fecha` (`resumen_dia`) y por `fecha` y `productoId` (`resumen_producto`). |
| Agregación | Cada venta se suma una vez a `resumen_dia` (ventas y total por día) y a `resumen_producto` (unidades por día y producto) con un contador `enResumen` en la venta. Una tarea periódica de `payments-service` aplica lo pendiente. La consulta lee a lo más 92 documentos de `resumen_dia`, suma `totalVentas` y `cantidadVentas`, y ordena los productos por unidades para devolver los diez más vendidos. No usa `$facet` ni recorre las ventas. |
| Límites | Rango de máximo 92 días y `desde` menor o igual que `hasta` (C6). El cuerpo de la respuesta no lleva datos de clientes. |
| Semántica | `totalVentas` es lo recaudado en la caja virtual. No descuenta reembolsos pendientes: la venta de un pedido anulado después de pagar sigue contando (M1 S34 y M3 3.11). |
| Permisos | `dueno` y `administrador` (M4). Las filas por cliente nunca salen de payments. |
| Datos de la prueba | Un script de carga genera ventas ficticias con una semilla fija en `payments_db` de una instancia de prueba (9.8). |

## 9.8 Plan de la prueba de carga

Es reproducible: mismo script, mismas semillas y mismos límites de recursos. Se ejecuta en el Módulo 10 contra el sistema completo y **lo medido reemplaza** a la proyección de 9.2.

| Tema | Definición |
| --- | --- |
| Tipo de resultado | **Medición** sobre el sistema implementado. Las cifras de entrada son **proyección** (9.2). |
| Entorno | Todos los componentes en Docker Compose en una sola máquina del equipo. Se registran el procesador, la memoria, el sistema operativo y las versiones. Límites por contenedor: 1 CPU y 512 MB. |
| Datos | Ficticios, con semilla 42. Catálogo de 40 productos. Ventas generadas por script directamente en `payments_db` de la instancia de prueba, con el usuario administrador de la inicialización, y nunca por la API. |
| Herramienta | Un script de Python con `asyncio` y `httpx` (las bibliotecas del curso). Genera la carga, mide cada solicitud y escribe un CSV. Sin herramientas adicionales. |
| Etapas | Calentamiento de 15 s que no se cuenta, el nivel de carga durante el tiempo indicado, y enfriamiento. Cada escenario se repite 3 veces y se informa la mediana de las repeticiones. |
| Métricas | Concurrencia, duración, solicitudes, latencia p50, p95 y p99, solicitudes por segundo (throughput), errores por código, y CPU y memoria de cada contenedor muestreados cada 2 s con `docker stats`. |
| Criterio | Cumple si todas las métricas de 9.2 y de la tabla están dentro del objetivo en las 3 repeticiones. Si no, se informa el valor medido y se decide si se corrige o se revisa el ADR. |
| Límite de recursos | Ningún contenedor supera el 80 % de su memoria ni sostiene más del 90 % de su CPU durante el nivel objetivo. |
| Cómo se ejecuta | `carga/` con instrucciones de arranque, generación de datos y ejecución (Módulo 10). |

### Escenarios de carga

| ID | Escenario | Carga | Objetivo | Margen sobre la proyección |
| --- | --- | --- | --- | --- |
| C1 | Catálogo (S06) | Subir de 10 a 50 y a 100 usuarios simultáneos, 60 s cada nivel, consulta sin sesión | p95 de 300 ms a 50 por segundo. Errores menores al 1 % | 5 veces la proyección |
| C2 | Crear pedido (S12) | 2 por segundo durante 120 s y una ráfaga de 10 simultáneos | p95 de 800 ms. Errores menores al 1 % | 200 veces la proyección |
| C3 | Sin sobreventa | 30 pedidos simultáneos de un producto con stock 10 | Exactamente 10 pedidos creados, 20 respuestas 409 y stock final 0 sin valores negativos | Corrección, no rendimiento |
| C4 | Aviso de pago (S21) | 5 por segundo durante 60 s, con 20 % de avisos repetidos | p95 de 500 ms. Una sola venta por `eventoId` | 500 veces la proyección |
| C5 | Reporte de ventas (S34), 92 días | 13.800 ventas, 5 consultas simultáneas, 60 s | p95 de 1,5 s. Errores menores al 1 % | Escenario pico real |
| C6 | Reporte de ventas (S34), 10 veces el pico | 138.000 ventas, 5 consultas simultáneas, 60 s | p95 de 5 s. Sin superar el límite de memoria | Margen de crecimiento |
| C7 | Detalle por GraphQL (R36) | 10 por segundo durante 60 s con pedidos de 2 y de 30 ítems | p95 de 600 ms. Una llamada a inventory por consulta | Verifica también el batching |
| C8 | Comparación REST y GraphQL | El detalle de un pedido de 2 ítems por S14 y S06, frente a una consulta `resumenPedido` | Se informa la diferencia medida de latencia p95 y de llamadas. No hay objetivo | No se afirma una mejora sin medirla |
| C9 | Despacho (I14) | Ráfaga de 200 órdenes publicadas en 10 s | Las 200 llegan a dispatch en el orden de llegada, sin pérdida ni duplicados, y en menos de 30 s | Margen sobre la proyección |

### Fallos y desconexiones

| ID | Fallo provocado | Comportamiento esperado | Qué se prueba |
| --- | --- | --- | --- |
| F1 | Inventory detenido durante C2 | S12 responde 503 de forma controlada, sin pedidos a medias. Al reiniciar, vuelve a responder 201 en menos de 30 s. | Inventory caído (M3 3.11) |
| F2 | ActiveMQ detenido durante un pago y reiniciado | El pedido queda `pagado` y `despachoPublicado` en falso. En menos de 30 s tras reiniciar el broker, la orden llega a dispatch una sola vez. | Broker caído y desconexión del consumidor |
| F3 | Dispatch reiniciado con mensajes pendientes | Reconecta y consume lo pendiente sin duplicar órdenes. | Desconexión del consumidor |
| F4 | Orders lento (más de 5 s) en C4 | El aviso se registra, el pago queda `aprobado` con `confirmadoEnPedidos` en falso y se repite I12. El pedido pasa a `pagado` al normalizarse. | Dependencia lenta |
| F5 | Vault detenido con los sistemas en ejecución | Los sistemas siguen con sus secretos. El API Gateway sigue 15 minutos y luego responde 503 (M6 6.10). | Gestor de secretos caído |
| F6 | Auth detenido durante C1 y C4 | El catálogo y el aviso de pago siguen respondiendo. Las rutas con token responden 503. | Autenticación caída |
| F7 | Proveedor de pago o de correo sin respuesta | S20 responde 502 o 503 sin guardar un pago pendiente. La boleta queda con `correoEnviado` en falso y se reintenta cada 5 min. | Dependencia externa caída (adaptador de prueba) |

## 9.9 Resultados medidos

Salida real de `carga/carga.py` y `carga/fallos.py`, ejecutados en el Módulo 10 en Windows, en modo local sobre MongoDB 7.0.45, Vault 1.18.5 y ActiveMQ 6.2.0, a la escala descrita allí (10.6 y 10.11). Duraciones al 25 % del plan, sin límite de recursos por proceso. CPU y memoria son el máximo entre los procesos del sistema medidos. La CPU se cuenta por núcleo (como la entrega `psutil`): 100 % es un núcleo completo, así que un proceso con varios hilos puede pasar de 100 %. El detalle por proceso, los percentiles p50 y p99 y las variantes de C1 con 10 y 100 usuarios están en 10.9.9.

| ID | Escenario | Objetivo | Concurrencia y duración | p95 | Throughput | Errores 5xx | CPU máx. | Memoria máx. | ¿Cumple? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | Catálogo (S06) | p95 de 300 ms a 50 por segundo. Errores menores al 1 % | 50 usuarios, 16.2 s | 203.8 ms | 40.1 por s | 0 (0.0 %) | 46 % | 199 MB | Sí |
| C2 | Crear pedido (S12) | p95 de 800 ms. Errores menores al 1 % | 2 por segundo, 30.3 s, más ráfaga de 10 | 154.5 ms | 2.0 por s | 0 (0.0 %) | 12 % | 199 MB | Sí |
| C3 | Sin sobreventa | 10 pedidos creados, 20 respuestas 409 y stock final 0 | 30 simultáneas | 267.4 ms | 104.3 por s | 0 | — | — | Sí (creados 10, 409: 20, stock final 0) |
| C4 | Aviso de pago (S21) | p95 de 500 ms. Una sola venta por `eventoId` | 5 por segundo con 20 % repetidos, 15.2 s | 305.5 ms | 6.0 por s | 0 (0.0 %) | 26 % | 204 MB | Sí |
| C5 | Reporte de ventas (S34), 92 días | p95 de 1,5 s. Errores menores al 1 % | 5 simultáneas, 15.1 s, 13.800 ventas | 40.5 ms | 135.5 por s | 0 (0.0 %) | 104 % | 202 MB | Sí |
| C6 | Reporte de ventas (S34), 10 veces el pico | p95 de 5 s. Sin superar el límite de memoria | 5 simultáneas, 15.1 s, 138.000 ventas | 39.3 ms | 135.8 por s | 0 (0.0 %) | 107 % | 329 MB | Sí |
| C7 | Detalle por GraphQL (R36) | p95 de 600 ms. Una llamada a inventory por consulta | 10 por segundo, 16.3 s | 20.3 ms | 9.2 por s | 0 (0.0 %) | 15 % | 329 MB | Sí |
| C8 | Comparación REST y GraphQL | Se informa la diferencia | 100 repeticiones | REST 22.7 ms; GraphQL 19.3 ms | — | 0 | — | — | Sí (diferencia -3.4 ms; llamadas del navegador 2 frente a 1) |
| C9 | Despacho (I14) | 200 en orden, sin pérdida ni duplicados, en menos de 30 s | 200 mensajes | — | — | — | — | — | Sí (recibidas 200, última a los 12.6 s) |

| ID | Fallo | Resultado observado | ¿Cumple? |
| --- | --- | --- | --- |
| F1 | Inventory detenido durante C2 | {"detenido_en_s": 5.8, "reiniciado_en_s": 20.9, "respuestas_durante_la_caida": [[503, "INVENTARIO_NO_DISPONIBLE"]], "pedidos_sin_reserva": 0, "segundos_hasta_el_primer_201": 0.1} | Sí |
| F2 | ActiveMQ detenido durante un pago y reiniciado | {"estado_con_broker_caido": "pagado", "despachoPublicado_con_broker_caido": false, "segundos_tras_reiniciar_hasta_dispatch": 1.0, "ordenes_en_dispatch": 1, "despachoPublicado_final": true, "objetivo_del_plan_s": 30} | Sí |
| F3 | Dispatch reiniciado con mensajes pendientes | {"ordenes_antes_del_reinicio": 0, "ordenes_despues": 20, "duplicadas": 0, "segundos_hasta_consumir": 0.0} | Sí |
| F4 | Orders lento (más de 5 s) en C4 | {"respuesta_del_aviso": 200, "pago_durante_la_demora": "aprobado", "confirmadoEnPedidos_durante_la_demora": false, "segundos_hasta_pagado_tras_reanudar_orders": 0.0} | Sí |
| F5 | Vault detenido con los sistemas en ejecución | {"antes_de_la_ventana": [200, 200], "dentro_de_la_ventana": [200], "despues_de_la_ventana": 503, "codigo": "SERVICIO_NO_DISPONIBLE", "catalogo_publico_despues": 503, "ventana_prueba_s": 25, "ventana_plan_s": 900} | Sí |
| F6 | Auth detenido durante C1 y C4 | {"catalogo": 200, "aviso_de_pago": 200, "ruta_con_token": 503, "codigo": "AUTENTICACION_NO_DISPONIBLE", "pedido_pagado_despues": true} | Sí |
| F7 | Proveedor de pago o de correo sin respuesta | {"S20_con_pasarela_caida": 503, "codigo": "PASARELA_NO_DISPONIBLE", "pagos_guardados": 0, "correoEnviado_con_correo_caido": false, "segundos_hasta_reintento_exitoso": 0.0, "intervalo_de_reintento_de_la_prueba_s": 10, "intervalo_del_plan_s": 300} | Sí |

Diferencias con el plan de 9.8 (ver 10.11): duraciones al 25 %, sin límite de 1 CPU y 512 MB por proceso, F5 con ventana de 25 s en lugar de 15 minutos y F7 con reintento de correo cada 10 s en lugar de 300 s. En C1 se corrió también con 10 y 100 usuarios (10.9.9).

## 9.10 Cuándo se revisan las decisiones

| Condición | Qué se haría |
| --- | --- |
| El reporte de 92 días supera 1,5 s de p95 con los datos del pico, o 5 s con 10 veces el pico | Ya aplicado en el Módulo 10 (resúmenes diarios en payments). Siguiente paso: mover la lectura a una réplica o a un servicio de analítica. Si no alcanza, un servicio de analítica privado con la actualización definida (ADR-01). |
| El dueño pide comparar años, varios locales o análisis más allá de 92 días | Reabrir ADR-01: un servicio de analítica separado de las transacciones, con su origen de datos, retraso aceptado y permisos. |
| Aparecen más de 100 llamadas por segundo entre dos sistemas, mensajes de más de 100 KB, o una operación larga | Evaluar gRPC unary para ese camino y, para la operación larga, un trabajo asíncrono con identificador. |
| La cocina o los repartidores necesitan ver el estado en vivo | Evaluar eventos hacia el navegador (SSE o WebSocket) con un punto de adaptación en el API Gateway, sin exponer gRPC interno. |
| El catálogo supera su objetivo con 50 consultas por segundo | Caché de respuesta en inventory o réplica de lectura. No es una razón para crear un servicio nuevo. |

## 9.11 Control antes de avanzar

| Pregunta | Respuesta |
| --- | --- |
| ¿La decisión responde a una necesidad medida o proyectada de forma explícita? | Sí. 9.2 declara que es una proyección, con los supuestos y los cálculos. Las mediciones reales se registran en 9.9. |
| ¿Están implementados los componentes que la propuesta declara necesarios? | Se declaran necesarios el backend, el GraphQL Gateway y la agregación del reporte en payments (9.7). Analítica y gRPC se declaran no necesarios, con la ausencia justificada en los ADR. Su implementación se entrega en el Módulo 10. |
| ¿Las pruebas muestran cómo se comportan ante carga, fallos y desconexiones? | Están definidas en 9.8 (C1 a C9 y F1 a F7). Sus resultados reales están en 9.9 y en 10.9.9 y 10.9.10. |
