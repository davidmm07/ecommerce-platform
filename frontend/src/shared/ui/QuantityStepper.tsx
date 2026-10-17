import { Minus, Plus } from 'lucide-react';

import { cn } from '@/shared/lib/cn';

type QuantityStepperProps = {
  value: number;
  max: number;
  min?: number;
  onChange: (value: number) => void;
  label: string;
  size?: 'sm' | 'md';
};

export function QuantityStepper({
  value,
  max,
  min = 1,
  onChange,
  label,
  size = 'md',
}: QuantityStepperProps) {
  const clamp = (next: number) => Math.min(Math.max(next, min), Math.max(max, min));
  const height = size === 'sm' ? 'h-8' : 'h-10';
  return (
    <div
      className={cn(
        'inline-flex items-center rounded-lg bg-surface shadow-sm ring-1 ring-inset ring-line-strong',
        height,
      )}
    >
      <button
        type="button"
        className="grid h-full w-8 place-items-center text-fg-muted hover:text-fg disabled:opacity-40"
        onClick={() => onChange(clamp(value - 1))}
        disabled={value <= min}
        aria-label={`Decrease ${label}`}
      >
        <Minus className="size-3.5" aria-hidden />
      </button>
      <input
        type="number"
        inputMode="numeric"
        className="h-full w-12 border-0 bg-transparent p-0 text-center text-sm tabular-nums focus:ring-0 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
        value={value}
        min={min}
        max={max}
        aria-label={label}
        onChange={(event) => {
          const parsed = Number.parseInt(event.target.value, 10);
          if (!Number.isNaN(parsed)) {
            onChange(clamp(parsed));
          }
        }}
      />
      <button
        type="button"
        className="grid h-full w-8 place-items-center text-fg-muted hover:text-fg disabled:opacity-40"
        onClick={() => onChange(clamp(value + 1))}
        disabled={value >= max}
        aria-label={`Increase ${label}`}
      >
        <Plus className="size-3.5" aria-hidden />
      </button>
    </div>
  );
}
