import { ImagePlus, Trash2, UploadCloud } from 'lucide-react';
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
import { ResponsiveImage } from '@/shared/ui/ResponsiveImage';

import { useRemoveProductImage, useUploadProductImage } from '../queries';
import type { Product } from '../types';

export function ProductImageManager({ product }: { product: Product }) {
  const inputId = useId();
  const [progress, setProgress] = useState<number | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const uploadImage = useUploadProductImage(setProgress);
  const removeImage = useRemoveProductImage();
  const busy = uploadImage.isPending || removeImage.isPending;

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
