import { useQuery } from '@tanstack/react-query';

import type { CartLine } from '@/features/cart/cart-store';
import { quoteQuery } from '@/features/orders/api';
import type { StockShortage } from '@/features/orders/types';
import { ApiError } from '@/shared/api/http';

export function shortagesOf(error: unknown): StockShortage[] {
  if (error instanceof ApiError && Array.isArray(error.problem.shortages)) {
    return error.problem.shortages as StockShortage[];
  }
  return [];
}

export function useCartQuote(lines: CartLine[]) {
  const items = lines.map((line) => ({ product_id: line.productId, quantity: line.quantity }));
  return useQuery(quoteQuery(items));
}
