'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Plus, ArrowUp, X, BarChart3, ClipboardList, MessageSquare, Loader2, Menu, LayoutDashboard, Cable, Telescope } from 'lucide-react';
import Stage3 from './Stage3';
import Report from './Report';
import AnalysisProgress from './AnalysisProgress';
import ErrorState from './ErrorState';
import ConnectSource from './ConnectSource';
import { api } from '../lib/api';

const EXAMPLE_PROMPTS = [
  'Which entities lead across the key metrics, and why?',
  'Summarise the most important trends in this dataset.',
  'What does current research say about this topic?',
];

const MAX_INPUT_LINES = 6;

// Centred content column: 76% of the chat pane (12% gutters), expanding to 90% under 900px.
const COLUMN = 'w-[76%] max-[900px]:w-[90%] mx-auto';

function mapUploadError(msg) {
  const m = msg || 'The file could not be processed.';
  if (/empty|no data rows/i.test(m)) {
    return { title: 'Empty file', message: 'This file has no data rows. Check the file and upload again.' };
  }
  if (/encoding/i.test(m)) {
    return { title: 'Upload failed', message: m };
  }
  return { title: 'Upload failed', message: m };
}

export default function ChatInterface({
  conversation,
  onSendMessage,
  onFileUploaded,
  onRemoveFile,
  onFillPrompt,
  onRetry,
  currentFile,
  currentMatchFile,
  currentConversationId,
  isLoading,
  input,
  onInputChange,
  messageInputRef,
  activityAvailable,
  activityOpen,
  onOpenActivity,
}) {
  const messagesContainerRef = useRef(null);
  const fileInputRef = useRef(null);
  // Which slot the next file-dialog selection fills: 'main' (dataset) or 'match'
  // (match-history CSV that enables the XGBoost model).
  const uploadTargetRef = useRef('main');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [connectOpen, setConnectOpen] = useState(false);
  const [creatingDashboard, setCreatingDashboard] = useState(false);
  const router = useRouter();

  // Build a live web dashboard from the attached dataset — no AI pipeline.
  const handleCreateDashboard = async () => {
    if (!currentFile || creatingDashboard) return;
    setCreatingDashboard(true);
    try {
      const r = await api.createDashboard(currentFile.file_id, currentFile.filename);
      router.push(`/dashboard/${r.conversation_id}`);
    } catch (err) {
      setUploadError({ title: 'Dashboard failed', message: err?.message || 'Could not create the dashboard.' });
      setCreatingDashboard(false);
    }
  };

  // Scroll tracking (Fix 4). isAtBottom records whether the user is parked at the
  // bottom; prevMsgCount/prevConvId let us distinguish "user sent a message" and
  // "a conversation just loaded" from the constant SSE streaming mutations that
  // used to yank the view while the user was reading.
  const isAtBottom = useRef(true);
  const prevMsgCount = useRef(0);
  const prevConvId = useRef(null);

  const msgs = conversation?.messages;
  const msgCount = msgs?.length || 0;
  const convId = conversation?.id || null;

  const handleScroll = () => {
    const el = messagesContainerRef.current;
    if (!el) return;
    const threshold = 100; // px from bottom
    isAtBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
  };

  const scrollToBottom = () => {
    const el = messagesContainerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  };

  // Only scroll in two situations: (1) the user sent a message (msgCount grew
  // within the same conversation), or (2) a conversation loaded for the first
  // time (it changed and has messages). Never on streaming/activity/state churn.
  useEffect(() => {
    const convChanged = convId !== prevConvId.current;
    const sentMessage = !convChanged && msgCount > prevMsgCount.current;
    const conversationLoaded = convChanged && msgCount > 0;
    if (sentMessage || conversationLoaded) {
      requestAnimationFrame(scrollToBottom);
    }
    prevMsgCount.current = msgCount;
    prevConvId.current = convId;
  }, [msgCount, convId]);

  // Auto-grow the textarea up to MAX_INPUT_LINES, then scroll.
  const autoGrow = () => {
    const el = messageInputRef?.current;
    if (!el) return;
    el.style.height = 'auto';
    const styles = window.getComputedStyle(el);
    const lineHeight = parseFloat(styles.lineHeight) || 22;
    const padding = parseFloat(styles.paddingTop) + parseFloat(styles.paddingBottom);
    const maxHeight = lineHeight * MAX_INPUT_LINES + padding;
    el.style.height = Math.min(el.scrollHeight, maxHeight) + 'px';
    el.style.overflowY = el.scrollHeight > maxHeight ? 'auto' : 'hidden';
  };

  useEffect(() => {
    autoGrow();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [input]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) onSendMessage(input);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // First click attaches the main dataset; once that exists, the + button
  // attaches the optional match-history file into the second slot.
  const handleAttachClick = (kind) => {
    // kind may be an event object when wired directly to onClick — sanitise it.
    const slot = kind === 'main' || kind === 'match' ? kind : (currentFile ? 'match' : 'main');
    uploadTargetRef.current = slot;
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    const kind = uploadTargetRef.current;
    setUploadError(null);
    setUploading(true);
    try {
      const result = await api.uploadFile(file);
      onFileUploaded(result, kind);
    } catch (err) {
      setUploadError(mapUploadError(err?.message));
    } finally {
      setUploading(false);
    }
  };

  const isEmpty = !conversation || conversation.messages.length === 0;
  const hasText = input.trim().length > 0;
  const placeholder = currentFile ? 'Ask about your dataset...' : 'Ask the council anything...';

  return (
    <div className="relative flex-1 flex flex-col h-screen bg-[var(--background)] overflow-hidden">
      {/* Top fade — messages appear to fade in from above (1.2) */}
      <div className="pointer-events-none absolute top-0 left-0 right-0 h-[60px] z-10 bg-gradient-to-b from-[oklch(0.12_0_0)] to-transparent" />
      {/* Bottom blur strip behind the floating input so content underneath is
          softly blurred rather than fully visible (1.2) */}
      <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-[150px] z-10 backdrop-blur-sm [mask-image:linear-gradient(to_top,black_55%,transparent)]" />

      {/* Sticky floating button to (re)open the Activity / Sources panel */}
      {!activityOpen && (activityAvailable || !isEmpty) && (
        <button
          type="button"
          onClick={onOpenActivity}
          title="Show research activity & sources"
          aria-label="Show research activity and sources"
          className="fixed top-4 right-4 z-30 w-11 h-11 flex items-center justify-center rounded-full bg-[var(--surface-input)] border border-[var(--border-2)] text-[var(--muted)] shadow-[0_4px_16px_rgba(0,0,0,0.45)] hover:text-[var(--text)] hover:bg-[var(--active)] transition"
        >
          <Menu size={18} strokeWidth={1.5} />
        </button>
      )}

      {/* Scrollable content; last items scroll behind the floating input bar */}
      <div ref={messagesContainerRef} onScroll={handleScroll} className="flex-1 overflow-y-auto">
        <div className={`${COLUMN} py-6 pb-[180px] min-h-full`}>
          {uploadError ? (
            <ErrorState
              title={uploadError.title}
              message={uploadError.message}
              onRetry={() => { setUploadError(null); handleAttachClick(); }}
            />
          ) : conversation?.notFound ? (
            <ErrorState
              title="Conversation not found"
              message="This conversation doesn't exist or has been removed."
              onRetry={null}
            />
          ) : isEmpty ? (
            <EmptyState onFillPrompt={onFillPrompt} onAttachClick={handleAttachClick} onConnectClick={() => setConnectOpen(true)} />
          ) : (
            conversation.messages.map((msg, index) =>
              msg.role === 'user' ? (
                <div key={index} className="group flex flex-col items-end mb-8 animate-msg-in">
                  <div className="bg-[var(--user-bubble)] text-[oklch(0.92_0_0)] rounded-xl max-w-[70%] px-4 py-3 whitespace-pre-wrap leading-relaxed">
                    {msg.content}
                  </div>
                  {msg.ts && (
                    <div className="text-[12px] text-[var(--faint)] mt-1 mr-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                      {new Date(msg.ts).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}
                    </div>
                  )}
                </div>
              ) : (
                // AI response inks directly onto the page — no card, full width
                <div key={index} className="mb-8 text-left">
                  {/* keyed so each phase (progress → report) fades in smoothly */}
                  <div key={msg.error ? 'error' : msg.type || 'pending'} className="animate-msg-in">
                    {msg.error ? (
                      <ErrorState title={msg.error.title} message={msg.error.message} onRetry={onRetry} />
                    ) : msg.type === 'full_report' && msg.report ? (
                      <>
                        <DashboardReadyBanner onOpen={() => router.push(`/dashboard/${currentConversationId}`)} />
                        <Report report={msg.report} conversationId={currentConversationId} />
                      </>
                    ) : msg.type === 'chairman_followup' && msg.stage3 ? (
                      <Stage3 finalResponse={msg.stage3} />
                    ) : (
                      msg.progress && (
                        <div className="flex flex-col gap-3">
                          <AnalysisProgress progress={msg.progress} />
                          <p className="inline-flex items-center gap-1.5 text-[12.5px] text-[var(--faint)] max-w-[460px] leading-relaxed">
                            <LayoutDashboard size={13} strokeWidth={1.5} />
                            A live dashboard is generated automatically when the research completes.
                          </p>
                          {msg.interrupted && (
                            <p className="text-[13px] text-[var(--muted)] max-w-[460px] leading-relaxed">
                              Research is continuing in the background. This page will update automatically.
                            </p>
                          )}
                        </div>
                      )
                    )}
                  </div>
                </div>
              )
            )
          )}
        </div>
      </div>

      {/* Floating input bar */}
      <div className={`absolute bottom-6 left-1/2 -translate-x-1/2 z-20 ${COLUMN}`}>
        {(currentFile || currentMatchFile) && (
          <div className="flex flex-col items-start gap-1.5 mb-2">
            {currentFile && !currentConversationId && (
              <button
                type="button"
                onClick={handleCreateDashboard}
                disabled={creatingDashboard}
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--surface-input)] border border-[var(--border-2)] text-sm text-[var(--text)] hover:border-[var(--accent)] transition disabled:opacity-60"
                title="Build a live web dashboard from this dataset (no AI run)"
              >
                {creatingDashboard
                  ? <Loader2 size={16} strokeWidth={1.5} className="animate-spin" />
                  : <LayoutDashboard size={16} strokeWidth={1.5} />}
                {creatingDashboard ? 'Building dashboard…' : 'Create dashboard'}
              </button>
            )}
            {currentFile && (
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--surface-input)] border border-[var(--border-2)] text-sm text-[var(--text)]">
                <BarChart3 size={16} strokeWidth={1.5} />
                <span className="font-medium">{currentFile.filename}</span>
                <button
                  type="button"
                  onClick={() => onRemoveFile('main')}
                  className="text-[var(--muted)] hover:text-[var(--danger)] leading-none"
                  aria-label="Remove dataset file"
                >
                  <X size={16} strokeWidth={1.5} />
                </button>
              </div>
            )}
            {currentMatchFile && (
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--surface-input)] border border-[var(--border-2)] text-sm text-[var(--text)]">
                <ClipboardList size={16} strokeWidth={1.5} />
                <span className="font-medium">{currentMatchFile.filename}</span>
                <span className="text-[11px] text-[var(--muted)]">match history</span>
                <button
                  type="button"
                  onClick={() => onRemoveFile('match')}
                  className="text-[var(--muted)] hover:text-[var(--danger)] leading-none"
                  aria-label="Remove match history file"
                >
                  <X size={16} strokeWidth={1.5} />
                </button>
              </div>
            )}
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          className="flex items-end gap-2 bg-[var(--surface-input)] border border-[var(--border-2)] rounded-2xl shadow-[0_4px_24px_rgba(0,0,0,0.4)] px-3 py-2"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.xls,.xlsx"
            onChange={handleFileChange}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => handleAttachClick()}
            disabled={uploading || (!!currentFile && !!currentMatchFile)}
            title={
              !currentFile
                ? 'Attach dataset (CSV or Excel)'
                : !currentMatchFile
                ? 'Attach optional match-history CSV (enables XGBoost)'
                : 'Both files attached'
            }
            className="shrink-0 w-9 h-9 flex items-center justify-center rounded-full text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--active)] transition disabled:opacity-50"
          >
            {uploading ? (
              <Loader2 size={18} strokeWidth={1.5} className="animate-spin" />
            ) : (
              <Plus size={18} strokeWidth={1.5} />
            )}
          </button>

          <textarea
            ref={messageInputRef}
            className="flex-1 bg-transparent resize-none outline-none text-[var(--text)] placeholder:text-[var(--faint)] text-[15px] leading-6 py-2 px-1 max-h-40 overflow-y-hidden"
            placeholder={placeholder}
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            rows={1}
          />

          <button
            type="submit"
            disabled={!hasText || isLoading}
            aria-label="Send"
            className={`shrink-0 w-9 h-9 rounded-full flex items-center justify-center transition ${
              hasText
                ? 'bg-white text-black hover:bg-[oklch(0.88_0_0)]'
                : 'bg-[var(--active)] text-[var(--faint)] cursor-not-allowed'
            }`}
          >
            <ArrowUp size={18} strokeWidth={1.5} />
          </button>
        </form>
      </div>

      {connectOpen && (
        <ConnectSource
          onImported={(result) => onFileUploaded(result, 'main')}
          onClose={() => setConnectOpen(false)}
        />
      )}
    </div>
  );
}

function DashboardReadyBanner({ onOpen }) {
  return (
    <div className="flex items-center gap-3 mb-4 px-4 py-3 rounded-xl border border-[var(--border-2)] bg-[oklch(0.16_0.02_250)]">
      <LayoutDashboard size={18} strokeWidth={1.5} className="shrink-0 text-[var(--accent)]" />
      <div className="flex-1 text-[13px] text-[var(--muted)]">
        <span className="text-[var(--text)] font-medium">Live dashboard generated from this research.</span>{' '}
        Charts, metrics and the research findings are pinned there — keep editing it with the dashboard assistant.
      </div>
      <button
        onClick={onOpen}
        className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[var(--new-chat)] text-[var(--background)] text-[13px] font-medium hover:bg-[var(--new-chat-hover)] transition"
      >
        Open dashboard
      </button>
    </div>
  );
}

function EmptyState({ onFillPrompt, onAttachClick, onConnectClick }) {
  return (
    <div className="flex flex-col items-center justify-center text-center min-h-[70vh]">
      <h2 className="text-3xl font-semibold text-[var(--text)] mb-3">datavisual.studio</h2>
      <p className="text-base text-[var(--muted)] max-w-[500px] mb-7 leading-relaxed">
        Upload a dataset or connect your database — then ask the AI council for
        an analytical report, or build a live web dashboard from the data.
      </p>

      <div className="flex flex-wrap items-stretch justify-center gap-3 mb-7">
        <button
          type="button"
          onClick={onAttachClick}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[var(--raised)] border border-[var(--border-2)] text-[var(--text)] text-sm hover:border-[var(--accent)] transition"
        >
          <BarChart3 size={16} strokeWidth={1.5} /> Upload dataset
        </button>
        <button
          type="button"
          onClick={onConnectClick}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[var(--raised)] border border-[var(--border-2)] text-[var(--text)] text-sm hover:border-[var(--accent)] transition"
        >
          <Cable size={16} strokeWidth={1.5} /> Connect database / API
        </button>
        <button
          type="button"
          onClick={() => onFillPrompt('')}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[var(--raised)] border border-[var(--border-2)] text-[var(--text)] text-sm hover:border-[var(--accent)] transition"
        >
          <MessageSquare size={16} strokeWidth={1.5} /> Ask without data
        </button>
      </div>

      {/* The two core flows, spelled out */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-[640px] mb-7 text-left">
        <button
          type="button"
          onClick={onAttachClick}
          className="rounded-xl border border-[var(--border-2)] bg-[var(--raised)] p-4 hover:border-[var(--accent)] transition"
        >
          <div className="flex items-center gap-2 mb-1.5">
            <LayoutDashboard size={16} strokeWidth={1.5} className="text-[var(--accent)]" />
            <span className="text-sm font-semibold text-[var(--text)]">Build a dashboard</span>
          </div>
          <p className="text-[12.5px] text-[var(--muted)] leading-relaxed m-0">
            Attach a file or connect a database, then click <span className="text-[var(--text)]">Create dashboard</span>.
            You get metrics, charts and a data table instantly — refine it by chatting
            (&quot;add a pie of revenue by product&quot;) and refresh it from the source anytime.
          </p>
        </button>
        <button
          type="button"
          onClick={() => onFillPrompt('')}
          className="rounded-xl border border-[var(--border-2)] bg-[var(--raised)] p-4 hover:border-[var(--accent)] transition"
        >
          <div className="flex items-center gap-2 mb-1.5">
            <Telescope size={16} strokeWidth={1.5} className="text-[var(--accent)]" />
            <span className="text-sm font-semibold text-[var(--text)]">Deep research</span>
          </div>
          <p className="text-[12.5px] text-[var(--muted)] leading-relaxed m-0">
            Type any question (with or without data). Live web research plus a council of
            AI models produce a cited report — and the findings land on a dashboard you
            can keep editing.
          </p>
        </button>
      </div>

      <div className="flex flex-col gap-2 w-full max-w-[460px]">
        {EXAMPLE_PROMPTS.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => onFillPrompt(p)}
            className="px-3.5 py-2.5 rounded-lg bg-[var(--raised)] border border-[var(--border)] text-[var(--muted)] text-sm text-left hover:text-[var(--text)] hover:border-[var(--border-2)] transition"
          >
            {p}
          </button>
        ))}
      </div>
    </div>
  );
}
