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
