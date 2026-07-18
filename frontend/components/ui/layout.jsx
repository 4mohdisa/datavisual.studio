'use client';

import { forwardRef } from 'react';
import { Inbox, AlertTriangle, Loader2 } from 'lucide-react';

// Layout primitives (Launch Phase 1a). THE rule that keeps pages aligned:
// no primitive sets its own OUTER margin — spacing is owned by the parent
// (Stack/Row/Grid `gap`, Section padding). Children with their own margins are
// the reason pages drift, so these deliberately have none.

const GAP = { none: 'gap-0', xs: 'gap-1.5', sm: 'gap-2', md: 'gap-4', lg: 'gap-6', xl: 'gap-10' };
const ALIGN = { start: 'items-start', center: 'items-center', end: 'items-end', stretch: 'items-stretch', baseline: 'items-baseline' };
const JUSTIFY = { start: 'justify-start', center: 'justify-center', end: 'justify-end', between: 'justify-between', around: 'justify-around' };
const MAXW = { sm: 'max-w-[640px]', md: 'max-w-[820px]', lg: 'max-w-[1120px]', xl: 'max-w-[1320px]', full: 'max-w-none' };
// Literal strings so Tailwind's content scan generates them.
const COLS = {
  1: 'grid-cols-1',
  2: 'grid-cols-1 sm:grid-cols-2',
  3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
  4: 'grid-cols-2 lg:grid-cols-4',
};

// Full-height page surface (background + base text colour).
export function Page({ className = '', children, ...p }) {
  return <div className={`min-h-screen bg-[var(--background)] text-[var(--text)] ${className}`} {...p}>{children}</div>;
}

// Centred, width-capped content column with responsive horizontal padding.
export function Container({ size = 'lg', className = '', children, ...p }) {
  return <div className={`w-full ${MAXW[size]} mx-auto px-5 sm:px-6 ${className}`} {...p}>{children}</div>;
}

// A vertical band with consistent block padding (owns vertical rhythm).
export function Section({ as: As = 'section', className = '', children, ...p }) {
  return <As className={`py-12 sm:py-16 ${className}`} {...p}>{children}</As>;
}

// Vertical flex with gap.
export function Stack({ gap = 'md', className = '', children, ...p }) {
  return <div className={`flex flex-col ${GAP[gap]} ${className}`} {...p}>{children}</div>;
}

// Horizontal flex with gap/alignment.
export function Row({ gap = 'md', align = 'center', justify = 'start', wrap = false, className = '', children, ...p }) {
  return <div className={`flex ${wrap ? 'flex-wrap' : ''} ${ALIGN[align]} ${JUSTIFY[justify]} ${GAP[gap]} ${className}`} {...p}>{children}</div>;
}

// Responsive grid (1–4 columns).
export function Grid({ cols = 2, gap = 'md', className = '', children, ...p }) {
  return <div className={`grid ${COLS[cols] || COLS[1]} ${GAP[gap]} ${className}`} {...p}>{children}</div>;
}

// Bordered raised panel.
export const Card = forwardRef(function Card({ as: As = 'div', className = '', children, ...p }, ref) {
  return (
    <As ref={ref} className={`rounded-xl border border-[var(--border-2)] bg-[var(--raised)] p-5 ${className}`} {...p}>
      {children}
    </As>
  );
});

// Title + actions header row (one <h1>/<h2> per the `as` you pass; defaults h1).
export function PageHeader({ title, actions, as: As = 'h1', className = '' }) {
  return (
    <Row justify="between" align="center" gap="md" wrap className={className}>
      <As className="text-[22px] font-semibold text-[var(--text)] m-0 truncate">{title}</As>
      {actions ? <Row gap="sm" wrap>{actions}</Row> : null}
    </Row>
  );
}

// --- States (empty / error / loading) — no blank screens, no dead spinners. ---

export function EmptyState({ icon: Icon = Inbox, title, description, action, className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center text-center py-14 px-6 ${className}`}>
      <Icon size={28} strokeWidth={1.5} className="text-[var(--faint)] mb-3" aria-hidden="true" />
      <div className="text-[15px] font-semibold text-[var(--text)]">{title}</div>
      {description ? <p className="text-[13px] text-[var(--muted)] mt-1 max-w-[380px] leading-relaxed">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ title = 'Something went wrong', description, onRetry, retryLabel = 'Try again', className = '' }) {
  return (
    <div role="alert" className={`flex flex-col items-center justify-center text-center py-14 px-6 ${className}`}>
      <AlertTriangle size={28} strokeWidth={1.5} className="text-[var(--danger)] mb-3" aria-hidden="true" />
      <div className="text-[15px] font-semibold text-[var(--text)]">{title}</div>
      {description ? <p className="text-[13px] text-[var(--muted)] mt-1 max-w-[380px] leading-relaxed">{description}</p> : null}
      {onRetry ? (
        <button
          onClick={onRetry}
          className="mt-4 inline-flex items-center rounded-md border border-[var(--border-2)] px-3 py-1.5 text-[13px] text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--active)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--focus-ring)] transition"
        >
          {retryLabel}
        </button>
      ) : null}
    </div>
  );
}

export function LoadingState({ label = 'Loading…', className = '' }) {
  return (
    <div role="status" className={`flex items-center justify-center gap-2 py-14 text-[13px] text-[var(--muted)] ${className}`}>
      <Loader2 size={15} className="animate-spin" aria-hidden="true" /> {label}
    </div>
  );
}
