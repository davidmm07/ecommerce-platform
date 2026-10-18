import { getJson } from '@/shared/api/http';

export type RowOutcome = 'created' | 'updated' | 'unchanged' | 'skipped' | 'failed';

export type ImageOutcome = 'attached' | 'unchanged' | 'failed';

export type ImportRow = {
  line: number;
  sku: string | null;
  outcome: RowOutcome;
  image: ImageOutcome | null;
  messages: string[];
};

export type ImportReport = {
  dry_run: boolean;
  summary: {
    total_rows: number;
    created: number;
    updated: number;
    unchanged: number;
    skipped: number;
    failed: number;
    images: Record<ImageOutcome, number>;
  };
  rows: ImportRow[];
};

export const MAX_IMPORT_BYTES = 5 * 1024 * 1024;

export const importsApi = {
  upload: (file: File, dryRun: boolean) => {
    const body = new FormData();
    body.append('file', file);
    return getJson<ImportReport>('/product-imports', {
      method: 'POST',
      body,
      query: { dry_run: dryRun },
    });
  },
};
