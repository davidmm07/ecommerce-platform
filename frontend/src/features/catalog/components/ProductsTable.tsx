import { Link } from '@tanstack/react-router';
import type { ColumnDef, SortingState } from '@tanstack/react-table';
import { flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table';
import { ArrowDown, ArrowUp, ArrowUpDown, Pencil, Trash2 } from 'lucide-react';
import { useMemo } from 'react';

import { cn } from '@/shared/lib/cn';
import { formatDateTime, formatMoney, formatWeight } from '@/shared/lib/format';
import { ResponsiveImage } from '@/shared/ui/ResponsiveImage';
import { buttonClasses, dangerHover, dangerText } from '@/shared/ui/styles';

import type { Product } from '../types';
import { StockBadge } from './StockBadge';

type ProductsTableProps = {
  products: Product[];
  sorting: SortingState;
  onSortingChange: (sorting: SortingState) => void;
  onArchive: (product: Product) => void;
};

export function ProductsTable({
  products,
  sorting,
  onSortingChange,
  onArchive,
}: ProductsTableProps) {
  const columns = useMemo<ColumnDef<Product>[]>(
    () => [
      {
        accessorKey: 'sku',
        header: 'SKU',
        enableSorting: false,
        cell: (info) => <span className="font-mono text-xs">{info.getValue<string>()}</span>,
      },
      {
        accessorKey: 'name',
        header: 'Name',
        cell: ({ row }) => (
          <div className="flex items-center gap-3">
            <ResponsiveImage
              image={row.original.image}
              alt={row.original.name}
              sizes="48px"
              className="size-12 shrink-0 rounded-md"
            />
            <div>
              <p className="font-medium text-fg">{row.original.name}</p>
              <p className="text-xs text-fg-muted">{row.original.category_label}</p>
            </div>
          </div>
        ),
      },
      {
        accessorKey: 'price',
        header: 'Price',
        cell: ({ row }) => (
          <span className="tabular-nums">
            {formatMoney(row.original.price, row.original.currency)}
          </span>
        ),
      },
      {
        accessorKey: 'stock',
        header: 'Stock',
        enableSorting: false,
        cell: ({ row }) => (
          <div className="flex items-center gap-2">
            <span className="w-10 text-right tabular-nums">{row.original.stock}</span>
            <StockBadge stock={row.original.stock} />
          </div>
        ),
      },
      {
        accessorKey: 'weight_kg',
        header: 'Weight',
        enableSorting: false,
        cell: ({ row }) => formatWeight(row.original.weight_kg),
      },
      {
        accessorKey: 'created_at',
        header: 'Created',
        sortDescFirst: true,
        cell: ({ row }) => (
          <span className="whitespace-nowrap text-fg-muted">
            {formatDateTime(row.original.created_at)}
          </span>
        ),
      },
      {
        id: 'actions',
        header: () => <span className="sr-only">Actions</span>,
        enableSorting: false,
        cell: ({ row }) => (
          <div className="flex justify-end gap-1">
            <Link
              to="/admin/products/$productId/edit"
              params={{ productId: row.original.id }}
              className={buttonClasses('ghost', 'sm')}
              aria-label={`Edit ${row.original.name}`}
            >
              <Pencil className="size-4" aria-hidden />
            </Link>
            <button
              type="button"
              className={cn(buttonClasses('ghost', 'sm'), dangerText, dangerHover)}
              onClick={() => onArchive(row.original)}
              aria-label={`Delete ${row.original.name}`}
            >
              <Trash2 className="size-4" aria-hidden />
            </button>
          </div>
        ),
      },
    ],
    [onArchive],
  );

  const table = useReactTable({
    data: products,
    columns,
    state: { sorting },
    manualSorting: true,
    enableMultiSort: false,
    enableSortingRemoval: true,
    onSortingChange: (updater) =>
      onSortingChange(typeof updater === 'function' ? updater(sorting) : updater),
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.id,
  });

  return (
    <div className="overflow-x-auto rounded-xl bg-surface shadow-sm ring-1 ring-line">
      <table className="min-w-full divide-y divide-line text-sm">
        <thead className="bg-surface-muted">
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => {
                const sorted = header.column.getIsSorted();
                const canSort = header.column.getCanSort();
                const content = flexRender(header.column.columnDef.header, header.getContext());
                return (
                  <th
                    key={header.id}
                    scope="col"
                    aria-sort={
                      sorted === 'asc' ? 'ascending' : sorted === 'desc' ? 'descending' : undefined
                    }
                    className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-fg-muted"
                  >
                    {canSort ? (
                      <button
                        type="button"
                        onClick={header.column.getToggleSortingHandler()}
                        className="inline-flex items-center gap-1 uppercase hover:text-fg"
                      >
                        {content}
                        {sorted === 'asc' ? (
                          <ArrowUp className="size-3.5" aria-hidden />
                        ) : sorted === 'desc' ? (
                          <ArrowDown className="size-3.5" aria-hidden />
                        ) : (
                          <ArrowUpDown className="size-3.5 opacity-40" aria-hidden />
                        )}
                      </button>
                    ) : (
                      content
                    )}
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody className="divide-y divide-line-soft">
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id} className="hover:bg-surface-muted">
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-4 py-3 align-middle text-fg-secondary">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
