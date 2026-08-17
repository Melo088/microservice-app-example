# Despliegue en Kubernetes

## 1. Alcance

`k8s/` despliega la misma aplicación que `docker-compose.prod.yml`, con las mismas imágenes publicadas por CI/CD en Docker Hub, pero sobre un clúster de Kubernetes en vez de una sola máquina con Docker Compose. Es una segunda forma de despliegue, ambas despliegan la misma aplicación, con modelos de infraestructura distintos. Probado localmente con `kind` (un clúster de Kubernetes real corriendo en contenedores Docker, sin costo). Ningún manifiesto asume que el clúster sea `kind` en particular; aplicarlos contra un clúster administrado real no requeriría cambios.

## 2. Estructura

```
k8s/
  00-namespace.yaml
  01-configmap.yaml
  02-secret.example.yaml
  10-redis-queue.yaml
  11-zipkin.yaml
  20-auth-api.yaml
  21-users-api.yaml
  22-todos-api.yaml
  23-frontend.yaml
  24-log-message-processor.yaml
  kustomization.yaml
  kind-config.yaml
```

El prefijo numérico es solo una ayuda a la lectura (namespace y configuración primero, infraestructura de soporte después, servicios de la aplicación al final), no algo de lo que dependa el orden real de aplicación pues eso lo resuelve `kustomization.yaml`.

## 3. Decisiones

### Los mismos `/health` que ya existen, ahora como `readinessProbe`/`livenessProbe`

`auth-api` usa `/version`, `frontend` usa `/`, `todos-api` y `users-api` usan `/health`. Son exactamente los mismos endpoints documentados en `docs/DOCKER.md` sección 3 para el patrón Health Endpoint Monitoring a nivel Docker; acá Kubernetes los consume de forma nativa para decidir si un pod recibe tráfico (`readinessProbe`) y si necesita reiniciarse (`livenessProbe`). `log-message-processor` no lleva ninguno de los dos, por la misma razón que no tiene `HEALTHCHECK` en su Dockerfile, no es un servidor HTTP, no hay una ruta que consultar.

### Sin orden de arranque garantizado entre servicios

`docker-compose.yml` bloquea el arranque de un servicio hasta que otro esté sano (`depends_on: condition: service_healthy`). Kubernetes no tiene ese mecanismo entre Deployments distintos: cada uno arranca cuando puede, y si falla se reinicia solo. El `readinessProbe` evita que un Service le mande tráfico a un pod que todavía no está listo, pero no impide que ese pod exista mientras tanto. No se agregaron `initContainers` para imitar el orden de Compose a propósito: es una decisión explícita, no una limitación pasada por alto. Varios servicios ya toleran esto por su cuenta (`todos-api` reintenta la conexión a Redis con backoff, por ejemplo).

### `frontend` y `zipkin` con `NodePort`, el resto con `ClusterIP`

Misma decisión de seguridad que ya está tomada en el grupo de seguridad de red de Terraform y en `docker-compose.prod.yml`: solo esos dos componentes necesitan ser alcanzables desde afuera.

### `PersistentVolumeClaim` para `log-message-processor`

Cumple el mismo rol que el volumen `log-data` de `docker-compose.yml`: el filtro `persist` del patrón Pipes and Filters (`docs/DOCKER.md` sección 5) escribe en `/data/processed.log`, y ese archivo debe sobrevivir a que el pod se reinicie.

### `replicas: 1` en todos lados, con una excepción documentada en el propio manifiesto

`todos-api` guarda los todos en un `memory-cache` dentro del proceso, no en Redis ni en ninguna base compartida (`todoController.js`). Escalarlo a más de un pod haría que cada copia tuviera datos distintos, y el Service repartiría tráfico entre ellas de forma inconsistente para quien está usando la app. `users-api`, en cambio, sí sería seguro escalarlo (`kubectl scale deployment users-api --replicas=3`): sus datos vienen de un `data.sql` estático cargado en una base H2 en memoria, sin ninguna escritura propia (`UsersController` solo tiene rutas `GET`), así que todas las copias arrancarían con exactamente los mismos datos.

## 4. Uso local con `kind`

```bash
kind create cluster --name microservice-app-example --config k8s/kind-config.yaml

cp k8s/02-secret.example.yaml k8s/02-secret.yaml
# editar k8s/02-secret.yaml con un JWT_SECRET propio antes de aplicar

kubectl apply -k k8s/

kubectl -n microservice-app-example get pods
```

`k8s/02-secret.yaml` queda fuera de git (mismo patrón que `.env` y `ansible/inventory.ini`). `k8s/kind-config.yaml` mapea los `NodePort` de `frontend` (30080) y `zipkin` (30411) a esos mismos puertos en la máquina host; sin ese archivo, esos puertos solo serían alcanzables dentro del contenedor que `kind` usa como nodo.

```bash
# frontend: http://localhost:30080
# zipkin:   http://localhost:30411/zipkin/

kind delete cluster --name microservice-app-example
```

## 5. Verificación 

Se aplicó todo contra un clúster `kind` real y se repitió la misma verificación de siempre: login, crear un todo, confirmar que `log-message-processor` recibe el mensaje y lo persiste en el volumen, y una prueba de resiliencia (borrar el pod de `users-api` a mano). Los tres primeros pasos no aparecían documentados en ningún lado todavía porque los tres problemas de abajo los bloqueaban.

**`runAsNonRoot: true` sin `runAsUser` no alcanza cuando el `USER` del Dockerfile es un nombre, no un número.** Los cinco Deployments fallaban con `CreateContainerConfigError`: "container has runAsNonRoot and image has non-numeric user (app), cannot verify user is non-root". Kubernetes no resuelve nombres de usuario del `USER` del Dockerfile, necesita el UID numérico para poder verificar que no es root sin tener que arrancar el contenedor primero. Se corrigió corriendo `docker run --rm --entrypoint id` contra cada imagen real para obtener el UID exacto (100 para `auth-api` y `users-api`, 1000 para `todos-api`, `frontend` y `log-message-processor`) y agregando `runAsUser` explícito en cada manifiesto.

**`users-api` (Spring Boot 1.5.6 sobre Java 8) tarda más en arrancar de lo que un `livenessProbe` sin `startupProbe` tolera.** Con `initialDelaySeconds: 30`, Kubernetes mataba el contenedor antes de que terminara de levantar, en un bucle de reinicios. Se agregó un `startupProbe` (hasta 120 segundos de margen para el primer arranque), que desactiva el `livenessProbe` hasta que el primero tenga éxito, así un arranque lento no se confunde con un proceso colgado.

**Con la CPU resuelta, `users-api` seguía muriendo, esta vez `OOMKilled`, con el límite de memoria en 512Mi.** Este problema no podía aparecer en ninguna verificación anterior del proyecto porque ningún `docker run` de Compose o de las pruebas anteriores impuso nunca un límite de memoria; Docker sin ese límite deja usar la memoria que el proceso pida. Se midió el uso real con `docker stats` contra la imagen sin ningún límite: un pico de ~925MiB al arrancar (Hibernate, Spring Security y Spring Cloud Sleuth cargando todos a la vez) y un estable de ~917MiB. El límite de memoria de `users-api` se subió a 1280Mi en base a esa medición, no a una suposición.

Los otros cuatro servicios no necesitaron ningún ajuste de recursos ni de probes más allá del arreglo de `runAsUser`.
