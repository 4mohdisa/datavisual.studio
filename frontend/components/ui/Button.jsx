// Custom button primitive. Variants map to the app's CSS-variable palette so
// every button in the product shares one look.
const VARIANTS = {
  primary:
    'bg-[var(--new-chat)] text-[var(--background)] hover:bg-[var(--new-chat-hover)] font-medium',
  secondary:
    'bg-[var(--user-bubble)] text-[var(--text)] hover:bg-[var(--active)]',
  outline:
    'border border-[var(--border-2)] text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--active)]',
  ghost: 'text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--active)]',
  danger: 'bg-[var(--danger)] text-white hover:brightness-110 font-medium',
};

const SIZES = {
  sm: 'px-2.5 py-1 text-xs rounded-md',
  md: 'px-4 py-2 text-sm rounded-md',
};

export default function Button({ variant = 'secondary', size = 'md', className = '', ...props }) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-1.5 whitespace-nowrap transition disabled:opacity-50 disabled:cursor-not-allowed ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...props}
    />
  );
}
