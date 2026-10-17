import { AlertTriangle, Loader2 } from 'lucide-react';
import type { ReactNode } from 'react';

import { cn } from '@/shared/lib/cn';

type Tone = 'neutral' | 'info' | 'success' | 'warning' | 'danger';

const tones: Record<Tone, string> = {
  neutral: 'bg-slate-100 text-slate-700 ring-slate-500/20',
  info: 'bg-indigo-50 text-indigo-700 ring-indigo-600/20',
  success: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  warning: 'bg-amber-50 text-amber-800 ring-amber-600/20',
  danger: 'bg-rose-50 text-rose-700 ring-rose-600/20',
};

export function Badge({
  tone = 'neutral',
  children,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset',
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('rounded-xl bg-white shadow-sm ring-1 ring-slate-200', className)}>
      {children}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {description && <p className="mt-1 text-sm text-slate-600">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div role="status" className="flex items-center justify-center gap-2 py-16 text-slate-500">
      <Loader2 className="size-5 animate-spin" aria-hidden />
      <span className="text-sm">{label}...</span>
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center rounded-xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
      {icon && <div className="mb-3 text-slate-400">{icon}</div>}
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      {description && <p className="mt-1 max-w-md text-sm text-slate-600">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, action }: { message: string; action?: ReactNode }) {
  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-3 rounded-xl bg-rose-50 p-4 text-sm text-rose-800 ring-1 ring-rose-200 sm:flex-row sm:items-center"
    >
      <AlertTriangle className="size-5 shrink-0" aria-hidden />
      <p className="flex-1">{message}</p>
      {action}
    </div>
  );
}

export function StatTile({
  label,
  value,
  tone = 'neutral',
}: {
  label: string;
  value: ReactNode;
  tone?: Tone;
}) {
  const accent: Record<Tone, string> = {
    neutral: 'text-slate-900',
    info: 'text-indigo-700',
    success: 'text-emerald-700',
    warning: 'text-amber-700',
    danger: 'text-rose-700',
  };
  return (
    <Card className="px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={cn('mt-1 text-2xl font-semibold tabular-nums', accent[tone])}>{value}</p>
    </Card>
  );
}
