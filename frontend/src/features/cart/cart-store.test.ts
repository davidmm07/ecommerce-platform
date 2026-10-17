import { beforeEach, describe, expect, it } from 'vitest';

import type { Product } from '@/features/catalog/types';

import { cartActions, cartStore, cartSubtotal } from './cart-store';

const product = (overrides: Partial<Product> = {}): Product => ({
  id: 'p-1',
  sku: 'RS-001',
  name: 'Running Shoes',
  description: '',
  category: 'footwear',
  category_label: 'Footwear',
  price: '89.99',
  currency: 'USD',
  stock: 3,
  in_stock: true,
  weight_kg: '0.350',
  version: 1,
  created_at: '2026-10-17T12:00:00Z',
  updated_at: '2026-10-17T12:00:00Z',
  ...overrides,
});

describe('cart store', () => {
  beforeEach(() => cartActions.clear());

  it('merges repeated adds and never exceeds the stock', () => {
    cartActions.add(product(), 2);
    cartActions.add(product(), 5);
    expect(cartStore.state.lines).toHaveLength(1);
    expect(cartStore.state.lines[0]?.quantity).toBe(3);
  });

  it('ignores products without stock', () => {
    cartActions.add(product({ stock: 0 }));
    expect(cartStore.state.lines).toEqual([]);
  });

  it('updates quantities within bounds and removes lines', () => {
    cartActions.add(product(), 1);
    cartActions.setQuantity('p-1', 0);
    expect(cartStore.state.lines[0]?.quantity).toBe(1);
    cartActions.setQuantity('p-1', 99);
    expect(cartStore.state.lines[0]?.quantity).toBe(3);
    cartActions.remove('p-1');
    expect(cartStore.state.lines).toEqual([]);
  });

  it('computes the subtotal in cents', () => {
    cartActions.add(product({ id: 'a', price: '0.10', stock: 10 }), 3);
    cartActions.add(product({ id: 'b', price: '19.99', stock: 10 }), 2);
    expect(cartSubtotal(cartStore.state.lines)).toBe('40.28');
  });

  it('persists the cart in local storage', () => {
    cartActions.add(product(), 2);
    const stored = JSON.parse(window.localStorage.getItem('ecommerce.cart.v1') ?? '{}');
    expect(stored.lines[0].quantity).toBe(2);
  });
});
