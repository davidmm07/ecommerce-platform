import { CreditCard } from 'lucide-react';

import { TEST_CARDS } from '../card';

export function TestCards({ onPick }: { onPick: (number: string) => void }) {
  return (
    <details className="rounded-lg bg-accent-soft p-3 text-sm ring-1 ring-accent/20">
      <summary className="flex cursor-pointer items-center gap-2 font-medium text-accent-soft-fg">
        <CreditCard className="size-4" aria-hidden />
        Payments are simulated, pick a test card
      </summary>
      <ul className="mt-3 space-y-1.5">
        {TEST_CARDS.map((card) => (
          <li key={card.number} className="flex flex-wrap items-center justify-between gap-2">
            <button
              type="button"
              onClick={() => onPick(card.number)}
              className="font-mono text-accent-fg underline-offset-2 hover:underline"
            >
              {card.number}
            </button>
            <span className="text-fg-muted">{card.outcome}</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-fg-muted">
        Use any future expiry date and any 3 digit CVC. No real payment is made.
      </p>
    </details>
  );
}
