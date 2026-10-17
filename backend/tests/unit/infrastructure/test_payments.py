import asyncio

import pytest

from ecommerce.application.ports.payments import ChargeRequest, ChargeResult, PaymentGatewayError
from ecommerce.domain.money import Money
from ecommerce.domain.payments.card import PaymentCard
from ecommerce.infrastructure.payments.resilient import ResilientPaymentGateway
from ecommerce.infrastructure.payments.simulated import (
    FAILING_CARD,
    FLAKY_CARD,
    SimulatedPaymentGateway,
)
from tests.factories import FixedClock


def charge_request(number: str, *, key: str = "key-0001", year: int = 2030) -> ChargeRequest:
    card = PaymentCard.parse(
        number=number, expiry_month=12, expiry_year=year, cvc="123", holder_name="Ada"
    )
    return ChargeRequest(
        amount=Money.of("10.00"), card=card, reference="ORD-1", idempotency_key=key
    )


@pytest.fixture
def gateway() -> SimulatedPaymentGateway:
    return SimulatedPaymentGateway(clock=FixedClock())


async def test_approves_regular_cards(gateway: SimulatedPaymentGateway) -> None:
    result = await gateway.charge(charge_request("5555555555554444"))
    assert result.approved
    assert (result.card_brand, result.card_last4) == ("mastercard", "4444")
    assert result.reference is not None
    assert result.reference.startswith("sim_ch_")


@pytest.mark.parametrize(
    ("number", "code"),
    [
        ("4000000000000002", "card_declined"),
        ("4000000000009995", "insufficient_funds"),
        ("4000000000000069", "expired_card"),
        ("4000000000000127", "incorrect_cvc"),
    ],
)
async def test_declines_the_documented_test_cards(
    gateway: SimulatedPaymentGateway, number: str, code: str
) -> None:
    result = await gateway.charge(charge_request(number))
    assert not result.approved
    assert result.decline_code == code


async def test_declines_expired_cards(gateway: SimulatedPaymentGateway) -> None:
    result = await gateway.charge(charge_request("4242424242424242", year=2025))
    assert result.decline_code == "expired_card"


async def test_is_idempotent_per_key(gateway: SimulatedPaymentGateway) -> None:
    first = await gateway.charge(charge_request("4242424242424242", key="same-key"))
    second = await gateway.charge(charge_request("4242424242424242", key="same-key"))
    assert first == second


async def test_simulates_outages(gateway: SimulatedPaymentGateway) -> None:
    with pytest.raises(PaymentGatewayError):
        await gateway.charge(charge_request(FAILING_CARD))


async def test_resilient_gateway_retries_transient_failures(
    gateway: SimulatedPaymentGateway,
) -> None:
    resilient = ResilientPaymentGateway(gateway, max_attempts=2, backoff_seconds=0)
    result = await resilient.charge(charge_request(FLAKY_CARD))
    assert result.approved


async def test_resilient_gateway_gives_up_after_the_last_attempt(
    gateway: SimulatedPaymentGateway,
) -> None:
    resilient = ResilientPaymentGateway(gateway, max_attempts=3, backoff_seconds=0)
    with pytest.raises(PaymentGatewayError, match="outage"):
        await resilient.charge(charge_request(FAILING_CARD))


async def test_resilient_gateway_turns_timeouts_into_gateway_errors() -> None:
    class SlowGateway:
        async def charge(self, request: ChargeRequest) -> ChargeResult:
            await asyncio.sleep(1)
            raise AssertionError

    resilient = ResilientPaymentGateway(
        SlowGateway(), max_attempts=1, timeout_seconds=0.01, backoff_seconds=0
    )
    with pytest.raises(PaymentGatewayError, match="timed out"):
        await resilient.charge(charge_request("4242424242424242"))


async def test_simulated_latency_is_applied() -> None:
    slow = SimulatedPaymentGateway(clock=FixedClock(), latency_seconds=0.01)
    assert (await slow.charge(charge_request("4242424242424242"))).approved
