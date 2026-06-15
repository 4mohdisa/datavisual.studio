import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import ActivityPanel from './components/ActivityPanel';
import CommandPalette from './components/CommandPalette';
import { api } from './api';

// ---- client-side persistence (frontend only — no backend changes) ----
const META_KEY = 'dvs_conv_meta';   // { [id]: { title, hasFile } }
const HIDDEN_KEY = 'dvs_hidden';     // [id, ...] soft-deleted / hidden convs

function loadMeta() {
  try { return JSON.parse(localStorage.getItem(META_KEY)) || {}; } catch { return {}; }
}
function loadHidden() {
  try { return new Set(JSON.parse(localStorage.getItem(HIDDEN_KEY)) || []); } catch { return new Set(); }
}
function deriveTitle(messages) {
  const firstUser = (messages || []).find((m) => m.role === 'user');
  if (firstUser && firstUser.content) return firstUser.content.trim().slice(0, 40);
  return 'New conversation';
}

// Ordered pipeline stages (must match backend _PROGRESS_PCT keys).
const STAGE_ORDER = ['data_analysis', 'research', 'council_stage1', 'council_stage2', 'council_stage3', 'synthesis', 'done'];

// Build an AnalysisProgress `progress` object from a backend current_stage, so a
// reloaded "running" conversation shows the right step highlighted.
function progressFromStage(stage) {
  const idx = STAGE_ORDER.indexOf(stage);
  const stepStatus = (name) => {
    const i = STAGE_ORDER.indexOf(name);
    if (idx < 0) return 'pending';
    if (i < idx) return 'done';
    if (i === idx) return 'active';
    return 'pending';
  };
  const synthIdx = STAGE_ORDER.indexOf('synthesis');
  let report = 'pending';
  if (idx > synthIdx) report = 'done';
  else if (idx === synthIdx) report = 'active';
  return {
    analysis: stepStatus('data_analysis'),
    research: stepStatus('research'),
    stage1: stepStatus('council_stage1'),
    stage2: stepStatus('council_stage2'),
    stage3: stepStatus('council_stage3'),
    report,
  };
}

const newProgressMessage = (mode) => ({
  role: 'assistant',
  type: null,
  stage1: null,
  stage2: null,
  stage3: null,
  report: null,
  metadata: null,
  progress: {
    analysis: mode === 'data' ? 'pending' : 'skipped',
    research: 'pending',
    stage1: 'pending',
    stage2: 'pending',
    stage3: 'pending',
    report: 'pending',
  },
});

function App() {
  const { id: routeId } = useParams();
  const navigate = useNavigate();
  const currentConversationId = routeId || null;

  const [conversations, setConversations] = useState([]);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  // files: per-conversation attached file info { [convId]: { file_id, filename, ... } }
  const [files, setFiles] = useState({});
  // file attached while at the root (no conversation yet) — moved into `files`
  // once the conversation id is created on first send.
  const [rootFile, setRootFile] = useState(null);
  // Optional second file: a match-history CSV that enables the XGBoost model.
  // Stored per-conversation like the main file, with a root slot pre-conversation.
  const [matchFiles, setMatchFiles] = useState({});
  const [rootMatchFile, setRootMatchFile] = useState(null);
  const [loadingConvos, setLoadingConvos] = useState(true);
  const [convMeta, setConvMeta] = useState(loadMeta);
  const [hiddenIds, setHiddenIds] = useState(loadHidden);
  const [input, setInput] = useState('');
  // Activity Panel: accumulating log of granular SSE "activity" events.
  const [activityLog, setActivityLog] = useState([]);
  const [activityOpen, setActivityOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  // Global keyboard shortcuts (6.4): Cmd/Ctrl K (palette), N (new), Slash (panel), Escape (close).
  useEffect(() => {
    const onKey = (e) => {
      const mod = e.metaKey || e.ctrlKey;
      const k = e.key.toLowerCase();
      if (mod && k === 'k') { e.preventDefault(); setPaletteOpen((o) => !o); }
      else if (mod && k === 'n') { e.preventDefault(); setRootFile(null); setRootMatchFile(null); setInput(''); navigate('/'); }
      else if (mod && e.key === '/') { e.preventDefault(); setActivityOpen((o) => !o); }
      else if (e.key === 'Escape') { setPaletteOpen(false); setActivityOpen(false); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [navigate]);

  const messageInputRef = useRef(null);
  const lastQuestionRef = useRef('');
  // When we create + navigate to a fresh conversation right before streaming, the
  // route effect must NOT re-fetch it (it would clobber the optimistic state).
  const skipNextLoadRef = useRef(null);
  const pollingRef = useRef(null);

  const stopPolling = () => {
    if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }
  };

  useEffect(() => {
    loadConversations();
  }, []);

  // Load (or clear) the active conversation whenever the URL :id changes.
  useEffect(() => {
    stopPolling();
    if (!currentConversationId) {
      setCurrentConversation(null);
      setActivityLog([]);
      return;
    }
    if (skipNextLoadRef.current === currentConversationId) {
      skipNextLoadRef.current = null;
      return; // freshly created + streaming — keep optimistic state
    }
    loadConversation(currentConversationId);
    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentConversationId]);

  // ---- persistence helpers ----
  const updateMeta = (id, patch) => {
    setConvMeta((prev) => {
      const next = { ...prev, [id]: { ...prev[id], ...patch } };
      try { localStorage.setItem(META_KEY, JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  };
  const persistHidden = (set) => {
    setHiddenIds(new Set(set));
    try { localStorage.setItem(HIDDEN_KEY, JSON.stringify([...set])); } catch { /* ignore */ }
  };

  const focusInput = () => {
    requestAnimationFrame(() => messageInputRef.current?.focus());
  };

  // ---- data loading ----
  const loadConversations = async () => {
    try {
      const convs = await api.listConversations();
      const hidden = loadHidden();
      // Hide zero-message conversations; also hide soft-deleted ones.
      const visible = convs.filter((c) => c.message_count > 0 && !hidden.has(c.id));
      setConversations(visible);
      return visible;
    } catch (error) {
      console.error('Failed to load conversations:', error);
      return [];
    } finally {
      setLoadingConvos(false);
    }
  };

  const loadConversation = async (id) => {
    let conv;
    try {
      conv = await api.getConversation(id);
    } catch (error) {
      // 404 / fetch failure → conversation not found (e.g. /chat/fake-id).
      console.error('Failed to load conversation:', error);
      setCurrentConversation({ id, messages: [], notFound: true });
      setActivityLog([]);
      return;
    }

    const storedActivity = conv.pipeline?.activity || [];

    // Sources tab is derived from `search_complete` activity links. If the saved
    // activity log has no source links (e.g. older conversations, or a partial
    // save) but internet_findings still holds sources, synthesise a search_complete
    // event so the Sources tab restores on reload instead of going blank.
    const inf = conv.pipeline?.internet_findings || {};
    const allSources =
      inf.all_sources ||
      inf.sources ||
      (inf.searches || [])
        .flatMap((s) => s.sources || [])
        .filter((s, i, arr) => arr.findIndex((x) => x.url === s.url) === i) ||
      [];
    const hasSourceLinks = storedActivity.some(
      (e) => e.event === 'search_complete' && e.links?.length > 0
    );
    const activity =
      allSources.length > 0 && !hasSourceLinks
        ? [
            ...storedActivity,
            {
              type: 'activity',
              event: 'search_complete',
              detail: `${allSources.length} sources from previous research`,
              reasoning: 'Sources restored from saved conversation.',
              links: allSources,
              ts: new Date().toISOString(),
            },
          ]
        : storedActivity;

    const status = conv.status || ((conv.messages || []).length ? 'complete' : 'pending');

    // Backfill client-side metadata (title + hasFile) from the full record.
    const patch = { title: deriveTitle(conv.messages) };
    if (conv.file) {
      patch.hasFile = true;
      setFiles((prev) => (prev[id] ? prev : { ...prev, [id]: { file_id: conv.file.id, filename: conv.file.name } }));
    }
    updateMeta(id, patch);

    if (status === 'running') {
      // Part 2d — interrupted state. Show a progress indicator at the last known
      // stage; the activity panel gets a reload notice + whatever completed before.
      const messages = [...(conv.messages || [])];
      if (!messages.some((m) => m.role === 'assistant')) {
        messages.push({
          role: 'assistant',
          type: null,
          progress: progressFromStage(conv.current_stage),
          interrupted: true,
        });
      }
      setCurrentConversation({ ...conv, messages });
      setActivityLog([
        {
          type: 'activity',
          event: 'reload_notice',
          detail: 'Research was running when page reloaded. Polling for completion...',
        },
        ...activity,
      ]);
      setActivityOpen(false); // panel starts closed on reload (Part 4)
      startPolling(id);
    } else if (status === 'error') {
      const messages = ensureErrorMessage([...(conv.messages || [])], conv.error_message);
      setCurrentConversation({ ...conv, messages });
      setActivityLog(activity);
      setActivityOpen(false);
    } else {
      // complete or pending — render the stored conversation as-is.
      setCurrentConversation(conv);
      setActivityLog(activity);
      setActivityOpen(false);
    }
  };

  // ---- background polling for a reloaded, still-running pipeline ----
  const startPolling = (id) => {
    stopPolling();
    pollingRef.current = setInterval(async () => {
      let s;
      try {
        s = await api.getStatus(id);
      } catch {
        return; // transient — keep polling
      }
      // Advance the on-screen progress indicator to the latest stage.
      setCurrentConversation((prev) => {
        if (!prev || prev.id !== id) return prev;
        return _updateLastMsg(prev, (m) => {
          if (m.role === 'assistant' && !m.type) m.progress = progressFromStage(s.current_stage);
        });
      });

      if (s.status === 'complete') {
        stopPolling();
        try {
          const full = await api.getConversation(id);
          setCurrentConversation(full);
          setActivityLog(full.pipeline?.activity || []);
        } catch { /* ignore */ }
        loadConversations();
      } else if (s.status === 'error') {
        stopPolling();
        setCurrentConversation((prev) =>
          prev && prev.id === id ? { ...prev, messages: ensureErrorMessage([...prev.messages], s.error_message) } : prev
        );
      }
    }, 2000);
  };

  // ---- conversation lifecycle ----
  const handleNewConversation = async () => {
    if (newChatDisabled) {
      focusInput();
      return;
    }
    setRootFile(null);
    setInput('');
    navigate('/');
    focusInput();
  };

  const handleSelectConversation = (id) => navigate(`/chat/${id}`);

  const handleRenameConversation = (id, newTitle) => {
    updateMeta(id, { title: newTitle });
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, title: newTitle } : c)));
  };

  const handleRetry = () => {
    if (lastQuestionRef.current) handleSendMessage(lastQuestionRef.current);
  };

  const handleDeleteConversation = (id) => {
    const next = new Set(hiddenIds);
    next.add(id);
    persistHidden(next);
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (id === currentConversationId) navigate('/');
  };

  const handleFileUploaded = (uploadResult, kind = 'main') => {
    if (kind === 'match') {
      if (currentConversationId) {
        setMatchFiles((prev) => ({ ...prev, [currentConversationId]: uploadResult || undefined }));
      } else {
        setRootMatchFile(uploadResult || null);
      }
      return;
    }
    if (currentConversationId) {
      setFiles((prev) => ({ ...prev, [currentConversationId]: uploadResult || undefined }));
      updateMeta(currentConversationId, { hasFile: !!uploadResult });
    } else {
      setRootFile(uploadResult || null);
    }
  };

  const handleRemoveFile = (kind = 'main') => {
    if (kind === 'match') {
      if (currentConversationId) {
        setMatchFiles((prev) => ({ ...prev, [currentConversationId]: undefined }));
      } else {
        setRootMatchFile(null);
      }
      return;
    }
    if (currentConversationId) {
      setFiles((prev) => ({ ...prev, [currentConversationId]: undefined }));
      updateMeta(currentConversationId, { hasFile: false });
    } else {
      setRootFile(null);
    }
  };

  const handleFillPrompt = (text) => {
    setInput(text);
    focusInput();
  };

  const currentFile = currentConversationId ? files[currentConversationId] : rootFile;
  const currentMatchFile = currentConversationId ? matchFiles[currentConversationId] : rootMatchFile;

  // New Chat button: disabled when the active conversation is empty (nothing to leave).
  const newChatDisabled = !!currentConversation
    && !currentConversation.notFound
    && (currentConversation.messages || []).length === 0;

  // ---- send + staged progress ----
  const handleSendMessage = async (content) => {
    // Resolve (or create) the conversation id. The router flow generates the id
    // client-side, navigates to /chat/{id}, then creates the backend JSON BEFORE
    // streaming so a mid-stream reload can still find + poll the conversation.
    let convId = currentConversationId;
    const isFirstMessage = !convId || !currentConversation || (currentConversation.messages || []).length === 0;

    if (!convId) {
      convId = (typeof crypto !== 'undefined' && crypto.randomUUID)
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const carriedFile = rootFile;
      const carriedMatch = rootMatchFile;
      if (carriedFile) setFiles((prev) => ({ ...prev, [convId]: carriedFile }));
      if (carriedMatch) setMatchFiles((prev) => ({ ...prev, [convId]: carriedMatch }));
      skipNextLoadRef.current = convId;
      navigate(`/chat/${convId}`);
      try {
        await api.createConversationWithId(
          convId, content.trim().slice(0, 40), carriedFile?.file_id || null, carriedMatch?.file_id || null
        );
      } catch (e) {
        console.error('Failed to create conversation:', e);
      }
      setRootFile(null);
      setRootMatchFile(null);
    }

    const fileId = files[convId]?.file_id || (currentConversationId ? null : rootFile?.file_id) || null;
    const matchHistoryFileId = matchFiles[convId]?.file_id || (currentConversationId ? null : rootMatchFile?.file_id) || null;

    lastQuestionRef.current = content;
    setIsLoading(true);
    setInput('');

    if (isFirstMessage) updateMeta(convId, { title: content.trim().slice(0, 40) });

    try {
      const mode = fileId ? 'data' : 'text';
      const userMessage = { role: 'user', content, ts: Date.now() };
      const assistantMessage = newProgressMessage(mode);

      setCurrentConversation((prev) => {
        const base = prev && prev.id === convId && !prev.notFound ? prev : { id: convId, messages: [] };
        return { ...base, id: convId, notFound: false, messages: [...(base.messages || []), userMessage, assistantMessage] };
      });

      const setStep = (key, value) =>
        setCurrentConversation((prev) => _updateLastMsg(prev, (m) => {
          m.progress = { ...m.progress, [key]: value };
        }));

      await api.analyseStream(convId, content, fileId, matchHistoryFileId, (eventType, event) => {
        if (eventType === 'activity') {
          setActivityLog((prev) => [...prev, event]);
          setActivityOpen(true);
          if (event.event === 'stage_error') {
            setCurrentConversation((prev) => _updateLastMsg(prev, (m) => {
              m.error = { title: 'Analysis failed', message: event.detail };
            }));
          }
          return;
        }
        switch (eventType) {
          case 'analysis_start': setStep('analysis', 'active'); break;
          case 'analysis_complete':
            setCurrentConversation((prev) => _updateLastMsg(prev, (m) => {
              m.progress = { ...m.progress, analysis: 'done' };
              m.analysisData = event.data;
            }));
            break;
          case 'research_start': setStep('research', 'active'); break;
          case 'research_complete':
            setCurrentConversation((prev) => _updateLastMsg(prev, (m) => {
              m.progress = { ...m.progress, research: 'done' };
              m.internetFindings = event.data;
            }));
            break;
          case 'stage1_start': setStep('stage1', 'active'); break;
          case 'stage1_complete':
            setCurrentConversation((prev) => _updateLastMsg(prev, (m) => {
              m.progress = { ...m.progress, stage1: 'done' };
              m.stage1 = event.data;
            }));
            break;
          case 'stage2_start': setStep('stage2', 'active'); break;
          case 'stage2_complete':
            setCurrentConversation((prev) => _updateLastMsg(prev, (m) => {
              m.progress = { ...m.progress, stage2: 'done' };
              m.stage2 = event.data;
              m.metadata = event.metadata;
            }));
            break;
          case 'stage3_start': setStep('stage3', 'active'); break;
          case 'stage3_complete':
            setCurrentConversation((prev) => _updateLastMsg(prev, (m) => {
              m.progress = { ...m.progress, stage3: 'done', report: 'active' };
              m.stage3 = event.data;
            }));
            break;
          case 'followup_start':
            setCurrentConversation((prev) => _updateLastMsg(prev, (m) => {
              m.progress = { ...m.progress, followup: 'active' };
            }));
            break;
          case 'report_complete':
            setCurrentConversation((prev) => _updateLastMsg(prev, (m) => {
              m.progress = { ...m.progress, report: 'done' };
              m.report = event.data;
              m.type = 'full_report';
            }));
            break;
          case 'followup_complete':
            setCurrentConversation((prev) => _updateLastMsg(prev, (m) => {
              m.progress = { ...m.progress, followup: 'done' };
              m.stage3 = event.data;
              m.type = 'chairman_followup';
            }));
            break;
          case 'title_complete':
            loadConversations();
            break;
          case 'complete':
            loadConversations();
            setIsLoading(false);
            break;
          case 'error':
            console.error('Stream error:', event.message);
            setCurrentConversation((prev) => _updateLastMsg(prev, (m) => {
              if (!m.error) m.error = { title: 'Analysis failed', message: event.message };
            }));
            setIsLoading(false);
            break;
          default:
            break;
        }
      });
    } catch (error) {
      console.error('Failed to send message:', error);
      setCurrentConversation((prev) => ({ ...prev, messages: prev.messages.slice(0, -2) }));
      setIsLoading(false);
    }
  };

  // Merge client-side titles/hasFile into the sidebar list.
  const sidebarConversations = conversations.map((c) => ({
    ...c,
    title: convMeta[c.id]?.title || c.title || 'New conversation',
    hasFile: convMeta[c.id]?.hasFile || false,
  }));

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[var(--background)] text-[var(--text)]">
      <Sidebar
        conversations={sidebarConversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onDeleteConversation={handleDeleteConversation}
        onRenameConversation={handleRenameConversation}
        newChatDisabled={newChatDisabled}
        loading={loadingConvos}
      />
      <ChatInterface
        conversation={currentConversation}
        onSendMessage={handleSendMessage}
        onFileUploaded={handleFileUploaded}
        onRemoveFile={handleRemoveFile}
        onFillPrompt={handleFillPrompt}
        onRetry={handleRetry}
        currentFile={currentFile}
        currentMatchFile={currentMatchFile}
        currentConversationId={currentConversationId}
        isLoading={isLoading}
        input={input}
        onInputChange={setInput}
        messageInputRef={messageInputRef}
        activityAvailable={activityLog.length > 0}
        activityOpen={activityOpen}
        onOpenActivity={() => setActivityOpen(true)}
      />
      <ActivityPanel
        log={activityLog}
        open={activityOpen}
        onClose={() => setActivityOpen(false)}
      />
      {paletteOpen && (
        <CommandPalette
          conversations={sidebarConversations}
          onSelect={(id) => navigate(`/chat/${id}`)}
          onClose={() => setPaletteOpen(false)}
        />
      )}
    </div>
  );
}

function _updateLastMsg(prev, mutate) {
  if (!prev || !prev.messages || prev.messages.length === 0) return prev;
  const messages = [...prev.messages];
  const last = { ...messages[messages.length - 1] };
  last.progress = { ...last.progress };
  mutate(last);
  messages[messages.length - 1] = last;
  return { ...prev, messages };
}

// Attach an error to the last assistant message, or append one if none exists.
function ensureErrorMessage(messages, errorMessage) {
  const msg = { title: 'Analysis failed', message: errorMessage || 'The pipeline encountered an error.' };
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === 'assistant') {
      messages[i] = { ...messages[i], error: msg };
      return messages;
    }
  }
  messages.push({ role: 'assistant', type: null, error: msg });
  return messages;
}

export default App;
