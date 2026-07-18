import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Grid, Row, Stack, Card, EmptyState, ErrorState, LoadingState } from './layout';

describe('layout primitives', () => {
  it('Grid maps cols → responsive column classes', () => {
    const { container } = render(<Grid cols={3}>x</Grid>);
    const el = container.firstChild;
    expect(el.className).toContain('grid-cols-1');
    expect(el.className).toContain('sm:grid-cols-2');
    expect(el.className).toContain('lg:grid-cols-3');
  });

  it('Stack/Row apply the requested gap', () => {
    const { container: s } = render(<Stack gap="lg">x</Stack>);
    expect(s.firstChild.className).toContain('gap-6');
    const { container: r } = render(<Row gap="sm" justify="between">x</Row>);
    expect(r.firstChild.className).toContain('gap-2');
    expect(r.firstChild.className).toContain('justify-between');
  });

  it('Card renders children in a bordered panel', () => {
    render(<Card><span>inside</span></Card>);
    expect(screen.getByText('inside')).toBeInTheDocument();
  });

  it('state components expose the right roles', () => {
    const { rerender } = render(<LoadingState label="Working" />);
    expect(screen.getByRole('status')).toHaveTextContent('Working');
    rerender(<ErrorState title="Boom" />);
    expect(screen.getByRole('alert')).toHaveTextContent('Boom');
  });

  it('EmptyState shows title + description', () => {
    render(<EmptyState title="Nothing here" description="Add something" />);
    expect(screen.getByText('Nothing here')).toBeInTheDocument();
    expect(screen.getByText('Add something')).toBeInTheDocument();
  });
});
