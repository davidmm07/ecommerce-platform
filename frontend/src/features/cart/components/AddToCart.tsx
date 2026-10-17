import { ShoppingCart } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import type { Product } from '@/features/catalog/types';
import { Button } from '@/shared/ui/Button';
import { QuantityStepper } from '@/shared/ui/QuantityStepper';

import { MAX_QUANTITY_PER_LINE, cartActions, useCartQuantity } from '../cart-store';

type AddToCartProps = {
  product: Product;
  size?: 'sm' | 'md';
};

export function AddToCart({ product, size = 'md' }: AddToCartProps) {
  const inCart = useCartQuantity(product.id);
  const available = Math.min(product.stock, MAX_QUANTITY_PER_LINE) - inCart;
  const [quantity, setQuantity] = useState(1);

  if (product.stock <= 0) {
    return (
      <Button variant="secondary" size={size} disabled className="w-full">
        Out of stock
      </Button>
    );
  }

  if (available <= 0) {
    return (
      <Button variant="secondary" size={size} disabled className="w-full">
        All available units are in your cart
      </Button>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <QuantityStepper
        value={Math.min(quantity, available)}
        max={available}
        onChange={setQuantity}
        label={`quantity of ${product.name}`}
        size={size}
      />
      <Button
        size={size}
        className="flex-1"
        icon={<ShoppingCart className="size-4" aria-hidden />}
        onClick={() => {
          const added = Math.min(quantity, available);
          cartActions.add(product, added);
          setQuantity(1);
          toast.success(`${added} x ${product.name} added to your cart`);
        }}
      >
        Add to cart
      </Button>
    </div>
  );
}
