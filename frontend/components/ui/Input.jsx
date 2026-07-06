// Text input + textarea sharing one style. `as="textarea"` renders a textarea.
export const inputClass =
  'w-full bg-[var(--surface-input)] border border-[var(--border-2)] rounded-md px-3 py-2 text-sm ' +
  'text-[var(--text)] placeholder:text-[var(--faint)] outline-none focus:border-[var(--accent)]';

export default function Input({ as, className = '', ...props }) {
  const cls = `${inputClass} ${className}`;
  if (as === 'textarea') return <textarea className={cls} {...props} />;
  return <input className={cls} {...props} />;
}

// Styled native select — options: [{value, label}] or plain strings.
export function Select({ options = [], className = '', ...props }) {
  return (
    <select className={`${inputClass} appearance-none cursor-pointer ${className}`} {...props}>
      {options.map((o) => {
        const v = typeof o === 'string' ? o : o.value;
        const l = typeof o === 'string' ? o : o.label;
        return <option key={v} value={v}>{l}</option>;
      })}
    </select>
  );
}
