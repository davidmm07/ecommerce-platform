from typing import Any
from uuid import UUID


class ApplicationError(Exception):
    code = "application_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def details(self) -> dict[str, Any]:
        return {}


class NotFoundError(ApplicationError):
    code = "not_found"

    def __init__(self, resource: str, identifier: object) -> None:
        super().__init__(f"{resource} {identifier} was not found")
        self.resource = resource
        self.identifier = str(identifier)

    def details(self) -> dict[str, Any]:
        return {"resource": self.resource, "id": self.identifier}


class ConflictError(ApplicationError):
    code = "conflict"


class DuplicateSku(ConflictError):
    code = "duplicate_sku"

    def __init__(self, sku: str) -> None:
        super().__init__(f"A product with SKU {sku} already exists")
        self.sku = sku

    def details(self) -> dict[str, Any]:
        return {"sku": self.sku}


class ConcurrentModification(ConflictError):
    code = "concurrent_modification"

    def __init__(self, resource: str) -> None:
        super().__init__(f"The {resource} was modified by another request, retry with fresh data")


class IdempotencyKeyReused(ConflictError):
    code = "idempotency_key_reused"

    def __init__(self) -> None:
        super().__init__("This Idempotency-Key was already used with a different request body")


class RequestInProgress(ConflictError):
    code = "request_in_progress"

    def __init__(self) -> None:
        super().__init__("A request with this Idempotency-Key is still being processed")


class VersionMismatch(ApplicationError):
    code = "version_mismatch"

    def __init__(self, expected: int, current: int) -> None:
        super().__init__(f"Expected version {expected} but the current version is {current}")
        self.expected = expected
        self.current = current

    def details(self) -> dict[str, Any]:
        return {"expected_version": self.expected, "current_version": self.current}


class PaymentDeclined(ApplicationError):
    code = "payment_declined"

    def __init__(self, order_id: UUID, order_number: str, decline_code: str) -> None:
        super().__init__(f"The payment for order {order_number} was declined ({decline_code})")
        self.order_id = order_id
        self.order_number = order_number
        self.decline_code = decline_code

    def details(self) -> dict[str, Any]:
        return {
            "order_id": str(self.order_id),
            "order_number": self.order_number,
            "decline_code": self.decline_code,
        }


class PaymentUnavailable(ApplicationError):
    code = "payment_unavailable"

    def __init__(self, order_id: UUID, order_number: str) -> None:
        super().__init__(
            f"The payment provider could not process order {order_number}, no charge was made"
        )
        self.order_id = order_id
        self.order_number = order_number

    def details(self) -> dict[str, Any]:
        return {"order_id": str(self.order_id), "order_number": self.order_number}


class InvalidImportFile(ApplicationError):
    code = "invalid_import_file"


class ImportLimitExceeded(ApplicationError):
    code = "import_limit_exceeded"
