from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    environment: Literal["local", "test", "production"] = "local"
    database_url: str
    database_pool_size: int = Field(default=10, ge=1, le=100)
    database_echo: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "text"] = "json"
    docs_enabled: bool = True
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )
    shipping_base_fee: Decimal = Field(default=Decimal("4.99"), ge=0, decimal_places=2)
    shipping_per_kg_fee: Decimal = Field(default=Decimal("1.25"), ge=0, decimal_places=2)
    free_shipping_threshold: Decimal = Field(default=Decimal("100.00"), ge=0, decimal_places=2)
    payment_latency_ms: int = Field(default=400, ge=0, le=10_000)
    payment_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    payment_max_attempts: int = Field(default=3, ge=1, le=5)
    import_max_bytes: int = Field(default=5 * 1024 * 1024, ge=1024)
    import_max_rows: int = Field(default=5_000, ge=1)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def max_request_bytes(self) -> int:
        return self.import_max_bytes + 64 * 1024
