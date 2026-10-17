import type { SortingState } from '@tanstack/react-table';

import type { ProductSort } from './types';

export function toSorting(sort: ProductSort | undefined): SortingState {
  switch (sort) {
    case 'name':
      return [{ id: 'name', desc: false }];
    case 'price_asc':
      return [{ id: 'price', desc: false }];
    case 'price_desc':
      return [{ id: 'price', desc: true }];
    case 'newest':
      return [{ id: 'created_at', desc: true }];
    default:
      return [];
  }
}

export function fromSorting(sorting: SortingState): ProductSort | undefined {
  const [first] = sorting;
  if (!first) {
    return undefined;
  }
  if (first.id === 'price') {
    return first.desc ? 'price_desc' : 'price_asc';
  }
  if (first.id === 'name') {
    return first.desc ? undefined : 'name';
  }
  if (first.id === 'created_at') {
    return first.desc ? 'newest' : undefined;
  }
  return undefined;
}
