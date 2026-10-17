import { describe, expect, it } from 'vitest';

import type { CartLine } from '@/features/cart/cart-store';

import { checkoutSchema, emptyCheckout, toPlaceOrderInput } from './checkout-form';

const valid = {
  ...emptyCheckout,
  name: ' Ada Lovelace ',
  email: 'ada@example.com',
  line1: '221B Baker Street',
  city: 'London',
  postal_code: 'NW1 6XE',
  country: 'gb',
  holder_name: 'Ada Lovelace',
  card_number: '4242 4242 4242 4242',
  expiry: '12/30',
  cvc: '123',
};

const lines: CartLine[] = [
  {
    productId: 'p-1',
    sku: 'RS-001',
    name: 'Running Shoes',
    unitPrice: '89.99',
    currency: 'USD',
    quantity: 2,
    maxQuantity: 5,
  },
];

describe('checkout form', () => {
  it('accepts a complete checkout', () => {
    expect(checkoutSchema.safeParse(valid).success).toBe(true);
  });

  it('rejects invalid cards, expired dates and bad emails', () => {
    const result = checkoutSchema.safeParse({
      ...valid,
      email: 'nope',
      card_number: '4242 4242 4242 4241',
      expiry: '01/20',
      cvc: '1',
    });
    expect(result.success).toBe(false);
    const fields = new Set(result.error?.issues.map((issue) => issue.path[0]));
    expect(fields).toEqual(new Set(['email', 'card_number', 'expiry', 'cvc']));
  });

  it('builds the API payload from the form and the cart', () => {
    expect(toPlaceOrderInput(valid, lines)).toEqual({
      items: [{ product_id: 'p-1', quantity: 2 }],
      customer: { name: 'Ada Lovelace', email: 'ada@example.com' },
      shipping_address: {
        line1: '221B Baker Street',
        city: 'London',
        postal_code: 'NW1 6XE',
        country: 'GB',
      },
      payment: {
        card_number: '4242424242424242',
        expiry_month: 12,
        expiry_year: 2030,
        cvc: '123',
        holder_name: 'Ada Lovelace',
      },
    });
  });
});
