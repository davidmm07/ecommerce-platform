import { z } from 'zod';

import type { Product, ProductChanges, ProductInput } from './types';
import { CATEGORY_VALUES } from './types';

const SKU_PATTERN = /^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$/;
const PRICE_PATTERN = /^\d{1,10}(?:\.\d{1,2})?$/;
const WEIGHT_PATTERN = /^\d{1,4}(?:\.\d{1,3})?$/;
const MARKUP_PATTERN = /<\s*\/?\s*[A-Za-z!][^>]*>/;
const SQL_PAYLOAD_PATTERNS = [
  /\b(?:drop|truncate|alter)\s+(?:table|database|schema|view|index)\b/i,
  /\bdelete\s+from\b/i,
  /\binsert\s+into\b/i,
  /\bunion\s+(?:all\s+)?select\b/i,
  /\bupdate\s+\w+\s+set\s+\w+\s*=/i,
  /\b(?:exec|execute)\s*\(/i,
  /['"]\s*\)*\s*(?:or|and)\s+['"]?\w+['"]?\s*=\s*['"]?\w+/i,
  /;\s*--|['")]\s*--/,
  /\/\*|\*\//,
  /\b(?:xp_cmdshell|pg_sleep|waitfor\s+delay)\b/i,
];

export function looksLikeSqlPayload(value: string): boolean {
  return SQL_PAYLOAD_PATTERNS.some((pattern) => pattern.test(value));
}

const plainText = (max: number) =>
  z
    .string()
    .max(max, `Use at most ${max} characters`)
    .refine((value) => !MARKUP_PATTERN.test(value), 'HTML markup is not allowed')
    .refine((value) => !looksLikeSqlPayload(value), 'This looks like an SQL injection payload');

export const productFormSchema = z.object({
  sku: z
    .string()
    .trim()
    .min(3, 'Use at least 3 characters')
    .max(32, 'Use at most 32 characters')
    .regex(SKU_PATTERN, 'Letters, digits and single hyphens only, e.g. RS-001'),
  name: plainText(200).refine((value) => value.trim().length > 0, 'Name is required'),
  description: plainText(2000),
  category: z
    .union([z.enum(CATEGORY_VALUES), z.literal('')])
    .refine((value) => value !== '', 'Choose a category'),
  price: z
    .string()
    .trim()
    .regex(PRICE_PATTERN, 'Use a positive amount with up to 2 decimals')
    .refine((value) => Number(value) > 0, 'Price must be greater than 0')
    .refine((value) => Number(value) <= 1_000_000, 'Price must not exceed 1,000,000'),
  stock: z
    .string()
    .trim()
    .regex(/^\d{1,7}$/, 'Use a whole number of units')
    .refine((value) => Number(value) <= 1_000_000, 'Stock must not exceed 1,000,000'),
  weight_kg: z
    .string()
    .trim()
    .regex(WEIGHT_PATTERN, 'Use kilograms with up to 3 decimals')
    .refine((value) => Number(value) <= 1000, 'Weight must not exceed 1000 kg'),
});

export type ProductFormValues = z.input<typeof productFormSchema>;

export const PRODUCT_FIELDS = [
  'sku',
  'name',
  'description',
  'category',
  'price',
  'stock',
  'weight_kg',
] as const;

export function toFormValues(product?: Product): ProductFormValues {
  return {
    sku: product?.sku ?? '',
    name: product?.name ?? '',
    description: product?.description ?? '',
    category: product?.category ?? '',
    price: product?.price ?? '',
    stock: product ? String(product.stock) : '',
    weight_kg: product ? String(Number(product.weight_kg)) : '',
  };
}

export function toProductInput(values: ProductFormValues): ProductInput {
  return {
    sku: values.sku.trim().toUpperCase(),
    name: values.name.trim(),
    description: values.description.trim(),
    category: values.category as ProductInput['category'],
    price: values.price.trim(),
    stock: Number(values.stock),
    weight_kg: values.weight_kg.trim(),
  };
}

export function changedFields(product: Product, values: ProductFormValues): ProductChanges {
  const input = toProductInput(values);
  const changes: ProductChanges = {};
  if (input.name !== product.name) changes.name = input.name;
  if (input.description !== product.description) changes.description = input.description;
  if (input.category !== product.category) changes.category = input.category;
  if (Number(input.price) !== Number(product.price)) changes.price = input.price;
  if (input.stock !== product.stock) changes.stock = input.stock;
  if (Number(input.weight_kg) !== Number(product.weight_kg)) changes.weight_kg = input.weight_kg;
  return changes;
}
