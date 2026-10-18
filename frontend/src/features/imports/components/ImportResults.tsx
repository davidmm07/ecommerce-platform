import { useMemo, useState } from 'react';

import { cn } from '@/shared/lib/cn';
import { Badge, Card, StatTile } from '@/shared/ui/display';

import type { ImageOutcome, ImportReport, RowOutcome } from '../api';

const OUTCOME_TONE: Record<RowOutcome, 'success' | 'info' | 'neutral' | 'warning' | 'danger'> = {
  created: 'success',
  updated: 'info',
  unchanged: 'neutral',
  skipped: 'warning',
  failed: 'danger',
};

const IMAGE_TONE: Record<ImageOutcome, 'success' | 'neutral' | 'danger'> = {
  attached: 'success',
  unchanged: 'neutral',
  failed: 'danger',
};

const FILTERS: Array<{ value: RowOutcome | 'issues' | 'all'; label: string }> = [
  { value: 'issues', label: 'Needs attention' },
  { value: 'all', label: 'All rows' },
  { value: 'created', label: 'Created' },
  { value: 'updated', label: 'Updated' },
  { value: 'unchanged', label: 'Unchanged' },
  { value: 'skipped', label: 'Skipped' },
  { value: 'failed', label: 'Failed' },
];

export function ImportResults({ report }: { report: ImportReport }) {
  const [filter, setFilter] = useState<RowOutcome | 'issues' | 'all'>('issues');
  const rows = useMemo(
    () =>
      report.rows.filter((row) => {
        if (filter === 'all') return true;
        if (filter === 'issues') {
          return row.outcome === 'failed' || row.outcome === 'skipped' || row.messages.length > 0;
        }
        return row.outcome === filter;
      }),
    [report.rows, filter],
  );
  const { summary } = report;
  const hasImages = report.rows.some((row) => row.image !== null);

  return (
    <section className="space-y-4" aria-label="Import results">
      {report.dry_run && (
        <p className="rounded-lg bg-accent-soft px-4 py-3 text-sm text-accent-soft-fg ring-1 ring-accent/20">
          Dry run: nothing was saved and no image was downloaded. Upload again without "Validate
          only" to apply these changes.
        </p>
      )}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatTile label="Rows" value={summary.total_rows} />
        <StatTile label="Created" value={summary.created} tone="success" />
        <StatTile label="Updated" value={summary.updated} tone="info" />
        <StatTile label="Unchanged" value={summary.unchanged} />
        <StatTile label="Skipped" value={summary.skipped} tone="warning" />
        <StatTile label="Failed" value={summary.failed} tone="danger" />
      </div>
      {hasImages && (
        <div className="grid grid-cols-3 gap-3 lg:grid-cols-6">
          <StatTile label="Images attached" value={summary.images.attached} tone="success" />
          <StatTile label="Images unchanged" value={summary.images.unchanged} />
          <StatTile label="Images failed" value={summary.images.failed} tone="danger" />
        </div>
      )}
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Filter rows">
        {FILTERS.map((option) => (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={filter === option.value}
            onClick={() => setFilter(option.value)}
            className={cn(
              'rounded-full px-3 py-1 text-sm font-medium ring-1 ring-inset',
              filter === option.value
                ? 'bg-fg text-surface ring-fg'
                : 'bg-surface text-fg-secondary ring-line-strong hover:bg-surface-muted',
            )}
          >
            {option.label}
          </button>
        ))}
      </div>
      <Card className="overflow-x-auto">
        <table className="min-w-full divide-y divide-line text-sm">
          <thead className="bg-surface-muted text-left text-xs font-semibold uppercase tracking-wide text-fg-muted">
            <tr>
              <th scope="col" className="w-16 px-4 py-3">
                Line
              </th>
              <th scope="col" className="w-32 px-4 py-3">
                SKU
              </th>
              <th scope="col" className="w-32 px-4 py-3">
                Outcome
              </th>
              {hasImages && (
                <th scope="col" className="w-32 px-4 py-3">
                  Image
                </th>
              )}
              <th scope="col" className="px-4 py-3">
                Details
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-soft">
            {rows.length === 0 ? (
              <tr>
                <td colSpan={hasImages ? 5 : 4} className="px-4 py-8 text-center text-fg-muted">
                  No rows in this view.
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.line}>
                  <td className="px-4 py-3 tabular-nums text-fg-muted">{row.line}</td>
                  <td className="px-4 py-3 font-mono text-xs">{row.sku ?? '-'}</td>
                  <td className="px-4 py-3">
                    <Badge tone={OUTCOME_TONE[row.outcome]} className="capitalize">
                      {row.outcome}
                    </Badge>
                  </td>
                  {hasImages && (
                    <td className="px-4 py-3">
                      {row.image ? (
                        <Badge tone={IMAGE_TONE[row.image]} className="capitalize">
                          {row.image}
                        </Badge>
                      ) : (
                        <span className="text-fg-subtle">-</span>
                      )}
                    </td>
                  )}
                  <td className="px-4 py-3 text-fg-secondary">
                    {row.messages.length > 0 ? (
                      <ul className="list-inside list-disc space-y-0.5">
                        {row.messages.map((message) => (
                          <li key={message}>{message}</li>
                        ))}
                      </ul>
                    ) : (
                      <span className="text-fg-subtle">-</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </Card>
    </section>
  );
}
