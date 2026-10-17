import { Link } from '@tanstack/react-router';

import { AddToCart } from '@/features/cart/components/AddToCart';
import { formatMoney } from '@/shared/lib/format';
import { Badge, Card } from '@/shared/ui/display';
import { ResponsiveImage } from '@/shared/ui/ResponsiveImage';

import type { Product } from '../types';
import { StockBadge } from './StockBadge';

const CARD_IMAGE_SIZES =
  '(min-width: 1280px) 296px, (min-width: 1024px) 31vw, (min-width: 640px) 47vw, calc(100vw - 2rem)';

export function ProductCard({
  product,
  priority = false,
}: {
  product: Product;
  priority?: boolean;
}) {
  return (
    <Card className="flex h-full flex-col overflow-hidden transition-shadow hover:shadow-md">
      <Link
        to="/products/$productId"
        params={{ productId: product.id }}
        tabIndex={-1}
        aria-hidden
        className="block"
      >
        <ResponsiveImage
          image={product.image}
          alt={product.name}
          sizes={CARD_IMAGE_SIZES}
          priority={priority}
          className="aspect-[4/3] w-full"
        />
      </Link>
      <div className="flex flex-1 flex-col gap-3 p-4">
        <div className="flex items-start justify-between gap-2">
          <Badge>{product.category_label}</Badge>
          <StockBadge stock={product.stock} />
        </div>
        <div>
          <h3 className="text-base font-semibold leading-snug text-fg">
            <Link
              to="/products/$productId"
              params={{ productId: product.id }}
              className="hover:text-accent-fg focus-visible:outline-none focus-visible:underline"
            >
              {product.name}
            </Link>
          </h3>
          <p className="mt-0.5 font-mono text-xs text-fg-muted">{product.sku}</p>
        </div>
        <p className="line-clamp-2 flex-1 text-sm text-fg-muted">{product.description}</p>
        <p className="text-xl font-semibold tabular-nums text-fg">
          {formatMoney(product.price, product.currency)}
        </p>
        <AddToCart product={product} size="sm" />
      </div>
    </Card>
  );
}
