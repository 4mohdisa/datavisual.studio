/**
 * API client for the Datavisual.studio backend.
 */

const API_BASE = 'http://localhost:8001';

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
   * Create a new conversation.
   */
  async createConversation() {
    const response = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    if (!response.ok) {
      throw new Error('Failed to create conversation');
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
   * Send a message in a conversation.
   */
  async sendMessage(conversationId, content) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content }),
      }
    );
    if (!response.ok) {
      throw new Error('Failed to send message');
    }
    return response.json();
  },

  /**
   * Upload a data file (CSV/Excel/JSON).
   */
  async uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
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
   * Run the analyse pipeline (replaces sendMessage for the new UI).
   */
  async analyseStream(conversationId, question, fileId, matchHistoryFileId, onEvent) {
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
  async exportReport(conversationId) {
    const response = await fetch(`${API_BASE}/api/export/${conversationId}`);
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

  /**
   * Send a message and receive streaming updates.
   * @param {string} conversationId - The conversation ID
   * @param {string} content - The message content
   * @param {function} onEvent - Callback function for each event: (eventType, data) => void
   * @returns {Promise<void>}
   */
  async sendMessageStream(conversationId, content, onEvent) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content }),
      }
    );

    if (!response.ok) {
      throw new Error('Failed to send message');
    }

    return _readSSE(response, onEvent);
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
