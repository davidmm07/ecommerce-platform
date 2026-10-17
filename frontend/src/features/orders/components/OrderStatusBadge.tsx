import { Badge } from '@/shared/ui/display';

import type { OrderStatus } from '../types';

const STATUS: Record<OrderStatus, { label: string; tone: 'success' | 'danger' | 'warning' }> = {
  paid: { label: 'Paid', tone: 'success' },
  payment_failed: { label: 'Payment failed', tone: 'danger' },
  pending_payment: { label: 'Pending payment', tone: 'warning' },
};

export function OrderStatusBadge({ status }: { status: OrderStatus }) {
  const { label, tone } = STATUS[status];
  return <Badge tone={tone}>{label}</Badge>;
}
