import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Night 3, BUG 4 (no export state): the dashboard Export button had no feedback
// and swallowed every error (`.catch(() => {})`). Export spawns Chrome and
// renders images — it takes seconds. Silence is a bug. This test demands a real
// idle → generating → (download | error) state machine.

vi.mock('../lib/api', () => ({ api: { exportReport: vi.fn() } }));
import { api } from '../lib/api';
import ExportDashboardButton from './ExportDashboardButton';

describe('ExportDashboardButton', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows a generating state while exporting, then returns to idle', async () => {
    let resolve;
    api.exportReport.mockReturnValue(new Promise((r) => { resolve = r; }));
    render(<ExportDashboardButton conversationId="c1" />);

    const btn = screen.getByRole('button', { name: /export/i });
    await userEvent.click(btn);

    expect(screen.getByText(/generating|exporting/i)).toBeInTheDocument();
    expect(screen.getByRole('button')).toBeDisabled();

    resolve('pdf');
    await screen.findByRole('button', { name: /export/i });
    expect(screen.getByRole('button')).not.toBeDisabled();
  });

  it('surfaces an error instead of swallowing it', async () => {
    api.exportReport.mockRejectedValue(new Error('Chrome not found'));
    render(<ExportDashboardButton conversationId="c1" />);

    await userEvent.click(screen.getByRole('button', { name: /export/i }));

    expect(await screen.findByText(/fail|error|couldn|try again/i)).toBeInTheDocument();
  });
});
