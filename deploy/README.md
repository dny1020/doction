# Deploy en la Raspberry Pi (pull-based desde GHCR)

GitHub Actions construye y publica `ghcr.io/dny1020/doction` en cada push a `main`.
La Pi hace pull cada 5 minutos vía systemd timer — sin puertos expuestos, sin runners.

## Setup (una sola vez)

```bash
# 1. copiar artefactos
scp deploy/compose.yaml deploy/deploy.sh rpi:/opt/doction/
scp deploy/doction-deploy.* rpi:/tmp/

ssh rpi
chmod +x /opt/doction/deploy.sh
# /opt/doction/.env debe tener: SECRET_KEY=..., SECURE_COOKIES=1

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

## Backups

`/data` (BD SQLite + repo git de páginas + uploads) tiene todo el estado. `backup.sh` hace un
snapshot consistente sin parar la app (usa la API online de SQLite, segura con WAL) y conserva
los últimos `DOCTION_BACKUP_KEEP` (7 por defecto).

```bash
# setup (una sola vez)
scp deploy/backup.sh deploy/restore.sh rpi:/opt/doction/
scp deploy/doction-backup.* rpi:/tmp/
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
(def. `/mnt/ssd/doction-backups`), `DOCTION_BACKUP_KEEP` (def. `7`).

## Restore

```bash
# para la app, restaura el snapshot y la vuelve a levantar (pide confirmación)
sudo /opt/doction/restore.sh /mnt/ssd/doction-backups/20260618-033000
```
