import { keepPreviousData, queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';

import { catalogApi } from './api';
import type { Product, ProductChanges, ProductInput, ProductQuery } from './types';

export const productKeys = {
  all: ['products'] as const,
  lists: () => [...productKeys.all, 'list'] as const,
  list: (query: ProductQuery) => [...productKeys.lists(), query] as const,
  details: () => [...productKeys.all, 'detail'] as const,
  detail: (id: string) => [...productKeys.details(), id] as const,
};

export const categoriesQuery = () =>
  queryOptions({
    queryKey: ['categories'],
    queryFn: ({ signal }) => catalogApi.categories(signal),
    staleTime: Infinity,
  });

export const productsQuery = (query: ProductQuery) =>
  queryOptions({
    queryKey: productKeys.list(query),
    queryFn: ({ signal }) => catalogApi.search(query, signal),
    placeholderData: keepPreviousData,
  });

export const productQuery = (id: string) =>
  queryOptions({
    queryKey: productKeys.detail(id),
    queryFn: ({ signal }) => catalogApi.get(id, signal),
  });

export function useCreateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ProductInput) => catalogApi.create(input),
    onSuccess: (product) => {
      queryClient.setQueryData(productKeys.detail(product.id), product);
      return queryClient.invalidateQueries({ queryKey: productKeys.lists() });
    },
  });
}

export function useUpdateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ product, changes }: { product: Product; changes: ProductChanges }) =>
      catalogApi.update(product.id, product.version, changes),
    onSuccess: (product) => {
      queryClient.setQueryData(productKeys.detail(product.id), product);
      return queryClient.invalidateQueries({ queryKey: productKeys.lists() });
    },
  });
}

export function useArchiveProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (product: Product) => catalogApi.archive(product.id, product.version),
    onSuccess: (_, product) => {
      queryClient.removeQueries({ queryKey: productKeys.detail(product.id) });
      return queryClient.invalidateQueries({ queryKey: productKeys.lists() });
    },
  });
}
