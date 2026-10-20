import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ClipboardCheck, FileSpreadsheet, UploadCloud } from 'lucide-react';
import { useId, useState } from 'react';
import { toast } from 'sonner';

import { productKeys } from '@/features/catalog/queries';
import { describeError } from '@/shared/api/http';
import { cn } from '@/shared/lib/cn';
import { Button } from '@/shared/ui/Button';
import { Card, ErrorState, PageHeader } from '@/shared/ui/display';

import type { ImportReport } from '../api';
import { MAX_IMPORT_BYTES, importsApi } from '../api';
import type { ImportMode } from '../components/ImportModePicker';
import { ImportModePicker } from '../components/ImportModePicker';
import { ImportResults } from '../components/ImportResults';

const COLUMNS = ['name', 'sku', 'description', 'category', 'price', 'stock', 'weight_kg'];
const IMAGE_COLUMNS = [
  'image_url',
  'image_author',
  'image_license',
  'image_license_url',
  'image_source_url',
];

export function ImportPage() {
  const inputId = useId();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<ImportMode>('validate');
  const [report, setReport] = useState<ImportReport | null>(null);
  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: ({ selected, validateOnly }: { selected: File; validateOnly: boolean }) =>
      importsApi.upload(selected, validateOnly),
    onSuccess: (result) => {
      setReport(result);
      if (!result.dry_run) {
        void queryClient.invalidateQueries({ queryKey: productKeys.all });
      }
      const { created, updated, failed, images } = result.summary;
      const imageNote = images.attached + images.failed > 0 ? `, ${images.attached} images` : '';
      toast.success(
        result.dry_run
          ? `Validated ${result.summary.total_rows} rows`
          : `Imported: ${created} created, ${updated} updated, ${failed} failed${imageNote}`,
      );
    },
  });

  const run = (validateOnly: boolean) => {
    if (file) {
      upload.mutate({ selected: file, validateOnly });
    }
  };

  const choose = (selected: File | undefined) => {
    setLocalError(null);
    setReport(null);
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
          <ImportModePicker value={mode} onChange={setMode} disabled={upload.isPending} />
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-fg-muted">
              {file ? `Ready: ${file.name}` : 'Choose a CSV file to continue.'}
            </p>
            <Button
              size="lg"
              className="w-full sm:w-auto"
              disabled={!file}
              loading={upload.isPending}
              icon={
                mode === 'validate' ? (
                  <ClipboardCheck className="size-5" aria-hidden />
                ) : (
                  <UploadCloud className="size-5" aria-hidden />
                )
              }
              onClick={() => run(mode === 'validate')}
            >
              {mode === 'validate' ? 'Validate file' : 'Import products'}
            </Button>
          </div>
          {upload.isPending && upload.variables.validateOnly === false && (
            <p className="text-sm text-fg-muted" role="status">
              Saving products, then downloading and optimizing their images. Large files can take a
              minute.
            </p>
          )}
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
          <p>Optional image columns:</p>
          <code className="block break-all rounded-lg bg-slate-900 p-3 font-mono text-xs leading-relaxed text-slate-100 dark:bg-slate-950 dark:ring-1 dark:ring-line">
            {IMAGE_COLUMNS.join(',')}
          </code>
          <ul className="list-inside list-disc space-y-1">
            <li>Existing SKUs are updated, new ones are created.</li>
            <li>Price needs up to 2 decimals and must be above 0, a leading $ is accepted.</li>
            <li>Stock is a whole number of units, weight is in kilograms.</li>
            <li>If a SKU repeats, the last row wins and earlier ones are reported.</li>
            <li>Invalid rows are reported and skipped, valid rows are saved together.</li>
            <li>
              An image_url is downloaded after the products are saved. A failed download is reported
              and the product keeps its current image.
            </li>
          </ul>
        </Card>
      </div>
      {report && (
        <div className="mt-8">
          <ImportResults
            report={report}
            importing={upload.isPending}
            onImport={
              file && report.dry_run
                ? () => {
                    setMode('import');
                    run(false);
                  }
                : undefined
            }
          />
        </div>
      )}
    </>
  );
}
