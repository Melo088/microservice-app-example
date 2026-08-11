# Microservice App - PRFT Devops Training

This is the application you are going to use through the whole traninig. This, hopefully, will teach you the fundamentals you need in a real project. You will find a basic TODO application designed with a [microservice architecture](https://microservices.io). Although is a TODO application, it is interesting because the microservices that compose it are written in different programming language or frameworks (Go, Python, Vue, Java, and NodeJS). With this design you will experiment with multiple build tools and environments. 

## Run w/ Docker

Cada servicio tiene su propio `Dockerfile` (multistage, con healthcheck y usuario no-root) y hay un `docker-compose.yml` en la raíz que levanta los 5 servicios más Redis y Zipkin.

```bash
docker compose up -d      # construye (la primera vez) y levanta todo
docker compose ps         # esperar ~30-40s a que todo quede "healthy"
docker compose down       # apagar
```

Con todo arriba: frontend en `http://localhost:8080` (login `admin`/`admin`), Zipkin en `http://localhost:9411`.

Documentación completa:
- [`docs/DOCKER.md`](docs/DOCKER.md): qué imagen base se eligió para cada servicio y por qué, y cómo quedó implementado el patrón *Health Endpoint Monitoring*.
- [`docs/COMPOSE.md`](docs/COMPOSE.md): cómo está armado `docker-compose.yml`, y el paso a paso completo para verificar que todo funciona (incluyendo el pipeline `todos-api → Redis → log-message-processor`, un ejemplo del patrón *Pipes and Filters*).

## Components
In each folder you can find a more in-depth explanation of each component:

1. [Users API](/users-api) is a Spring Boot application. Provides user profiles. At the moment, does not provide full CRUD, just getting a single user and all users.
2. [Auth API](/auth-api) is a Go application, and provides authorization functionality. Generates [JWT](https://jwt.io/) tokens to be used with other APIs.
3. [TODOs API](/todos-api) is a NodeJS application, provides CRUD functionality over user's TODO records. Also, it logs "create" and "delete" operations to [Redis](https://redis.io/) queue.
4. [Log Message Processor](/log-message-processor) is a queue processor written in Python. Its purpose is to read messages from a Redis queue and print them to standard output.
5. [Frontend](/frontend) Vue application, provides UI.

## Architecture

Take a look at the components diagram that describes them and their interactions.
![microservice-app-example](/arch-img/Microservices.png)