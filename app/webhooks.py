"""Entrega de webhooks de salida: firma HMAC + reintentos con backoff.

Sin dependencias nuevas: `urllib.request` de la stdlib dentro de un hilo, igual
que `mcp.py` no usa SDK y `graph.py` no usa NetworkX. Es la primera llamada HTTP
saliente del proyecto, y por eso vive aislada aquí y nunca en el camino de la
petición: `db.emit_event()` solo encola, y este worker entrega aparte.

Sobre SSRF: **no se filtran destinos a propósito**. El caso de uso es justamente
publicar hacia servicios de la red interna (n8n en `http://n8n:5678`), así que
bloquear direcciones privadas rompería la función. Solo un usuario autenticado
puede registrar un webhook; ese es el límite de confianza.
"""

import asyncio
import hashlib
import hmac
import logging
import urllib.error
import urllib.request

from app import db
from app.models import PendingDelivery
from app.version import VERSION

logger = logging.getLogger(__name__)

TIMEOUT = 10.0


def sign(secret: str, body: bytes) -> str:
    """Firma del cuerpo, para que el receptor pueda verificar el origen."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def deliver(item: PendingDelivery) -> tuple[bool, str]:
    """Envía una entrega. Devuelve (ok, detalle). Nunca lanza."""
    body = item.payload_json.encode("utf-8")
    request = urllib.request.Request(
        item.url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": f"doction/{VERSION}",
            "X-Doction-Event": item.event,
            "X-Doction-Delivery": str(item.id),
            "X-Doction-Signature": sign(item.secret, body),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return True, f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        # El receptor respondió, pero con error: reintentable (puede estar caído
        # temporalmente o desplegándose).
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # timeout, DNS, conexión rechazada…
        return False, f"{type(exc).__name__}: {exc}"


async def delivery_worker(*, interval: float = 5.0, batch: int = 10) -> None:
    """Drena la cola de entregas pendientes sin bloquear el loop."""
    logger.info("webhook delivery worker iniciado")
    while True:
        try:
            pending = await asyncio.to_thread(db.due_deliveries, batch)
            if not pending:
                await asyncio.sleep(interval)
                continue
            for item in pending:
                # try/except por entrega: un receptor roto no puede bloquear la
                # cola del resto, que es lo que pasaría con un fallo al vuelo.
                try:
                    ok, detail = await asyncio.to_thread(deliver, item)
                    if ok:
                        await asyncio.to_thread(db.mark_delivered, item.id, item.webhook_id, detail)
                    else:
                        await asyncio.to_thread(
                            db.mark_failed, item.id, item.webhook_id, detail, item.attempts
                        )
                        logger.warning(
                            "webhook %s: entrega %s falló (%s), intento %s de %s",
                            item.webhook_id,
                            item.id,
                            detail,
                            item.attempts + 1,
                            db.MAX_DELIVERY_ATTEMPTS,
                        )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("error inesperado entregando %s", item.id)
        except asyncio.CancelledError:
            logger.info("webhook delivery worker detenido")
            raise
        except Exception:
            logger.exception("webhook delivery worker error; reintentando")
            await asyncio.sleep(interval)


__all__ = ["deliver", "delivery_worker", "sign"]
