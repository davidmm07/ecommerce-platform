import { useSuspenseQuery } from '@tanstack/react-query';
import { Link, getRouteApi } from '@tanstack/react-router';
import { ArrowLeft, Pencil } from 'lucide-react';

import { AddToCart } from '@/features/cart/components/AddToCart';
import { formatMoney, formatWeight } from '@/shared/lib/format';
import { buttonClasses } from '@/shared/ui/styles';
import { Badge, Card } from '@/shared/ui/display';
import { ResponsiveImage } from '@/shared/ui/ResponsiveImage';

import { StockBadge } from '../components/StockBadge';
import { productQuery } from '../queries';

const route = getRouteApi('/products/$productId');

export function ProductDetailPage() {
  const { productId } = route.useParams();
  const { data: product } = useSuspenseQuery(productQuery(productId));

  return (
    <div className="space-y-6">
      <Link to="/products" className={buttonClasses('ghost', 'sm')}>
        <ArrowLeft className="size-4" aria-hidden />
        Back to shop
      </Link>
      <Card className="grid overflow-hidden md:grid-cols-2">
        <ResponsiveImage
          image={product.image}
          alt={product.name}
          sizes="(min-width: 1280px) 616px, (min-width: 768px) 50vw, 100vw"
          priority
          fit="contain"
          className="aspect-[4/3] w-full md:aspect-auto md:min-h-96"
        />
        <div className="space-y-5 p-6 md:p-8">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>{product.category_label}</Badge>
            <StockBadge stock={product.stock} />
          </div>
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-fg">{product.name}</h1>
            <p className="mt-1 font-mono text-sm text-fg-muted">SKU {product.sku}</p>
          </div>
          <p className="text-3xl font-semibold tabular-nums text-fg">
            {formatMoney(product.price, product.currency)}
          </p>
          {product.description && (
            <p className="whitespace-pre-line text-fg-secondary">{product.description}</p>
          )}
          <dl className="grid grid-cols-2 gap-4 rounded-lg bg-surface-muted p-4 text-sm">
            <div>
              <dt className="text-fg-muted">Available units</dt>
              <dd className="font-medium tabular-nums text-fg">{product.stock}</dd>
            </div>
            <div>
              <dt className="text-fg-muted">Shipping weight</dt>
              <dd className="font-medium text-fg">{formatWeight(product.weight_kg)}</dd>
            </div>
          </dl>
          <AddToCart product={product} />
          <Link
            to="/admin/products/$productId/edit"
            params={{ productId: product.id }}
            className={buttonClasses('ghost', 'sm')}
          >
            <Pencil className="size-4" aria-hidden />
            Edit in admin
          </Link>
        </div>
      </Card>
    </div>
  );
}
