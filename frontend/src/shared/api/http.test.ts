import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError, NetworkError, buildUrl, describeError, isRetryable, request } from './http';

const problem = {
  type: 'urn:ecommerce:problem:validation_failed',
  title: 'Validation failed',
  status: 422,
  detail: 'price: must be greater than 0',
  code: 'validation_failed',
  request_id: 'abc123',
  errors: [{ field: 'price', message: 'must be greater than 0' }],
};

function mockFetch(response: Response | Error) {
  const fetchMock = vi.fn(() =>
    response instanceof Error ? Promise.reject(response) : Promise.resolve(response),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('http client', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('builds urls without empty query values', () => {
    expect(buildUrl('/products', { q: 'shoes', page: 2, category: undefined, sort: '' })).toBe(
      '/api/v1/products?q=shoes&page=2',
    );
  });

  it('sends JSON and returns data with headers', async () => {
    const fetchMock = mockFetch(
      new Response(JSON.stringify({ id: '1' }), { status: 201, headers: { ETag: '"1"' } }),
    );
    const response = await request<{ id: string }>('/products', {
      method: 'POST',
      body: { name: 'x' },
      headers: { 'If-Match': '"1"' },
    });
    expect(response.data).toEqual({ id: '1' });
    expect(response.headers.get('etag')).toBe('"1"');
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.body).toBe('{"name":"x"}');
    expect(init.headers).toMatchObject({
      'Content-Type': 'application/json',
      'If-Match': '"1"',
    });
  });

  it('turns problem details into ApiError', async () => {
    mockFetch(new Response(JSON.stringify(problem), { status: 422 }));
    const error = await request('/products').catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect(apiError.status).toBe(422);
    expect(apiError.code).toBe('validation_failed');
    expect(apiError.fieldErrors).toEqual(problem.errors);
    expect(isRetryable(apiError)).toBe(false);
  });

  it('falls back to a generic problem for non JSON errors', async () => {
    mockFetch(new Response('bad gateway', { status: 502, statusText: 'Bad Gateway' }));
    const error = (await request('/products').catch((caught: unknown) => caught)) as ApiError;
    expect(error.problem.title).toBe('Bad Gateway');
    expect(isRetryable(error)).toBe(true);
  });

  it('wraps connection failures in NetworkError', async () => {
    mockFetch(new TypeError('Failed to fetch'));
    const error = await request('/products').catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(NetworkError);
    expect(isRetryable(error)).toBe(true);
  });

  it('hides internal error details behind the request id', () => {
    const error = new ApiError({ ...problem, status: 500, code: 'internal_error' });
    expect(describeError(error)).toBe('Something went wrong on our side. Reference: abc123.');
    expect(describeError(new ApiError(problem))).toBe('price: must be greater than 0');
  });
});
