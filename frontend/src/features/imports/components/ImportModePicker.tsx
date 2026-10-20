import { ClipboardCheck, DatabaseZap } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import { cn } from '@/shared/lib/cn';

export type ImportMode = 'validate' | 'import';

const OPTIONS: Array<{
  value: ImportMode;
  title: string;
  description: string;
  icon: LucideIcon;
}> = [
  {
    value: 'validate',
    title: 'Validate only',
    description: 'Dry run: check every row and preview the report. Nothing is saved.',
    icon: ClipboardCheck,
  },
  {
    value: 'import',
    title: 'Import products',
    description: 'Save the valid rows in one transaction, then download their images.',
    icon: DatabaseZap,
  },
];

export function ImportModePicker({
  value,
  onChange,
  disabled = false,
}: {
  value: ImportMode;
  onChange: (mode: ImportMode) => void;
  disabled?: boolean;
}) {
  return (
    <fieldset disabled={disabled} className="min-w-0">
      <legend className="text-sm font-semibold text-fg">What should happen?</legend>
      <div className="mt-2 grid gap-3 sm:grid-cols-2">
        {OPTIONS.map(({ value: option, title, description, icon: Icon }) => {
          const selected = option === value;
          return (
            <label
              key={option}
              className={cn(
                'relative flex cursor-pointer items-start gap-3 rounded-xl p-4 transition-colors',
                'has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-accent',
                'has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-60',
                selected
                  ? 'bg-accent-soft ring-2 ring-accent'
                  : 'bg-surface ring-1 ring-line-strong hover:bg-surface-muted',
              )}
            >
              <input
                type="radio"
                name="import-mode"
                value={option}
                checked={selected}
                onChange={() => onChange(option)}
                className="sr-only"
              />
              <span
                className={cn(
                  'flex size-10 shrink-0 items-center justify-center rounded-lg',
                  selected ? 'bg-accent text-white' : 'bg-surface-hover text-fg-muted',
                )}
                aria-hidden
              >
                <Icon className="size-5" />
              </span>
              <span className="min-w-0 flex-1">
                <span
                  className={cn(
                    'block text-sm font-semibold',
                    selected ? 'text-accent-soft-fg' : 'text-fg',
                  )}
                >
                  {title}
                </span>
                <span className="mt-0.5 block text-sm text-fg-muted">{description}</span>
              </span>
              <span
                className={cn(
                  'mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full',
                  selected ? 'bg-accent' : 'ring-2 ring-inset ring-line-strong',
                )}
                aria-hidden
              >
                {selected && <span className="size-2 rounded-full bg-white" />}
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
