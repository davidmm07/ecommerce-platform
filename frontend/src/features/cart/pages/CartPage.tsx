import { Link } from '@tanstack/react-router';
import { ShoppingBag, Trash2 } from 'lucide-react';

import { OrderSummary } from '@/features/checkout/components/OrderSummary';
import { useCartQuote } from '@/features/checkout/quote';
import { formatMoney, multiplyMoney } from '@/shared/lib/format';
import { buttonClasses } from '@/shared/ui/styles';
import { Card, EmptyState, PageHeader } from '@/shared/ui/display';
import { QuantityStepper } from '@/shared/ui/QuantityStepper';

import { cartActions, useCartLines } from '../cart-store';

export function CartPage() {
  const lines = useCartLines();
  const quote = useCartQuote(lines);

  if (lines.length === 0) {
    return (
      <>
        <PageHeader title="Your cart" />
        <EmptyState
          icon={<ShoppingBag className="size-10" aria-hidden />}
          title="Your cart is empty"
          description="Browse the catalog and add a few products."
          action={
            <Link to="/products" className={buttonClasses('primary')}>
              Continue shopping
            </Link>
          }
        />
      </>
    );
  }

  const blocked = quote.isError || quote.isPending;

  return (
    <>
      <PageHeader title="Your cart" description="Review quantities before checking out." />
      <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
        <Card className="divide-y divide-slate-100">
          {lines.map((line) => (
            <div key={line.productId} className="flex flex-wrap items-center gap-4 p-4">
              <div className="min-w-0 flex-1">
                <Link
                  to="/products/$productId"
                  params={{ productId: line.productId }}
                  className="font-medium text-slate-900 hover:text-indigo-600"
                >
                  {line.name}
                </Link>
                <p className="font-mono text-xs text-slate-500">{line.sku}</p>
                <p className="mt-1 text-sm text-slate-600">
                  {formatMoney(line.unitPrice, line.currency)} each
                </p>
              </div>
              <QuantityStepper
                value={line.quantity}
                max={line.maxQuantity}
                onChange={(quantity) => cartActions.setQuantity(line.productId, quantity)}
                label={`quantity of ${line.name}`}
                size="sm"
              />
              <p className="w-24 text-right font-medium tabular-nums text-slate-900">
                {formatMoney(multiplyMoney(line.unitPrice, line.quantity), line.currency)}
              </p>
              <button
                type="button"
                onClick={() => cartActions.remove(line.productId)}
                className="rounded-md p-2 text-slate-400 hover:bg-rose-50 hover:text-rose-600"
                aria-label={`Remove ${line.name}`}
              >
                <Trash2 className="size-4" aria-hidden />
              </button>
            </div>
          ))}
        </Card>
        <div>
          <OrderSummary
            lines={lines}
            footer={
              <Link
                to="/checkout"
                disabled={blocked}
                className={`${buttonClasses('primary', 'lg')} w-full ${blocked ? 'pointer-events-none opacity-60' : ''}`}
              >
                Proceed to checkout
              </Link>
            }
          />
        </div>
      </div>
    </>
  );
}
