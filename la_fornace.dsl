workspace "Pizzeria La Fornace" "Arquitectura Backend Seguro C4 - Pizzería La Fornace (Maipú)" {

    !identifiers hierarchical

    model {
        // Actores del sistema
        visitante = person "Visitante" "Persona anónima que consulta la carta y combos de pizzas."
        cliente = person "Cliente" "Cliente registrado que realiza pedidos, paga y consulta sus boletas."
        cajero = person "Cajero Virtual" "Personal de caja que controla ventas web y boletas."
        despachador = person "Encargado de Despacho" "Personal que imprime las órdenes de despacho en orden de llegada."
        dueno = person "Dueño" "Dueño del restaurante que genera reportes de ventas y administra productos."
        admin = person "Administrador" "Administrador del sistema que gestiona usuarios, clientes y catálogo."

        // Sistemas externos
        pasarelaPago = softwareSystem "Plataforma de Pago (Servipag/Banco)" "Sistema externo que procesa cobros y notifica avisos firmados HMAC-SHA256. En la entrega se usa un adaptador de prueba (pasarela_prueba) con el mismo contrato, porque Servipag no tiene un entorno de prueba público." {
            tags "SistemaExterno"
        }
        proveedorCorreo = softwareSystem "Proveedor de Correo" "Servicio externo para envío de enlaces de verificación y boletas digitales. En la entrega se usa un adaptador de prueba (correo_prueba) con el mismo contrato." {
            tags "SistemaExterno"
        }

        sistema = softwareSystem "Pizzería La Fornace - Backend Seguro" "Plataforma de ventas en línea, gestión de menú, pedidos, pagos y despacho asíncrono." {
            tags "SistemaEvaluado"

            frontend = container "Frontend Responsivo" "Interfaz web HTML5, Bootstrap 5.3 y JavaScript." "Aplicación Web (HTML/JS) (puerto 8080)" {
                tags "Frontend"
            }

            apiGateway = container "API Gateway" "Punto de entrada único al backend; valida el Bearer token, aplica la política de cada ruta (RBAC) y reenvía solo a destinos declarados." "FastAPI / Python 3.13 (puerto 8443 TLS)" {
                tags "Gateway"

                httpEntry = component "Adaptador HTTP" "Recibe solicitudes HTTPS de la web y genera respuestas estandarizadas." "Módulo de Entrada" {
                    tags "EntradaC3"
                }
                identityFilter = component "Filtro de Acceso ZTA" "Introspecta el Bearer token con Auth Service y valida la matriz RBAC por rol." "Módulo de Seguridad" {
                    tags "ControlC3"
                }
                routeDispatcher = component "Despachador de Rutas" "Reenvía con X-Gateway-Secret e inyecta la identidad verificada en cabeceras X-Authenticated-*." "Módulo de Enrutamiento" {
                    tags "AplicacionC3"
                }
                errorMapper = component "Traductor de Errores" "Convierte fallos de red y excepciones en JSON estandarizados con requestId." "Módulo de Errores" {
                    tags "ErrorC3"
                }
            }

            authService = container "Auth Service" "Gestión de cuentas, hash bcrypt (costo 12), sesiones temporales (15 min) y tokens de verificación." "FastAPI / Python 3.13 (puerto 9101 en local, 8000 en Compose; TLS)" {
                tags "Seguridad"

                identityApi = component "API de Identidad" "Atiende login, logout, verificación de correo, creación de cuentas (/internal/accounts) e introspección (/internal/introspect)." "API Interna" {
                    tags "EntradaC3"
                }
                sessionManager = component "Gestor de Sesiones" "Controla vigencia, revocación y tokens temporales de 15 minutos." "Servicio de Identidad" {
                    tags "AplicacionC3"
                }
                credentialsVerifier = component "Verificador Bcrypt" "Valida contraseñas con sal propia y hash adaptativo bcrypt." "Módulo de Seguridad" {
                    tags "ControlC3"
                }
                identityRepo = component "Repositorio de Identidades" "Persiste cuentas, tokens y sesiones en auth_db." "Acceso a Datos" {
                    tags "PersistenciaC3"
                }
                secretsClient = component "Cliente Vault" "Obtiene de Vault los secretos de par (gateway-introspect, clients-to-auth, auth-to-notifications) y su usuario de MongoDB." "Adaptador Integración" {
                    tags "IntegracionC3"
                }
            }

            clientsService = container "clients-service" "Autoridad sobre datos personales (RUN, nombre, dirección, teléfono, nacimiento, sexo). Atiende el registro y crea la cuenta en auth-service." "FastAPI / Python 3.13 (puerto 9102 en local, 8000 en Compose; TLS)" {
                tags "Privado"
            }

            inventoryService = container "inventory-service" "Autoridad de catálogo (pizzas, combos), precios vigentes, disponible y stock." "FastAPI / Python 3.13 (puerto 9103 en local, 8000 en Compose; TLS)" {
                tags "Privado"
            }

            ordersService = container "orders-service" "Autoridad del estado del pedido (pendiente_pago, pagado, etc.), reservas de stock e idempotencia." "FastAPI / Python 3.13 (puerto 9104 en local, 8000 en Compose; TLS)" {
                tags "Privado"

                ordersApi = component "API de Pedidos" "Recibe peticiones de creación, consulta y anulación de pedidos." "API Interna" {
                    tags "EntradaC3"
                }
                accessPolicy = component "Política C1 (Propiedad)" "Valida que el pedido pertenece a la cuenta autenticada (cuentaId). Un pedido ajeno responde 404." "Regla de Autorización" {
                    tags "ControlC3"
                }
                idempotency = component "Control de Idempotencia" "Detecta peticiones duplicadas usando Idempotency-Key." "Regla de Negocio" {
                    tags "ControlC3"
                }
                orderWorkflow = component "Servicio de Pedidos" "Coordina el ciclo de vida del pedido, transiciones y vencimientos de 15 min." "Servicio de Aplicación" {
                    tags "AplicacionC3"
                }
                inventoryAdapter = component "Adaptador de Inventario" "Reserva y confirma stock en inventory-service (/internal/stock/reservations)." "Adaptador Privado" {
                    tags "IntegracionC3"
                }
                stompPublisher = component "Publicador STOMP ActiveMQ" "Publica órdenes pagadas en /queue/cola_pedidos para despacho." "Adaptador de Mensajería" {
                    tags "IntegracionC3"
                }
                ordersRepo = component "Repositorio de Pedidos" "Persiste pedidos, detalles e historial en orders_db." "Acceso a Datos" {
                    tags "PersistenciaC3"
                }
            }

            paymentsService = container "payments-service" "Gestión de cobros, verificación HMAC de avisos de pago, caja virtual, boletas y reportes." "FastAPI / Python 3.13 (puerto 9105 en local, 8000 en Compose; TLS)" {
                tags "Privado"
            }

            dispatchService = container "dispatch-service" "Consumidor STOMP de cola_pedidos; entrega las órdenes de despacho por orden de llegada para imprimirlas." "FastAPI / Python 3.13 (puerto 9106 en local, 8000 en Compose; TLS)" {
                tags "Privado"
            }

            notificationsService = container "notifications-service" "Aísla el proveedor de correo; envía boletas, verificaciones y recibe contacto." "FastAPI / Python 3.13 (puerto 9107 en local, 8000 en Compose; TLS)" {
                tags "Privado"
            }

            graphqlGateway = container "GraphQL Gateway" "Backend-For-Frontend (BFF) de solo lectura que agrega datos de orders, inventory y clients." "Node.js 22 / Apollo Server 5 (puerto 9108 en local, 8000 en Compose; TLS)" {
                tags "Gateway"

                graphqlEndpoint = component "Endpoint GraphQL" "Recibe consultas POST /api/v1/graphql." "Adaptador GraphQL" {
                    tags "EntradaC3"
                }
                queryValidator = component "Validador de Consultas" "Verifica complejidad (máx 600) y profundidad (máx 5)." "Validación GraphQL" {
                    tags "ControlC3"
                }
                fieldAccess = component "Field Policy" "Restringe acceso por campo según el rol del usuario." "Módulo de Autorización" {
                    tags "ControlC3"
                }
                resolvers = component "Resolvers (resumenPedido / miCuenta)" "Ejecuta resoluciones combinadas usando DataLoader para evitar N+1." "Resolvers GraphQL" {
                    tags "AplicacionC3"
                }
                serviceConnectors = component "Conectores HTTP" "Consulta APIs REST de lectura en orders, inventory y clients con X-Service-Id y X-Service-Secret." "Adaptadores Integración" {
                    tags "IntegracionC3"
                }
                responseComposer = component "Compositor de Respuestas" "Maneja errores parciales y formatea la respuesta JSON." "Módulo de Resultados" {
                    tags "ErrorC3"
                }
            }

            secretManager = container "HashiCorp Vault" "Almacenamiento seguro de secretos (API KV v2). Cada componente tiene un token propio de solo lectura, limitado a sus rutas." "HashiCorp Vault 1.18 (puerto 8200)" {
                tags "Seguridad"
            }

            activemqBroker = container "ActiveMQ Broker" "Broker de mensajería asíncrona STOMP para la cola de despacho de pedidos." "Apache ActiveMQ 6.2.0 (puerto 61613 STOMP)" {
                tags "Broker"
            }

            dbIdentity = container "auth_db" "Base de datos de cuentas, contraseñas hash bcrypt y sesiones activas." "MongoDB 7.0" {
                tags "BaseDatos"
            }
            dbClients = container "clients_db" "Base de datos de perfiles personales y domicilios de clientes." "MongoDB 7.0" {
                tags "BaseDatos"
            }
            dbInventory = container "inventory_db" "Base de datos de productos (12 ítems del menú), precios y movimientos de stock." "MongoDB 7.0" {
                tags "BaseDatos"
            }
            dbOrders = container "orders_db" "Base de datos de pedidos, ítems congelados, historial y claves de idempotencia." "MongoDB 7.0" {
                tags "BaseDatos"
            }
            dbPayments = container "payments_db" "Base de datos de pagos, avisos de pago, ventas de caja virtual y boletas." "MongoDB 7.0" {
                tags "BaseDatos"
            }
            dbDispatch = container "dispatch_db" "Base de datos de órdenes de despacho e historial de impresión." "MongoDB 7.0" {
                tags "BaseDatos"
            }
            dbNotifications = container "notifications_db" "Base de datos de registros de mensajería y mensajes de contacto." "MongoDB 7.0" {
                tags "BaseDatos"
            }
        }

        // Relaciones de contexto C1
        visitante -> sistema "Consulta carta y combos de pizza"
        cliente -> sistema "Realiza pedidos, paga y consulta sus boletas"
        cajero -> sistema "Controla caja virtual y consulta ventas"
        despachador -> sistema "Imprime las órdenes de despacho en orden de llegada"
        dueno -> sistema "Consulta reporte de ventas agregadas (92 días)"
        admin -> sistema "Administra usuarios, clientes y menú"
        sistema -> pasarelaPago "Procesa cobros y recibe avisos de pago" "HTTPS / Aviso HMAC"
        sistema -> proveedorCorreo "Envía correos con enlace y boleta digital" "HTTPS / API Key"

        // Relaciones de contenedores C2
        visitante -> sistema.frontend "Navega catálogo de pizzas y combos" "HTTP"
        cliente -> sistema.frontend "Arma carrito y realiza pedido" "HTTP"
        cajero -> sistema.frontend "Consulta ventas y boletas" "HTTP"
        despachador -> sistema.frontend "Gestiona la cola de despacho" "HTTP"
        dueno -> sistema.frontend "Consulta reporte de ventas" "HTTP"
        admin -> sistema.frontend "Administra productos y usuarios" "HTTP"

        sistema.frontend -> sistema.apiGateway "Solicitudes HTTPS/JSON con Authorization Bearer" "HTTPS/JSON"
        sistema.apiGateway -> sistema.authService "Introspección del token (/internal/introspect) con X-Service-Id y X-Service-Secret" "HTTPS/JSON"
        sistema.apiGateway -> sistema.clientsService "Enruta perfil y registro (/api/v1/clients, /api/v1/auth/register) con X-Gateway-Secret" "HTTPS/JSON"
        sistema.apiGateway -> sistema.inventoryService "Enruta catálogo público y administración (/api/v1/products) con X-Gateway-Secret" "HTTPS/JSON"
        sistema.apiGateway -> sistema.ordersService "Enruta creación y consulta de pedidos (/api/v1/orders) con X-Gateway-Secret" "HTTPS/JSON"
        sistema.apiGateway -> sistema.paymentsService "Enruta cobros, avisos de pago, boletas y reportes con X-Gateway-Secret" "HTTPS/JSON"
        sistema.apiGateway -> sistema.dispatchService "Enruta cola de despacho (/api/v1/admin/dispatch-orders) con X-Gateway-Secret" "HTTPS/JSON"
        sistema.apiGateway -> sistema.notificationsService "Enruta mensajes de contacto (/api/v1/contact-messages) con X-Gateway-Secret" "HTTPS/JSON"
        sistema.apiGateway -> sistema.graphqlGateway "Enruta consultas agregadas BFF (/api/v1/graphql) con X-Gateway-Secret" "HTTPS/JSON"

        sistema.clientsService -> sistema.authService "Crea la cuenta del cliente al registrarse (/internal/accounts) con X-Service-Secret" "HTTPS/JSON"
        sistema.ordersService -> sistema.clientsService "Consulta datos del cliente (/internal/clients/by-account) con X-Service-Secret" "HTTPS/JSON"
        sistema.ordersService -> sistema.inventoryService "Reserva y confirma stock (/internal/stock/reservations) con X-Service-Secret" "HTTPS/JSON"
        sistema.ordersService -> sistema.activemqBroker "Publica órdenes pagadas en /queue/cola_pedidos" "STOMP"

        sistema.paymentsService -> sistema.ordersService "Valida pedido pagable y confirma pago (/internal/orders/{id}/payable, /payment-confirmation) con X-Service-Secret" "HTTPS/JSON"
        sistema.paymentsService -> sistema.notificationsService "Solicita envío de boleta digital por correo (/internal/emails) con X-Service-Secret" "HTTPS/JSON"
        pasarelaPago -> sistema.apiGateway "Envía aviso de pago firmado HMAC-SHA256 (X-Signature, X-Timestamp)" "HTTPS/JSON"
        sistema.paymentsService -> pasarelaPago "Crea cobro inicial (POST /cobros con X-API-Key)" "HTTPS/JSON"
        cliente -> pasarelaPago "Realiza pago en la pasarela externa" "Web"
        sistema.paymentsService -> sistema.paymentsService "Verifica firma HMAC-SHA256 y previene duplicados"

        sistema.dispatchService -> sistema.activemqBroker "Consume órdenes de /queue/cola_pedidos" "STOMP"
        sistema.activemqBroker -> sistema.dispatchService "Entrega mensajes a cola de despacho (Listener)" "STOMP"
        sistema.authService -> sistema.notificationsService "Solicita envío de correo de activación (/internal/emails) con X-Service-Secret" "HTTPS/JSON"
        sistema.notificationsService -> proveedorCorreo "Envía correos a clientes" "HTTPS/API Key"

        // Respuestas de API Gateway hacia el Frontend
        sistema.dispatchService -> sistema.apiGateway "Devuelve órdenes de despacho" "HTTPS/JSON"
        sistema.apiGateway -> sistema.frontend "Devuelve respuestas al cliente" "HTTPS/JSON"

        // Conexiones a bases de datos
        sistema.authService -> sistema.dbIdentity "Lee y escribe cuentas y sesiones" "Mongo Driver"
        sistema.clientsService -> sistema.dbClients "Lee y escribe perfiles y domicilios" "Mongo Driver"
        sistema.inventoryService -> sistema.dbInventory "Lee y escribe catálogo y stock" "Mongo Driver"
        sistema.ordersService -> sistema.dbOrders "Lee y escribe pedidos e historial" "Mongo Driver"
        sistema.paymentsService -> sistema.dbPayments "Lee y escribe ventas y boletas" "Mongo Driver"
        sistema.dispatchService -> sistema.dbDispatch "Lee y escribe órdenes de despacho" "Mongo Driver"
        sistema.notificationsService -> sistema.dbNotifications "Lee y escribe mensajes de contacto" "Mongo Driver"

        // Conexiones a Vault: los 9 componentes leen con su propio token de solo lectura
        sistema.apiGateway -> sistema.secretManager "Lee gateway-to-* y gateway-introspect" "Vault API"
        sistema.graphqlGateway -> sistema.secretManager "Lee gateway-to-graphql y graphql-to-orders/inventory/clients" "Vault API"
        sistema.authService -> sistema.secretManager "Lee auth/db y secretos de par" "Vault API"
        sistema.clientsService -> sistema.secretManager "Lee clients/db y secretos de par" "Vault API"
        sistema.inventoryService -> sistema.secretManager "Lee inventory/db y secretos de par" "Vault API"
        sistema.ordersService -> sistema.secretManager "Lee orders/db, orders/activemq y secretos de par" "Vault API"
        sistema.paymentsService -> sistema.secretManager "Lee payments/db, payments/webhook, payments/provider y secretos de par" "Vault API"
        sistema.dispatchService -> sistema.secretManager "Lee dispatch/db y dispatch/activemq" "Vault API"
        sistema.notificationsService -> sistema.secretManager "Lee notifications/db, notifications/mail y secretos de par" "Vault API"

        // Componentes C3 - API Gateway
        sistema.frontend -> sistema.apiGateway.httpEntry "Envía petición HTTPS" "HTTPS/JSON"
        sistema.apiGateway.httpEntry -> sistema.apiGateway.identityFilter "Pasa petición para verificación ZTA"
        sistema.apiGateway.identityFilter -> sistema.authService "POST /internal/introspect con X-Service-Id y X-Service-Secret" "HTTPS/JSON"
        sistema.apiGateway.identityFilter -> sistema.apiGateway.routeDispatcher "Permite la petición inyectando X-Authenticated-User/Roles"
        sistema.apiGateway.routeDispatcher -> sistema.inventoryService "GET /products con X-Gateway-Secret" "HTTPS/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.ordersService "POST /orders con X-Gateway-Secret" "HTTPS/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.graphqlGateway "POST /graphql con X-Gateway-Secret" "HTTPS/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.apiGateway.errorMapper "Mapea fallos en respuesta JSON limpia"

        // Componentes C3 - GraphQL Gateway
        sistema.apiGateway -> sistema.graphqlGateway.graphqlEndpoint "Envía query GraphQL" "HTTPS/JSON"
        sistema.graphqlGateway.graphqlEndpoint -> sistema.graphqlGateway.queryValidator "Verifica costo y profundidad"
        sistema.graphqlGateway.queryValidator -> sistema.graphqlGateway.fieldAccess "Comprueba permisos por campo"
        sistema.graphqlGateway.fieldAccess -> sistema.graphqlGateway.resolvers "Ejecuta resolvers"
        sistema.graphqlGateway.resolvers -> sistema.graphqlGateway.serviceConnectors "Consulta subsistemas usando DataLoader"
        sistema.graphqlGateway.serviceConnectors -> sistema.ordersService "GET /orders/{id} y GET /orders?limit=" "HTTPS/JSON"
        sistema.graphqlGateway.serviceConnectors -> sistema.inventoryService "GET /products?ids=..." "HTTPS/JSON"
        sistema.graphqlGateway.serviceConnectors -> sistema.clientsService "GET /clients/me" "HTTPS/JSON"
        sistema.graphqlGateway.resolvers -> sistema.graphqlGateway.responseComposer "Genera JSON agregando datos o errores parciales"

        // Componentes C3 - Orders Service
        sistema.apiGateway -> sistema.ordersService.ordersApi "POST /orders" "HTTPS/JSON"
        sistema.ordersService.ordersApi -> sistema.ordersService.accessPolicy "Verifica pertenencia de cuenta (C1)"
        sistema.ordersService.accessPolicy -> sistema.ordersService.idempotency "Comprueba Idempotency-Key"
        sistema.ordersService.idempotency -> sistema.ordersService.orderWorkflow "Inicia flujo de pedido"
        sistema.ordersService.orderWorkflow -> sistema.ordersService.inventoryAdapter "Reserva stock temporal (15 min)"
        sistema.ordersService.inventoryAdapter -> sistema.inventoryService "POST /internal/stock/reservations" "HTTPS/JSON"
        sistema.ordersService.orderWorkflow -> sistema.ordersService.stompPublisher "Publica orden al confirmarse el pago"
        sistema.ordersService.stompPublisher -> sistema.activemqBroker "SEND /queue/cola_pedidos" "STOMP"
        sistema.ordersService.orderWorkflow -> sistema.ordersService.ordersRepo "Guarda pedido y estado"
        sistema.ordersService.ordersRepo -> sistema.dbOrders "Persiste en MongoDB" "Mongo Driver"

        // Entornos de despliegue
        prod = deploymentEnvironment "Produccion_Docker" {
            deploymentNode "Servidor Cloud La Fornace" "Servidor Linux con Docker Compose y redes aisladas. Solo se publican 8443, 8080 y 9201, y solo en 127.0.0.1." "Docker Host" {
                tags "ZonaEntorno"

                deploymentNode "Red Pública" "Red con los únicos puertos publicados: 8443 (API Gateway), 8080 (frontend) y 9201 (pasarela de prueba)." "Docker Network" {
                    tags "ZonaPublica"
                    deploymentNode "Contenedor API Gateway" "Única entrada al backend (127.0.0.1:8443 -> 8000). Conectado también a la red privada." "Docker Container" {
                        containerInstance sistema.apiGateway
                    }
                    deploymentNode "Contenedor Frontend" "Sirve las páginas estáticas (127.0.0.1:8080). Solo en la red pública." "Docker Container" {
                        containerInstance sistema.frontend
                    }
                    deploymentNode "Contenedor Pasarela de Prueba" "Adaptador de la plataforma de pago (127.0.0.1:9201). Conectado también a la red privada para avisar al API Gateway." "Docker Container" {
                        softwareSystemInstance pasarelaPago
                    }
                }

                deploymentNode "Red Privada Interna" "Red interna sin salida a Internet y sin puertos publicados (internal: true)." "Docker Network" {
                    tags "ZonaPrivada"
                    deploymentNode "Contenedor Auth Service" "Servicio de Autenticación." "Docker Container" {
                        containerInstance sistema.authService
                    }
                    deploymentNode "Contenedor GraphQL Gateway" "Agregador BFF de consultas." "Docker Container" {
                        containerInstance sistema.graphqlGateway
                    }
                    deploymentNode "Contenedor Orders Service" "Servicio de Pedidos." "Docker Container" {
                        containerInstance sistema.ordersService
                    }
                    deploymentNode "Contenedor Inventory Service" "Servicio de Inventario." "Docker Container" {
                        containerInstance sistema.inventoryService
                    }
                    deploymentNode "Contenedor Clients Service" "Servicio de Clientes." "Docker Container" {
                        containerInstance sistema.clientsService
                    }
                    deploymentNode "Contenedor Payments Service" "Servicio de Pagos." "Docker Container" {
                        containerInstance sistema.paymentsService
                    }
                    deploymentNode "Contenedor Dispatch Service" "Servicio de Despacho." "Docker Container" {
                        containerInstance sistema.dispatchService
                    }
                    deploymentNode "Contenedor Notifications Service" "Servicio de Notificaciones." "Docker Container" {
                        containerInstance sistema.notificationsService
                    }
                    deploymentNode "Contenedor Correo de Prueba" "Adaptador del proveedor de correo, con bandeja consultable." "Docker Container" {
                        softwareSystemInstance proveedorCorreo
                    }
                    deploymentNode "Contenedor ActiveMQ" "Broker STOMP." "Docker Container" {
                        containerInstance sistema.activemqBroker
                    }
                    deploymentNode "Contenedor Vault" "Gestor de Secretos." "Docker Container" {
                        containerInstance sistema.secretManager
                    }
                    deploymentNode "Contenedor MongoDB 7" "Una instancia con autenticación; cada sistema tiene un usuario con readWrite solo sobre su base." "Docker Container" {
                        containerInstance sistema.dbIdentity
                        containerInstance sistema.dbClients
                        containerInstance sistema.dbInventory
                        containerInstance sistema.dbOrders
                        containerInstance sistema.dbPayments
                        containerInstance sistema.dbDispatch
                        containerInstance sistema.dbNotifications
                    }
                }
            }
        }
    }

    views {
        systemContext sistema "C1_Contexto_La_Fornace" "Diagrama de Contexto de Pizzería La Fornace." {
            title "C1 - Contexto del Sistema Pizzería La Fornace"
            include *
            autoLayout lr
        }

        container sistema "C2_Contenedores_La_Fornace" "Diagrama de Contenedores (Microservicios) de Pizzería La Fornace." {
            title "C2 - Contenedores de Pizzería La Fornace"
            include *
            autoLayout lr
        }

        component sistema.apiGateway "C3_API_Gateway_La_Fornace" "Componentes Internos del API Gateway." {
            title "C3 - API Gateway (ZTA & RBAC)"
            include *
            autoLayout lr
        }

        component sistema.graphqlGateway "C3_GraphQL_La_Fornace" "Componentes Internos del GraphQL Gateway (BFF)." {
            title "C3 - GraphQL Gateway (Agregador)"
            include *
            autoLayout lr
        }

        component sistema.ordersService "C3_Orders_Service_La_Fornace" "Componentes Internos del Servicio de Pedidos." {
            title "C3 - Servicio de Pedidos (Idempotencia & Reservas)"
            include *
            autoLayout lr
        }

        // Vistas Dinámicas
        dynamic sistema "D_F01_Consulta_Menu" "Flujo de consulta pública del catálogo de pizzas." {
            title "F01 - Consulta de Menú y Pizzas (Público)"
            1: visitante -> sistema.frontend "Navega a la carta del sitio web" "HTTP"
            2: sistema.frontend -> sistema.apiGateway "GET /api/v1/products" "HTTPS/JSON"
            3: sistema.apiGateway -> sistema.inventoryService "GET /products (con X-Gateway-Secret)" "HTTPS/JSON"
            4: sistema.inventoryService -> sistema.dbInventory "Busca catálogo activo" "Mongo Driver"
            5: sistema.dbInventory -> sistema.inventoryService "Retorna 12 productos del catálogo" "Mongo Driver"
            6: sistema.inventoryService -> sistema.apiGateway "Devuelve lista de pizzas sin stock público" "HTTPS/JSON"
            7: sistema.apiGateway -> sistema.frontend "Respuesta 200 OK" "HTTPS/JSON"
            8: sistema.frontend -> visitante "Muestra pizzas, acompañamientos y combos" "HTTP"
            autoLayout lr
        }

        dynamic sistema "D_F02_Crear_Pedido" "Flujo de creación de pedido con validación ZTA y reserva atómica de stock." {
            title "F02 - Creación de Pedido con Reserva de Stock (Cliente)"
            1: cliente -> sistema.frontend "Confirma pedido en el carrito" "HTTP"
            2: sistema.frontend -> sistema.apiGateway "POST /api/v1/orders con Bearer Token e Idempotency-Key" "HTTPS/JSON"
            3: sistema.apiGateway -> sistema.authService "POST /internal/introspect con X-Service-Id y X-Service-Secret" "HTTPS/JSON"
            4: sistema.authService -> sistema.apiGateway "Devuelve cuentaId y roles verificados" "HTTPS/JSON"
            5: sistema.apiGateway -> sistema.ordersService "POST /orders con X-Gateway-Secret y X-Authenticated-User" "HTTPS/JSON"
            6: sistema.ordersService -> sistema.inventoryService "POST /internal/stock/reservations (reserva por 15 min)" "HTTPS/JSON"
            7: sistema.inventoryService -> sistema.dbInventory "Descuenta stock atómicamente" "Mongo Driver"
            8: sistema.inventoryService -> sistema.ordersService "Reserva confirmada con precios congelados" "HTTPS/JSON"
            9: sistema.ordersService -> sistema.dbOrders "Persiste pedido en estado 'pendiente_pago'" "Mongo Driver"
            10: sistema.ordersService -> sistema.apiGateway "Devuelve ped_id y expiraEn (15 min)" "HTTPS/JSON"
            11: sistema.apiGateway -> sistema.frontend "201 Created con resumen de pedido" "HTTPS/JSON"
            12: sistema.frontend -> cliente "Muestra resumen y botón 'Pagar'" "HTTP"
            autoLayout lr
        }

        dynamic sistema "D_F03_Pago_Webhook" "Flujo de pago en la pasarela y confirmación por aviso firmado HMAC." {
            title "F03 - Pago y Confirmación por Aviso HMAC (Pasarela)"
            1: cliente -> sistema.frontend "Selecciona medio de pago y presiona 'Pagar'" "HTTP"
            2: sistema.frontend -> sistema.apiGateway "POST /api/v1/orders/{id}/payments" "HTTPS/JSON"
            3: sistema.apiGateway -> sistema.paymentsService "POST /orders/{id}/payments" "HTTPS/JSON"
            4: sistema.paymentsService -> pasarelaPago "Crea cobro (POST /cobros con X-API-Key)" "HTTPS/JSON"
            5: pasarelaPago -> sistema.paymentsService "Devuelve urlPago" "HTTPS/JSON"
            6: sistema.paymentsService -> sistema.apiGateway "201 con pagoId y urlPago" "HTTPS/JSON"
            7: sistema.apiGateway -> sistema.frontend "Entrega urlPago; el navegador redirige a la pasarela" "HTTPS/JSON"
            8: cliente -> pasarelaPago "Completa el pago" "Web"
            9: pasarelaPago -> sistema.apiGateway "POST /api/v1/payments/webhook (X-Signature, X-Timestamp)" "HTTPS/JSON"
            10: sistema.apiGateway -> sistema.paymentsService "Reenvía el aviso sin alterar firma ni timestamp" "HTTPS/JSON"
            11: sistema.paymentsService -> sistema.paymentsService "Verifica firma HMAC-SHA256, monto y duplicados (eventoId)"
            12: sistema.paymentsService -> sistema.apiGateway "Responde 200 de inmediato" "HTTPS/JSON"
            13: sistema.apiGateway -> pasarelaPago "200 OK al aviso" "HTTPS/JSON"
            14: sistema.paymentsService -> sistema.ordersService "En segundo plano: POST /internal/orders/{id}/payment-confirmation" "HTTPS/JSON"
            15: sistema.ordersService -> sistema.dbOrders "Actualiza estado a 'pagado'" "Mongo Driver"
            16: sistema.ordersService -> sistema.activemqBroker "Publica orden en /queue/cola_pedidos" "STOMP"
            17: sistema.paymentsService -> sistema.notificationsService "Solicita envío de boleta digital por correo" "HTTPS/JSON"
            autoLayout lr
        }

        dynamic sistema "D_F04_Despacho_STOMP" "Flujo de recepción asíncrona de la orden de despacho vía ActiveMQ." {
            title "F04 - Despacho Asíncrono (ActiveMQ STOMP)"
            1: sistema.ordersService -> sistema.activemqBroker "SEND /queue/cola_pedidos (datos sin precios)" "STOMP"
            2: sistema.activemqBroker -> sistema.dispatchService "MESSAGE /queue/cola_pedidos (Consumer Listener)" "STOMP"
            3: sistema.dispatchService -> sistema.dbDispatch "Guarda la orden de despacho por orden de llegada" "Mongo Driver"
            4: despachador -> sistema.frontend "Abre sección 'Despacho' en el panel interno" "HTTP"
            5: sistema.frontend -> sistema.apiGateway "GET /api/v1/admin/dispatch-orders" "HTTPS/JSON"
            6: sistema.apiGateway -> sistema.dispatchService "GET /admin/dispatch-orders" "HTTPS/JSON"
            7: sistema.dispatchService -> sistema.apiGateway "Devuelve órdenes listas para imprimir" "HTTPS/JSON"
            8: sistema.apiGateway -> sistema.frontend "Devuelve órdenes de despacho al navegador" "HTTPS/JSON"
            9: despachador -> sistema.frontend "Presiona 'Imprimir' (GET /api/v1/admin/dispatch-orders/{pedidoId}/print)" "HTTP"
            autoLayout lr
        }

        dynamic sistema "D_F05_Registro_Cliente" "Flujo de registro de un cliente con creación de cuenta y correo de verificación." {
            title "F05 - Registro de Cliente y Verificación de Correo"
            1: visitante -> sistema.frontend "Completa el formulario de registro" "HTTP"
            2: sistema.frontend -> sistema.apiGateway "POST /api/v1/auth/register" "HTTPS/JSON"
            3: sistema.apiGateway -> sistema.clientsService "POST /clients/register con X-Gateway-Secret" "HTTPS/JSON"
            4: sistema.clientsService -> sistema.authService "POST /internal/accounts (crea la cuenta y su hash bcrypt)" "HTTPS/JSON"
            5: sistema.authService -> sistema.dbIdentity "Guarda la cuenta en estado pendiente_verificacion" "Mongo Driver"
            6: sistema.authService -> sistema.notificationsService "POST /internal/emails (enlace de verificación)" "HTTPS/JSON"
            7: sistema.notificationsService -> proveedorCorreo "Envía el correo de verificación" "HTTPS/API Key"
            8: sistema.clientsService -> sistema.dbClients "Guarda perfil y domicilio" "Mongo Driver"
            9: sistema.clientsService -> sistema.apiGateway "201 con id y estado pendiente_verificacion" "HTTPS/JSON"
            10: sistema.apiGateway -> sistema.frontend "201 Created" "HTTPS/JSON"
            autoLayout lr
        }

        deployment * prod "Despliegue_La_Fornace" "Diagrama de Despliegue en Docker Compose para Pizzería La Fornace." {
            title "Despliegue - Pizzería La Fornace (Docker Compose & Redes Aisladas)"
            include *
            autoLayout lr
        }

        styles {
            element "Deployment Node" {
                background #E9EFF5
                color #213F56
                stroke #8FA5B7
            }
            element "ZonaEntorno" {
                background #F4F6F8
                color #213F56
            }
            element "ZonaPublica" {
                background #DCEAF7
                color #173B5D
            }
            element "ZonaPrivada" {
                background #E5EEE8
                color #20513D
            }
            element "Person" {
                shape person
                background #2C3E50
                color #FFFFFF
            }
            element "SistemaEvaluado" {
                background #173B5D
                color #FFFFFF
            }
            element "SistemaExterno" {
                background #7F8C8D
                color #FFFFFF
            }
            element "Container" {
                shape roundedbox
                background #E3ECF5
                color #173B5D
            }
            element "Frontend" {
                shape webbrowser
                background #3498DB
                color #FFFFFF
            }
            element "Gateway" {
                background #2980B9
                color #FFFFFF
            }
            element "Seguridad" {
                background #8E44AD
                color #FFFFFF
            }
            element "Privado" {
                background #2ECC71
                color #FFFFFF
            }
            element "Broker" {
                background #E67E22
                color #FFFFFF
            }
            element "BaseDatos" {
                shape cylinder
                background #34495E
                color #FFFFFF
            }
            element "EntradaC3" {
                background #D3E9F7
                color #153F62
            }
            element "ControlC3" {
                background #DBE4EC
                color #213F56
            }
            element "AplicacionC3" {
                background #D7E9DE
                color #20533E
            }
            element "IntegracionC3" {
                background #E9E2F2
                color #4A3666
            }
            element "PersistenciaC3" {
                background #E9EBEE
                color #334454
            }
            element "ErrorC3" {
                background #F2E6DB
                color #70462C
            }
            relationship "Relationship" {
                color #7F8C8D
                thickness 2
            }
        }
    }
}
