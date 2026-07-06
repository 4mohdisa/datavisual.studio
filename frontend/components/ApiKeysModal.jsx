'use client';

import { useEffect, useState } from 'react';
import Modal from './ui/Modal';
import Field from './ui/Field';
import Input from './ui/Input';
import Button from './ui/Button';
import { api } from '../lib/api';

// Per-user AI keys — the app is free; users pay their AI providers directly.
// Keys are stored on the user's record on the backend's local disk and are
// only ever sent to OpenRouter / Google.
export default function ApiKeysModal({ onClose, onSaved }) {
  const [loaded, setLoaded] = useState(null);
  const [openrouterKey, setOpenrouterKey] = useState('');
  const [geminiKey, setGeminiKey] = useState('');
  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.getAccountSettings().then(setLoaded).catch(() => setError('Could not load your settings.'));
  }, []);

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      setTestResult(await api.validateAccountKey(openrouterKey.trim() || null));
    } catch {
      setTestResult({ valid: false, error: 'Validation request failed' });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setSaved(false);
    try {
      const view = await api.saveAccountSettings({
        openrouter_api_key: openrouterKey.trim() || null,
        gemini_api_key: geminiKey.trim() || null,
      });
      setLoaded(view);
      setOpenrouterKey('');
      setGeminiKey('');
      setSaved(true);
      onSaved?.(view);
    } catch (e) {
      setError(e.message || 'Failed to save keys');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal title="Your AI keys" onClose={onClose} width="w-[500px]">
      <p className="text-[12.5px] text-[var(--muted)] -mt-2 mb-4 leading-relaxed">
        datavisual.studio is free — you bring your own AI keys and pay the providers
        directly. Keys are stored privately with your account and only sent to the
        AI providers themselves.
      </p>
      {error && <div className="mb-4 text-sm text-[var(--danger)]">{error}</div>}

      <Field
        label="OpenRouter API key (required)"
        hint={
          loaded?.openrouter_key_set
            ? `Current key: ${loaded.openrouter_key_masked} — leave blank to keep it.`
            : 'Powers the AI council, research and the dashboard assistant. Get one at openrouter.ai/keys.'
        }
      >
        <div className="flex gap-2">
          <Input
            type="password"
            value={openrouterKey}
            onChange={(e) => { setOpenrouterKey(e.target.value); setTestResult(null); setSaved(false); }}
            placeholder={loaded?.openrouter_key_set ? '••••••••••  (unchanged)' : 'sk-or-v1-…'}
            autoComplete="off"
          />
          <Button onClick={handleTest} disabled={testing} className="shrink-0">
            {testing ? 'Testing…' : 'Test'}
          </Button>
        </div>
        {testResult && (
          <div className={`mt-1.5 text-xs ${testResult.valid ? 'text-[oklch(0.75_0.15_150)]' : 'text-[var(--danger)]'}`}>
            {testResult.valid ? '✓ Key is valid' : `✗ ${testResult.error}`}
          </div>
        )}
      </Field>

      <Field
        label="Gemini API key (optional)"
        hint={
          loaded?.gemini_key_set
            ? 'A Gemini key is saved — leave blank to keep it.'
            : 'Gemini models call Google directly (cheaper; generous free tier). Get one at aistudio.google.com.'
        }
      >
        <Input
          type="password"
          value={geminiKey}
          onChange={(e) => { setGeminiKey(e.target.value); setSaved(false); }}
          placeholder={loaded?.gemini_key_set ? '••••••••••  (unchanged)' : 'AIza…'}
          autoComplete="off"
        />
      </Field>

      <div className="flex items-center justify-end gap-3 mt-5">
        {saved && <span className="text-xs text-[oklch(0.75_0.15_150)]">Saved ✓</span>}
        <Button variant="primary" onClick={handleSave} disabled={saving || !loaded}>
          {saving ? 'Saving…' : 'Save keys'}
        </Button>
      </div>
    </Modal>
  );
}
