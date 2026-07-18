'use client';

import { useEffect, useRef } from 'react';

// Focusable-element selector (visible, not disabled, in the tab order).
const FOCUSABLE = [
  'a[href]', 'area[href]', 'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])', 'textarea:not([disabled])', 'button:not([disabled])',
  'iframe', 'audio[controls]', 'video[controls]',
  '[contenteditable]:not([contenteditable="false"])', '[tabindex]:not([tabindex="-1"])',
].join(',');

// Focus management for modals/drawers/overlays (Phase 1c — the gap axe can't see).
// On activate: remember the trigger and move focus inside. While open: keep
// Tab/Shift+Tab within the container. Escape → onEscape. On deactivate: restore
// focus to the trigger. Attach the returned ref to the dialog container (give it
// tabIndex={-1} so it's a focus fallback when it has no focusable children yet).
//
//   const ref = useFocusTrap({ active: open, onEscape: onClose });
//   <div ref={ref} role="dialog" aria-modal="true" tabIndex={-1}>…</div>
export function useFocusTrap({ active = true, onEscape } = {}) {
  const ref = useRef(null);
  const restoreRef = useRef(null);
  const escRef = useRef(onEscape);
  escRef.current = onEscape;   // always call the latest handler without re-running the effect

  useEffect(() => {
    if (!active) return;
    const container = ref.current;
    if (!container) return;

    restoreRef.current = document.activeElement;
    const items = () => Array.from(container.querySelectorAll(FOCUSABLE))
      .filter((el) => el.offsetWidth > 0 || el.offsetHeight > 0 || el === document.activeElement);

    // Move focus in (first focusable, else the container itself).
    (items()[0] || container).focus();

    const onKey = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); escRef.current?.(); return; }
      if (e.key !== 'Tab') return;
      const list = items();
      if (list.length === 0) { e.preventDefault(); container.focus(); return; }
      const first = list[0], last = list[list.length - 1];
      const el = document.activeElement;
      if (e.shiftKey && (el === first || el === container || !container.contains(el))) {
        e.preventDefault(); last.focus();
      } else if (!e.shiftKey && el === last) {
        e.preventDefault(); first.focus();
      }
    };
    // Capture phase so we win over inner handlers and catch focus already outside.
    document.addEventListener('keydown', onKey, true);
    return () => {
      document.removeEventListener('keydown', onKey, true);
      const el = restoreRef.current;
      if (el && typeof el.focus === 'function') el.focus();
    };
  }, [active]);

  return ref;
}
