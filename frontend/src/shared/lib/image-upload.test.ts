import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError, NetworkError, upload } from '@/shared/api/http';

import { prepareImageForUpload, validateImageFile } from './image-upload';

class FakeXhr {
  static last: FakeXhr;
  status = 0;
  statusText = '';
  responseText = '';
  method = '';
  url = '';
  headers: Record<string, string> = {};
  upload: { onprogress: ((event: ProgressEvent) => void) | null } = { onprogress: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  body: unknown;

  constructor() {
    FakeXhr.last = this;
  }

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }

  setRequestHeader(name: string, value: string) {
    this.headers[name] = value;
  }

  send(body: unknown) {
    this.body = body;
  }

  abort() {
    this.onabort?.();
  }

  respond(status: number, body: unknown) {
    this.status = status;
    this.responseText = JSON.stringify(body);
    this.onload?.();
  }
}

describe('image upload helpers', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('accepts common raster formats only', () => {
    expect(validateImageFile(new File(['x'], 'a.jpg', { type: 'image/jpeg' }))).toBeNull();
    expect(validateImageFile(new File(['x'], 'a.svg', { type: 'image/svg+xml' }))).toMatch(
      /JPEG, PNG, WebP or AVIF/,
    );
    const huge = new File([new Uint8Array(26 * 1024 * 1024)], 'a.png', { type: 'image/png' });
    expect(validateImageFile(huge)).toMatch(/25 MB/);
  });

  it('uploads the original when the browser cannot resize', async () => {
    const file = new File(['x'], 'a.jpg', { type: 'image/jpeg' });
    expect(await prepareImageForUpload(file)).toBe(file);
  });

  it('reports progress and parses the response', async () => {
    vi.stubGlobal('XMLHttpRequest', FakeXhr);
    const progress: number[] = [];
    const body = new FormData();
    const pending = upload<{ id: string }>('/products/p/image', body, {
      method: 'PUT',
      headers: { 'If-Match': '"2"' },
      onProgress: (fraction) => progress.push(fraction),
    });
    const xhr = FakeXhr.last;
    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 50, total: 100 } as ProgressEvent);
    xhr.respond(200, { id: 'p' });

    await expect(pending).resolves.toEqual({ id: 'p' });
    expect(progress).toEqual([0.5]);
    expect([xhr.method, xhr.url, xhr.headers['If-Match']]).toEqual([
      'PUT',
      '/api/v1/products/p/image',
      '"2"',
    ]);
    expect(xhr.body).toBe(body);
  });

  it('turns failures into API and network errors', async () => {
    vi.stubGlobal('XMLHttpRequest', FakeXhr);
    const rejected = upload('/products/p/image', new FormData());
    FakeXhr.last.respond(415, {
      type: 'urn:ecommerce:problem:unsupported_image_type',
      title: 'Unsupported image type',
      status: 415,
      detail: 'Upload a JPEG, PNG, WebP or AVIF image',
      code: 'unsupported_image_type',
    });
    await expect(rejected).rejects.toBeInstanceOf(ApiError);

    const offline = upload('/products/p/image', new FormData());
    FakeXhr.last.onerror?.();
    await expect(offline).rejects.toBeInstanceOf(NetworkError);

    const controller = new AbortController();
    const cancelled = upload('/products/p/image', new FormData(), { signal: controller.signal });
    controller.abort();
    await expect(cancelled).rejects.toMatchObject({ name: 'AbortError' });
  });
});
