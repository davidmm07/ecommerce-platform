import asyncio
import logging
from collections import Counter, OrderedDict
from uuid import uuid4

from ecommerce.application.ports.payments import ChargeRequest, ChargeResult, PaymentGatewayError
from ecommerce.application.ports.system import Clock

DECLINING_CARDS = {
    "4000000000000002": "card_declined",
    "4000000000009995": "insufficient_funds",
    "4000000000000069": "expired_card",
    "4000000000000127": "incorrect_cvc",
}
FAILING_CARD = "4000000000000119"
FLAKY_CARD = "4000000000000259"
_MAX_REMEMBERED = 10_000

logger = logging.getLogger(__name__)


class SimulatedPaymentGateway:
    def __init__(self, *, clock: Clock, latency_seconds: float = 0.0) -> None:
        self._clock = clock
        self._latency_seconds = latency_seconds
        self._results: OrderedDict[str, ChargeResult] = OrderedDict()
        self._attempts: Counter[str] = Counter()

    async def charge(self, request: ChargeRequest) -> ChargeResult:
        remembered = self._results.get(request.idempotency_key)
        if remembered is not None:
            return remembered
        if self._latency_seconds:
            await asyncio.sleep(self._latency_seconds)
        card = request.card
        self._attempts[request.idempotency_key] += 1
        if card.number == FAILING_CARD:
            raise PaymentGatewayError("simulated provider outage")
        if card.number == FLAKY_CARD and self._attempts[request.idempotency_key] == 1:
            raise PaymentGatewayError("simulated transient network error")
        decline_code = self._decline_code_for(request)
        result = ChargeResult(
            approved=decline_code is None,
            card_brand=card.brand.value,
            card_last4=card.last4,
            reference=f"sim_ch_{uuid4().hex[:24]}",
            decline_code=decline_code,
        )
        self._remember(request.idempotency_key, result)
        logger.info(
            "simulated charge processed",
            extra={
                "payment_reference": result.reference,
                "order_number": request.reference,
                "amount": str(request.amount.amount),
                "approved": result.approved,
            },
        )
        return result

    def _decline_code_for(self, request: ChargeRequest) -> str | None:
        card = request.card
        if card.is_expired(self._clock.now().date()):
            return "expired_card"
        return DECLINING_CARDS.get(card.number)

    def _remember(self, key: str, result: ChargeResult) -> None:
        self._results[key] = result
        self._attempts.pop(key, None)
        while len(self._results) > _MAX_REMEMBERED:
            self._results.popitem(last=False)
