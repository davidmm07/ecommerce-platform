export function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `checkout-${crypto.randomUUID()}`;
  }
  const random = Array.from({ length: 4 }, () => Math.random().toString(36).slice(2, 10)).join('');
  return `checkout-${random}`;
}
