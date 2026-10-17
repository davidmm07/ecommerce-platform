import { keepPreviousData, queryOptions } from '@tanstack/react-query';

import type { Page } from '@/shared/api/http';
import { getJson, request } from '@/shared/api/http';

import type { CartItemInput, Order, OrderSummary, PlaceOrderInput, Quote } from './types';

export const ordersApi = {
  quote: (items: CartItemInput[], signal?: AbortSignal) =>
    getJson<Quote>('/checkout/quote', { method: 'POST', body: { items }, signal }),

  place: async (input: PlaceOrderInput, idempotencyKey: string) => {
    const response = await request<Order>('/orders', {
      method: 'POST',
      body: input,
      headers: { 'Idempotency-Key': idempotencyKey },
    });
    return response.data;
  },

  get: (id: string, signal?: AbortSignal) => getJson<Order>(`/orders/${id}`, { signal }),

  list: (query: { page?: number; page_size?: number; email?: string }, signal?: AbortSignal) =>
    getJson<Page<OrderSummary>>('/orders', { query, signal }),
};

export const orderKeys = {
  all: ['orders'] as const,
  list: (query: object) => [...orderKeys.all, 'list', query] as const,
  detail: (id: string) => [...orderKeys.all, 'detail', id] as const,
  quote: (items: CartItemInput[]) => ['quote', items] as const,
};

export const orderQuery = (id: string) =>
  queryOptions({
    queryKey: orderKeys.detail(id),
    queryFn: ({ signal }) => ordersApi.get(id, signal),
  });

export const ordersQuery = (query: { page?: number; page_size?: number; email?: string }) =>
  queryOptions({
    queryKey: orderKeys.list(query),
    queryFn: ({ signal }) => ordersApi.list(query, signal),
    placeholderData: keepPreviousData,
  });

export const quoteQuery = (items: CartItemInput[]) =>
  queryOptions({
    queryKey: orderKeys.quote(items),
    queryFn: ({ signal }) => ordersApi.quote(items, signal),
    enabled: items.length > 0,
    placeholderData: keepPreviousData,
    retry: false,
  });
