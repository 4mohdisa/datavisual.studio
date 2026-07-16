/**
 * API client for the Datavisual.studio backend.
 */

// All requests go through the Next.js proxy (/api/backend/*), which handles
// authentication, per-user ownership and plan quotas before reaching the
// FastAPI engine. The engine itself is never exposed to the browser.
const API_BASE = '/api/backend';

// ---- datavisual.studio additions ----

export const api = {
  /**
   * List all conversations.
   */
  async listConversations() {
    const response = await fetch(`${API_BASE}/api/conversations`);
    if (!response.ok) {
      throw new Error('Failed to list conversations');
    }
    return response.json();
  },

  /**
   * Create a conversation with a client-generated id (router flow).
   */
  async createConversationWithId(conversationId, title, fileId, matchHistoryFileId) {
    const response = await fetch(`${API_BASE}/api/conversations/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversation_id: conversationId,
        title: title || null,
        file_id: fileId || null,
        match_history_file_id: matchHistoryFileId || null,
      }),
    });
    if (!response.ok) throw new Error('Failed to create conversation');
    return response.json();
  },

  /**
   * Create a standalone web dashboard from an uploaded dataset (no AI run).
   */
  async createDashboard(fileId, title, template, focus) {
    const response = await fetch(`${API_BASE}/api/dashboard`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        file_id: fileId,
        title: title || null,
        template: template || 'overview',
        focus: focus || null,
      }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to create dashboard');
    }
    return response.json();
  },

  /**
   * Zero-key onboarding: build an instant dashboard from a bundled sample
   * dataset (no upload, no AI key, no cost). Returns { conversation_id }.
   */
  async sampleDashboard(sample) {
    const response = await fetch(`${API_BASE}/api/sample-dashboard`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sample: sample || null }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Could not create the sample dashboard');
    }
    return response.json();
  },

  /**
   * Rebuild the widget spec for an existing record (migrates old dashboards).
   */
  async ensureDashboard(conversationId) {
    const response = await fetch(`${API_BASE}/api/dashboard`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: conversationId }),
    });
    if (!response.ok) throw new Error('Failed to build dashboard');
    return response.json();
  },

  /**
   * Prebuilt components available to add (computed from the dataset).
   */
  async dashboardSuggestions(conversationId) {
    const response = await fetch(`${API_BASE}/api/dashboard/${conversationId}/suggestions`);
    if (!response.ok) throw new Error('Failed to load components');
    return response.json();
  },

  /**
   * The living-monitor "Update" — re-pull data AND re-run pinned research,
   * returning { dashboard, changes, synced_at }. Supersedes the old data-only
   * refresh.
   */
  async syncDashboard(conversationId) {
    const response = await fetch(`${API_BASE}/api/dashboard/${conversationId}/sync`, { method: 'POST' });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Update failed');
    }
    return response.json();
  },

  /**
   * Edit the existing dashboard in place — natural-language message or direct
   * ops (e.g. removing a widget). Returns {reply, dashboard}.
   */
  async dashboardChat(conversationId, { message, ops }) {
    const response = await fetch(`${API_BASE}/api/dashboard/${conversationId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: message || null, ops: ops || null }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Dashboard edit failed');
    }
    return response.json();
  },

  /**
   * Enable a public share link for a conversation (dashboard or research).
   * Idempotent — returns the existing token if already shared.
   */
  async shareConversation(conversationId) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}/share`, { method: 'POST' });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Could not create a share link');
    }
    return response.json();
  },

  /** Revoke a public share link. */
  async unshareConversation(conversationId) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}/share`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Could not revoke the link');
    return response.json();
  },

  /**
   * Import data from an external source (SQL database or REST API).
   * Returns the same shape as uploadFile, so it plugs into the same flow.
   */
  async connectSource(payload) {
    const response = await fetch(`${API_BASE}/api/connect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Import failed');
    }
    return response.json();
  },

  /**
   * The signed-in user's own AI-key configuration (masked).
   */
  async getAccountSettings() {
    const response = await fetch(`${API_BASE}/api/account/settings`);
    if (!response.ok) throw new Error('Failed to load account settings');
    return response.json();
  },

  async saveAccountSettings({ openrouter_api_key, gemini_api_key }) {
    const response = await fetch(`${API_BASE}/api/account/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ openrouter_api_key, gemini_api_key }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to save keys');
    }
    return response.json();
  },

  async validateAccountKey(openrouterKey) {
    const response = await fetch(`${API_BASE}/api/account/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ openrouter_api_key: openrouterKey || null }),
    });
    if (!response.ok) return { valid: false, error: 'Validation request failed' };
    return response.json();
  },

  /**
   * Admin-only project analytics, gated by the backend's ADMIN_PASSWORD
   * (403 = wrong/missing password).
   */
  async adminOverview(password) {
    const headers = password ? { 'x-admin-password': password } : {};
    const response = await fetch(`${API_BASE}/api/admin/overview`, { headers });
    if (response.status === 403) throw new Error('forbidden');
    if (!response.ok) throw new Error('Failed to load analytics');
    return response.json();
  },

  /**
   * Best-effort client error logging (7.2).
   */
  async logError(payload) {
    try {
      await fetch(`${API_BASE}/api/error-log`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch {
      /* ignore */
    }
  },

  /**
   * Fetch the raw dataset rows (capped) for the dashboard data table.
   */
  async getDataset(conversationId, limit = 2000) {
    const response = await fetch(`${API_BASE}/api/dataset/${conversationId}?limit=${limit}`);
    if (!response.ok) throw new Error('Failed to load dataset');
    return response.json();
  },

  /**
   * Poll the pipeline status for a conversation.
   */
  async getStatus(conversationId) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}/status`);
    if (!response.ok) throw new Error('Failed to get status');
    return response.json();
  },

  /**
   * Get a specific conversation.
   */
  async getConversation(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}`
    );
    if (!response.ok) {
      throw new Error('Failed to get conversation');
    }
    return response.json();
  },

  /**
   * Upload a data file (CSV/Excel/JSON). When a direct-backend origin is
   * configured (the Vercel split), the file goes STRAIGHT to the backend with a
   * short-lived HMAC ticket so it bypasses the serverless body-size limit.
   * Otherwise it goes through the proxy (single-box deploys, local dev).
   */
  async uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    if (process.env.NEXT_PUBLIC_BACKEND_ORIGIN) {
      try {
        const t = await fetch('/api/upload-ticket', { method: 'POST' });
        if (t.ok) {
          const { ticket, backend_origin } = await t.json();
          const direct = await fetch(`${backend_origin}/api/upload-direct`, {
            method: 'POST',
            headers: { 'X-Upload-Ticket': ticket },
            body: formData,
          });
          if (!direct.ok) {
            const err = await direct.json().catch(() => ({}));
            throw new Error(err.detail || 'Upload failed');
          }
          return direct.json();
        }
        // 501 (not configured) or other → fall through to the proxied path.
      } catch (e) {
        if (e instanceof Error && e.message !== 'Upload failed') { /* network → fall back */ }
        else throw e;
      }
    }

    const response = await fetch(`${API_BASE}/api/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Upload failed');
    }
    return response.json();
  },

  /**
   * Kick off the analyse pipeline as a background job (the DEFAULT, Vercel-safe
   * transport). Returns immediately; the caller polls getStatus() for progress.
   */
  async analyseStart(conversationId, question, fileId, matchHistoryFileId) {
    const response = await fetch(`${API_BASE}/api/analyse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversation_id: conversationId,
        question,
        file_id: fileId || null,
        match_history_file_id: matchHistoryFileId || null,
      }),
    });
    if (!response.ok) throw new Error('Analyse request failed');
    return response.json();
  },

  /**
   * Run the analyse pipeline as a live SSE stream (opt-in, NEXT_PUBLIC_STREAMING=1).
   * The ?stream=1 flag tells the backend to stream rather than kick off a job.
   */
  async analyseStream(conversationId, question, fileId, matchHistoryFileId, onEvent) {
    const response = await fetch(`${API_BASE}/api/analyse?stream=1`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversation_id: conversationId,
        question,
        file_id: fileId || null,
        match_history_file_id: matchHistoryFileId || null,
      }),
    });
    if (!response.ok) throw new Error('Analyse request failed');
    return _readSSE(response, onEvent);
  },

  /**
   * Re-run data analysis on a filtered dataset.
   */
  async reanalyse(conversationId, filters) {
    const response = await fetch(`${API_BASE}/api/reanalyse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: conversationId, filters }),
    });
    if (!response.ok) throw new Error('Reanalyse failed');
    return response.json();
  },

  /**
   * Download the PDF export for a conversation.
   */
  /**
   * Ask the backend which export format it can produce ('pdf' or 'html').
   */
  async getExportFormat() {
    try {
      const response = await fetch(`${API_BASE}/api/export-format`);
      if (!response.ok) return 'pdf';
      const data = await response.json();
      return data.format || 'pdf';
    } catch {
      return 'pdf';
    }
  },

  /**
   * Download the report. The backend returns a PDF when available, otherwise a
   * self-contained HTML file — we pick the extension from the response type and
   * honour the server's Content-Disposition filename when present.
   */
  async exportReport(conversationId, format, mode) {
    const params = new URLSearchParams();
    if (format) params.set('format', format);
    if (mode) params.set('mode', mode);
    const qs = params.toString() ? `?${params}` : '';
    const response = await fetch(`${API_BASE}/api/export/${conversationId}${qs}`);
    if (!response.ok) {
      // Surface the backend's actionable message (e.g. missing Pango/Cairo).
      let detail = 'Export failed';
      try {
        const err = await response.json();
        if (err && err.detail) detail = err.detail;
      } catch {
        // non-JSON error body; keep generic message
      }
      throw new Error(detail);
    }

    const contentType = response.headers.get('Content-Type') || '';
    const ext = contentType.includes('pdf') ? 'pdf' : 'html';
    let filename = `report-${conversationId.slice(0, 8)}.${ext}`;
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="?([^"]+)"?/);
    if (match) filename = match[1];

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    return ext;
  },
};

async function _readSSE(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        try {
          const event = JSON.parse(data);
          onEvent(event.type, event);
        } catch (e) {
          console.error('Failed to parse SSE event:', e);
        }
      }
    }
  }
}
