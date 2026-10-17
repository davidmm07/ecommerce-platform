import { useForm } from '@tanstack/react-form';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, Navigate, useNavigate } from '@tanstack/react-router';
import { Lock } from 'lucide-react';
import type { ReactNode } from 'react';
import { useRef, useState } from 'react';
import { toast } from 'sonner';

import { cartActions, useCartLines } from '@/features/cart/cart-store';
import { productKeys } from '@/features/catalog/queries';
import { orderKeys, ordersApi } from '@/features/orders/api';
import type { PlaceOrderInput } from '@/features/orders/types';
import { ApiError, NetworkError, describeError } from '@/shared/api/http';
import { fieldError, useServerErrors } from '@/shared/lib/forms';
import { newIdempotencyKey } from '@/shared/lib/ids';
import { Button } from '@/shared/ui/Button';
import { buttonClasses } from '@/shared/ui/styles';
import { Card, ErrorState, PageHeader } from '@/shared/ui/display';
import { TextField } from '@/shared/ui/fields';

import { brandLabel, cardBrand, formatCardNumber, formatExpiry } from '../card';
import type { CheckoutValues } from '../checkout-form';
import {
  CHECKOUT_FIELDS,
  checkoutSchema,
  emptyCheckout,
  toPlaceOrderInput,
} from '../checkout-form';
import { OrderSummary } from '../components/OrderSummary';
import { TestCards } from '../components/TestCards';
import { shortagesOf } from '../quote';

export function CheckoutPage() {
  const lines = useCartLines();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const server = useServerErrors();
  const idempotencyKey = useRef(newIdempotencyKey());
  const [failure, setFailure] = useState<string | null>(null);

  const placeOrder = useMutation({
    mutationFn: (input: PlaceOrderInput) => ordersApi.place(input, idempotencyKey.current),
    onSettled: (_, error) => {
      if (!(error instanceof NetworkError)) {
        idempotencyKey.current = newIdempotencyKey();
      }
      void queryClient.invalidateQueries({ queryKey: productKeys.all });
      void queryClient.invalidateQueries({ queryKey: orderKeys.all });
    },
  });

  const form = useForm({
    defaultValues: emptyCheckout,
    validators: { onChange: checkoutSchema },
    onSubmit: async ({ value }) => {
      setFailure(null);
      try {
        const order = await placeOrder.mutateAsync(toPlaceOrderInput(value, lines));
        cartActions.clear();
        toast.success(`Order ${order.number} confirmed`);
        await navigate({
          to: '/orders/$orderId',
          params: { orderId: order.id },
          search: { placed: true },
        });
      } catch (error) {
        handleFailure(error);
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    },
  });

  function handleFailure(error: unknown) {
    if (error instanceof ApiError && error.code === 'validation_failed') {
      const mapped: Record<string, string> = {};
      for (const issue of error.fieldErrors) {
        const field = CHECKOUT_FIELDS[issue.field];
        if (field && !mapped[field]) {
          mapped[field] = issue.message;
        }
      }
      server.setErrors(mapped);
      setFailure('Some details need your attention.');
      return;
    }
    if (error instanceof ApiError && error.code === 'payment_declined') {
      const declineCode = error.problem.decline_code;
      const code = (typeof declineCode === 'string' ? declineCode : 'card_declined').replaceAll(
        '_',
        ' ',
      );
      setFailure(`Your card was declined (${code}). No charge was made, try another card.`);
      return;
    }
    if (error instanceof ApiError && error.code === 'insufficient_stock') {
      const shortages = shortagesOf(error)
        .map((shortage) => `${shortage.sku} has ${shortage.available} left`)
        .join(', ');
      setFailure(`Some items sold out while you were checking out: ${shortages}.`);
      return;
    }
    setFailure(describeError(error));
  }

  if (lines.length === 0 && !placeOrder.isSuccess) {
    return <Navigate to="/cart" />;
  }

  const textField = (
    name: keyof CheckoutValues,
    label: string,
    props: {
      autoComplete?: string;
      inputMode?: 'text' | 'email' | 'numeric';
      type?: string;
      placeholder?: string;
      format?: (value: string) => string;
      className?: string;
      hint?: ReactNode;
    } = {},
  ) => (
    <form.Field name={name}>
      {(field) => (
        <TextField
          label={label}
          required
          type={props.type ?? 'text'}
          autoComplete={props.autoComplete}
          inputMode={props.inputMode}
          placeholder={props.placeholder}
          hint={props.hint}
          containerClassName={props.className}
          value={field.state.value}
          onBlur={field.handleBlur}
          onChange={(event) => {
            server.clear(name);
            field.handleChange(
              props.format ? props.format(event.target.value) : event.target.value,
            );
          }}
          error={fieldError(field, server.errors)}
        />
      )}
    </form.Field>
  );

  return (
    <>
      <PageHeader title="Checkout" description="Shipping and payment details." />
      <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
        <form
          noValidate
          className="space-y-6"
          onSubmit={(event) => {
            event.preventDefault();
            void form.handleSubmit();
          }}
        >
          {failure && <ErrorState message={failure} />}
          <Section title="Contact">
            <div className="grid gap-4 sm:grid-cols-2">
              {textField('name', 'Full name', { autoComplete: 'name' })}
              {textField('email', 'Email', {
                autoComplete: 'email',
                inputMode: 'email',
                type: 'email',
              })}
            </div>
          </Section>
          <Section title="Shipping address">
            <div className="grid gap-4 sm:grid-cols-6">
              {textField('line1', 'Street address', {
                autoComplete: 'address-line1',
                className: 'sm:col-span-6',
              })}
              {textField('city', 'City', {
                autoComplete: 'address-level2',
                className: 'sm:col-span-3',
              })}
              {textField('postal_code', 'Postal code', {
                autoComplete: 'postal-code',
                className: 'sm:col-span-2',
              })}
              {textField('country', 'Country', {
                autoComplete: 'country',
                placeholder: 'US',
                className: 'sm:col-span-1',
                format: (value) => value.toUpperCase().slice(0, 2),
              })}
            </div>
          </Section>
          <Section title="Payment">
            <div className="space-y-4">
              <TestCards
                onPick={(number) => {
                  server.clear('card_number');
                  form.setFieldValue('card_number', number);
                  if (!form.getFieldValue('expiry')) {
                    form.setFieldValue('expiry', '12/30');
                  }
                  if (!form.getFieldValue('cvc')) {
                    form.setFieldValue('cvc', '123');
                  }
                }}
              />
              <div className="grid gap-4 sm:grid-cols-6">
                {textField('holder_name', 'Name on card', {
                  autoComplete: 'cc-name',
                  className: 'sm:col-span-6',
                })}
                <form.Subscribe selector={(state) => state.values.card_number}>
                  {(number) =>
                    textField('card_number', 'Card number', {
                      autoComplete: 'cc-number',
                      inputMode: 'numeric',
                      placeholder: '4242 4242 4242 4242',
                      format: formatCardNumber,
                      className: 'sm:col-span-4',
                      hint: number ? `Detected brand: ${brandLabel(cardBrand(number))}` : undefined,
                    })
                  }
                </form.Subscribe>
                {textField('expiry', 'Expiry', {
                  autoComplete: 'cc-exp',
                  inputMode: 'numeric',
                  placeholder: 'MM/YY',
                  format: formatExpiry,
                  className: 'sm:col-span-1',
                })}
                {textField('cvc', 'CVC', {
                  autoComplete: 'cc-csc',
                  inputMode: 'numeric',
                  placeholder: '123',
                  format: (value) => value.replace(/\D/g, '').slice(0, 4),
                  className: 'sm:col-span-1',
                })}
              </div>
            </div>
          </Section>
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-between">
            <Link to="/cart" className={buttonClasses('secondary', 'lg')}>
              Back to cart
            </Link>
            <form.Subscribe selector={(state) => state.isSubmitting}>
              {(isSubmitting) => (
                <Button
                  type="submit"
                  size="lg"
                  loading={isSubmitting}
                  icon={<Lock className="size-4" aria-hidden />}
                >
                  {isSubmitting ? 'Processing payment' : 'Place order'}
                </Button>
              )}
            </form.Subscribe>
          </div>
        </form>
        <div className="lg:sticky lg:top-6 lg:self-start">
          <OrderSummary lines={lines} />
        </div>
      </div>
    </>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card className="p-5">
      <h2 className="mb-4 text-base font-semibold text-fg">{title}</h2>
      {children}
    </Card>
  );
}
