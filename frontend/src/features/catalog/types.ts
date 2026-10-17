export const CATEGORY_VALUES = [
  'accessories',
  'beauty',
  'books',
  'clothing',
  'electronics',
  'food-beverage',
  'footwear',
  'games',
  'gifts',
  'health',
  'home-office',
  'kitchen',
  'misc',
  'outdoors',
  'pets',
  'sports',
  'stationery',
  'tools',
] as const;

export type CategoryValue = (typeof CATEGORY_VALUES)[number];

export type Category = {
  value: CategoryValue;
  label: string;
};

export type Product = {
  id: string;
  sku: string;
  name: string;
  description: string;
  category: CategoryValue;
  category_label: string;
  price: string;
  currency: string;
  stock: number;
  in_stock: boolean;
  weight_kg: string;
  version: number;
  created_at: string;
  updated_at: string;
};

export type ProductInput = {
  sku: string;
  name: string;
  description: string;
  category: CategoryValue;
  price: string;
  stock: number;
  weight_kg: string;
};

export type ProductChanges = Partial<Omit<ProductInput, 'sku'>>;

export const PRODUCT_SORTS = ['relevance', 'name', 'price_asc', 'price_desc', 'newest'] as const;

export type ProductSort = (typeof PRODUCT_SORTS)[number];

export type ProductQuery = {
  q?: string;
  category?: CategoryValue;
  min_price?: number;
  max_price?: number;
  in_stock?: boolean;
  sort?: ProductSort;
  page?: number;
  page_size?: number;
};
