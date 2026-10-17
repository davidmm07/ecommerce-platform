import { useForm } from '@tanstack/react-form';
import { Save } from 'lucide-react';
import { toast } from 'sonner';

import { describeError } from '@/shared/api/http';
import { fieldError, serverFieldErrors, useServerErrors } from '@/shared/lib/forms';
import { Button } from '@/shared/ui/Button';
import { Card } from '@/shared/ui/display';
import { SelectField, TextAreaField, TextField } from '@/shared/ui/fields';

import type { ProductFormValues } from '../product-form';
import { PRODUCT_FIELDS, productFormSchema, toFormValues } from '../product-form';
import type { Category, Product } from '../types';

type ProductFormProps = {
  product?: Product;
  categories: Category[];
  submitLabel: string;
  onSubmit: (values: ProductFormValues) => Promise<void>;
  onCancel: () => void;
};

export function ProductForm({
  product,
  categories,
  submitLabel,
  onSubmit,
  onCancel,
}: ProductFormProps) {
  const server = useServerErrors();
  const form = useForm({
    defaultValues: toFormValues(product),
    validators: { onChange: productFormSchema },
    onSubmit: async ({ value }) => {
      try {
        await onSubmit(value);
      } catch (error) {
        const fieldErrors = serverFieldErrors(error, PRODUCT_FIELDS);
        server.setErrors(fieldErrors);
        toast.error(
          Object.keys(fieldErrors).length > 0
            ? 'Please fix the highlighted fields.'
            : describeError(error),
        );
      }
    },
  });

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        void form.handleSubmit();
      }}
    >
      <Card className="space-y-6 p-6">
        <div className="grid gap-5 md:grid-cols-2">
          <form.Field name="sku">
            {(field) => (
              <TextField
                label="SKU"
                required
                disabled={Boolean(product)}
                hint={
                  product
                    ? 'The SKU identifies the product and cannot change.'
                    : 'For example RS-001.'
                }
                value={field.state.value}
                onBlur={field.handleBlur}
                onChange={(event) => {
                  server.clear(field.name);
                  field.handleChange(event.target.value);
                }}
                error={fieldError(field, server.errors)}
                autoComplete="off"
                className="font-mono uppercase"
              />
            )}
          </form.Field>
          <form.Field name="name">
            {(field) => (
              <TextField
                label="Name"
                required
                value={field.state.value}
                onBlur={field.handleBlur}
                onChange={(event) => {
                  server.clear(field.name);
                  field.handleChange(event.target.value);
                }}
                error={fieldError(field, server.errors)}
              />
            )}
          </form.Field>
        </div>
        <form.Field name="description">
          {(field) => (
            <TextAreaField
              label="Description"
              rows={4}
              value={field.state.value}
              onBlur={field.handleBlur}
              onChange={(event) => {
                server.clear(field.name);
                field.handleChange(event.target.value);
              }}
              error={fieldError(field, server.errors)}
              hint="Plain text, up to 2000 characters."
            />
          )}
        </form.Field>
        <div className="grid gap-5 md:grid-cols-4">
          <form.Field name="category">
            {(field) => (
              <SelectField
                label="Category"
                required
                value={field.state.value}
                onBlur={field.handleBlur}
                onChange={(event) => {
                  server.clear(field.name);
                  field.handleChange(event.target.value as ProductFormValues['category']);
                }}
                error={fieldError(field, server.errors)}
              >
                <option value="">Choose...</option>
                {categories.map((category) => (
                  <option key={category.value} value={category.value}>
                    {category.label}
                  </option>
                ))}
              </SelectField>
            )}
          </form.Field>
          <form.Field name="price">
            {(field) => (
              <TextField
                label="Price (USD)"
                required
                inputMode="decimal"
                value={field.state.value}
                onBlur={field.handleBlur}
                onChange={(event) => {
                  server.clear(field.name);
                  field.handleChange(event.target.value);
                }}
                error={fieldError(field, server.errors)}
                placeholder="0.00"
              />
            )}
          </form.Field>
          <form.Field name="stock">
            {(field) => (
              <TextField
                label="Stock"
                required
                inputMode="numeric"
                value={field.state.value}
                onBlur={field.handleBlur}
                onChange={(event) => {
                  server.clear(field.name);
                  field.handleChange(event.target.value);
                }}
                error={fieldError(field, server.errors)}
                placeholder="0"
              />
            )}
          </form.Field>
          <form.Field name="weight_kg">
            {(field) => (
              <TextField
                label="Weight (kg)"
                required
                inputMode="decimal"
                value={field.state.value}
                onBlur={field.handleBlur}
                onChange={(event) => {
                  server.clear(field.name);
                  field.handleChange(event.target.value);
                }}
                error={fieldError(field, server.errors)}
                placeholder="0.000"
              />
            )}
          </form.Field>
        </div>
        <div className="flex justify-end gap-2 border-t border-slate-100 pt-5">
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <form.Subscribe selector={(state) => state.isSubmitting}>
            {(isSubmitting) => (
              <Button
                type="submit"
                loading={isSubmitting}
                icon={<Save className="size-4" aria-hidden />}
              >
                {submitLabel}
              </Button>
            )}
          </form.Subscribe>
        </div>
      </Card>
    </form>
  );
}
