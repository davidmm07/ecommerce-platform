import type { AnyFieldApi } from '@tanstack/react-form';
import { useCallback, useState } from 'react';

import { ApiError } from '@/shared/api/http';

export type ServerErrors = Record<string, string>;

export function fieldError(
  field: AnyFieldApi,
  serverErrors: ServerErrors = {},
): string | undefined {
  const meta = field.state.meta;
  const submitted = field.form.state.submissionAttempts > 0;
  const clientError = meta.isTouched || submitted ? messageOf(meta.errors[0]) : undefined;
  return clientError ?? serverErrors[field.name as string];
}

function messageOf(error: unknown): string | undefined {
  if (!error) {
    return undefined;
  }
  if (typeof error === 'string') {
    return error;
  }
  if (typeof error === 'object' && 'message' in error && typeof error.message === 'string') {
    return error.message;
  }
  return undefined;
}

export function serverFieldErrors(error: unknown, fieldNames: readonly string[]): ServerErrors {
  if (!(error instanceof ApiError)) {
    return {};
  }
  const errors: ServerErrors = {};
  for (const issue of error.fieldErrors) {
    if (fieldNames.includes(issue.field) && !(issue.field in errors)) {
      errors[issue.field] = issue.message;
    }
  }
  return errors;
}

export function useServerErrors() {
  const [errors, setErrors] = useState<ServerErrors>({});
  const clear = useCallback((field: string) => {
    setErrors((current) => {
      if (!(field in current)) {
        return current;
      }
      const next = { ...current };
      delete next[field];
      return next;
    });
  }, []);
  return { errors, setErrors, clear };
}
