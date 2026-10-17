export type OrderStatus = 'pending_payment' | 'paid' | 'payment_failed';

export type OrderLine = {
  product_id: string;
  sku: string;
  name: string;
  unit_price: string;
  quantity: number;
  line_total: string;
  unit_weight_kg: string;
};

export type Totals = {
  subtotal: string;
  shipping: string;
  total: string;
  total_weight_kg: string;
  currency: string;
};

export type Order = {
  id: string;
  number: string;
  status: OrderStatus;
  customer: { name: string; email: string };
  shipping_address: { line1: string; city: string; postal_code: string; country: string };
  lines: OrderLine[];
  totals: Totals;
  payment: {
    card_brand: string;
    card_last4: string;
    reference: string | null;
    failure_code: string | null;
  } | null;
  created_at: string;
  updated_at: string;
};

export type OrderSummary = {
  id: string;
  number: string;
  status: OrderStatus;
  customer_name: string;
  customer_email: string;
  item_count: number;
  total: string;
  currency: string;
  created_at: string;
};

export type CartItemInput = {
  product_id: string;
  quantity: number;
};

export type Quote = {
  lines: OrderLine[];
  totals: Totals;
};

export type PlaceOrderInput = {
  items: CartItemInput[];
  customer: { name: string; email: string };
  shipping_address: { line1: string; city: string; postal_code: string; country: string };
  payment: {
    card_number: string;
    expiry_month: number;
    expiry_year: number;
    cvc: string;
    holder_name: string;
  };
};

export type StockShortage = {
  sku: string;
  requested: number;
  available: number;
};
