import { useQuery } from '@tanstack/react-query';
import { Link, getRouteApi } from '@tanstack/react-router';
import { PackagePlus, Search, Upload } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import { describeError } from '@/shared/api/http';
import { useDebouncedValue } from '@/shared/hooks/useDebouncedValue';
import { cn } from '@/shared/lib/cn';
import { buttonClasses } from '@/shared/ui/styles';
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog';
import { EmptyState, ErrorState, PageHeader, Spinner } from '@/shared/ui/display';
import { inputClasses } from '@/shared/ui/styles';
import { Pagination } from '@/shared/ui/Pagination';

import { ProductsTable } from '../components/ProductsTable';
import { productsQuery, useArchiveProduct } from '../queries';
import { fromSorting, toSorting } from '../table-sorting';
import type { Product } from '../types';

const route = getRouteApi('/admin/products');
const PAGE_SIZE = 20;

export function AdminProductsPage() {
  const search = route.useSearch();
  const navigate = route.useNavigate();
  const [text, setText] = useState(search.q ?? '');
  const debounced = useDebouncedValue(text.trim(), 300);
  const [pending, setPending] = useState<Product | null>(null);
  const archive = useArchiveProduct();
  const products = useQuery(productsQuery({ ...search, page_size: PAGE_SIZE }));

  useEffect(() => {
    if (debounced !== (search.q ?? '')) {
      void navigate({
        search: (previous) => ({ ...previous, q: debounced || undefined, page: undefined }),
        replace: true,
      });
    }
  }, [debounced, search.q, navigate]);

  const onArchive = useCallback((product: Product) => setPending(product), []);

  const confirmArchive = () => {
    if (!pending) {
      return;
    }
    archive.mutate(pending, {
      onSuccess: () => {
        toast.success(`${pending.name} was removed from the catalog`);
        setPending(null);
      },
      onError: (error) => {
        toast.error(describeError(error));
        setPending(null);
      },
    });
  };

  const page = products.data;

  return (
    <>
      <PageHeader
        title="Products"
        description="Create, edit and remove catalog products."
        actions={
          <>
            <Link to="/admin/import" className={buttonClasses('secondary')}>
              <Upload className="size-4" aria-hidden />
              Import CSV
            </Link>
            <Link to="/admin/products/new" className={buttonClasses('primary')}>
              <PackagePlus className="size-4" aria-hidden />
              New product
            </Link>
          </>
        }
      />
      <div className="relative mb-4 max-w-md">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-subtle"
          aria-hidden
        />
        <input
          type="search"
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Filter by name or SKU"
          aria-label="Filter products"
          className={cn(inputClasses(), 'pl-9')}
        />
      </div>
      {products.isError ? (
        <ErrorState message={describeError(products.error)} />
      ) : products.isPending ? (
        <Spinner label="Loading products" />
      ) : page && page.total === 0 ? (
        <EmptyState
          title={search.q ? 'No products match this filter' : 'The catalog is empty'}
          description="Create a product or import the sample CSV to get started."
          action={
            <Link to="/admin/import" className={buttonClasses('primary')}>
              Import products
            </Link>
          }
        />
      ) : (
        page && (
          <>
            <ProductsTable
              products={page.items}
              sorting={toSorting(search.sort)}
              onSortingChange={(sorting) =>
                void navigate({
                  search: (previous) => ({
                    ...previous,
                    sort: fromSorting(sorting),
                    page: undefined,
                  }),
                  replace: true,
                })
              }
              onArchive={onArchive}
            />
            <Pagination
              page={page.page}
              pageSize={page.page_size}
              total={page.total}
              totalPages={page.total_pages}
              onPageChange={(next) =>
                void navigate({ search: (previous) => ({ ...previous, page: next }) })
              }
            />
          </>
        )
      )}
      <ConfirmDialog
        open={pending !== null}
        title="Remove product?"
        description={
          <p>
            <span className="font-medium text-fg">{pending?.name}</span> will no longer be sold.
            Past orders keep their history.
          </p>
        }
        confirmLabel="Remove"
        loading={archive.isPending}
        onConfirm={confirmArchive}
        onCancel={() => setPending(null)}
      />
    </>
  );
}
