import { Search, X } from 'lucide-react';
import { useEffect, useState } from 'react';

import { useDebouncedValue } from '@/shared/hooks/useDebouncedValue';
import { cn } from '@/shared/lib/cn';
import { inputClasses } from '@/shared/ui/styles';

import type { ShopSearch } from '../search-params';
import type { Category, ProductSort } from '../types';

const SORT_LABELS: Record<ProductSort, string> = {
  relevance: 'Best match',
  name: 'Name',
  price_asc: 'Price: low to high',
  price_desc: 'Price: high to low',
  newest: 'Newest',
};

type SearchToolbarProps = {
  search: ShopSearch;
  categories: Category[];
  onChange: (changes: Partial<ShopSearch>) => void;
  onReset: () => void;
};

export function SearchToolbar({ search, categories, onChange, onReset }: SearchToolbarProps) {
  const [text, setText] = useState(search.q ?? '');
  const debounced = useDebouncedValue(text.trim(), 300);

  useEffect(() => {
    if (debounced !== (search.q ?? '')) {
      onChange({ q: debounced || undefined });
    }
  }, [debounced, search.q, onChange]);

  const hasFilters = Boolean(
    search.q ||
    search.category ||
    search.min_price !== undefined ||
    search.max_price !== undefined ||
    search.in_stock,
  );

  return (
    <div className="space-y-3 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <div className="relative">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400"
          aria-hidden
        />
        <input
          type="search"
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Search by name, SKU or description, typos are fine"
          aria-label="Search products"
          maxLength={100}
          className={cn(inputClasses(), 'h-11 pl-9 text-base')}
        />
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <select
          aria-label="Category"
          value={search.category ?? ''}
          onChange={(event) =>
            onChange({ category: (event.target.value || undefined) as ShopSearch['category'] })
          }
          className={inputClasses()}
        >
          <option value="">All categories</option>
          {categories.map((category) => (
            <option key={category.value} value={category.value}>
              {category.label}
            </option>
          ))}
        </select>
        <PriceInput
          label="Min price"
          value={search.min_price}
          onCommit={(min_price) => onChange({ min_price })}
        />
        <PriceInput
          label="Max price"
          value={search.max_price}
          onCommit={(max_price) => onChange({ max_price })}
        />
        <select
          aria-label="Sort by"
          value={search.sort ?? 'relevance'}
          onChange={(event) => onChange({ sort: event.target.value as ProductSort })}
          className={inputClasses()}
        >
          {Object.entries(SORT_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <div className="col-span-2 flex items-center justify-between gap-3 md:col-span-1">
          <label className="inline-flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={search.in_stock === true}
              onChange={(event) => onChange({ in_stock: event.target.checked || undefined })}
              className="size-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-600"
            />
            In stock only
          </label>
          {hasFilters && (
            <button
              type="button"
              onClick={() => {
                setText('');
                onReset();
              }}
              className="inline-flex items-center gap-1 text-sm font-medium text-indigo-600 hover:text-indigo-500"
            >
              <X className="size-3.5" aria-hidden />
              Clear
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function PriceInput({
  label,
  value,
  onCommit,
}: {
  label: string;
  value: number | undefined;
  onCommit: (value: number | undefined) => void;
}) {
  const [draft, setDraft] = useState(value === undefined ? '' : String(value));
  useEffect(() => setDraft(value === undefined ? '' : String(value)), [value]);

  const commit = () => {
    const trimmed = draft.trim();
    const parsed = Number(trimmed);
    const next = trimmed === '' || Number.isNaN(parsed) || parsed < 0 ? undefined : parsed;
    if (next !== value) {
      onCommit(next);
    }
    if (next === undefined) {
      setDraft('');
    }
  };

  return (
    <input
      type="number"
      inputMode="decimal"
      min={0}
      step="0.01"
      placeholder={label}
      aria-label={label}
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === 'Enter') {
          commit();
        }
      }}
      className={inputClasses()}
    />
  );
}
