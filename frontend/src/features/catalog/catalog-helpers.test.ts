import { describe, expect, it } from 'vitest';

import {
  changedFields,
  looksLikeSqlPayload,
  productFormSchema,
  toFormValues,
  toProductInput,
} from './product-form';
import { parseAdminProductsSearch, parseShopSearch } from './search-params';
import { fromSorting, toSorting } from './table-sorting';
import type { Product } from './types';

const product: Product = {
  id: 'p-1',
  sku: 'RS-001',
  name: 'Running Shoes',
  description: 'Lightweight',
  category: 'footwear',
  category_label: 'Footwear',
  price: '89.99',
  currency: 'USD',
  stock: 150,
  in_stock: true,
  weight_kg: '0.350',
  version: 3,
  image: null,
  created_at: '2026-10-17T12:00:00Z',
  updated_at: '2026-10-17T12:00:00Z',
};

describe('search params', () => {
  it('keeps valid values and drops invalid ones', () => {
    expect(
      parseShopSearch({ q: '  shoes ', category: 'footwear', page: '2', sort: 'price_desc' }),
    ).toEqual({ q: 'shoes', category: 'footwear', page: 2, sort: 'price_desc' });
    expect(
      parseShopSearch({ category: 'spaceships', page: -1, min_price: 'abc', sort: 'x' }),
    ).toEqual({});
    expect(parseAdminProductsSearch({ q: '', page: 1 })).toEqual({ page: 1 });
  });
});

describe('table sorting', () => {
  it('maps table state to API sort values and back', () => {
    expect(fromSorting([{ id: 'price', desc: true }])).toBe('price_desc');
    expect(fromSorting([{ id: 'name', desc: false }])).toBe('name');
    expect(fromSorting([{ id: 'name', desc: true }])).toBeUndefined();
    expect(fromSorting([{ id: 'created_at', desc: true }])).toBe('newest');
    expect(fromSorting([])).toBeUndefined();
    expect(toSorting('newest')).toEqual([{ id: 'created_at', desc: true }]);
    expect(toSorting(undefined)).toEqual([]);
  });
});

describe('product form mapping', () => {
  it('round trips a product through the form values', () => {
    const values = toFormValues(product);
    expect(values).toMatchObject({ stock: '150', weight_kg: '0.35', price: '89.99' });
    expect(toProductInput({ ...values, sku: ' rs-001 ' })).toMatchObject({
      sku: 'RS-001',
      stock: 150,
      category: 'footwear',
    });
  });

  it('only sends the fields that changed', () => {
    const values = { ...toFormValues(product), price: '94.99', stock: '150', name: 'Trail Shoes' };
    expect(changedFields(product, values)).toEqual({ name: 'Trail Shoes', price: '94.99' });
    expect(changedFields(product, toFormValues(product))).toEqual({});
  });

  it('mirrors the server validation rules', () => {
    const result = productFormSchema.safeParse({
      sku: 'R?',
      name: '<b>x</b>',
      description: '',
      category: '',
      price: '0',
      stock: '-5',
      weight_kg: '1.2345',
    });
    expect(result.success).toBe(false);
    const fields = new Set(result.error?.issues.map((issue) => issue.path[0]));
    expect(fields).toEqual(new Set(['sku', 'name', 'category', 'price', 'stock', 'weight_kg']));
  });
});

describe('sql payload rule', () => {
  it('flags injection payloads and keeps ordinary product text', () => {
    for (const payload of [
      "Robert'); DROP TABLE products;--",
      "x' OR '1'='1",
      '1 UNION SELECT password FROM users',
      'Lamp /* hidden */',
    ]) {
      expect(looksLikeSqlPayload(payload)).toBe(true);
    }
    for (const text of [
      "Robert's Running Shoes",
      'Rock & Roll; Vol. 2',
      'Drop Earrings',
      'Select from 6 colors',
      'Update your set of tools',
    ]) {
      expect(looksLikeSqlPayload(text)).toBe(false);
    }
  });
});
