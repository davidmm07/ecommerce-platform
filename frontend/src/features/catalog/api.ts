import type { Page } from '@/shared/api/http';
import { getJson, request, upload } from '@/shared/api/http';

import type {
  Category,
  ImageCredit,
  Product,
  ProductChanges,
  ProductInput,
  ProductQuery,
} from './types';

export const catalogApi = {
  categories: (signal?: AbortSignal) => getJson<Category[]>('/categories', { signal }),

  search: (query: ProductQuery, signal?: AbortSignal) =>
    getJson<Page<Product>>('/products', { query, signal }),

  get: (id: string, signal?: AbortSignal) => getJson<Product>(`/products/${id}`, { signal }),

  create: (input: ProductInput) => getJson<Product>('/products', { method: 'POST', body: input }),

  update: (id: string, version: number, changes: ProductChanges) =>
    getJson<Product>(`/products/${id}`, {
      method: 'PATCH',
      body: changes,
      headers: { 'If-Match': `"${version}"` },
    }),

  uploadImage: (
    id: string,
    version: number,
    file: File,
    onProgress?: (fraction: number) => void,
  ) => {
    const body = new FormData();
    body.append('file', file);
    return upload<Product>(`/products/${id}/image`, body, {
      method: 'PUT',
      headers: { 'If-Match': `"${version}"` },
      onProgress,
    });
  },

  importImageFromUrl: (
    id: string,
    version: number,
    body: {
      url: string;
      credit: (Omit<ImageCredit, 'license_url'> & { license_url?: string }) | null;
    },
  ) =>
    getJson<Product>(`/products/${id}/image/from-url`, {
      method: 'PUT',
      body,
      headers: { 'If-Match': `"${version}"` },
    }),

  removeImage: (id: string, version: number) =>
    getJson<Product>(`/products/${id}/image`, {
      method: 'DELETE',
      headers: { 'If-Match': `"${version}"` },
    }),

  archive: async (id: string, version: number) => {
    await request<void>(`/products/${id}`, {
      method: 'DELETE',
      headers: { 'If-Match': `"${version}"` },
    });
  },
};
