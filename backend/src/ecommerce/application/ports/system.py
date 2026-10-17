from collections.abc import Callable
from datetime import datetime
from typing import Protocol
from uuid import UUID


class Clock(Protocol):
    def now(self) -> datetime: ...


type IdFactory = Callable[[], UUID]
