import { Store, useStore } from '@tanstack/react-store';

export const THEME_PREFERENCES = ['system', 'light', 'dark'] as const;
export const THEME_STORAGE_KEY = 'ecommerce.theme';

export type ThemePreference = (typeof THEME_PREFERENCES)[number];
export type ResolvedTheme = 'light' | 'dark';

type ThemeState = {
  preference: ThemePreference;
  system: ResolvedTheme;
};

const darkQuery =
  typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    ? window.matchMedia('(prefers-color-scheme: dark)')
    : null;

function isPreference(value: unknown): value is ThemePreference {
  return typeof value === 'string' && (THEME_PREFERENCES as readonly string[]).includes(value);
}

function readPreference(): ThemePreference {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isPreference(stored) ? stored : 'system';
  } catch {
    return 'system';
  }
}

function writePreference(preference: ThemePreference): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    return;
  }
}

export function resolveTheme(preference: ThemePreference, system: ResolvedTheme): ResolvedTheme {
  return preference === 'system' ? system : preference;
}

export function nextPreference(preference: ThemePreference): ThemePreference {
  const index = THEME_PREFERENCES.indexOf(preference);
  return THEME_PREFERENCES[(index + 1) % THEME_PREFERENCES.length] ?? 'system';
}

export const themeStore = new Store<ThemeState>({
  preference: readPreference(),
  system: darkQuery?.matches ? 'dark' : 'light',
});

export function applyTheme(root: HTMLElement = document.documentElement): void {
  const { preference, system } = themeStore.state;
  const theme = resolveTheme(preference, system);
  root.classList.toggle('dark', theme === 'dark');
  root.style.colorScheme = theme;
}

themeStore.subscribe(() => {
  writePreference(themeStore.state.preference);
  applyTheme();
});

darkQuery?.addEventListener('change', (event) => {
  themeStore.setState((state) => ({ ...state, system: event.matches ? 'dark' : 'light' }));
});

export const themeActions = {
  set(preference: ThemePreference): void {
    themeStore.setState((state) => ({ ...state, preference }));
  },
  cycle(): void {
    themeStore.setState((state) => ({ ...state, preference: nextPreference(state.preference) }));
  },
};

export function useThemePreference(): ThemePreference {
  return useStore(themeStore, (state) => state.preference);
}

export function useResolvedTheme(): ResolvedTheme {
  return useStore(themeStore, (state) => resolveTheme(state.preference, state.system));
}
