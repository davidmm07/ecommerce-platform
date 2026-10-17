import { describe, expect, it } from 'vitest';

import { formatMoney, formatWeight, multiplyMoney, pluralize, sumMoney } from './format';

describe('money helpers', () => {
  it('formats decimal strings as currency', () => {
    expect(formatMoney('1299.5')).toBe('$1,299.50');
    expect(formatMoney('0.00')).toBe('$0.00');
  });

  it('multiplies and sums in cents to avoid floating point drift', () => {
    expect(multiplyMoney('0.10', 3)).toBe('0.30');
    expect(sumMoney(['0.10', '0.20'])).toBe('0.30');
    expect(sumMoney([multiplyMoney('19.99', 3), '4.99'])).toBe('64.96');
  });
});

describe('formatWeight', () => {
  it('uses grams below one kilogram', () => {
    expect(formatWeight('0.350')).toBe('350 g');
    expect(formatWeight('35.000')).toBe('35 kg');
    expect(formatWeight('1.25')).toBe('1.25 kg');
  });
});

describe('pluralize', () => {
  it('handles singular and plural forms', () => {
    expect(pluralize(1, 'product')).toBe('1 product');
    expect(pluralize(84, 'product')).toBe('84 products');
  });
});
