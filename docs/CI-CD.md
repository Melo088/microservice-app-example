# CI/CD con GitHub Actions

## 1. Alcance

Cinco workflows, uno por servicio, en `.github/workflows/`. Cada uno construye la imagen del servicio con su propio Dockerfile y la publica en Docker Hub. No hay un workflow compartido: cada archivo es independiente y solo le interesa su propia carpeta.

## 2. Workflow x servicio

La alternativa más simple es un único workflow que reconstruye las 5 imágenes en cada push a master. Se descartó porque si solo se cambiara una línea en `todos-api`, no tiene sentido reconstruir y republicar `users-api` o `frontend`, que no cambiaron. Cada workflow tiene un filtro `paths` que lo limita a su propia carpeta:

```yaml
on:
  push:
    branches: [master]
    paths:
      - "auth-api/**"
      - ".github/workflows/auth-api.yml"
```

El propio archivo del workflow también está en la lista de paths, para que si se edita (por ejemplo, para cambiar el tag), el cambio se pruebe a sí mismo.

## 3. Credenciales: access token, no contraseña

`docker/login-action` recibe un usuario y una contraseña. Se usó un access token de Docker Hub (`DOCKERHUB_TOKEN`, guardado como secret de GitHub) en vez de la contraseña real de la cuenta.

## 4. Tags: latest y el hash corto del commit

Cada build publica dos tags:

```yaml
tags: |
  melo15036/microservice-app-example-auth-api:latest
  melo15036/microservice-app-example-auth-api:${{ steps.vars.outputs.sha_short }}
```

`latest` sirve para desarrollo local rápido (`docker pull ... :latest`, siempre la última versión). El hash corto del commit (calculado con `git rev-parse --short HEAD` en el paso `Set short SHA`) da trazabilidad pues se puede saber exactamente qué commit generó una imagen en particular, y fijar un despliegue a esa versión específica en vez de a `latest`. Esto importa para cuando estas imágenes se referencien desde manifiestos de Kubernetes o desde un `docker-compose.prod.yml`.

## 5. `workflow_dispatch`: probar antes de mergear

El trigger `push` solo dispara en `master`. Como el flujo de trabajo de este repo es por rama de feature, eso significa que un workflow nuevo no corre ni una vez hasta que su propia rama se mergea, momento en el que ya es tarde para corregir un error de sintaxis o de configuración sin otro commit. Por eso los cinco workflows también tienen:

```yaml
workflow_dispatch: {}
```

Esto agrega un botón "Run workflow" en la pestaña Actions de GitHub, que permite dispararlo a mano sobre cualquier rama, incluida la que todavía no se mergeó. Es la forma de probar un workflow antes de confiarle un merge a master.

## 6. Cache de build

`cache-from`/`cache-to` con `type=gha` usa el cache de GitHub Actions para las capas de Docker. No cambia el resultado del build, solo la velocidad: si `auth-api/go.mod` no cambió entre dos runs, esa capa no se vuelve a descargar ni compilar. Cada workflow usa su propio `scope` (`auth-api`, `todos-api`, etc.) para que los caches de los cinco servicios no se pisen entre sí.

