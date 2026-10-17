import { afterEach, describe, expect, it } from 'vitest';

import {
  THEME_STORAGE_KEY,
  applyTheme,
  nextPreference,
  resolveTheme,
  themeActions,
  themeStore,
} from './theme';

describe('theme', () => {
  afterEach(() => themeActions.set('system'));

  it('resolves the system preference', () => {
    expect(resolveTheme('system', 'dark')).toBe('dark');
    expect(resolveTheme('light', 'dark')).toBe('light');
    expect(resolveTheme('dark', 'light')).toBe('dark');
  });

  it('cycles through system, light and dark', () => {
    expect(nextPreference('system')).toBe('light');
    expect(nextPreference('light')).toBe('dark');
    expect(nextPreference('dark')).toBe('system');
  });

  it('applies the class and color scheme and persists the choice', () => {
    themeActions.set('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.documentElement.style.colorScheme).toBe('dark');
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');

    themeActions.cycle();
    expect(themeStore.state.preference).toBe('system');
    themeStore.setState((state) => ({ ...state, system: 'light' }));
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('can apply the theme to any root element', () => {
    const root = document.createElement('div');
    themeActions.set('dark');
    applyTheme(root);
    expect(root.classList.contains('dark')).toBe(true);
  });
});
