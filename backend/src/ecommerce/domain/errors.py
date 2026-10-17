from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any


class DomainError(Exception):
    code = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def details(self) -> dict[str, Any]:
        return {}


class InvalidValue(DomainError):
    code = "invalid_value"


@dataclass(frozen=True, slots=True)
class FieldError:
    field: str
    message: str


class DomainValidationError(DomainError):
    code = "validation_failed"

    def __init__(self, errors: Sequence[FieldError]) -> None:
        super().__init__("; ".join(f"{error.field}: {error.message}" for error in errors))
        self.errors = tuple(errors)

    def details(self) -> dict[str, Any]:
        return {"errors": [{"field": e.field, "message": e.message} for e in self.errors]}


class FieldErrors:
    def __init__(self) -> None:
        self._errors: list[FieldError] = []

    @contextmanager
    def collect(self, field: str = "") -> Iterator[None]:
        try:
            yield
        except DomainValidationError as exc:
            self._errors.extend(
                FieldError(f"{field}.{error.field}" if field else error.field, error.message)
                for error in exc.errors
            )
        except InvalidValue as exc:
            self._errors.append(FieldError(field or "value", exc.message))

    def add(self, field: str, message: str) -> None:
        self._errors.append(FieldError(field, message))

    @property
    def errors(self) -> tuple[FieldError, ...]:
        return tuple(self._errors)

    def __bool__(self) -> bool:
        return bool(self._errors)

    def raise_if_any(self) -> None:
        if self._errors:
            raise DomainValidationError(self._errors)
