import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { ImportReport } from '../api';
import { ImportResults } from './ImportResults';

function report(rows: ImportReport['rows']): ImportReport {
  return {
    dry_run: false,
    summary: {
      total_rows: rows.length,
      created: rows.length,
      updated: 0,
      unchanged: 0,
      skipped: 0,
      failed: 0,
      images: {
        attached: rows.filter((row) => row.image === 'attached').length,
        unchanged: 0,
        failed: rows.filter((row) => row.image === 'failed').length,
      },
    },
    rows,
  };
}

describe('ImportResults', () => {
  it('shows image outcomes when the file had image columns', () => {
    render(
      <ImportResults
        report={report([
          { line: 2, sku: 'DL-001', outcome: 'created', image: 'attached', messages: [] },
          {
            line: 3,
            sku: 'FL-001',
            outcome: 'created',
            image: 'failed',
            messages: ['image: The image URL answered 404'],
          },
        ])}
      />,
    );
    expect(screen.getByText('Images attached').nextSibling).toHaveTextContent('1');
    expect(screen.getByRole('columnheader', { name: 'Image' })).toBeInTheDocument();
    const failedRow = screen.getByText('FL-001').closest('tr');
    expect(failedRow).not.toBeNull();
    expect(within(failedRow as HTMLElement).getByText('failed')).toBeInTheDocument();
    expect(screen.getByText('image: The image URL answered 404')).toBeInTheDocument();
  });

  it('hides the image column for files without images', () => {
    render(
      <ImportResults
        report={report([
          { line: 2, sku: 'DL-001', outcome: 'created', image: null, messages: ['note'] },
        ])}
      />,
    );
    expect(screen.queryByRole('columnheader', { name: 'Image' })).toBeNull();
    expect(screen.queryByText('Images attached')).toBeNull();
  });
});
