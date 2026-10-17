export const ACCEPTED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/avif'];
export const MAX_SOURCE_BYTES = 25 * 1024 * 1024;
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
export const MAX_UPLOAD_DIMENSION = 2560;
const RESIZE_ABOVE_BYTES = 3 * 1024 * 1024;

export function validateImageFile(file: File): string | null {
  if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
    return 'Choose a JPEG, PNG, WebP or AVIF image.';
  }
  if (file.size > MAX_SOURCE_BYTES) {
    return 'The image is larger than 25 MB.';
  }
  return null;
}

export async function prepareImageForUpload(
  file: File,
  { maxDimension = MAX_UPLOAD_DIMENSION, quality = 0.9 } = {},
): Promise<File> {
  if (typeof createImageBitmap !== 'function' || typeof document === 'undefined') {
    return file;
  }
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
  } catch {
    return file;
  }
  try {
    const scale = Math.min(1, maxDimension / Math.max(bitmap.width, bitmap.height));
    if (scale === 1 && file.size <= RESIZE_ABOVE_BYTES) {
      return file;
    }
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    const context = canvas.getContext('2d');
    if (!context) {
      return file;
    }
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, 'image/webp', quality),
    );
    if (!blob || blob.size >= file.size || !ACCEPTED_IMAGE_TYPES.includes(blob.type)) {
      return file;
    }
    const extension = blob.type.split('/')[1] ?? 'webp';
    return new File([blob], `${file.name.replace(/\.[^.]+$/, '')}.${extension}`, {
      type: blob.type,
    });
  } finally {
    bitmap.close();
  }
}
