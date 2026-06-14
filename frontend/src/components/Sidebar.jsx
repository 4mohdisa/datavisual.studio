import { useState } from 'react';
import { Plus, Database, MoreHorizontal, Pencil, Trash2 } from 'lucide-react';
import ConfirmDialog from './ConfirmDialog';

function parseDate(s) {
  if (!s) return null;
  // Backend timestamps are UTC but may lack a timezone marker — add Z if missing.
  const hasTz = /[zZ]|[+-]\d\d:?\d\d$/.test(s);
  const d = new Date(hasTz ? s : s + 'Z');
  return isNaN(d.getTime()) ? null : d;
}

function formatRelativeTime(s) {
  const d = parseDate(s);
  if (!d) return '';
  const now = new Date();
  const diffMs = now - d;
  const min = Math.floor(diffMs / 60000);
  const hr = Math.floor(diffMs / 3600000);
  const day = Math.floor(diffMs / 86400000);

  if (min < 1) return 'Just now';
  if (min < 60) return `${min} minute${min === 1 ? '' : 's'} ago`;
  if (hr < 24) return `${hr} hour${hr === 1 ? '' : 's'} ago`;
  if (day === 1) return 'Yesterday';
  if (day < 7) return `${day} days ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onRenameConversation,
  newChatDisabled,
}) {
  const [openMenuId, setOpenMenuId] = useState(null);
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState('');
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);

  const newChatClass = newChatDisabled
    ? 'bg-[oklch(0.25_0_0)] text-[oklch(0.45_0_0)] cursor-not-allowed'
    : 'bg-[var(--new-chat)] text-[var(--background)] hover:bg-[var(--new-chat-hover)] cursor-pointer';

  const startRename = (conv) => {
    setRenamingId(conv.id);
    setRenameValue(conv.title || 'New conversation');
    setOpenMenuId(null);
  };

  const commitRename = () => {
    if (renamingId) {
      const v = renameValue.trim();
      if (v) onRenameConversation?.(renamingId, v);
    }
    setRenamingId(null);
  };

  const cancelRename = () => setRenamingId(null);

  return (
    <div className="w-[280px] shrink-0 flex flex-col h-screen bg-[var(--background)] border-r border-[var(--border)]">
      <div className="p-4 border-b border-[var(--border)]">
        <h1 className="text-lg font-semibold text-[var(--text)] m-0 mb-3">datavisual.studio</h1>
        <button
          className={`w-full flex items-center justify-center gap-1.5 px-4 py-2 rounded-[0.2rem] font-medium text-sm transition-colors ${newChatClass}`}
          onClick={onNewConversation}
          aria-disabled={newChatDisabled}
          title={newChatDisabled ? 'Send a message first' : 'New conversation'}
        >
          <Plus size={16} strokeWidth={1.5} />
          New Conversation
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {conversations.length === 0 ? (
          <div className="p-4 text-center text-[var(--faint)] text-sm">No conversations yet</div>
        ) : (
          conversations.map((conv) => {
            const active = conv.id === currentConversationId;
            const isRenaming = renamingId === conv.id;
            const menuOpen = openMenuId === conv.id;
            return (
              <div
                key={conv.id}
                className={`group relative pl-3 pr-9 py-3 mb-1 rounded-md cursor-pointer border-l-2 transition-colors ${
                  active ? 'bg-[var(--active)] border-white' : 'border-transparent hover:bg-[var(--active)]'
                }`}
                onClick={() => !isRenaming && onSelectConversation(conv.id)}
              >
                <div className="flex items-center gap-1.5">
                  {isRenaming ? (
                    <input
                      autoFocus
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      onBlur={commitRename}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') { e.preventDefault(); commitRename(); }
                        else if (e.key === 'Escape') { e.preventDefault(); cancelRename(); }
                      }}
                      className="flex-1 min-w-0 bg-[var(--surface-input)] border border-[var(--border-2)] rounded px-2 py-0.5 text-sm text-[var(--text)] outline-none focus:border-[var(--accent)]"
                    />
                  ) : (
                    <div className="flex-1 text-sm text-[var(--text)] mb-1 truncate">
                      {conv.title || 'New conversation'}
                    </div>
                  )}
                  {conv.hasFile && !isRenaming && (
                    <Database size={14} strokeWidth={1.5} className="shrink-0 text-[var(--muted)]" />
                  )}
                </div>
                {!isRenaming && (
                  <div className="text-xs text-[var(--faint)]">{formatRelativeTime(conv.created_at)}</div>
                )}

                {/* Three-dot menu trigger (appears on hover / when its menu is open) */}
                {!isRenaming && (
                  <button
                    className={`absolute top-2.5 right-2 p-1 rounded text-[var(--muted)] hover:text-[var(--text)] hover:bg-[oklch(0.18_0_0)] transition ${
                      menuOpen ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                    }`}
                    onClick={(e) => {
                      e.stopPropagation();
                      setOpenMenuId(menuOpen ? null : conv.id);
                    }}
                    aria-label="Conversation options"
                  >
                    <MoreHorizontal size={16} strokeWidth={1.5} />
                  </button>
                )}

                {/* Dropdown */}
                {menuOpen && (
                  <div
                    className="absolute right-2 top-9 z-20 w-36 bg-[var(--surface-input)] border border-[var(--border-2)] rounded-md shadow-[0_4px_24px_rgba(0,0,0,0.4)] py-1"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <button
                      className="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-[var(--text)] hover:bg-[var(--active)] transition"
                      onClick={() => startRename(conv)}
                    >
                      <Pencil size={16} strokeWidth={1.5} /> Rename
                    </button>
                    <button
                      className="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-[var(--danger)] hover:bg-[var(--active)] transition"
                      onClick={() => { setConfirmDeleteId(conv.id); setOpenMenuId(null); }}
                    >
                      <Trash2 size={16} strokeWidth={1.5} /> Delete
                    </button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Click-away layer to close an open dropdown */}
      {openMenuId && (
        <div className="fixed inset-0 z-10" onClick={() => setOpenMenuId(null)} />
      )}

      {/* Delete confirmation */}
      {confirmDeleteId && (
        <ConfirmDialog
          title="Delete conversation?"
          body="This will permanently remove this conversation. This cannot be undone."
          confirmLabel="Delete"
          onConfirm={() => {
            onDeleteConversation(confirmDeleteId);
            setConfirmDeleteId(null);
          }}
          onCancel={() => setConfirmDeleteId(null)}
        />
      )}
    </div>
  );
}
