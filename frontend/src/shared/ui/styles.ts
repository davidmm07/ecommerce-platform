import { cn } from '@/shared/lib/cn';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

const variants: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-white hover:bg-accent-hover focus-visible:outline-accent shadow-sm',
  secondary:
    'bg-surface text-fg ring-1 ring-inset ring-line-strong hover:bg-surface-muted focus-visible:outline-line-strong shadow-sm',
  ghost: 'text-fg-secondary hover:bg-surface-hover focus-visible:outline-line-strong',
  danger:
    'bg-rose-600 text-white hover:bg-rose-500 focus-visible:outline-rose-600 shadow-sm dark:bg-rose-500 dark:hover:bg-rose-400',
};

const sizes: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-sm gap-1.5',
  md: 'h-10 px-4 text-sm gap-2',
  lg: 'h-12 px-6 text-base gap-2',
};

export const buttonClasses = (variant: ButtonVariant = 'primary', size: ButtonSize = 'md') =>
  cn(
    'inline-flex items-center justify-center rounded-lg font-medium transition-colors',
    'focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60',
    variants[variant],
    sizes[size],
  );

export const inputClasses = (invalid = false) =>
  cn(
    'block w-full rounded-lg border-0 bg-surface px-3 py-2 text-sm text-fg shadow-sm ring-1 ring-inset',
    'placeholder:text-fg-subtle focus:ring-2 focus:ring-inset disabled:bg-surface-muted disabled:text-fg-muted',
    invalid
      ? 'ring-rose-400 focus:ring-rose-500 dark:ring-rose-500/70'
      : 'ring-line-strong focus:ring-accent',
  );

export type Tone = 'neutral' | 'info' | 'success' | 'warning' | 'danger';

export const softTone: Record<Tone, string> = {
  neutral: 'bg-surface-hover text-fg-secondary ring-line-strong/60',
  info: 'bg-accent-soft text-accent-fg ring-accent/25',
  success:
    'bg-emerald-50 text-emerald-800 ring-emerald-600/20 dark:bg-emerald-400/10 dark:text-emerald-300 dark:ring-emerald-400/25',
  warning:
    'bg-amber-50 text-amber-900 ring-amber-600/20 dark:bg-amber-400/10 dark:text-amber-200 dark:ring-amber-400/25',
  danger:
    'bg-rose-50 text-rose-800 ring-rose-600/20 dark:bg-rose-400/10 dark:text-rose-300 dark:ring-rose-400/25',
};

export const strongTone: Record<Tone, string> = {
  neutral: 'text-fg',
  info: 'text-accent-fg',
  success: 'text-emerald-700 dark:text-emerald-400',
  warning: 'text-amber-700 dark:text-amber-400',
  danger: 'text-rose-700 dark:text-rose-400',
};

export const dangerText = 'text-rose-600 dark:text-rose-400';

export const dangerHover =
  'hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-400/10 dark:hover:text-rose-400';
