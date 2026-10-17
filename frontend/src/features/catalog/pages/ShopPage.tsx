import { useQuery } from '@tanstack/react-query';
import { getRouteApi } from '@tanstack/react-router';
import { PackageSearch } from 'lucide-react';
import { useCallback } from 'react';

import { describeError } from '@/shared/api/http';
import { pluralize } from '@/shared/lib/format';
import { Button } from '@/shared/ui/Button';
import { EmptyState, ErrorState, PageHeader } from '@/shared/ui/display';
import { Pagination } from '@/shared/ui/Pagination';

import { ProductCard } from '../components/ProductCard';
import { SearchToolbar } from '../components/SearchToolbar';
import { categoriesQuery, productsQuery } from '../queries';
import type { ShopSearch } from '../search-params';

const route = getRouteApi('/products');
const PAGE_SIZE = 12;

export function ShopPage() {
  const search = route.useSearch();
  const navigate = route.useNavigate();
  const categories = useQuery(categoriesQuery());
  const products = useQuery(productsQuery({ ...search, page_size: PAGE_SIZE }));

  const updateSearch = useCallback(
    (changes: Partial<ShopSearch>) => {
      void navigate({
        search: (previous) => ({ ...previous, ...changes, page: undefined }),
        replace: true,
      });
    },
    [navigate],
  );

  const resetSearch = useCallback(() => {
    void navigate({ search: {}, replace: true });
  }, [navigate]);

  const page = products.data;

  return (
    <>
      <PageHeader
        title="Shop"
        description={
          page
            ? `${pluralize(page.total, 'product')} found`
            : 'Find products by name, SKU or description.'
        }
      />
      <SearchToolbar
        search={search}
        categories={categories.data ?? []}
        onChange={updateSearch}
        onReset={resetSearch}
      />
      <section aria-live="polite" aria-busy={products.isFetching} className="mt-6">
        {products.isError ? (
          <ErrorState
            message={describeError(products.error)}
            action={
              <Button variant="secondary" size="sm" onClick={() => void products.refetch()}>
                Try again
              </Button>
            }
          />
        ) : products.isPending ? (
          <ProductGridSkeleton />
        ) : page && page.items.length === 0 ? (
          <EmptyState
            icon={<PackageSearch className="size-10" aria-hidden />}
            title="No products match your search"
            description="Try a different term, remove a filter or check the spelling."
            action={
              <Button variant="secondary" onClick={resetSearch}>
                Clear search
              </Button>
            }
          />
        ) : (
          page && (
            <>
              <div
                className={`grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 ${products.isPlaceholderData ? 'opacity-60' : ''}`}
              >
                {page.items.map((product, index) => (
                  <ProductCard
                    key={product.id}
                    product={product}
                    priority={page.page === 1 && index < 4}
                  />
                ))}
              </div>
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
      </section>
    </>
  );
}

function ProductGridSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" aria-hidden>
      {Array.from({ length: 8 }, (_, index) => (
        <div key={index} className="h-80 animate-pulse rounded-xl bg-surface ring-1 ring-line" />
      ))}
    </div>
  );
}
