# Contenedores de microservice-app-example

Este documento explica las decisiones detrás de los 5 `Dockerfile` del proyecto y de `docker-compose.yml`: qué imagen base se eligió para cada servicio y por qué, cómo quedó implementado el patrón **Health Endpoint Monitoring**, y qué limitaciones conocidas quedan pendientes.

## 1. Principios aplicados en los 5 Dockerfiles

- **Multistage build.** Cada Dockerfile tiene dos etapas: una para construir (`builder`, con compiladores y herramientas pesadas) y otra para correr (limpia, solo con el binario/artefacto ya construido). Todo lo que solo se usó para construir se descarta al terminar el build y nunca llega a la imagen final.
- **Usuario no-root.** Ningún servicio corre como `root` en producción. Si alguien compromete el proceso adentro del contenedor, no hereda privilegios de administrador del sistema operativo del contenedor.
- **Cache de capas.** En todos los servicios, los archivos de dependencias (`package.json`, `pom.xml`, `requirements.txt`) se copian e instalan **antes** que el código fuente. Así, si solo se cambia el código, Docker reutiliza la capa de instalación de dependencias del build anterior en vez de repetirla.
- **Configuración por variable de entorno, no hardcodeada.** Ningún Dockerfile fija `REDIS_HOST`, `JWT_SECRET`, direcciones de otros servicios, etc. Todo eso vive en `docker-compose.yml` (y más adelante, en Kubernetes, en `ConfigMap`/`Secret`).

## 2. Servicio por servicio

### auth-api (Go)

| | |
|---|---|
| Build | `golang:1.24-alpine` |
| Runtime | `alpine:3.20` |
| Puerto | `AUTH_API_PORT` |
| Healthcheck | `GET /version` → 200 real |

El repo trae `Gopkg.toml`/`Gopkg.lock` (herramienta `dep`, obsoleta), pero el `README.md` de `auth-api` documenta construir con Go modules (`go mod init && go mod tidy && go build`), probado contra Go 1.18+. Se sigue esa ruta documentada, no la de `dep`.

`CGO_ENABLED=0` en el build produce un binario 100% estático. Sin eso, la imagen final necesitaría coincidir con las librerías del sistema usadas al compilar.

El healthcheck usa `/version`, la única ruta de este servicio que responde sin necesitar un JWT.

### todos-api (Node.js / Express)

| | |
|---|---|
| Build y runtime | `node:20-alpine` |
| Puerto | `TODO_API_PORT` (default 8082 en el código) |
| Healthcheck | `GET /health` → 200 real |

`npm ci --omit=dev` en vez de `npm ci`: el script `"start"` de `package.json` corre `nodemon`, que vive en `devDependencies`. `nodemon` reinicia el proceso cuando detecta cambios en archivos. Lo cual es útil en desarrollo, pero no tiene tanto sentido dentro de un contenedor (el código no cambia en caliente). Por eso la imagen final arranca con `node server.js` directo, y `nodemon` ni siquiera se instala.

Este servicio tiene una ruta `GET /health` real, registrada en `server.js` antes del middleware de JWT (`app.use(jwt(...))`), que se aplica globalmente a todas las rutas definidas después de él. Por eso `/health` responde 200 sin necesitar un token, y el healthcheck usa `curl -f`, igual que en `auth-api` y `frontend`.

### users-api (Java / Spring Boot 1.5.6)

| | |
|---|---|
| Build | `maven:3.9-eclipse-temurin-8` |
| Runtime | `eclipse-temurin:8-jre-alpine` |
| Puerto | `SERVER_PORT` (default 8083 en `application.properties`) |
| Healthcheck | `GET /health` → 200 real |

Fijado a Java 8 a propósito: esta combinación de Spring Boot 1.5.6 + `jjwt` 0.7.0 + `spring-cloud-starter-zipkin` 1.3.1 es anterior a varios cambios importantes en versiones modernas de Spring/JDK. Se usa el mismo target que el propio README documenta ("Java openJDK8").

El proyecto no trae `spring-boot-starter-actuator`, así que no existe un `/actuator/health`. En su lugar se agregó un `HealthController` propio, mapeado a `GET /health`, que responde 200 con un cuerpo `{"status":"UP"}`. `JwtAuthenticationFilter` deja pasar las peticiones a esa ruta antes de exigir el header `Authorization`, de la misma forma en que ya dejaba pasar las peticiones `OPTIONS`. Con eso el healthcheck usa `curl -f`, igual que en `auth-api`, `frontend` y `todos-api`. `--start-period=30s` es más largo que en los demás servicios porque Spring Boot tarda en inicializar el contexto de la aplicación.

### log-message-processor (Python)

| | |
|---|---|
| Build y runtime | `python:3.11-slim` |
| Puerto | N/A es un consumidor de Redis, no una API |
| Healthcheck | ninguno (justificación abajo) |

`requirements.txt` fija `redis==2.10.6` (2017), cuyo código internamente hace `from distutils.version import StrictVersion`. `distutils` se eliminó de la librería estándar de Python en la versión 3.12. Se probó directamente: con Python 3.12, el simple `import redis` falla con
`ModuleNotFoundError: No module named 'distutils'`. El contenedor jamás llega a arrancar. `python:3.11-slim` es la última versión que todavía trae `distutils`, así que corre el `requirements.txt` sin modificarlo. El arreglo de fondo (actualizar el pin de `redis` a una versión que ya no dependa de `distutils`).

La etapa `builder` instala `gcc` por si `thriftpy2` (dependencia transitiva de `py_zipkin`) necesita compilar su extensión en Cython. En la práctica, sobre una base Debian/glibc como `python:3.11-slim`, `pip` suele encontrar un wheel ya compilado (`manylinux...whl`) y no llega a usar `gcc`. Pero como la etapa `builder` se descarta al final, tenerlo ahí "por si acaso" (por ejemplo, en otra arquitectura de CPU) no cuesta nada en la imagen final.

`pip install --user` instala en `/root/.local` en vez del lugar del sistema, para poder copiar ese único directorio a la etapa final sin arrastrar nada más. `PYTHONUNBUFFERED=1` (y el flag `-u` del `CMD`, redundantes entre sí a propósito) evitan que Python retenga la salida de `print()` en un buffer.

La única señal real disponible sin tocar el código de la aplicación es "¿el proceso sigue vivo?", y eso ya lo expone Docker de forma nativa con el estado del contenedor.

### frontend (Vue.js 2)

| | |
|---|---|
| Build y runtime | `node:8-alpine` |
| Puerto | `PORT` (default 8080) |
| Healthcheck | `GET /` → 200  |

El `CMD` final es `npm start`, que corre `build/dev-server.js`, lo que es un servidor de **desarrollo** de webpack (`webpack-dev-middleware`) y no un servidor estático para producción. 

Así está diseñada esta app: el enrutamiento hacia `auth-api`/`todos-api` (`proxyTable` en `config/index.js`) solo existe en ese script de desarrollo. Una configuración de producción de verdad haría `npm run build` para generar una carpeta `dist/` estática y la serviría con nginx, con un `nginx.conf` que reproduzca ese mismo enrutamiento. 

Fijado a `node:8-alpine` (no `node:20` como los demás) porque este toolchain es realmente de 2017: webpack 2, Babel 6 y, sobre todo, `node-sass` 4.x, que solo distribuye binarios nativos precompilados para versiones de Node viejas (ABI de Node 8/10). En Node 20, `npm ci` intentaría compilar `node-sass` desde código fuente vía `node-gyp`, que para esa versión necesita un intérprete de Python 2, que ya no existe en ningún lado. Usar la versión de Node que el propio README documenta como probada (8.17.0) evita el problema. 

## 3. Patrón Health Endpoint Monitoring

| Servicio | ¿Endpoint de salud real en el código? | Qué usa el `HEALTHCHECK` |
|---|---|---|
| auth-api | Sí (`GET /version`, sin auth) | Chequeo real, `curl -f` |
| frontend | Sí (`GET /`, sirve la SPA) | Chequeo real, `curl -f` |
| todos-api | Sí (`GET /health`, sin auth) | Chequeo real, `curl -f` |
| users-api | Sí (`GET /health`, sin auth) | Chequeo real, `curl -f` |
| log-message-processor | No aplica (sin puerto) | Ninguno |

Los cuatro healthchecks marcados como reales en esta tabla verifican liveness (que el proceso sigue vivo y su servidor HTTP responde), no readiness (que el servicio está en condiciones de atender tráfico con todas sus dependencias externas disponibles). La distinción no pesa igual en cada servicio.

En `users-api`, la base de datos es H2 en memoria, sin datasource externo configurado. No existe un estado intermedio en el que el proceso esté vivo pero alguna dependencia esté caída, así que liveness y readiness coinciden en la práctica.

En `todos-api`, sí hay una dependencia externa real: Redis. Sin embargo, los datos de los todos se guardan en un `memory-cache` dentro del proceso (`todoController.js`), no en Redis. Redis solo se usa para publicar en `log_channel`, el canal que alimenta a `log-message-processor`. Si Redis se cae, las operaciones sobre `/todos` siguen funcionando, pero esa publicación falla en silencio y `/health` no lo refleja. Esta brecha queda identificada como pendiente (ver sección 4).


## 4. Pendientes

1. **`redis==2.10.6` en `log-message-processor`** debería actualizarse a una versión que no dependa de `distutils`.
2. **`frontend` corre su servidor de desarrollo en la imagen "de producción".** La solución real es `npm run build` + nginx con un `nginx.conf` que replique el `proxyTable` de `config/index.js`.
3. **`todos-api` reporta `/health` como liveness únicamente.** No verifica la conexión a Redis, así que una caída de Redis no queda reflejada ahí, aunque sí afecta la publicación de eventos hacia `log-message-processor`. El momento natural para revisar esto es al extender `log-message-processor` con el patrón Pipes and Filters, cuando ese mismo canal de Redis vuelve a tocarse.

