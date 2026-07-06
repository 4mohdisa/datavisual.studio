'use client';

import { useState } from 'react';
import { Database, Globe } from 'lucide-react';
import Modal from './ui/Modal';
import Field from './ui/Field';
import Input from './ui/Input';
import Button from './ui/Button';
import { api } from '../lib/api';

// Power BI-style data connector: pull rows from a SQL database or a REST API.
// The import lands as a normal dataset, so the caller treats the result exactly
// like a file upload (chat analysis, dashboards, predictions all work on it).
export default function ConnectSource({ onImported, onClose }) {
  const [type, setType] = useState('database');
  const [name, setName] = useState('');
  const [connStr, setConnStr] = useState('');
  const [query, setQuery] = useState('');
  const [url, setUrl] = useState('');
  const [headersText, setHeadersText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    setBusy(true);
    setError('');
    try {
      let headers = null;
      if (type === 'api' && headersText.trim()) {
        try {
          headers = JSON.parse(headersText);
        } catch {
          throw new Error('Headers must be valid JSON, e.g. {"Authorization": "Bearer …"}');
        }
      }
      const result = await api.connectSource({
        type,
        name: name.trim() || null,
        connection_string: connStr.trim() || null,
        query: query.trim() || null,
        url: url.trim() || null,
        headers,
      });
      onImported(result);
      onClose();
    } catch (e) {
      setError(e.message || 'Import failed');
    } finally {
      setBusy(false);
    }
  };

  const canSubmit = type === 'database' ? connStr.trim() && query.trim() : url.trim();

  return (
    <Modal title="Connect a data source" onClose={onClose} width="w-[540px]">
      <div className="flex gap-2 mb-5">
        <Button
          variant={type === 'database' ? 'primary' : 'outline'}
          onClick={() => { setType('database'); setError(''); }}
        >
          <Database size={15} strokeWidth={1.5} /> Database
        </Button>
        <Button
          variant={type === 'api' ? 'primary' : 'outline'}
          onClick={() => { setType('api'); setError(''); }}
        >
          <Globe size={15} strokeWidth={1.5} /> REST API
        </Button>
      </div>

      <Field label="Dataset name" hint="Optional — how this import appears in file chips and dashboards.">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. sales_2026" />
      </Field>

      {type === 'database' ? (
        <>
          <Field
            label="Connection URL"
            hint="PostgreSQL, MySQL and SQLite are supported. The connection is stored locally (data/sources.json) so dashboards can be refreshed from it."
          >
            <Input
              value={connStr}
              onChange={(e) => setConnStr(e.target.value)}
              placeholder="postgresql://user:password@host:5432/dbname"
              className="font-mono text-[13px]"
              spellCheck={false}
              autoComplete="off"
            />
          </Field>
          <Field label="SQL query" hint="Read-only: SELECT (or WITH … SELECT) queries only. Up to 100,000 rows are imported.">
            <Input
              as="textarea"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              rows={4}
              placeholder="SELECT * FROM sales WHERE year = 2026"
              className="resize-y font-mono text-[13px]"
              spellCheck={false}
            />
          </Field>
        </>
      ) : (
        <>
          <Field label="Endpoint URL" hint="Must return JSON — either an array of records or an object containing one (e.g. {'data': [...]}).">
            <Input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://api.example.com/v1/records"
              className="font-mono text-[13px]"
              spellCheck={false}
            />
          </Field>
          <Field label="Headers (JSON, optional)" hint='e.g. {"Authorization": "Bearer sk-…"}'>
            <Input
              as="textarea"
              value={headersText}
              onChange={(e) => setHeadersText(e.target.value)}
              rows={2}
              placeholder='{"Authorization": "Bearer …"}'
              className="resize-y font-mono text-[13px]"
              spellCheck={false}
            />
          </Field>
        </>
      )}

      <div className="flex items-center justify-end gap-3 mt-5">
        {error && <span className="mr-auto text-xs text-[var(--danger)]">{error}</span>}
        <Button variant="primary" onClick={submit} disabled={busy || !canSubmit}>
          {busy ? 'Importing…' : 'Import data'}
        </Button>
      </div>
    </Modal>
  );
}
