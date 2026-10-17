import { z } from 'zod';

import type { CartLine } from '@/features/cart/cart-store';
import type { PlaceOrderInput } from '@/features/orders/types';

import { digitsOnly, isExpired, parseExpiry, passesLuhn } from './card';

export const checkoutSchema = z.object({
  name: z.string().trim().min(1, 'Enter your full name').max(120),
  email: z.string().trim().pipe(z.email('Enter a valid email address')),
  line1: z.string().trim().min(1, 'Enter the street address').max(200),
  city: z.string().trim().min(1, 'Enter the city').max(100),
  postal_code: z
    .string()
    .trim()
    .regex(/^[A-Za-z0-9][A-Za-z0-9 -]{1,14}$/, 'Enter a valid postal code'),
  country: z
    .string()
    .trim()
    .regex(/^[A-Za-z]{2}$/, 'Use a two letter country code, e.g. US'),
  holder_name: z.string().trim().min(1, 'Enter the name on the card').max(100),
  card_number: z.string().refine(passesLuhn, 'Enter a valid card number'),
  expiry: z
    .string()
    .refine((value) => parseExpiry(value) !== null, 'Use MM/YY')
    .refine((value) => {
      const parsed = parseExpiry(value);
      return parsed === null || !isExpired(parsed);
    }, 'This card has expired'),
  cvc: z.string().regex(/^\d{3,4}$/, '3 or 4 digits'),
});

export type CheckoutValues = z.input<typeof checkoutSchema>;

export const CHECKOUT_FIELDS: Record<string, keyof CheckoutValues> = {
  'customer.name': 'name',
  'customer.email': 'email',
  'shipping_address.line1': 'line1',
  'shipping_address.city': 'city',
  'shipping_address.postal_code': 'postal_code',
  'shipping_address.country': 'country',
  'payment.holder_name': 'holder_name',
  'payment.card_number': 'card_number',
  'payment.expiry_month': 'expiry',
  'payment.expiry_year': 'expiry',
  'payment.cvc': 'cvc',
};

export const emptyCheckout: CheckoutValues = {
  name: '',
  email: '',
  line1: '',
  city: '',
  postal_code: '',
  country: 'US',
  holder_name: '',
  card_number: '',
  expiry: '',
  cvc: '',
};

export function toPlaceOrderInput(values: CheckoutValues, lines: CartLine[]): PlaceOrderInput {
  const expiry = parseExpiry(values.expiry) ?? { month: 0, year: 0 };
  return {
    items: lines.map((line) => ({ product_id: line.productId, quantity: line.quantity })),
    customer: { name: values.name.trim(), email: values.email.trim() },
    shipping_address: {
      line1: values.line1.trim(),
      city: values.city.trim(),
      postal_code: values.postal_code.trim(),
      country: values.country.trim().toUpperCase(),
    },
    payment: {
      card_number: digitsOnly(values.card_number),
      expiry_month: expiry.month,
      expiry_year: expiry.year,
      cvc: values.cvc,
      holder_name: values.holder_name.trim(),
    },
  };
}
