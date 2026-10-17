import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ApiError } from '@/shared/api/http';

import type { Category } from '../types';
import { ProductForm } from './ProductForm';

vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const categories: Category[] = [
  { value: 'footwear', label: 'Footwear' },
  { value: 'electronics', label: 'Electronics' },
];

async function fillValidProduct() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/SKU/), 'rs-001');
  await user.type(screen.getByLabelText(/^Name/), 'Running Shoes');
  await user.selectOptions(screen.getByLabelText(/Category/), 'footwear');
  await user.type(screen.getByLabelText(/Price/), '89.99');
  await user.type(screen.getByLabelText(/Stock/), '150');
  await user.type(screen.getByLabelText(/Weight/), '0.35');
  return user;
}

describe('ProductForm', () => {
  it('shows client side validation errors on submit', async () => {
    const onSubmit = vi.fn();
    render(
      <ProductForm
        categories={categories}
        submitLabel="Create product"
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Create product' }));

    expect(await screen.findByText('Use at least 3 characters')).toBeInTheDocument();
    expect(screen.getByText('Choose a category')).toBeInTheDocument();
    expect(screen.getByText('Use a positive amount with up to 2 decimals')).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('submits valid values', async () => {
    const onSubmit = vi.fn(() => Promise.resolve());
    render(
      <ProductForm
        categories={categories}
        submitLabel="Create product"
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />,
    );
    const user = await fillValidProduct();
    await user.click(screen.getByRole('button', { name: 'Create product' }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ sku: 'rs-001', price: '89.99', category: 'footwear' }),
    );
  });

  it('maps server field errors next to the fields and clears them on edit', async () => {
    const onSubmit = vi.fn(() =>
      Promise.reject(
        new ApiError({
          type: 'urn:ecommerce:problem:duplicate_sku',
          title: 'Validation failed',
          status: 422,
          detail: 'name: must be plain text',
          code: 'validation_failed',
          errors: [{ field: 'name', message: 'Rejected by the server' }],
        }),
      ),
    );
    render(
      <ProductForm
        categories={categories}
        submitLabel="Create product"
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />,
    );
    const user = await fillValidProduct();
    await user.click(screen.getByRole('button', { name: 'Create product' }));

    expect(await screen.findByText('Rejected by the server')).toBeInTheDocument();
    await user.type(screen.getByLabelText(/^Name/), ' Pro');
    expect(screen.queryByText('Rejected by the server')).not.toBeInTheDocument();
  });
});
