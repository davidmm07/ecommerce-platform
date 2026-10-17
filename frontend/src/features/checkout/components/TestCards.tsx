import { CreditCard } from 'lucide-react';

import { TEST_CARDS } from '../card';

export function TestCards({ onPick }: { onPick: (number: string) => void }) {
  return (
    <details className="rounded-lg bg-indigo-50/60 p-3 text-sm ring-1 ring-indigo-100">
      <summary className="flex cursor-pointer items-center gap-2 font-medium text-indigo-900">
        <CreditCard className="size-4" aria-hidden />
        Payments are simulated, pick a test card
      </summary>
      <ul className="mt-3 space-y-1.5">
        {TEST_CARDS.map((card) => (
          <li key={card.number} className="flex flex-wrap items-center justify-between gap-2">
            <button
              type="button"
              onClick={() => onPick(card.number)}
              className="font-mono text-indigo-700 underline-offset-2 hover:underline"
            >
              {card.number}
            </button>
            <span className="text-slate-600">{card.outcome}</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-slate-500">
        Use any future expiry date and any 3 digit CVC. No real payment is made.
      </p>
    </details>
  );
}
