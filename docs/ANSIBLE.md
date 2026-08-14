# Despliegue con Ansible

## 1. Alcance

`ansible/` instala Docker y despliega la aplicación sobre la máquina virtual que Terraform aprovisiona (ver `docs/TERRAFORM.md`). No crea ni modifica ningún recurso de Azure, actúa únicamente dentro de la VM que ya existe, conectándose por SSH con la llave generada para ese propósito.

## 2. Estructura

```
ansible/
  ansible.cfg
  inventory.example.ini
  playbook.yml
  roles/
    docker/tasks/main.yml
    deploy/
      defaults/main.yml
      templates/env.j2
      tasks/main.yml
```

`playbook.yml` aplica dos roles en orden: `docker` instala Docker Engine y el plugin `docker compose`; `deploy` copia `docker-compose.prod.yml` a la VM y levanta el stack.

## 3. Decisiones

### Repositorio oficial de Docker, no `get.docker.com`

El rol `docker` agrega el repositorio apt oficial de Docker para Ubuntu (llave GPG, `apt_repository`, instalación de `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`, `docker-compose-plugin`) en vez de usar el script de conveniencia `get.docker.com`. Docker mismo desaconseja ese script para uso repetible o productivo; el camino por apt es idempotente y verificable paso a paso.

### `become: true` en todo el play

Instalar paquetes con `apt` requiere privilegios de root, así que el play completo corre con `become: true`, no solo las tareas del rol `docker`. La razón para incluir también al rol `deploy`: ese rol agrega al usuario remoto al grupo `docker`, pero la membresía a un grupo nuevo no aplica a una sesión SSH ya abierta, solo a las que se abran después. Ejecutar `docker compose` como root evita depender de que Ansible abra una segunda conexión SSH dentro del mismo playbook para que ese cambio de grupo tenga efecto.

### `docker-compose.prod.yml`, no `docker-compose.yml`

El `docker-compose.yml` de la raíz del repositorio usa `build:` en cada servicio, lo que asume que el código fuente está presente donde se ejecuta. La VM no tiene ese código, y no lo necesita: cada imagen ya está construida y publicada en Docker Hub por los workflows de CI/CD (ver `docs/CI-CD.md`). `docker-compose.prod.yml` reemplaza cada `build:` por un `image: melo15036/microservice-app-example-<servicio>:${IMAGE_TAG:-latest}`, y el rol `deploy` copia ese archivo a la VM renombrado como `docker-compose.yml` remoto, para no tener que pasar `-f` en cada comando.

Ese archivo también deja de publicar los puertos de `auth-api`, `todos-api` y `users-api` al host, algo que sí hace el compose local para poder depurar cada servicio por separado. En la VM, el grupo de seguridad de red de Azure ya bloquea el acceso externo a esos puertos (solo 22, 8080 y 9411 quedan abiertos, ver `docs/TERRAFORM.md`), así que no publicarlos tampoco a nivel de Docker es una segunda capa de la misma decisión, no publicar algo que de todas formas no debería ser alcanzable desde afuera.

### Variables sensibles fuera del repositorio

`JWT_SECRET`, `SENDGRID_API_KEY` y `SENDGRID_TO` no tienen un valor por defecto sensible en `ansible/roles/deploy/defaults/main.yml` (`JWT_SECRET` sí trae el mismo valor de desarrollo que usa el compose local, `myfancysecret`, pensado para reemplazarse). Se pasan con `-e` en la línea de comandos o en un archivo de variables propio, sin versionar, de la misma forma en que `.env` (no `.env.example`) ya está fuera de git para el compose local.

## 4. Uso

```bash
cd ansible
cp inventory.example.ini inventory.ini
# completar inventory.ini con la IP que entrega terraform output vm_public_ip

ansible-playbook -i inventory.ini playbook.yml \
  -e "jwt_secret=<un-secreto-propio> sendgrid_api_key=<opcional> sendgrid_to=<opcional>"
```

`inventory.ini` queda ignorado por git (contiene la IP pública de la VM), igual que `.env` y los `.tfvars` de Terraform.

## 5. Verificación hecha sin Azure

Antes de correr esto contra la VM real, cada parte se probó por separado:

- El rol `deploy` completo, con Ansible real (módulos `file`, `copy`, `template`, `command`), contra `localhost`: la plantilla `.env` se generó con las variables correctas, `docker-compose.prod.yml` se copió como se esperaba, y `docker compose pull` más `docker compose up -d` levantaron los siete contenedores sanos usando las imágenes ya publicadas en Docker Hub, no imágenes construidas localmente.
- El rol `docker`, en la parte que agrega el repositorio apt oficial e instala los cinco paquetes, contra un contenedor real de `ubuntu:24.04` (la misma versión que aprovisiona Terraform): el repositorio resolvió los cinco paquetes para el codename `noble`, y la instalación completa terminó sin errores, con `docker --version` y `docker compose version` respondiendo.

Lo que queda pendiente es correr el playbook completo, con ambos roles encadenados, contra la VM real de Azure. Eso se hace en un único ciclo junto con las capturas finales de `docs/TERRAFORM.md` (ver sección 4 de ese documento).
