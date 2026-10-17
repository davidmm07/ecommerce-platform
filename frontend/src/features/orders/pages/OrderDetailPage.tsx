import { useSuspenseQuery } from '@tanstack/react-query';
import { Link, getRouteApi } from '@tanstack/react-router';
import { ArrowLeft, CheckCircle2, XCircle } from 'lucide-react';

import { brandLabel } from '@/features/checkout/card';
import { formatDateTime, formatMoney, formatWeight } from '@/shared/lib/format';
import { buttonClasses } from '@/shared/ui/styles';
import { Card } from '@/shared/ui/display';

import { orderQuery } from '../api';
import { OrderStatusBadge } from '../components/OrderStatusBadge';

const route = getRouteApi('/orders/$orderId');

export function OrderDetailPage() {
  const { orderId } = route.useParams();
  const { placed } = route.useSearch();
  const { data: order } = useSuspenseQuery(orderQuery(orderId));
  const currency = order.totals.currency;

  return (
    <div className="space-y-6">
      <Link to="/orders" className={buttonClasses('ghost', 'sm')}>
        <ArrowLeft className="size-4" aria-hidden />
        All orders
      </Link>
      {placed && order.status === 'paid' && (
        <div className="flex items-start gap-3 rounded-xl bg-emerald-50 p-4 text-emerald-900 ring-1 ring-emerald-200">
          <CheckCircle2 className="mt-0.5 size-5 shrink-0" aria-hidden />
          <div>
            <p className="font-semibold">Thank you, your order is confirmed.</p>
            <p className="text-sm">
              A confirmation for {order.number} would be sent to {order.customer.email}.
            </p>
          </div>
        </div>
      )}
      {order.status === 'payment_failed' && (
        <div className="flex items-start gap-3 rounded-xl bg-rose-50 p-4 text-rose-900 ring-1 ring-rose-200">
          <XCircle className="mt-0.5 size-5 shrink-0" aria-hidden />
          <p className="text-sm">
            The payment failed ({order.payment?.failure_code ?? 'unknown reason'}). The reserved
            stock was released and nothing was charged.
          </p>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="font-mono text-2xl font-semibold text-slate-900">{order.number}</h1>
        <OrderStatusBadge status={order.status} />
        <span className="text-sm text-slate-500">{formatDateTime(order.created_at)}</span>
      </div>
      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <Card className="self-start overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
              <tr>
                <th scope="col" className="px-4 py-3">
                  Product
                </th>
                <th scope="col" className="px-4 py-3 text-right">
                  Unit price
                </th>
                <th scope="col" className="px-4 py-3 text-right">
                  Qty
                </th>
                <th scope="col" className="px-4 py-3 text-right">
                  Total
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {order.lines.map((line) => (
                <tr key={line.product_id}>
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-900">{line.name}</p>
                    <p className="font-mono text-xs text-slate-500">{line.sku}</p>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {formatMoney(line.unit_price, currency)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{line.quantity}</td>
                  <td className="px-4 py-3 text-right font-medium tabular-nums">
                    {formatMoney(line.line_total, currency)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <div className="space-y-4">
          <Card className="space-y-2 p-5 text-sm">
            <h2 className="text-base font-semibold text-slate-900">Totals</h2>
            <Line label="Subtotal" value={formatMoney(order.totals.subtotal, currency)} />
            <Line
              label={`Shipping (${formatWeight(order.totals.total_weight_kg)})`}
              value={
                Number(order.totals.shipping) === 0
                  ? 'Free'
                  : formatMoney(order.totals.shipping, currency)
              }
            />
            <div className="border-t border-slate-200 pt-2 font-semibold text-slate-900">
              <Line label="Total" value={formatMoney(order.totals.total, currency)} />
            </div>
          </Card>
          <Card className="space-y-1 p-5 text-sm text-slate-700">
            <h2 className="mb-1 text-base font-semibold text-slate-900">Ship to</h2>
            <p>{order.customer.name}</p>
            <p>{order.shipping_address.line1}</p>
            <p>
              {order.shipping_address.postal_code} {order.shipping_address.city},{' '}
              {order.shipping_address.country}
            </p>
            <p className="text-slate-500">{order.customer.email}</p>
          </Card>
          {order.payment && (
            <Card className="space-y-1 p-5 text-sm text-slate-700">
              <h2 className="mb-1 text-base font-semibold text-slate-900">Payment</h2>
              <p>
                {brandLabel(order.payment.card_brand)} ending in {order.payment.card_last4}
              </p>
              {order.payment.reference && (
                <p className="font-mono text-xs text-slate-500">{order.payment.reference}</p>
              )}
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function Line({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-slate-600">{label}</span>
      <span className="tabular-nums">{value}</span>
    </div>
  );
}
