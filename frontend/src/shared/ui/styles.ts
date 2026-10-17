import { cn } from '@/shared/lib/cn';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

const variants: Record<ButtonVariant, string> = {
  primary:
    'bg-indigo-600 text-white hover:bg-indigo-500 focus-visible:outline-indigo-600 shadow-sm',
  secondary:
    'bg-white text-slate-900 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 focus-visible:outline-slate-400 shadow-sm',
  ghost: 'text-slate-700 hover:bg-slate-100 focus-visible:outline-slate-400',
  danger: 'bg-rose-600 text-white hover:bg-rose-500 focus-visible:outline-rose-600 shadow-sm',
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
    'block w-full rounded-lg border-0 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm ring-1 ring-inset',
    'placeholder:text-slate-400 focus:ring-2 focus:ring-inset disabled:bg-slate-50 disabled:text-slate-500',
    invalid ? 'ring-rose-400 focus:ring-rose-500' : 'ring-slate-300 focus:ring-indigo-600',
  );
