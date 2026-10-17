const moneyFormatters = new Map<string, Intl.NumberFormat>();

export function formatMoney(amount: string | number, currency = 'USD'): string {
  let formatter = moneyFormatters.get(currency);
  if (!formatter) {
    formatter = new Intl.NumberFormat('en-US', { style: 'currency', currency });
    moneyFormatters.set(currency, formatter);
  }
  return formatter.format(Number(amount));
}

export function multiplyMoney(unitPrice: string, quantity: number): string {
  const cents = Math.round(Number(unitPrice) * 100) * quantity;
  return (cents / 100).toFixed(2);
}

export function sumMoney(amounts: string[]): string {
  const cents = amounts.reduce((total, amount) => total + Math.round(Number(amount) * 100), 0);
  return (cents / 100).toFixed(2);
}

const dateFormatter = new Intl.DateTimeFormat('en-US', {
  dateStyle: 'medium',
  timeStyle: 'short',
});

export function formatDateTime(iso: string): string {
  return dateFormatter.format(new Date(iso));
}

export function formatWeight(kilograms: string | number): string {
  const value = Number(kilograms);
  return value < 1
    ? `${Math.round(value * 1000)} g`
    : `${value.toFixed(value % 1 === 0 ? 0 : 2)} kg`;
}

export function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`;
}
