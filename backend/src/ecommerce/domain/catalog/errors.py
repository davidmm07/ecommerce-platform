from dataclasses import dataclass
from typing import Any

from ecommerce.domain.errors import DomainError


@dataclass(frozen=True, slots=True)
class StockShortage:
    sku: str
    requested: int
    available: int


class InsufficientStock(DomainError):
    code = "insufficient_stock"

    def __init__(self, shortages: tuple[StockShortage, ...]) -> None:
        skus = ", ".join(shortage.sku for shortage in shortages)
        super().__init__(f"Not enough stock for: {skus}")
        self.shortages = shortages

    def details(self) -> dict[str, Any]:
        return {
            "shortages": [
                {"sku": s.sku, "requested": s.requested, "available": s.available}
                for s in self.shortages
            ]
        }


class ProductUnavailable(DomainError):
    code = "product_unavailable"

    def __init__(self, sku: str) -> None:
        super().__init__(f"Product {sku} is no longer available")
        self.sku = sku

    def details(self) -> dict[str, Any]:
        return {"sku": self.sku}
