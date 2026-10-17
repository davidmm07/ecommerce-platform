import { Store, useStore } from '@tanstack/react-store';

import type { Product } from '@/features/catalog/types';
import { multiplyMoney, sumMoney } from '@/shared/lib/format';

export const MAX_QUANTITY_PER_LINE = 100;
const STORAGE_KEY = 'ecommerce.cart.v1';

export type CartLine = {
  productId: string;
  sku: string;
  name: string;
  unitPrice: string;
  currency: string;
  quantity: number;
  maxQuantity: number;
};

export type CartState = {
  lines: CartLine[];
};

function readStorage(): CartState {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : null;
    if (parsed && typeof parsed === 'object' && Array.isArray((parsed as CartState).lines)) {
      return { lines: (parsed as CartState).lines.filter(isCartLine) };
    }
  } catch {
    return { lines: [] };
  }
  return { lines: [] };
}

function isCartLine(value: unknown): value is CartLine {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const line = value as Partial<CartLine>;
  return (
    typeof line.productId === 'string' &&
    typeof line.sku === 'string' &&
    typeof line.name === 'string' &&
    typeof line.unitPrice === 'string' &&
    typeof line.quantity === 'number' &&
    typeof line.maxQuantity === 'number'
  );
}

function writeStorage(state: CartState): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    return;
  }
}

export const cartStore = new Store<CartState>(readStorage());

cartStore.subscribe(() => writeStorage(cartStore.state));

const clamp = (quantity: number, max: number) =>
  Math.max(1, Math.min(quantity, max, MAX_QUANTITY_PER_LINE));

export const cartActions = {
  add(product: Product, quantity = 1): void {
    const maxQuantity = Math.min(product.stock, MAX_QUANTITY_PER_LINE);
    if (maxQuantity < 1) {
      return;
    }
    cartStore.setState((state) => {
      const existing = state.lines.find((line) => line.productId === product.id);
      if (existing) {
        return {
          lines: state.lines.map((line) =>
            line.productId === product.id
              ? {
                  ...line,
                  name: product.name,
                  unitPrice: product.price,
                  maxQuantity,
                  quantity: clamp(line.quantity + quantity, maxQuantity),
                }
              : line,
          ),
        };
      }
      return {
        lines: [
          ...state.lines,
          {
            productId: product.id,
            sku: product.sku,
            name: product.name,
            unitPrice: product.price,
            currency: product.currency,
            quantity: clamp(quantity, maxQuantity),
            maxQuantity,
          },
        ],
      };
    });
  },

  setQuantity(productId: string, quantity: number): void {
    cartStore.setState((state) => ({
      lines: state.lines.map((line) =>
        line.productId === productId
          ? { ...line, quantity: clamp(quantity, line.maxQuantity) }
          : line,
      ),
    }));
  },

  remove(productId: string): void {
    cartStore.setState((state) => ({
      lines: state.lines.filter((line) => line.productId !== productId),
    }));
  },

  clear(): void {
    cartStore.setState(() => ({ lines: [] }));
  },
};

export function cartSubtotal(lines: CartLine[]): string {
  return sumMoney(lines.map((line) => multiplyMoney(line.unitPrice, line.quantity)));
}

export function useCartLines(): CartLine[] {
  return useStore(cartStore, (state) => state.lines);
}

export function useCartCount(): number {
  return useStore(cartStore, (state) =>
    state.lines.reduce((total, line) => total + line.quantity, 0),
  );
}

export function useCartQuantity(productId: string): number {
  return useStore(
    cartStore,
    (state) => state.lines.find((line) => line.productId === productId)?.quantity ?? 0,
  );
}
