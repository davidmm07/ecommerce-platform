export type FieldIssue = {
  field: string;
  message: string;
};

export type ProblemDetails = {
  type: string;
  title: string;
  status: number;
  detail: string;
  code: string;
  instance?: string;
  request_id?: string | null;
  errors?: FieldIssue[];
  [extension: string]: unknown;
};

export type Page<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

export class ApiError extends Error {
  readonly status: number;
  readonly problem: ProblemDetails;

  constructor(problem: ProblemDetails) {
    super(problem.detail || problem.title);
    this.name = 'ApiError';
    this.status = problem.status;
    this.problem = problem;
  }

  get code(): string {
    return this.problem.code;
  }

  get fieldErrors(): FieldIssue[] {
    return this.problem.errors ?? [];
  }
}

export class NetworkError extends Error {
  constructor(cause: unknown) {
    super('The server could not be reached. Check your connection and try again.', { cause });
    this.name = 'NetworkError';
  }
}

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

type QueryValue = string | number | boolean | null | undefined;

export type RequestOptions = {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  body?: unknown;
  query?: Record<string, QueryValue>;
  headers?: Record<string, string>;
  signal?: AbortSignal;
};

export type ApiResponse<T> = {
  data: T;
  headers: Headers;
  status: number;
};

export function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value));
    }
  }
  const search = params.toString();
  return `${API_BASE_URL}${path}${search ? `?${search}` : ''}`;
}

export async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<ApiResponse<T>> {
  const { method = 'GET', body, query, headers = {}, signal } = options;
  const isForm = body instanceof FormData;
  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      signal,
      headers: {
        Accept: 'application/json',
        ...(body !== undefined && !isForm ? { 'Content-Type': 'application/json' } : {}),
        ...headers,
      },
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error;
    }
    throw new NetworkError(error);
  }
  if (!response.ok) {
    throw new ApiError(await readProblem(response));
  }
  const data: unknown = response.status === 204 ? undefined : await response.json();
  return { data: data as T, headers: response.headers, status: response.status };
}

export async function getJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return (await request<T>(path, options)).data;
}

async function readProblem(response: Response): Promise<ProblemDetails> {
  let text = '';
  try {
    text = await response.text();
  } catch {
    text = '';
  }
  return parseProblem(response.status, response.statusText, text);
}

function parseProblem(status: number, statusText: string, text: string): ProblemDetails {
  const fallback: ProblemDetails = {
    type: 'about:blank',
    title: statusText || 'Request failed',
    status,
    detail: `The server answered with status ${status}.`,
    code: 'http_error',
  };
  try {
    const payload: unknown = JSON.parse(text);
    if (payload && typeof payload === 'object' && 'status' in payload) {
      return { ...fallback, ...(payload as Partial<ProblemDetails>) };
    }
  } catch {
    return fallback;
  }
  return fallback;
}

export type UploadOptions = {
  method?: 'POST' | 'PUT';
  headers?: Record<string, string>;
  onProgress?: (fraction: number) => void;
  signal?: AbortSignal;
};

export function upload<T>(path: string, body: FormData, options: UploadOptions = {}): Promise<T> {
  const { method = 'POST', headers = {}, onProgress, signal } = options;
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, buildUrl(path));
    xhr.setRequestHeader('Accept', 'application/json');
    for (const [name, value] of Object.entries(headers)) {
      xhr.setRequestHeader(name, value);
    }
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(event.loaded / event.total);
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as T);
        } catch (error) {
          reject(new NetworkError(error));
        }
        return;
      }
      reject(new ApiError(parseProblem(xhr.status, xhr.statusText, xhr.responseText)));
    };
    xhr.onerror = () => reject(new NetworkError(new Error('upload failed')));
    xhr.onabort = () => reject(new DOMException('The upload was cancelled', 'AbortError'));
    signal?.addEventListener('abort', () => xhr.abort(), { once: true });
    xhr.send(body);
  });
}

export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status >= 500 && error.code === 'internal_error') {
      const reference = error.problem.request_id ? ` Reference: ${error.problem.request_id}.` : '';
      return `Something went wrong on our side.${reference}`;
    }
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'Unexpected error.';
}

export function isRetryable(error: unknown): boolean {
  return error instanceof NetworkError || (error instanceof ApiError && error.status >= 500);
}
