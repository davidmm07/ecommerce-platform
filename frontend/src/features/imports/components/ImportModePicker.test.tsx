import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';

import type { ImportMode } from './ImportModePicker';
import { ImportModePicker } from './ImportModePicker';

function Harness({ disabled = false }: { disabled?: boolean }) {
  const [mode, setMode] = useState<ImportMode>('validate');
  return (
    <>
      <ImportModePicker value={mode} onChange={setMode} disabled={disabled} />
      <output>{mode}</output>
    </>
  );
}

describe('ImportModePicker', () => {
  it('starts on validate only and switches with a click or the keyboard', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const group = screen.getByRole('group', { name: 'What should happen?' });
    expect(group).toBeInTheDocument();
    const validate = screen.getByRole('radio', { name: /Validate only/ });
    const save = screen.getByRole('radio', { name: /Import products/ });
    expect(validate).toBeChecked();
    expect(validate).toHaveAccessibleName(/Nothing is saved/);

    await user.click(screen.getByText('Import products'));
    expect(save).toBeChecked();
    expect(screen.getByRole('status')).toHaveTextContent('import');

    await user.keyboard('{ArrowLeft}');
    expect(validate).toBeChecked();
  });

  it('can be disabled while a file is being processed', () => {
    render(<Harness disabled />);
    expect(screen.getByRole('radio', { name: /Import products/ })).toBeDisabled();
  });
});
