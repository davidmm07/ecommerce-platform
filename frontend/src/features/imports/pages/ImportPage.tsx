import { useMutation, useQueryClient } from '@tanstack/react-query';
import { FileSpreadsheet, UploadCloud } from 'lucide-react';
import { useId, useState } from 'react';
import { toast } from 'sonner';

import { productKeys } from '@/features/catalog/queries';
import { describeError } from '@/shared/api/http';
import { cn } from '@/shared/lib/cn';
import { Button } from '@/shared/ui/Button';
import { Card, ErrorState, PageHeader } from '@/shared/ui/display';

import { MAX_IMPORT_BYTES, importsApi } from '../api';
import { ImportResults } from '../components/ImportResults';

const COLUMNS = ['name', 'sku', 'description', 'category', 'price', 'stock', 'weight_kg'];

export function ImportPage() {
  const inputId = useId();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [dryRun, setDryRun] = useState(true);
  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: ({ selected, validateOnly }: { selected: File; validateOnly: boolean }) =>
      importsApi.upload(selected, validateOnly),
    onSuccess: (report) => {
      if (!report.dry_run) {
        void queryClient.invalidateQueries({ queryKey: productKeys.all });
      }
      const { created, updated, failed } = report.summary;
      toast.success(
        report.dry_run
          ? `Validated ${report.summary.total_rows} rows`
          : `Imported: ${created} created, ${updated} updated, ${failed} failed`,
      );
    },
  });

  const choose = (selected: File | undefined) => {
    setLocalError(null);
    upload.reset();
    if (!selected) {
      return;
    }
    if (!selected.name.toLowerCase().endsWith('.csv')) {
      setLocalError('Choose a .csv file.');
      return;
    }
    if (selected.size > MAX_IMPORT_BYTES) {
      setLocalError('The file is larger than 5 MB.');
      return;
    }
    setFile(selected);
  };

  return (
    <>
      <PageHeader
        title="Import products"
        description="Create or update products in bulk from a CSV file. Rows are matched by SKU."
      />
      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <Card className="space-y-4 self-start p-6">
          <label
            htmlFor={inputId}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              choose(event.dataTransfer.files[0]);
            }}
            className={cn(
              'flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors',
              dragging
                ? 'border-accent bg-accent-soft'
                : 'border-line-strong hover:border-accent-hover',
            )}
          >
            {file ? (
              <>
                <FileSpreadsheet className="size-10 text-accent-fg" aria-hidden />
                <p className="mt-3 font-medium text-fg">{file.name}</p>
                <p className="text-sm text-fg-muted">
                  {(file.size / 1024).toFixed(1)} KB, click to change
                </p>
              </>
            ) : (
              <>
                <UploadCloud className="size-10 text-fg-subtle" aria-hidden />
                <p className="mt-3 font-medium text-fg">Drop a CSV file here or click to browse</p>
                <p className="text-sm text-fg-muted">UTF-8, up to 5 MB and 5,000 rows</p>
              </>
            )}
            <input
              id={inputId}
              type="file"
              accept=".csv,text/csv"
              className="sr-only"
              onChange={(event) => {
                choose(event.target.files?.[0]);
                event.target.value = '';
              }}
            />
          </label>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <label className="inline-flex items-center gap-2 text-sm text-fg-secondary">
              <input
                type="checkbox"
                checked={dryRun}
                onChange={(event) => setDryRun(event.target.checked)}
                className="size-4 rounded border-line-strong text-accent-fg focus:ring-accent"
              />
              Validate only (dry run, nothing is saved)
            </label>
            <Button
              disabled={!file}
              loading={upload.isPending}
              icon={<UploadCloud className="size-4" aria-hidden />}
              onClick={() => file && upload.mutate({ selected: file, validateOnly: dryRun })}
            >
              {dryRun ? 'Validate file' : 'Import products'}
            </Button>
          </div>
          {(localError || upload.isError) && (
            <ErrorState message={localError ?? describeError(upload.error)} />
          )}
        </Card>
        <Card className="space-y-3 p-5 text-sm text-fg-secondary">
          <h2 className="text-base font-semibold text-fg">File format</h2>
          <p>The first row must name these columns, in any order:</p>
          <code className="block break-all rounded-lg bg-slate-900 p-3 font-mono text-xs leading-relaxed text-slate-100 dark:bg-slate-950 dark:ring-1 dark:ring-line">
            {COLUMNS.join(',')}
          </code>
          <ul className="list-inside list-disc space-y-1">
            <li>Existing SKUs are updated, new ones are created.</li>
            <li>Price needs up to 2 decimals and must be above 0, a leading $ is accepted.</li>
            <li>Stock is a whole number of units, weight is in kilograms.</li>
            <li>If a SKU repeats, the last row wins and earlier ones are reported.</li>
            <li>Invalid rows are reported and skipped, valid rows are saved together.</li>
          </ul>
        </Card>
      </div>
      {upload.data && (
        <div className="mt-8">
          <ImportResults report={upload.data} />
        </div>
      )}
    </>
  );
}
