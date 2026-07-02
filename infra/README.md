# Deploy en la Raspberry Pi (pull-based desde GHCR)

GitHub Actions construye y publica `ghcr.io/dny1020/doction` en cada push a `main`.
La Pi hace pull cada 5 minutos vía systemd timer — sin puertos expuestos, sin runners.

## Setup (una sola vez)

```bash
# 1. copiar artefactos
scp infra/compose.yaml infra/deploy.sh rpi:/opt/doction/
scp infra/doction-deploy.* rpi:/tmp/

ssh rpi
mkdir -p /mnt/ssd/doction/postgres   # volumen de Postgres, anidado bajo el mismo /mnt/ssd/doction
chmod +x /opt/doction/deploy.sh
# /opt/doction/.env debe tener: POSTGRES_PASSWORD=..., SECRET_KEY=..., SECURE_COOKIES=1

# 2. instalar el timer
sudo mv /tmp/doction-deploy.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now doction-deploy.timer

# 3. primer deploy + verificación
sudo systemctl start doction-deploy.service
journalctl -u doction-deploy -n 20
```

## Operación

```bash
systemctl list-timers doction-deploy.timer   # próxima ejecución
journalctl -u doction-deploy -f              # logs de deploys
sudo systemctl start doction-deploy.service  # forzar deploy ahora
```

## Rollback

```bash
# pin a una versión anterior publicada en GHCR
sed -i 's|doction:latest|doction:0.7|' /opt/doction/compose.yaml
sudo systemctl start doction-deploy.service
# (revertir el pin después de arreglar main)
```

## Migración a PostgreSQL (una sola vez, si vienes de una versión con SQLite)

```bash
ssh rpi
docker exec doction-postgres pg_isready -U doction   # confirma que postgres ya está arriba
docker exec doction python -m scripts.migrate_sqlite_to_postgres /data/doction.db
```

Corre una sola vez, justo después del primer `docker compose up -d` con el `compose.yaml`
nuevo — `doction` ya trae `DATABASE_URL` apuntando al `postgres` del compose, así que el
script lo usa tal cual. `/mnt/ssd/doction:/data` ya monta `doction.db` dentro del
contenedor en `/data/doction.db`, no hace falta copiarlo. Se niega a correr si el Postgres
destino ya tiene usuarios (evita duplicar datos si se corre dos veces por error). El
`doction.db` original en `/mnt/ssd/doction` queda intacto por si hay que volver atrás.

## Backups

El estado vive en dos sitios: Postgres (BD) y `/data` (repo git de páginas + uploads).
`backup.sh` hace un dump consistente de Postgres (`pg_dump`, vía MVCC, sin parar nada) +
tar de `pages/`/`uploads/`, y conserva los últimos `DOCTION_BACKUP_KEEP` (7 por defecto).

```bash
# setup (una sola vez)
scp infra/backup.sh infra/restore.sh rpi:/opt/doction/
scp infra/doction-backup.* rpi:/tmp/
ssh rpi
chmod +x /opt/doction/backup.sh /opt/doction/restore.sh
sudo mv /tmp/doction-backup.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now doction-backup.timer   # diario 03:30

# a mano
sudo /opt/doction/backup.sh                        # snapshot ahora
ls /mnt/ssd/doction-backups                         # snapshots disponibles
```

Variables: `DOCTION_DATA` (def. `/mnt/ssd/doction`), `DOCTION_BACKUP_DIR`
(def. `/mnt/ssd/doction-backups`), `DOCTION_BACKUP_KEEP` (def. `7`), `DOCTION_PG_CONTAINER`
(def. `doction-postgres`), `POSTGRES_USER`/`POSTGRES_DB` (def. `doction`/`doction`).

## Restore

```bash
# para la app, restaura el snapshot y la vuelve a levantar (pide confirmación)
sudo /opt/doction/restore.sh /mnt/ssd/doction-backups/20260618-033000
```

## Logs

`app/logging_config.py` manda a consola (`docker logs doction` / `journalctl` vía el
driver de Docker) y a archivo rotado (10 MB × 5) en `/mnt/ssd/doction/logs` (montado
como `/logs` en el contenedor). `backup.sh` solo empaqueta `pages/` y `uploads/`
puntualmente, así que esta carpeta no entra en los backups aunque viva anidada bajo
`/mnt/ssd/doction`. Nivel controlable con `LOG_LEVEL` en `/opt/doction/.env` (`INFO`
por defecto).

```bash
mkdir -p /mnt/ssd/doction/logs   # una sola vez, si no existe
tail -f /mnt/ssd/doction/logs/doction.log
```
