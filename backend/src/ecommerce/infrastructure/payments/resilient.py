import asyncio
import logging

from ecommerce.application.ports.payments import (
    ChargeRequest,
    ChargeResult,
    PaymentGateway,
    PaymentGatewayError,
)

logger = logging.getLogger(__name__)


class ResilientPaymentGateway:
    def __init__(
        self,
        inner: PaymentGateway,
        *,
        max_attempts: int = 3,
        timeout_seconds: float = 5.0,
        backoff_seconds: float = 0.2,
    ) -> None:
        self._inner = inner
        self._max_attempts = max_attempts
        self._timeout_seconds = timeout_seconds
        self._backoff_seconds = backoff_seconds

    async def charge(self, request: ChargeRequest) -> ChargeResult:
        attempt = 1
        while True:
            try:
                async with asyncio.timeout(self._timeout_seconds):
                    return await self._inner.charge(request)
            except (PaymentGatewayError, TimeoutError) as exc:
                if attempt >= self._max_attempts:
                    raise PaymentGatewayError(str(exc) or "payment provider timed out") from exc
                logger.warning(
                    "retrying payment",
                    extra={"order_number": request.reference, "attempt": attempt},
                )
                await asyncio.sleep(self._backoff_seconds * 2 ** (attempt - 1))
                attempt += 1
