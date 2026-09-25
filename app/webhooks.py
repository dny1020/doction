"""Outgoing webhook delivery: HMAC signature plus retries with backoff.

`db.emit_event()` only queues; this worker delivers, so no HTTP runs on the request path.
Destinations are unfiltered on purpose: internal services (n8n) are the use case, and only
an authenticated user can register a webhook.
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
    """Sign the body so the receiver can verify where it came from."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def deliver(item: PendingDelivery) -> tuple[bool, str]:
    """Send one delivery, returning (ok, detail). Never raises."""
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
        # The receiver answered with an error: retryable, it may be redeploying.
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # timeout, DNS, connection refused...
        return False, f"{type(exc).__name__}: {exc}"


async def delivery_worker(*, interval: float = 5.0, batch: int = 10) -> None:
    """Drain the pending delivery queue without blocking the event loop."""
    logger.info("webhook delivery worker started")
    while True:
        try:
            pending = await asyncio.to_thread(db.due_deliveries, batch)
            if not pending:
                await asyncio.sleep(interval)
                continue
            for item in pending:
                # Per delivery, so one broken receiver cannot block the queue.
                try:
                    ok, detail = await asyncio.to_thread(deliver, item)
                    if ok:
                        await asyncio.to_thread(db.mark_delivered, item.id, item.webhook_id, detail)
                    else:
                        await asyncio.to_thread(
                            db.mark_failed, item.id, item.webhook_id, detail, item.attempts
                        )
                        logger.warning(
                            "webhook %s: delivery %s failed (%s), attempt %s of %s",
                            item.webhook_id,
                            item.id,
                            detail,
                            item.attempts + 1,
                            db.MAX_DELIVERY_ATTEMPTS,
                        )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("unexpected error delivering %s", item.id)
        except asyncio.CancelledError:
            logger.info("webhook delivery worker stopped")
            raise
        except Exception:
            logger.exception("webhook delivery worker error; retrying")
            await asyncio.sleep(interval)


__all__ = ["deliver", "delivery_worker", "sign"]
