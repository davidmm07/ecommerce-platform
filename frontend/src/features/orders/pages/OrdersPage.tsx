import { useQuery } from '@tanstack/react-query';
import { Link, getRouteApi } from '@tanstack/react-router';
import type { ColumnDef } from '@tanstack/react-table';
import { flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table';
import { ReceiptText, Search } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { describeError } from '@/shared/api/http';
import { useDebouncedValue } from '@/shared/hooks/useDebouncedValue';
import { cn } from '@/shared/lib/cn';
import { formatDateTime, formatMoney } from '@/shared/lib/format';
import { buttonClasses } from '@/shared/ui/styles';
import { EmptyState, ErrorState, PageHeader, Spinner } from '@/shared/ui/display';
import { inputClasses } from '@/shared/ui/styles';
import { Pagination } from '@/shared/ui/Pagination';

import { ordersQuery } from '../api';
import { OrderStatusBadge } from '../components/OrderStatusBadge';
import type { OrderSummary } from '../types';

const route = getRouteApi('/orders');
const PAGE_SIZE = 20;

export function OrdersPage() {
  const search = route.useSearch();
  const navigate = route.useNavigate();
  const [email, setEmail] = useState(search.email ?? '');
  const debounced = useDebouncedValue(email.trim(), 400);
  const orders = useQuery(ordersQuery({ ...search, page_size: PAGE_SIZE }));

  useEffect(() => {
    if (debounced !== (search.email ?? '')) {
      void navigate({ search: { email: debounced || undefined }, replace: true });
    }
  }, [debounced, search.email, navigate]);

  const columns = useMemo<ColumnDef<OrderSummary>[]>(
    () => [
      {
        accessorKey: 'number',
        header: 'Order',
        cell: ({ row }) => (
          <Link
            to="/orders/$orderId"
            params={{ orderId: row.original.id }}
            className="font-mono font-medium text-accent-fg hover:text-accent-hover"
          >
            {row.original.number}
          </Link>
        ),
      },
      {
        accessorKey: 'created_at',
        header: 'Placed',
        cell: ({ row }) => (
          <span className="whitespace-nowrap">{formatDateTime(row.original.created_at)}</span>
        ),
      },
      {
        accessorKey: 'customer_name',
        header: 'Customer',
        cell: ({ row }) => (
          <div>
            <p className="font-medium text-fg">{row.original.customer_name}</p>
            <p className="text-xs text-fg-muted">{row.original.customer_email}</p>
          </div>
        ),
      },
      { accessorKey: 'item_count', header: 'Items' },
      {
        accessorKey: 'total',
        header: 'Total',
        cell: ({ row }) => (
          <span className="tabular-nums">
            {formatMoney(row.original.total, row.original.currency)}
          </span>
        ),
      },
      {
        accessorKey: 'status',
        header: 'Status',
        cell: ({ row }) => <OrderStatusBadge status={row.original.status} />,
      },
    ],
    [],
  );

  const table = useReactTable({
    data: orders.data?.items ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.id,
    manualPagination: true,
  });

  const page = orders.data;

  return (
    <>
      <PageHeader
        title="Orders"
        description="Every checkout attempt, including declined payments."
      />
      <div className="relative mb-4 max-w-md">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-subtle"
          aria-hidden
        />
        <input
          type="search"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="Filter by customer email"
          aria-label="Filter by customer email"
          className={cn(inputClasses(), 'pl-9')}
        />
      </div>
      {orders.isError ? (
        <ErrorState message={describeError(orders.error)} />
      ) : orders.isPending ? (
        <Spinner label="Loading orders" />
      ) : page && page.total === 0 ? (
        <EmptyState
          icon={<ReceiptText className="size-10" aria-hidden />}
          title="No orders yet"
          description="Orders appear here after a checkout."
          action={
            <Link to="/products" className={buttonClasses('primary')}>
              Go shopping
            </Link>
          }
        />
      ) : (
        page && (
          <>
            <div className="overflow-x-auto rounded-xl bg-surface shadow-sm ring-1 ring-line">
              <table className="min-w-full divide-y divide-line text-sm">
                <thead className="bg-surface-muted">
                  {table.getHeaderGroups().map((group) => (
                    <tr key={group.id}>
                      {group.headers.map((header) => (
                        <th
                          key={header.id}
                          scope="col"
                          className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-fg-muted"
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                        </th>
                      ))}
                    </tr>
                  ))}
                </thead>
                <tbody className="divide-y divide-line-soft">
                  {table.getRowModel().rows.map((row) => (
                    <tr key={row.id} className="hover:bg-surface-muted">
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="px-4 py-3 text-fg-secondary">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
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
    </>
  );
}
