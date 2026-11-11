# La Fornace — Backend seguro (Unidad 2) — v3

Entrega del backend de Pizzería La Fornace: 7 sistemas privados con base de datos propia, API Gateway, GraphQL Gateway de solo lectura, administrador de secretos (HashiCorp Vault), MongoDB, cola de despacho por STOMP (Apache ActiveMQ), y simuladores de pago y de correo.

## Alcance de esta entrega

- La entrega es el **backend**. Se prueba por su API, con los datos del frontend de la Evaluación 1 (`frontend-la-fornace`, 5 páginas HTML + Bootstrap 5.3): el catálogo de 12 productos (8 productos y 4 combos, mismos nombres y precios que `js/data.js`) y la cobertura de despacho de las sucursales.
- La carpeta `frontend/` contiene un frontend integrado (11 páginas) que consume esta API. Es una **demostración opcional**: el backend no depende de él y todas las pruebas de la guía se pueden hacer sin abrirlo.
- Guía de prueba por API: `GUIA-DE-PRUEBA.md`.

## Dos formas de ejecutarlo

| | A. Docker Compose | B. Local (sin Docker) |
| --- | --- | --- |
| Motores | MongoDB 7, Vault 1.18 y ActiveMQ 6.2.0 en contenedores | MongoDB 7, Vault 1.18.5 y ActiveMQ 6.2.0 instalados en el equipo |
| Servicios | Contenedores (Dockerfile.python y Dockerfile.node) | Procesos del equipo |
| Separación pública y privada | Redes `publica` y `privada`; solo se publican 8443, 8080 y 9201 | Todo escucha en `127.0.0.1`; el acceso directo se rechaza por secretos entre sistemas, no por red |
| Pruebas | Recorrido por API (guía, secciones 3 y 4) | Batería de 193 pruebas (`scripts/run_tests.py`) |
| Verificado en | Windows con Docker Desktop (`compose.py probar`, 28 pruebas) | Windows 11, Python 3.14, Node 26, Java 17 (`run_tests.py`, 193 pruebas) |

Con las dos formas se usan los mismos motores reales y el mismo código.

## Probar todo con un solo comando

`python probar_todo.py` (desde esta carpeta, con cualquier Python 3 instalado) crea `.venv`, instala las dependencias, ejecuta la batería local (193 pruebas) y después Docker Compose (28 pruebas), y escribe `ENVIAR-RESULTADOS.zip` con los resultados, las capturas y las versiones del entorno. Opciones: `--solo-local`, `--solo-compose`, `--sin-carga`, `--instalar-infra` (descarga Vault 1.18.5 y ActiveMQ 6.2.0 a `.herramientas`). MongoDB 7 (servicio), Java 17, Node y Docker Desktop deben estar instalados; el script informa lo que falte y cómo instalarlo.

## A. Docker Compose

Requisitos: Docker Desktop abierto (con `docker compose`) y Python 3. No hay que instalar librerías. Internet la primera vez, para descargar las imágenes.

```
python scripts/compose.py up          # construye e inicia todo (la primera vez tarda varios minutos)
python scripts/compose.py semilla     # carga datos ficticios
python scripts/compose.py estado      # contenedores y puertos publicados
python scripts/compose.py probar      # 28 pruebas: puertos publicados, red privada, acceso directo rechazado, usuarios de MongoDB por sistema y compra completa dentro de la red (requiere up y semilla)
python scripts/compose.py down        # detiene (con --borrar elimina también los datos)
```

Los datos viven en un volumen de Docker (`fornace_mongo-datos`) que sobrevive a `down`. Si copia el proyecto a otra carpeta o pierde `.run/credenciales-demo.json`, ejecute `python scripts/compose.py down --borrar` antes de volver a hacer `up` y `semilla`: la semilla no cambia las contraseñas de las cuentas que ya existen. En Windows use `py` si `python` no funciona. `up` termina con `todos los servicios estan sanos`.

**MongoDB con autenticación (solo Docker Compose).** `compose.py preparar` agrega a `.env` una clave `MONGO_ROOT_PASSWORD` al azar. El usuario `root` lo usan solo el contenedor `preparacion` (que crea un usuario por sistema, `<sistema>_user`, con permiso de lectura y escritura únicamente sobre `<sistema>_db`, con la clave que está en Vault) y el contenedor `herramientas` (semilla y pruebas). Los 7 sistemas arrancan con `MONGO_AUTH=1`. Si existe un volumen de datos creado con una versión anterior (sin autenticación), `preparacion` lo detecta y pide ejecutar `python scripts/compose.py down --borrar` y luego `up`. El modo local usa el MongoDB del equipo sin autenticación (`MONGO_AUTH=0`).

**Retención (7.9).** Cada sistema purga o anonimiza sus propios datos con una tarea periódica (`RETENCION_SEGUNDOS`, por defecto cada hora). Los plazos están en `common/fornace/retencion.py` y la prueba es `tests/suite_retencion.py`.

**Content-Security-Policy.** El API Gateway y el servidor del frontend (`scripts/serve_frontend.py`) la envían; la del frontend limita a qué orígenes puede conectarse una página (`API_ORIGEN`).

Versiones por omisión (se pueden cambiar en `.env`): `python:3.13-slim`, `node:22-slim`, `mongo:7`, `hashicorp/vault:1.18` (modo desarrollo) y `apache/activemq-classic:6.2.0` (`Dockerfile.broker`, sin privilegios, con un usuario por sistema y permisos por cola: solo orders escribe y solo dispatch lee).

## B. Local, sin Docker

Requisitos (Windows, con las versiones probadas):

- Python 3 y Node 22 o superior. La carpeta del proyecto no debe tener espacios en la ruta.
- MongoDB Community 7.0 instalado como servicio (`Get-Service MongoDB` debe mostrar `Running`, puerto 27017).
- HashiCorp Vault 1.18.5: el zip de Windows descomprimido (`vault.exe`).
- Java 17 o superior y Apache ActiveMQ Classic 6.2.0: el zip descomprimido.
- Docker Compose del proyecto detenido (usa los mismos puertos 8443, 8080 y 9201).

Instalación, una sola vez, en PowerShell desde esta carpeta:

```
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-test.txt
pip install -e common
python -m playwright install chromium
cd services\graphql_gateway; npm ci --omit=dev; cd ..\..
```

Variables de cada sesión (cambie las rutas por las suyas):

```
$env:VAULT_BIN = "C:\ruta\a\vault.exe"
$env:ACTIVEMQ_HOME = "C:\ruta\a\apache-activemq-6.2.0"
$env:PYTHONUTF8 = "1"
```

Uso:

```
python scripts\stack.py up            # inicia Vault, ActiveMQ y los servicios (certificados y secretos se generan solos)
python scripts\seed.py                # datos ficticios
python scripts\stack.py status        # puertos activos
python scripts\stack.py down --todo   # detiene todo y borra las bases del proyecto (las que terminan en _db)
python scripts\run_tests.py           # batería completa desde cero (unos 20 minutos)
python scripts\run_tests.py --sin-carga
```

`down --todo` no detiene el servicio MongoDB: solo elimina las bases `*_db`. El firewall de Windows puede preguntar por Java (ActiveMQ escucha en 0.0.0.0:61613): se puede cancelar, el proyecto usa `127.0.0.1`.

En Linux o macOS se usa igual (`python3`, `source .venv/bin/activate`, variables con `export`); `scripts/certs.sh` requiere `bash` y `openssl`.

La batería (`run_tests.py`) escribe los resultados reales en `tests/resultados/*.json`, las capturas del navegador en `tests/evidencia/` y la transcripción de los flujos por API en `tests/evidencia/demo-flujos.md`. Termina con `TOTAL 193/193`.

## Cuentas de ejemplo

Las contraseñas se generan al azar al cargar la semilla y quedan en `.run/credenciales-demo.json` (no están en el repositorio).

| Cuenta | Rol |
| --- | --- |
| `admin@ejemplo.cl` | administrador |
| `dueno@ejemplo.cl` | dueño (reporte de ventas) |
| `cajero@ejemplo.cl` | cajero virtual |
| `despachos@ejemplo.cl` | encargado de despachos |
| `camila@ejemplo.cl`, `pedro@ejemplo.cl` | clientes |

El correo de confirmación de un registro llega al servidor de correo de prueba:

```
python scripts/bandeja.py alumno@ejemplo.cl                    # modo B
python scripts/compose.py bandeja alumno@ejemplo.cl            # modo A
```

## Carpetas

| Ruta | Contenido |
| --- | --- |
| `services/` | Los 7 sistemas, el API Gateway, el GraphQL Gateway (Node) y los simuladores de pago y de correo. |
| `common/fornace/` | Código compartido: control de acceso, lectura de secretos, llamadas entre sistemas y tabla de rutas y roles (`routes.json`). |
| `scripts/` | `compose.py` y `bootstrap_compose.py` (modo A), `stack.py` y `run_tests.py` (modo B), `vault_init.py` (secretos y tokens en Vault), `activemq.xml.plantilla` (configuración del broker), `seed.py`, `bandeja.py`, `certs.sh`. |
| `tests/`, `carga/` | Suites de seguridad, negocio, GraphQL, gateway y navegador; pruebas de carga C1–C9 y de fallos F1–F7. |
| `docker-compose.yml`, `Dockerfile.*` | Modo A. |
| `frontend/` | Frontend integrado de demostración (opcional). |

## Seguridad

Los secretos se generan al azar al iniciar, viven en Vault y cada componente recibe un token de solo lectura con los suyos. No hay secretos en el código, en las imágenes ni en `docker-compose.yml`. Cada par de sistemas usa su propio secreto; la identidad la verifica el API Gateway y se propaga a los sistemas privados. Los precios, totales y estados de pago los calcula el servidor; el aviso de pago se valida con firma HMAC. Todo el tráfico entre componentes va por TLS con la CA del proyecto.

## Limitaciones conocidas

- Vault corre en modo desarrollo (en memoria): los secretos se regeneran al reiniciar. Es un entorno de laboratorio, no de producción.
- ActiveMQ conserva el heap por omisión de la JVM (1 GB); no se pudo fijar un límite menor. En Compose, el contenedor tiene `mem_limit: 1g`.
- En Compose, las imágenes base declaran puertos `EXPOSE` (por ejemplo, los de ActiveMQ) que `estado` muestra como metadatos; solo escucha el 61613 y ninguno se publica en el equipo.
- `mongo` no tiene healthcheck en Compose: su columna de salud queda vacía en `estado`.
- En el modo B no hay aislamiento de red: la prueba de que el puerto de un sistema privado "no está publicado" solo se puede hacer en el modo A.
- El navegador guarda el token en `sessionStorage` (legible por JavaScript); no hay cookie HttpOnly.
- Con CA propia, el navegador debe aceptar los certificados de `https://127.0.0.1:8443` y `https://127.0.0.1:9201` (de nuevo si se regeneran).
