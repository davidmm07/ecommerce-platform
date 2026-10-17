import { ChevronLeft, ChevronRight } from 'lucide-react';

import { Button } from '@/shared/ui/Button';

type PaginationProps = {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
};

export function Pagination({ page, totalPages, total, pageSize, onPageChange }: PaginationProps) {
  if (total === 0) {
    return null;
  }
  const first = (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);
  return (
    <nav
      aria-label="Pagination"
      className="mt-6 flex flex-col items-center justify-between gap-3 text-sm text-slate-600 sm:flex-row"
    >
      <p>
        Showing <span className="font-medium text-slate-900">{first}</span> to{' '}
        <span className="font-medium text-slate-900">{last}</span> of{' '}
        <span className="font-medium text-slate-900">{total}</span>
      </p>
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          icon={<ChevronLeft className="size-4" aria-hidden />}
        >
          Previous
        </Button>
        <span className="tabular-nums">
          Page {page} of {Math.max(totalPages, 1)}
        </span>
        <Button
          variant="secondary"
          size="sm"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          Next
          <ChevronRight className="size-4" aria-hidden />
        </Button>
      </div>
    </nav>
  );
}
