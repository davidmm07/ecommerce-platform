from uuid import uuid4

from ecommerce.application.catalog.images import (
    ImportProductImages,
    RemoveProductImage,
    ReplaceProductImage,
)
from ecommerce.application.catalog.use_cases import (
    ArchiveProduct,
    CreateProduct,
    GetProduct,
    SearchProducts,
    UpdateProduct,
)
from ecommerce.application.imports.use_case import ImportProducts
from ecommerce.application.ordering.cart import QuoteCart
from ecommerce.application.ordering.place_order import PlaceOrder
from ecommerce.application.ordering.queries import GetOrder, ListOrders
from ecommerce.application.ports.media import ImageProcessor, ObjectStorage
from ecommerce.application.ports.payments import PaymentGateway
from ecommerce.application.ports.system import Clock
from ecommerce.application.ports.unit_of_work import UnitOfWork
from ecommerce.domain.money import Money
from ecommerce.domain.ordering.pricing import (
    FreeShippingOverThreshold,
    ShippingPolicy,
    WeightBasedShipping,
)
from ecommerce.infrastructure.clock import SystemClock
from ecommerce.infrastructure.config import Settings
from ecommerce.infrastructure.files.csv_reader import CsvProductTableReader
from ecommerce.infrastructure.images.pillow_processor import PillowImageProcessor
from ecommerce.infrastructure.payments.resilient import ResilientPaymentGateway
from ecommerce.infrastructure.payments.simulated import SimulatedPaymentGateway
from ecommerce.infrastructure.persistence.database import (
    create_engine,
    create_session_factory,
    database_is_ready,
)
from ecommerce.infrastructure.persistence.read_models import (
    SqlAlchemyCatalogReadModel,
    SqlAlchemyOrderReadModel,
)
from ecommerce.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from ecommerce.infrastructure.storage.local import LocalObjectStorage
from ecommerce.infrastructure.storage.s3 import S3ObjectStorage, create_s3_client


class Container:
    def __init__(
        self,
        settings: Settings,
        *,
        clock: Clock | None = None,
        payment_gateway: PaymentGateway | None = None,
        storage: ObjectStorage | None = None,
        image_processor: ImageProcessor | None = None,
    ) -> None:
        self.settings = settings
        self.engine = create_engine(
            settings.database_url,
            pool_size=settings.database_pool_size,
            echo=settings.database_echo,
        )
        self._session_factory = create_session_factory(self.engine)
        self.clock = clock or SystemClock()
        self.payment_gateway = payment_gateway or self._build_payment_gateway()
        self.shipping_policy = self._build_shipping_policy()
        self.storage = storage or self._build_storage()
        self.image_processor = image_processor or PillowImageProcessor(
            max_pixels=settings.image_max_pixels,
            max_concurrency=settings.image_processing_concurrency,
        )

        uow_factory = self.unit_of_work
        self.create_product = CreateProduct(uow_factory=uow_factory, clock=self.clock, new_id=uuid4)
        self.update_product = UpdateProduct(uow_factory=uow_factory, clock=self.clock)
        self.archive_product = ArchiveProduct(uow_factory=uow_factory, clock=self.clock)
        self.get_product = GetProduct(uow_factory=uow_factory)
        self.search_products = SearchProducts(
            catalog=SqlAlchemyCatalogReadModel(self._session_factory)
        )
        self.import_products = ImportProducts(
            uow_factory=uow_factory,
            reader=CsvProductTableReader(),
            clock=self.clock,
            new_id=uuid4,
            max_rows=settings.import_max_rows,
        )
        self.replace_product_image = ReplaceProductImage(
            uow_factory=uow_factory,
            processor=self.image_processor,
            storage=self.storage,
            clock=self.clock,
            max_bytes=settings.image_max_bytes,
        )
        self.remove_product_image = RemoveProductImage(
            uow_factory=uow_factory, storage=self.storage, clock=self.clock
        )
        self.import_product_images = ImportProductImages(
            uow_factory=uow_factory, replace_image=self.replace_product_image
        )
        self.quote_cart = QuoteCart(uow_factory=uow_factory, shipping_policy=self.shipping_policy)
        self.place_order = PlaceOrder(
            uow_factory=uow_factory,
            payment_gateway=self.payment_gateway,
            shipping_policy=self.shipping_policy,
            clock=self.clock,
            new_id=uuid4,
        )
        self.get_order = GetOrder(uow_factory=uow_factory)
        self.list_orders = ListOrders(orders=SqlAlchemyOrderReadModel(self._session_factory))

    def unit_of_work(self) -> UnitOfWork:
        return SqlAlchemyUnitOfWork(self._session_factory)

    async def database_is_ready(self) -> bool:
        return await database_is_ready(self.engine)

    async def aclose(self) -> None:
        await self.engine.dispose()

    def _build_payment_gateway(self) -> PaymentGateway:
        simulated = SimulatedPaymentGateway(
            clock=self.clock, latency_seconds=self.settings.payment_latency_ms / 1000
        )
        return ResilientPaymentGateway(
            simulated,
            max_attempts=self.settings.payment_max_attempts,
            timeout_seconds=self.settings.payment_timeout_seconds,
        )

    def _build_storage(self) -> ObjectStorage:
        settings = self.settings
        if settings.media_backend == "s3" and settings.s3_bucket:
            client = create_s3_client(
                region=settings.s3_region, endpoint_url=settings.s3_endpoint_url
            )
            return S3ObjectStorage(client=client, bucket=settings.s3_bucket)
        return LocalObjectStorage(settings.media_root)

    def _build_shipping_policy(self) -> ShippingPolicy:
        return FreeShippingOverThreshold(
            inner=WeightBasedShipping(
                base_fee=Money(self.settings.shipping_base_fee),
                per_kg_fee=Money(self.settings.shipping_per_kg_fee),
            ),
            threshold=Money(self.settings.free_shipping_threshold),
        )
