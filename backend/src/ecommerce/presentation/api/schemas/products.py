from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import ConfigDict, Field

from ecommerce.application.catalog.images import ImageCreditInput
from ecommerce.application.catalog.queries import (
    MAX_SEARCH_TEXT_LENGTH,
    ProductSearchCriteria,
    ProductSort,
)
from ecommerce.application.catalog.use_cases import CreateProductCommand, UpdateProductCommand
from ecommerce.application.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_NUMBER,
    MAX_PAGE_SIZE,
    PageRequest,
)
from ecommerce.domain.catalog.category import Category
from ecommerce.domain.catalog.image import MAX_URL_LENGTH, ProductImage
from ecommerce.domain.catalog.product import (
    DESCRIPTION_MAX_LENGTH,
    MAX_STOCK,
    NAME_MAX_LENGTH,
    Product,
)
from ecommerce.domain.catalog.sku import SKU_MAX_LENGTH
from ecommerce.presentation.api.media import MediaUrls
from ecommerce.presentation.api.schemas.common import ApiModel

DEFAULT_IMAGE_WIDTH = 640

Price = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2, examples=["89.99"])]
Stock = Annotated[int, Field(ge=0, le=MAX_STOCK, examples=[150])]
Weight = Annotated[Decimal, Field(ge=0, max_digits=8, decimal_places=3, examples=["0.35"])]
Name = Annotated[str, Field(min_length=1, max_length=NAME_MAX_LENGTH, examples=["Running Shoes"])]
Description = Annotated[
    str,
    Field(
        max_length=DESCRIPTION_MAX_LENGTH,
        examples=["Lightweight running shoes for daily training"],
    ),
]


class CategoryOut(ApiModel):
    value: Category
    label: str


class ProductCreate(ApiModel):
    sku: str = Field(min_length=1, max_length=SKU_MAX_LENGTH, examples=["RS-001"])
    name: Name
    description: Description = ""
    category: Category
    price: Price
    stock: Stock
    weight_kg: Weight

    def to_command(self) -> CreateProductCommand:
        return CreateProductCommand(
            sku=self.sku,
            name=self.name,
            description=self.description,
            category=self.category.value,
            price=self.price,
            stock=self.stock,
            weight_kg=self.weight_kg,
        )


class ProductUpdate(ApiModel):
    name: Name | None = None
    description: Description | None = None
    category: Category | None = None
    price: Price | None = None
    stock: Stock | None = None
    weight_kg: Weight | None = None

    def to_command(self, product_id: UUID, expected_version: int | None) -> UpdateProductCommand:
        return UpdateProductCommand(
            product_id=product_id,
            expected_version=expected_version,
            name=self.name,
            description=self.description,
            category=self.category.value if self.category else None,
            price=self.price,
            stock=self.stock,
            weight_kg=self.weight_kg,
        )


class ImageSourceOut(ApiModel):
    type: str = Field(examples=["image/avif"])
    srcset: str = Field(
        examples=[
            "/media/products/0b7c/5f1e-160.avif 160w, /media/products/0b7c/5f1e-320.avif 320w"
        ]
    )


class ImageCreditOut(ApiModel):
    author: str = Field(examples=["Jane Doe"])
    license: str = Field(examples=["CC BY 2.0"])
    source_url: str = Field(examples=["https://www.flickr.com/photos/example/123"])
    license_url: str | None = Field(examples=["https://creativecommons.org/licenses/by/2.0/"])


class ImageCreditIn(ApiModel):
    author: str = Field(min_length=1, max_length=200)
    license: str = Field(min_length=1, max_length=60)
    source_url: str = Field(min_length=1, max_length=MAX_URL_LENGTH)
    license_url: str | None = Field(default=None, max_length=MAX_URL_LENGTH)

    def to_input(self) -> ImageCreditInput:
        return ImageCreditInput(
            author=self.author,
            license=self.license,
            source_url=self.source_url,
            license_url=self.license_url,
        )


class ImageFromUrlIn(ApiModel):
    url: str = Field(
        min_length=1, max_length=MAX_URL_LENGTH, examples=["https://images.example.com/p.jpg"]
    )
    credit: ImageCreditIn | None = None


class ProductImageOut(ApiModel):
    url: str = Field(examples=["/media/products/0b7c/5f1e-640.webp"])
    width: int = Field(examples=[1280])
    height: int = Field(examples=[960])
    placeholder: str = Field(examples=["data:image/webp;base64,UklGRkIAAABXRUJQVlA4IDYAAAA"])
    sources: list[ImageSourceOut]
    credit: ImageCreditOut | None

    @classmethod
    def from_domain(cls, image: ProductImage, media: MediaUrls) -> "ProductImageOut":
        fallback_width = next(
            (width for width in image.widths if width >= DEFAULT_IMAGE_WIDTH), image.widths[-1]
        )
        fallback_format = "webp" if "webp" in image.formats else image.formats[-1]
        return cls(
            url=media.url(image.variant_key(fallback_width, fallback_format)),
            width=image.width,
            height=image.height,
            placeholder=image.placeholder,
            credit=(
                ImageCreditOut(
                    author=image.credit.author,
                    license=image.credit.license,
                    source_url=image.credit.source_url,
                    license_url=image.credit.license_url,
                )
                if image.credit
                else None
            ),
            sources=[
                ImageSourceOut(
                    type=f"image/{fmt}",
                    srcset=", ".join(
                        f"{media.url(image.variant_key(width, fmt))} {width}w"
                        for width in image.widths
                    ),
                )
                for fmt in image.formats
            ],
        )


class ProductOut(ApiModel):
    id: UUID
    sku: str
    name: str
    description: str
    category: Category
    category_label: str
    price: Decimal
    currency: str
    stock: int
    in_stock: bool
    weight_kg: Decimal
    version: int
    image: ProductImageOut | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, product: Product, media: MediaUrls) -> "ProductOut":
        return cls(
            id=product.id,
            sku=product.sku.value,
            name=product.name,
            description=product.description,
            category=product.category,
            category_label=product.category.label,
            price=product.price.amount,
            currency=product.price.currency,
            stock=product.stock,
            in_stock=product.in_stock,
            weight_kg=product.weight_kg,
            version=product.version,
            image=ProductImageOut.from_domain(product.image, media) if product.image else None,
            created_at=product.created_at,
            updated_at=product.updated_at,
        )


class ProductSearchParams(ApiModel):
    model_config = ConfigDict(extra="ignore")

    q: str | None = Field(default=None, max_length=MAX_SEARCH_TEXT_LENGTH, examples=["shoes"])
    category: Category | None = None
    min_price: Decimal | None = Field(default=None, ge=0)
    max_price: Decimal | None = Field(default=None, ge=0)
    in_stock: bool | None = None
    sort: ProductSort = ProductSort.RELEVANCE
    page: int = Field(default=1, ge=1, le=MAX_PAGE_NUMBER)
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)

    def to_criteria(self) -> ProductSearchCriteria:
        return ProductSearchCriteria(
            text=self.q,
            category=self.category,
            min_price=self.min_price,
            max_price=self.max_price,
            in_stock=self.in_stock,
            sort=self.sort,
            page=PageRequest(self.page, self.page_size),
        )
