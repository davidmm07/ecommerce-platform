import { z } from 'zod';

import { CATEGORY_VALUES, PRODUCT_SORTS } from './types';

const optionalText = z.string().trim().max(100).optional().catch(undefined);
const optionalPrice = z.coerce.number().nonnegative().optional().catch(undefined);
const optionalPage = z.coerce.number().int().min(1).optional().catch(undefined);

export const shopSearchSchema = z.object({
  q: optionalText,
  category: z.enum(CATEGORY_VALUES).optional().catch(undefined),
  min_price: optionalPrice,
  max_price: optionalPrice,
  in_stock: z.boolean().optional().catch(undefined),
  sort: z.enum(PRODUCT_SORTS).optional().catch(undefined),
  page: optionalPage,
});

export type ShopSearch = z.infer<typeof shopSearchSchema>;

export const adminProductsSearchSchema = z.object({
  q: optionalText,
  sort: z.enum(PRODUCT_SORTS).optional().catch(undefined),
  page: optionalPage,
});

export type AdminProductsSearch = z.infer<typeof adminProductsSearchSchema>;

export function parseShopSearch(search: Record<string, unknown>): ShopSearch {
  return compact(shopSearchSchema.parse(search));
}

export function parseAdminProductsSearch(search: Record<string, unknown>): AdminProductsSearch {
  return compact(adminProductsSearchSchema.parse(search));
}

function compact<T extends Record<string, unknown>>(value: T): T {
  return Object.fromEntries(
    Object.entries(value).filter(([, entry]) => entry !== undefined && entry !== ''),
  ) as T;
}
