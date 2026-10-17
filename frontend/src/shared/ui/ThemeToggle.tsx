import { Monitor, Moon, Sun } from 'lucide-react';

import type { ThemePreference } from '@/shared/theme/theme';
import { nextPreference, themeActions, useThemePreference } from '@/shared/theme/theme';

const OPTIONS: Record<ThemePreference, { label: string; icon: typeof Sun }> = {
  system: { label: 'System theme', icon: Monitor },
  light: { label: 'Light theme', icon: Sun },
  dark: { label: 'Dark theme', icon: Moon },
};

export function ThemeToggle() {
  const preference = useThemePreference();
  const current = OPTIONS[preference];
  const next = OPTIONS[nextPreference(preference)];
  const Icon = current.icon;
  return (
    <button
      type="button"
      onClick={() => themeActions.cycle()}
      className="grid size-9 shrink-0 place-items-center rounded-lg text-fg-muted hover:bg-surface-hover hover:text-fg focus-visible:outline-2 focus-visible:outline-accent"
      aria-label={`${current.label}. Switch to ${next.label.toLowerCase()}`}
      title={`${current.label}, click for ${next.label.toLowerCase()}`}
    >
      <Icon className="size-5" aria-hidden />
    </button>
  );
}
