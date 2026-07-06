'use client';

import Modal from './ui/Modal';
import Button from './ui/Button';

export default function ConfirmDialog({ title, body, confirmLabel = 'Confirm', onConfirm, onCancel }) {
  return (
    <Modal onClose={onCancel} width="w-[400px]">
      <h3 className="text-base font-semibold text-[var(--text)] mb-2">{title}</h3>
      <p className="text-sm text-[var(--muted)] leading-relaxed mb-5">{body}</p>
      <div className="flex justify-end gap-2">
        <Button onClick={onCancel}>Cancel</Button>
        <Button variant="danger" onClick={onConfirm}>{confirmLabel}</Button>
      </div>
    </Modal>
  );
}
