import { Badge } from '@/shared/ui/display';

const LOW_STOCK = 10;

export function StockBadge({ stock }: { stock: number }) {
  if (stock <= 0) {
    return <Badge tone="danger">Out of stock</Badge>;
  }
  if (stock <= LOW_STOCK) {
    return <Badge tone="warning">Only {stock} left</Badge>;
  }
  return <Badge tone="success">In stock</Badge>;
}
