// Labelled form row: label, control, optional hint below.
export default function Field({ label, hint, children }) {
  return (
    <div className="mb-4">
      <label className="block text-[13px] font-medium text-[var(--text)] mb-1">{label}</label>
      {children}
      {hint && <div className="mt-1 text-xs text-[var(--faint)]">{hint}</div>}
    </div>
  );
}
