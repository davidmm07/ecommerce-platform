import { useSuspenseQuery } from '@tanstack/react-query';
import { Link, getRouteApi } from '@tanstack/react-router';
import { ArrowLeft, Package, Pencil } from 'lucide-react';

import { AddToCart } from '@/features/cart/components/AddToCart';
import { formatMoney, formatWeight } from '@/shared/lib/format';
import { buttonClasses } from '@/shared/ui/styles';
import { Badge, Card } from '@/shared/ui/display';

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
        <div className="flex min-h-64 items-center justify-center bg-gradient-to-br from-indigo-50 via-white to-slate-100">
          <Package className="size-24 text-indigo-300" aria-hidden />
        </div>
        <div className="space-y-5 p-6 md:p-8">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>{product.category_label}</Badge>
            <StockBadge stock={product.stock} />
          </div>
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-slate-900">{product.name}</h1>
            <p className="mt-1 font-mono text-sm text-slate-500">SKU {product.sku}</p>
          </div>
          <p className="text-3xl font-semibold tabular-nums text-slate-900">
            {formatMoney(product.price, product.currency)}
          </p>
          {product.description && (
            <p className="whitespace-pre-line text-slate-700">{product.description}</p>
          )}
          <dl className="grid grid-cols-2 gap-4 rounded-lg bg-slate-50 p-4 text-sm">
            <div>
              <dt className="text-slate-500">Available units</dt>
              <dd className="font-medium tabular-nums text-slate-900">{product.stock}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Shipping weight</dt>
              <dd className="font-medium text-slate-900">{formatWeight(product.weight_kg)}</dd>
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
