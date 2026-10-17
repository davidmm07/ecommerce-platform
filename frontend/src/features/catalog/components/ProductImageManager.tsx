import { ImagePlus, Link2, Trash2, UploadCloud } from 'lucide-react';
import { useEffect, useId, useState } from 'react';
import { toast } from 'sonner';

import { describeError } from '@/shared/api/http';
import { cn } from '@/shared/lib/cn';
import {
  ACCEPTED_IMAGE_TYPES,
  prepareImageForUpload,
  validateImageFile,
} from '@/shared/lib/image-upload';
import { Button } from '@/shared/ui/Button';
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog';
import { Card, ErrorState } from '@/shared/ui/display';
import { TextField } from '@/shared/ui/fields';
import { ResponsiveImage } from '@/shared/ui/ResponsiveImage';

import {
  useImportProductImageFromUrl,
  useRemoveProductImage,
  useUploadProductImage,
} from '../queries';
import type { Product } from '../types';
import { PhotoCredit } from './PhotoCredit';

export function ProductImageManager({ product }: { product: Product }) {
  const inputId = useId();
  const [progress, setProgress] = useState<number | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const uploadImage = useUploadProductImage(setProgress);
  const importImage = useImportProductImageFromUrl();
  const removeImage = useRemoveProductImage();
  const busy = uploadImage.isPending || importImage.isPending || removeImage.isPending;
  const [remote, setRemote] = useState({ url: '', author: '', license: '', source: '' });

  const importFromUrl = async () => {
    const url = remote.url.trim();
    if (!/^https:\/\//i.test(url)) {
      setError('Enter an https:// image URL.');
      return;
    }
    const author = remote.author.trim();
    if (author && (!remote.license.trim() || !remote.source.trim())) {
      setError('A credit needs the author, the license and the source page.');
      return;
    }
    setError(null);
    try {
      await importImage.mutateAsync({
        product,
        body: {
          url,
          credit: author
            ? { author, license: remote.license.trim(), source_url: remote.source.trim() }
            : null,
        },
      });
      setRemote({ url: '', author: '', license: '', source: '' });
      toast.success('Image imported');
    } catch (importError) {
      setError(describeError(importError));
    }
  };

  useEffect(
    () => () => {
      if (preview) {
        URL.revokeObjectURL(preview);
      }
    },
    [preview],
  );

  const choose = async (file: File | undefined) => {
    if (!file || busy) {
      return;
    }
    const problem = validateImageFile(file);
    if (problem) {
      setError(problem);
      return;
    }
    setError(null);
    setProgress(0);
    setPreview(URL.createObjectURL(file));
    try {
      const prepared = await prepareImageForUpload(file);
      await uploadImage.mutateAsync({ product, file: prepared });
      toast.success('Image updated');
    } catch (uploadError) {
      setError(describeError(uploadError));
    } finally {
      setPreview(null);
      setProgress(null);
    }
  };

  return (
    <Card className="space-y-4 p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-fg">Product image</h2>
          <p className="text-sm text-fg-muted">
            JPEG, PNG, WebP or AVIF. It is resized, converted to AVIF and WebP and served from a
            cache friendly URL.
          </p>
        </div>
        {product.image && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setConfirming(true)}
            disabled={busy}
            icon={<Trash2 className="size-4" aria-hidden />}
          >
            Remove
          </Button>
        )}
      </div>
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
          void choose(event.dataTransfer.files[0]);
        }}
        className={cn(
          'relative block cursor-pointer overflow-hidden rounded-xl ring-2 ring-dashed transition-colors',
          dragging ? 'ring-accent' : 'ring-line-strong hover:ring-accent-hover',
          busy && 'cursor-progress',
        )}
      >
        {preview ? (
          <img src={preview} alt="" className="aspect-[4/3] w-full bg-media object-contain" />
        ) : product.image ? (
          <ResponsiveImage
            image={product.image}
            alt={product.name}
            sizes="(min-width: 768px) 480px, 100vw"
            fit="contain"
            className="aspect-[4/3] w-full"
          />
        ) : (
          <div className="flex aspect-[4/3] w-full flex-col items-center justify-center gap-2 bg-media text-center text-fg-muted">
            <ImagePlus className="size-10" aria-hidden />
            <span className="font-medium text-fg">Drop an image or click to browse</span>
            <span className="text-xs">Up to 25 MB, large photos are downscaled before upload</span>
          </div>
        )}
        {progress !== null && (
          <div className="absolute inset-x-0 bottom-0 bg-slate-950/70 p-3 text-xs text-white">
            <div className="mb-1 flex items-center gap-2">
              <UploadCloud className="size-4" aria-hidden />
              {progress < 1 ? `Uploading ${Math.round(progress * 100)}%` : 'Processing...'}
            </div>
            <div
              role="progressbar"
              aria-label="Upload progress"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(progress * 100)}
              className="h-1.5 overflow-hidden rounded-full bg-white/20"
            >
              <div
                className="h-full bg-white transition-[width]"
                style={{ width: `${Math.round(progress * 100)}%` }}
              />
            </div>
          </div>
        )}
        <input
          id={inputId}
          type="file"
          accept={ACCEPTED_IMAGE_TYPES.join(',')}
          className="sr-only"
          disabled={busy}
          aria-label="Choose a product image"
          onChange={(event) => {
            void choose(event.target.files?.[0]);
            event.target.value = '';
          }}
        />
      </label>
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          void importFromUrl();
        }}
      >
        <TextField
          label="Or import from a URL"
          type="url"
          inputMode="url"
          placeholder="https://images.example.com/photo.jpg"
          value={remote.url}
          onChange={(event) => setRemote({ ...remote, url: event.target.value })}
          hint="The server downloads, validates and optimizes it. Private addresses are blocked."
        />
        <details className="text-sm">
          <summary className="cursor-pointer text-fg-muted hover:text-fg">
            Add a photo credit (optional)
          </summary>
          <div className="mt-3 space-y-3">
            <TextField
              label="Author"
              value={remote.author}
              onChange={(event) => setRemote({ ...remote, author: event.target.value })}
            />
            <TextField
              label="License"
              placeholder="CC BY 2.0"
              value={remote.license}
              onChange={(event) => setRemote({ ...remote, license: event.target.value })}
            />
            <TextField
              label="Source page"
              type="url"
              placeholder="https://www.flickr.com/photos/..."
              value={remote.source}
              onChange={(event) => setRemote({ ...remote, source: event.target.value })}
            />
          </div>
        </details>
        <Button
          type="submit"
          variant="secondary"
          disabled={busy || !remote.url.trim()}
          loading={importImage.isPending}
          icon={<Link2 className="size-4" aria-hidden />}
        >
          Import image
        </Button>
      </form>
      {product.image?.credit && <PhotoCredit credit={product.image.credit} />}
      {error && <ErrorState message={error} />}
      <ConfirmDialog
        open={confirming}
        title="Remove image?"
        description="The product will show a placeholder until a new image is uploaded."
        confirmLabel="Remove image"
        loading={removeImage.isPending}
        onCancel={() => setConfirming(false)}
        onConfirm={() =>
          removeImage.mutate(product, {
            onSuccess: () => toast.success('Image removed'),
            onError: (removeError) => setError(describeError(removeError)),
            onSettled: () => setConfirming(false),
          })
        }
      />
    </Card>
  );
}
