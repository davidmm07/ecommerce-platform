export type CardBrand = 'visa' | 'mastercard' | 'amex' | 'discover' | 'unknown';

export function digitsOnly(value: string): string {
  return value.replace(/\D/g, '');
}

export function passesLuhn(number: string): boolean {
  const digits = digitsOnly(number);
  if (digits.length < 12 || digits.length > 19) {
    return false;
  }
  let total = 0;
  for (let index = 0; index < digits.length; index += 1) {
    let digit = Number(digits[digits.length - 1 - index]);
    if (index % 2 === 1) {
      digit *= 2;
      if (digit > 9) {
        digit -= 9;
      }
    }
    total += digit;
  }
  return total % 10 === 0;
}

export function cardBrand(number: string): CardBrand {
  const digits = digitsOnly(number);
  const firstTwo = Number(digits.slice(0, 2));
  const firstFour = Number(digits.slice(0, 4));
  if (digits.startsWith('4')) return 'visa';
  if (firstTwo === 34 || firstTwo === 37) return 'amex';
  if ((firstTwo >= 51 && firstTwo <= 55) || (firstFour >= 2221 && firstFour <= 2720)) {
    return 'mastercard';
  }
  if (digits.startsWith('6011') || digits.startsWith('65')) return 'discover';
  return 'unknown';
}

const BRAND_LABELS: Record<CardBrand, string> = {
  visa: 'Visa',
  mastercard: 'Mastercard',
  amex: 'American Express',
  discover: 'Discover',
  unknown: 'Card',
};

export function brandLabel(brand: string): string {
  return BRAND_LABELS[brand as CardBrand] ?? 'Card';
}

export function formatCardNumber(value: string): string {
  return digitsOnly(value)
    .slice(0, 19)
    .replace(/(\d{4})(?=\d)/g, '$1 ');
}

export function formatExpiry(value: string): string {
  const digits = digitsOnly(value).slice(0, 4);
  return digits.length > 2 ? `${digits.slice(0, 2)}/${digits.slice(2)}` : digits;
}

export function parseExpiry(value: string): { month: number; year: number } | null {
  const match = /^(\d{2})\/(\d{2})$/.exec(value.trim());
  if (!match) {
    return null;
  }
  const month = Number(match[1]);
  const year = 2000 + Number(match[2]);
  return month >= 1 && month <= 12 ? { month, year } : null;
}

export function isExpired(expiry: { month: number; year: number }, today = new Date()): boolean {
  const current = today.getFullYear() * 12 + today.getMonth() + 1;
  return expiry.year * 12 + expiry.month < current;
}

export const TEST_CARDS = [
  { number: '4242 4242 4242 4242', outcome: 'Approved (Visa)' },
  { number: '5555 5555 5555 4444', outcome: 'Approved (Mastercard)' },
  { number: '4000 0000 0000 0259', outcome: 'Approved after an automatic retry' },
  { number: '4000 0000 0000 0002', outcome: 'Declined: card_declined' },
  { number: '4000 0000 0000 9995', outcome: 'Declined: insufficient_funds' },
  { number: '4000 0000 0000 0127', outcome: 'Declined: incorrect_cvc' },
  { number: '4000 0000 0000 0119', outcome: 'Provider outage, stock is released' },
] as const;
