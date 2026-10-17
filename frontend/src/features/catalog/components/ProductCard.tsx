import { Link } from '@tanstack/react-router';
import { Package } from 'lucide-react';

import { AddToCart } from '@/features/cart/components/AddToCart';
import { formatMoney } from '@/shared/lib/format';
import { Badge, Card } from '@/shared/ui/display';

import type { Product } from '../types';
import { StockBadge } from './StockBadge';

export function ProductCard({ product }: { product: Product }) {
  return (
    <Card className="flex h-full flex-col overflow-hidden transition-shadow hover:shadow-md">
      <div className="flex h-28 items-center justify-center bg-gradient-to-br from-indigo-50 via-white to-slate-100">
        <Package className="size-10 text-indigo-300" aria-hidden />
      </div>
      <div className="flex flex-1 flex-col gap-3 p-4">
        <div className="flex items-start justify-between gap-2">
          <Badge>{product.category_label}</Badge>
          <StockBadge stock={product.stock} />
        </div>
        <div>
          <h3 className="text-base font-semibold leading-snug text-slate-900">
            <Link
              to="/products/$productId"
              params={{ productId: product.id }}
              className="hover:text-indigo-600 focus-visible:outline-none focus-visible:underline"
            >
              {product.name}
            </Link>
          </h3>
          <p className="mt-0.5 font-mono text-xs text-slate-500">{product.sku}</p>
        </div>
        <p className="line-clamp-2 flex-1 text-sm text-slate-600">{product.description}</p>
        <p className="text-xl font-semibold tabular-nums text-slate-900">
          {formatMoney(product.price, product.currency)}
        </p>
        <AddToCart product={product} size="sm" />
      </div>
    </Card>
  );
}
