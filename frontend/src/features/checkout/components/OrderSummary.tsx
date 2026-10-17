import { AlertTriangle } from 'lucide-react';
import type { ReactNode } from 'react';

import type { CartLine } from '@/features/cart/cart-store';
import { cartSubtotal } from '@/features/cart/cart-store';
import { describeError } from '@/shared/api/http';
import { formatMoney, formatWeight } from '@/shared/lib/format';
import { Card } from '@/shared/ui/display';

import { shortagesOf, useCartQuote } from '../quote';

type OrderSummaryProps = {
  lines: CartLine[];
  footer?: ReactNode;
};

export function OrderSummary({ lines, footer }: OrderSummaryProps) {
  const quote = useCartQuote(lines);
  const totals = quote.data?.totals;
  const currency = totals?.currency ?? lines[0]?.currency ?? 'USD';
  const shortages = shortagesOf(quote.error);

  return (
    <Card className="p-5">
      <h2 className="text-base font-semibold text-slate-900">Order summary</h2>
      <dl className="mt-4 space-y-3 text-sm">
        <Row
          label="Subtotal"
          value={formatMoney(totals?.subtotal ?? cartSubtotal(lines), currency)}
        />
        <Row
          label={totals ? `Shipping (${formatWeight(totals.total_weight_kg)})` : 'Shipping'}
          value={
            totals
              ? Number(totals.shipping) === 0
                ? 'Free'
                : formatMoney(totals.shipping, currency)
              : quote.isFetching
                ? 'Calculating...'
                : '-'
          }
        />
        <div className="border-t border-slate-200 pt-3">
          <Row
            label={<span className="text-base font-semibold text-slate-900">Total</span>}
            value={
              <span className="text-base font-semibold text-slate-900">
                {totals ? formatMoney(totals.total, currency) : '-'}
              </span>
            }
          />
        </div>
      </dl>
      <p className="mt-3 text-xs text-slate-500">
        Shipping is calculated per started kilogram and is free for orders over $100.
      </p>
      {quote.isError && (
        <div
          role="alert"
          className="mt-4 flex gap-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200"
        >
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          <div>
            {shortages.length > 0 ? (
              <ul className="space-y-1">
                {shortages.map((shortage) => (
                  <li key={shortage.sku}>
                    Only {shortage.available} left of {shortage.sku}, you have {shortage.requested}.
                  </li>
                ))}
              </ul>
            ) : (
              describeError(quote.error)
            )}
          </div>
        </div>
      )}
      {footer && <div className="mt-5">{footer}</div>}
    </Card>
  );
}

function Row({ label, value }: { label: ReactNode; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-slate-600">{label}</dt>
      <dd className="tabular-nums text-slate-900">{value}</dd>
    </div>
  );
}
