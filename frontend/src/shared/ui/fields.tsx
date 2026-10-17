import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react';
import { useId } from 'react';

import { cn } from '@/shared/lib/cn';
import { inputClasses as controlClasses } from '@/shared/ui/styles';

type FieldShellProps = {
  id: string;
  label: string;
  hint?: ReactNode;
  error?: string;
  required?: boolean;
  children: ReactNode;
  className?: string;
};

export function FieldShell({
  id,
  label,
  hint,
  error,
  required,
  children,
  className,
}: FieldShellProps) {
  return (
    <div className={cn('space-y-1.5', className)}>
      <label htmlFor={id} className="block text-sm font-medium text-slate-800">
        {label}
        {required && <span className="ml-0.5 text-rose-500">*</span>}
      </label>
      {children}
      {error ? (
        <p id={`${id}-error`} role="alert" className="text-xs font-medium text-rose-600">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-xs text-slate-500">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

type BaseProps = {
  label: string;
  hint?: ReactNode;
  error?: string;
  containerClassName?: string;
};

export function TextField({
  label,
  hint,
  error,
  containerClassName,
  className,
  id,
  required,
  ...props
}: BaseProps & InputHTMLAttributes<HTMLInputElement>) {
  const generated = useId();
  const fieldId = id ?? generated;
  return (
    <FieldShell
      id={fieldId}
      label={label}
      hint={hint}
      error={error}
      required={required}
      className={containerClassName}
    >
      <input
        id={fieldId}
        aria-invalid={Boolean(error) || undefined}
        aria-describedby={error ? `${fieldId}-error` : hint ? `${fieldId}-hint` : undefined}
        required={required}
        className={cn(controlClasses(Boolean(error)), className)}
        {...props}
      />
    </FieldShell>
  );
}

export function TextAreaField({
  label,
  hint,
  error,
  containerClassName,
  className,
  id,
  required,
  ...props
}: BaseProps & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const generated = useId();
  const fieldId = id ?? generated;
  return (
    <FieldShell
      id={fieldId}
      label={label}
      hint={hint}
      error={error}
      required={required}
      className={containerClassName}
    >
      <textarea
        id={fieldId}
        aria-invalid={Boolean(error) || undefined}
        aria-describedby={error ? `${fieldId}-error` : hint ? `${fieldId}-hint` : undefined}
        required={required}
        className={cn(controlClasses(Boolean(error)), 'min-h-24', className)}
        {...props}
      />
    </FieldShell>
  );
}

export function SelectField({
  label,
  hint,
  error,
  containerClassName,
  className,
  id,
  required,
  children,
  ...props
}: BaseProps & SelectHTMLAttributes<HTMLSelectElement>) {
  const generated = useId();
  const fieldId = id ?? generated;
  return (
    <FieldShell
      id={fieldId}
      label={label}
      hint={hint}
      error={error}
      required={required}
      className={containerClassName}
    >
      <select
        id={fieldId}
        aria-invalid={Boolean(error) || undefined}
        required={required}
        className={cn(controlClasses(Boolean(error)), 'pr-8', className)}
        {...props}
      >
        {children}
      </select>
    </FieldShell>
  );
}
