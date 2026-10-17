import type { ReactNode } from 'react';
import { useEffect, useRef } from 'react';

import { Button } from '@/shared/ui/Button';

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  description: ReactNode;
  confirmLabel: string;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  loading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) {
      return;
    }
    if (open && !dialog.open) {
      dialog.showModal?.();
    } else if (!open && dialog.open) {
      dialog.close?.();
    }
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      onCancel={(event) => {
        event.preventDefault();
        onCancel();
      }}
      aria-labelledby="confirm-dialog-title"
      className="m-auto w-full max-w-md rounded-xl p-0 shadow-xl backdrop:bg-slate-900/40"
    >
      {open && (
        <div className="p-6">
          <h2 id="confirm-dialog-title" className="text-lg font-semibold text-slate-900">
            {title}
          </h2>
          <div className="mt-2 text-sm text-slate-600">{description}</div>
          <div className="mt-6 flex justify-end gap-2">
            <Button variant="secondary" onClick={onCancel} disabled={loading}>
              Cancel
            </Button>
            <Button variant="danger" onClick={onConfirm} loading={loading}>
              {confirmLabel}
            </Button>
          </div>
        </div>
      )}
    </dialog>
  );
}
