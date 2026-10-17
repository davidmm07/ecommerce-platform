import { describe, expect, it } from 'vitest';

import {
  TEST_CARDS,
  cardBrand,
  formatCardNumber,
  formatExpiry,
  isExpired,
  parseExpiry,
  passesLuhn,
} from './card';

describe('card helpers', () => {
  it('validates numbers with the Luhn checksum', () => {
    expect(passesLuhn('4242 4242 4242 4242')).toBe(true);
    expect(passesLuhn('4242424242424241')).toBe(false);
    expect(passesLuhn('4242')).toBe(false);
    for (const card of TEST_CARDS) {
      expect(passesLuhn(card.number)).toBe(true);
    }
  });

  it('detects brands from the issuer prefix', () => {
    expect(cardBrand('4242424242424242')).toBe('visa');
    expect(cardBrand('5555555555554444')).toBe('mastercard');
    expect(cardBrand('2223003122003222')).toBe('mastercard');
    expect(cardBrand('378282246310005')).toBe('amex');
    expect(cardBrand('6011111111111117')).toBe('discover');
    expect(cardBrand('3530111333300000')).toBe('unknown');
  });

  it('formats card numbers and expiry dates while typing', () => {
    expect(formatCardNumber('42424242abc42424242')).toBe('4242 4242 4242 4242');
    expect(formatExpiry('1')).toBe('1');
    expect(formatExpiry('1230')).toBe('12/30');
    expect(formatExpiry('12/305')).toBe('12/30');
  });

  it('parses and checks expiry dates', () => {
    expect(parseExpiry('12/30')).toEqual({ month: 12, year: 2030 });
    expect(parseExpiry('13/30')).toBeNull();
    expect(parseExpiry('1230')).toBeNull();
    const today = new Date(2026, 9, 17);
    expect(isExpired({ month: 10, year: 2026 }, today)).toBe(false);
    expect(isExpired({ month: 9, year: 2026 }, today)).toBe(true);
  });
});
