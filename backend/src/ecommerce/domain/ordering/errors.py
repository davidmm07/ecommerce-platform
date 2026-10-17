from typing import Any

from ecommerce.domain.errors import DomainError


class InvalidOrderTransition(DomainError):
    code = "invalid_order_transition"

    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"Cannot move an order from {current} to {target}")
        self.current = current
        self.target = target

    def details(self) -> dict[str, Any]:
        return {"current_status": self.current, "target_status": self.target}
