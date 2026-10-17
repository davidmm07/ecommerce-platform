from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator
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
    media_backend: Literal["local", "s3"] = "local"
    media_root: Path = Path("var/media")
    media_base_url: str = "/media"
    media_serve: bool = False
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = None
    s3_region: str = "us-east-1"
    image_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    image_max_pixels: int = Field(default=40_000_000, ge=10_000)
    image_processing_concurrency: int = Field(default=2, ge=1, le=16)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _require_bucket_for_s3(self) -> Self:
        if self.media_backend == "s3" and not self.s3_bucket:
            raise ValueError("APP_S3_BUCKET is required when APP_MEDIA_BACKEND is s3")
        return self

    @property
    def max_request_bytes(self) -> int:
        return max(self.import_max_bytes, self.image_max_bytes) + 64 * 1024
