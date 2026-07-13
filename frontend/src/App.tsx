import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import {
  Bot,
  CalendarDays,
  CheckCircle2,
  Clock,
  Brain,
  FileText,
  Lightbulb,
  Mic,
  NotebookPen,
  ListTodo,
  Pause,
  Play,
  Plus,
  Search,
  Send,
  Settings as SettingsIcon,
  MessageSquarePlus,
  Trash2,
  Upload,
  User,
  X
} from "lucide-react";
import { api, ChatContextSummary, ChatMessage, Conversation, FileHit, IndexedFile, Memory, Note, ReminderItem, Settings, TaskItem, TodaySummary, ToolActivity } from "./api/client";

type Tab = "today" | "chat" | "tasks" | "memory" | "files" | "notes" | "settings";
type VoiceStatus = "idle" | "listening" | "transcribing";
type SpeechResultLike = { isFinal: boolean; 0?: { transcript: string } };
type SpeechResultListLike = { length: number; [index: number]: SpeechResultLike };
type LocalSpeechRecognitionEvent = Event & { resultIndex: number; results: SpeechResultListLike };
type LocalSpeechRecognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: LocalSpeechRecognitionEvent) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};
type LocalSpeechRecognitionConstructor = new () => LocalSpeechRecognition;
type RecordingFormat = { mimeType: string; extension: string };

declare global {
  interface Window {
    SpeechRecognition?: LocalSpeechRecognitionConstructor;
    webkitSpeechRecognition?: LocalSpeechRecognitionConstructor;
  }
}

const tabs: Array<{ id: Tab; label: string; icon: typeof Bot }> = [
  { id: "today", label: "Today", icon: CalendarDays },
  { id: "chat", label: "Chat", icon: Bot },
  { id: "tasks", label: "Tasks", icon: ListTodo },
  { id: "memory", label: "Memory", icon: Brain },
  { id: "files", label: "Files", icon: FileText },
  { id: "notes", label: "Notes", icon: NotebookPen },
  { id: "settings", label: "Settings", icon: SettingsIcon }
];

function IconButton({
  title,
  children,
  onClick,
  disabled,
  tone = "neutral",
  type = "button"
}: {
  title: string;
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  tone?: "neutral" | "primary" | "danger";
  type?: "button" | "submit";
}) {
  const toneClass =
    tone === "primary"
      ? "cyber-icon-primary"
      : tone === "danger"
        ? "cyber-icon-danger"
        : "cyber-icon-neutral";
  return (
    <button
      type={type}
      title={title}
      aria-label={title}
      onClick={onClick}
      disabled={disabled}
      className={`cyber-icon-button ${toneClass}`}
    >
      {children}
    </button>
  );
}

function TextButton({
  children,
  onClick,
  disabled,
  type = "button"
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit";
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className="cyber-text-button"
    >
      {children}
    </button>
  );
}

function App() {
  const [activeTab, setActiveTab] = useState<Tab>("today");
  const [settings, setSettings] = useState<Settings | null>(null);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationQuery, setConversationQuery] = useState("");
  const [isSearchingConversations, setIsSearchingConversations] = useState(false);
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [activities, setActivities] = useState<ToolActivity[]>([]);
  const [actions, setActions] = useState<Array<{ type: "open_url"; url: string; label: string }>>([]);
  const [voiceReplies, setVoiceReplies] = useState(false);
  const [ttsVoice, setTtsVoice] = useState("alloy");
  const [memoryEnabled, setMemoryEnabled] = useState(true);
  const [useFileContext, setUseFileContext] = useState(true);
  const [recording, setRecording] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatus>("idle");
  const [liveTranscript, setLiveTranscript] = useState("");
  const [composerKey, setComposerKey] = useState(0);
  const [contextPreview, setContextPreview] = useState<ChatContextSummary | null>(null);
  const [isPreviewingContext, setIsPreviewingContext] = useState(false);

  const [memories, setMemories] = useState<Memory[]>([]);
  const [memoryDraft, setMemoryDraft] = useState("");
  const [files, setFiles] = useState<IndexedFile[]>([]);
  const [fileHits, setFileHits] = useState<FileHit[]>([]);
  const [fileQuery, setFileQuery] = useState("");
  const [notes, setNotes] = useState<Note[]>([]);
  const [noteTitle, setNoteTitle] = useState("");
  const [noteContent, setNoteContent] = useState("");
  const [noteQuery, setNoteQuery] = useState("");
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [reminders, setReminders] = useState<ReminderItem[]>([]);
  const [today, setToday] = useState<TodaySummary | null>(null);
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDetails, setTaskDetails] = useState("");
  const [taskDueDate, setTaskDueDate] = useState("");
  const [reminderTitle, setReminderTitle] = useState("");
  const [reminderAt, setReminderAt] = useState("");

  const abortRef = useRef<AbortController | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordingFormatRef = useRef<RecordingFormat>({ mimeType: "audio/webm", extension: "webm" });
  const speechRecognitionRef = useRef<LocalSpeechRecognition | null>(null);
  const voiceBaseInputRef = useRef("");
  const browserTranscriptRef = useRef("");
  const speechFinalPiecesRef = useRef<string[]>([]);
  const promptRef = useRef<HTMLTextAreaElement | null>(null);
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const shouldStickToBottomRef = useRef(true);

  useEffect(() => {
    void loadInitialState();
  }, []);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      void refreshConversations(conversationQuery);
    }, 220);
    return () => window.clearTimeout(handle);
  }, [conversationQuery]);

  useEffect(() => {
    if (!shouldStickToBottomRef.current) return;
    window.requestAnimationFrame(() => {
      const scroller = chatScrollRef.current;
      if (scroller) scroller.scrollTop = scroller.scrollHeight;
    });
  }, [messages, isLoading]);

  function updateScrollStickiness() {
    const scroller = chatScrollRef.current;
    if (!scroller) return;
    const distanceFromBottom = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight;
    shouldStickToBottomRef.current = distanceFromBottom < 80;
  }

  async function loadInitialState() {
    try {
      const loadedSettings = await api.settings();
      setSettings(loadedSettings);
      setTtsVoice(loadedSettings.tts_voice);
      await Promise.all([refreshMemories(), refreshFiles(), refreshNotes(), refreshTasks(), refreshReminders(), refreshToday(), refreshConversations()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Sidro.");
    }
  }

  async function refreshConversations(query = conversationQuery) {
    setIsSearchingConversations(true);
    try {
      setConversations(await api.conversations(query));
    } finally {
      setIsSearchingConversations(false);
    }
  }

  async function refreshMemories() {
    setMemories(await api.memories());
  }

  async function refreshFiles() {
    setFiles(await api.files());
  }

  async function refreshNotes() {
    setNotes(await api.notes());
  }
  async function refreshTasks() {
    setTasks(await api.tasks());
  }

  async function refreshReminders() {
    setReminders(await api.reminders());
  }

  async function refreshToday() {
    setToday(await api.today());
  }

  function speakWithBrowser(text: string) {
    if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) {
      throw new Error("Browser voice replies are not supported in this browser.");
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text.slice(0, 4000));
    utterance.lang = "en-US";
    utterance.rate = 0.98;
    utterance.pitch = 1;
    window.speechSynthesis.speak(utterance);
  }

  async function playReply(text: string, language?: string) {
    try {
      const audio = await api.speak(text, ttsVoice, language);
      const url = URL.createObjectURL(audio);
      const player = new Audio(url);
      player.onended = () => URL.revokeObjectURL(url);
      await player.play();
      setActivities((current) => [{ tool: "tts", status: "played", detail: "Backend voice reply" }, ...current]);
    } catch (err) {
      try {
        speakWithBrowser(text);
        setActivities((current) => [
          { tool: "tts", status: "browser fallback", detail: err instanceof Error ? err.message : "Backend TTS unavailable" },
          ...current
        ]);
      } catch (fallbackErr) {
        setActivities((current) => [
          { tool: "tts", status: "unavailable", detail: fallbackErr instanceof Error ? fallbackErr.message : "Voice reply failed" },
          ...current
        ]);
      }
    }
  }

  function clearComposer(remount = false) {
    if (promptRef.current) promptRef.current.value = "";
    setInput("");
    setLiveTranscript("");
    voiceBaseInputRef.current = "";
    browserTranscriptRef.current = "";
    speechFinalPiecesRef.current = [];
    if (remount) {
      setComposerKey((current) => current + 1);
      window.setTimeout(() => {
        if (promptRef.current) promptRef.current.value = "";
      }, 0);
    }
  }

  async function sendMessage(event?: FormEvent) {
    event?.preventDefault();
    stopBrowserSpeechRecognition();
    const message = (promptRef.current?.value ?? input).trim();
    if (!message || isLoading) return;

    clearComposer(true);
    setError("");
    setActions([]);
    setActivities([]);
    setContextPreview(null);
    shouldStickToBottomRef.current = true;
    setIsLoading(true);
    setMessages((current) => [...current, { role: "user", content: message }]);

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const response = await api.chat(
        {
          message,
          conversation_id: conversationId,
          use_file_context: useFileContext,
          memory_enabled: memoryEnabled
        },
        controller.signal
      );
      setConversationId(response.conversation_id);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: response.reply,
          metadata: {
            used_file_context: response.used_file_context,
            used_memory_context: response.used_memory_context,
            context_summary: response.context_summary,
            tool_activities: response.tool_activities,
            actions: response.actions
          }
        }
      ]);
      setActivities(response.tool_activities);
      setActions(response.actions);
      await Promise.all([refreshMemories(), refreshNotes(), refreshTasks(), refreshReminders(), refreshToday(), refreshConversations()]);
      if (voiceReplies) await playReply(response.reply, response.language);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setError("Stopped the current response.");
      } else {
        setError(err instanceof Error ? err.message : "Message failed.");
      }
    } finally {
      setIsLoading(false);
      abortRef.current = null;
      if ((promptRef.current?.value || "").trim() === message) {
        clearComposer(false);
      }
      window.setTimeout(() => promptRef.current?.focus(), 0);
    }
  }

  function stopCurrentRequest() {
    abortRef.current?.abort();
  }

  function startNewChat() {
    stopBrowserSpeechRecognition();
    abortRef.current?.abort();
    setActiveTab("chat");
    setConversationId(undefined);
    setMessages([]);
    clearComposer(true);
    setError("");
    setActivities([]);
    setActions([]);
    setContextPreview(null);
    setRecording(false);
    setVoiceStatus("idle");
    audioChunksRef.current = [];
  }

  function clearChatView() {
    startNewChat();
  }

  async function openConversation(id: string) {
    stopBrowserSpeechRecognition();
    abortRef.current?.abort();
    setActiveTab("chat");
    setError("");
    setActions([]);
    setActivities([]);
    setContextPreview(null);
    clearComposer(true);
    shouldStickToBottomRef.current = true;
    const result = await api.messages(id);
    setConversationId(id);
    setMessages(result.messages.filter((message) => message.role !== "system"));
  }

  async function removeConversation(id: string) {
    await api.deleteConversation(id);
    if (conversationId === id) {
      startNewChat();
    }
    await refreshConversations();
  }

  function startBrainstormChat() {
    stopBrowserSpeechRecognition();
    abortRef.current?.abort();
    const draft = "Let's brainstorm ideas for ";
    setActiveTab("chat");
    setConversationId(undefined);
    setMessages([]);
    setError("");
    setActions([]);
    setActivities([{ tool: "brainstorm", status: "ready", detail: "Fresh brainstorming chat started" }]);
    setContextPreview(null);
    setRecording(false);
    setVoiceStatus("idle");
    setLiveTranscript("");
    voiceBaseInputRef.current = "";
    browserTranscriptRef.current = "";
    speechFinalPiecesRef.current = [];
    audioChunksRef.current = [];
    setComposerKey((current) => current + 1);
    setInput(draft);
    window.setTimeout(() => {
      if (promptRef.current) {
        promptRef.current.value = draft;
        promptRef.current.focus();
        promptRef.current.setSelectionRange(draft.length, draft.length);
      }
    }, 0);
  }

  function stopBrowserSpeechRecognition() {
    const recognition = speechRecognitionRef.current;
    if (!recognition) return;
    recognition.onend = null;
    recognition.onerror = null;
    recognition.onresult = null;
    try {
      recognition.stop();
    } catch {
      // The browser may already have stopped it.
    }
    speechRecognitionRef.current = null;
  }

  function startBrowserSpeechRecognition() {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      setActivities([{ tool: "voice-preview", status: "unavailable", detail: "Live transcript preview is not supported in this browser." }]);
      return;
    }

    const recognition = new Recognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.onresult = (event) => {
      const finalPieces = [...speechFinalPiecesRef.current];
      let interimText = "";

      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const piece = event.results[index][0]?.transcript.trim() || "";
        if (!piece) continue;
        if (event.results[index].isFinal) {
          finalPieces.push(piece);
        } else {
          interimText = `${interimText} ${piece}`.trim();
        }
      }

      const finalText = finalPieces.join(" ").replace(/\s+/g, " ").trim();
      speechFinalPiecesRef.current = finalPieces;
      browserTranscriptRef.current = finalText;
      setLiveTranscript(interimText);
      setInput([voiceBaseInputRef.current, finalText, interimText].filter(Boolean).join(" ").replace(/\s+/g, " ").trim());
    };
    recognition.onerror = () => {
      setActivities([{ tool: "voice-preview", status: "limited", detail: "Recording continues; live preview is unavailable." }]);
    };
    recognition.onend = () => {
      if (mediaRecorderRef.current?.state === "recording") {
        try {
          recognition.start();
        } catch {
          // Some browsers reject immediate restarts; final Whisper transcription still runs.
        }
      }
    };
    speechRecognitionRef.current = recognition;
    try {
      recognition.start();
    } catch {
      speechRecognitionRef.current = null;
    }
  }

  function getRecordingFormat(): RecordingFormat {
    const candidates: RecordingFormat[] = [
      { mimeType: "audio/webm;codecs=opus", extension: "webm" },
      { mimeType: "audio/webm", extension: "webm" },
      { mimeType: "audio/ogg;codecs=opus", extension: "ogg" },
      { mimeType: "audio/mp4", extension: "m4a" }
    ];
    const supported = candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate.mimeType));
    return supported || { mimeType: "", extension: "webm" };
  }

  async function toggleRecording() {
    if (recording) {
      stopBrowserSpeechRecognition();
      mediaRecorderRef.current?.stop();
      setRecording(false);
      setVoiceStatus("transcribing");
      return;
    }

    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const format = getRecordingFormat();
      const recorder = format.mimeType ? new MediaRecorder(stream, { mimeType: format.mimeType }) : new MediaRecorder(stream);
      recordingFormatRef.current = format.mimeType ? format : { mimeType: recorder.mimeType || "audio/webm", extension: "webm" };
      audioChunksRef.current = [];
      voiceBaseInputRef.current = promptRef.current?.value.trim() || "";
      browserTranscriptRef.current = "";
      speechFinalPiecesRef.current = [];
      setLiveTranscript("");
      setInput(voiceBaseInputRef.current);
      setActivities([{ tool: "recording", status: "listening", detail: recordingFormatRef.current.mimeType || "browser default audio" }]);
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        stopBrowserSpeechRecognition();
        const format = recordingFormatRef.current;
        const blob = new Blob(audioChunksRef.current, { type: format.mimeType || "audio/webm" });
        const browserText = browserTranscriptRef.current.trim();
        if (blob.size < 512) {
          if (browserText) {
            setInput([voiceBaseInputRef.current, browserText].filter(Boolean).join(" ").trim());
            setActivities([{ tool: "voice-preview", status: "used", detail: browserText }]);
          } else {
            setError("I did not receive enough microphone audio. Try holding the mic button for a little longer.");
          }
          setVoiceStatus("idle");
          setLiveTranscript("");
          return;
        }
        setActivities([{ tool: "transcribe", status: "working", detail: `Sending ${Math.round(blob.size / 1024)} KB audio` }]);
        try {
          const result = await api.transcribe(blob, `recording.${format.extension}`);
          const transcript = result.text.trim() || browserText;
          if (!transcript) {
            setError("I could not hear clear speech in that recording. Try again closer to the microphone.");
            setActivities([{ tool: `transcribe:${result.provider}`, status: result.language || "empty", detail: "No speech detected" }]);
            return;
          }
          setInput([voiceBaseInputRef.current, transcript].filter(Boolean).join(" ").trim());
          setActivities([{ tool: `transcribe:${result.provider}`, status: result.language || "done", detail: result.text }]);
        } catch (err) {
          setError(err instanceof Error ? err.message : "Transcription failed.");
        } finally {
          setVoiceStatus("idle");
          setLiveTranscript("");
        }
      };
      mediaRecorderRef.current = recorder;
      recorder.start(250);
      startBrowserSpeechRecognition();
      setRecording(true);
      setVoiceStatus("listening");
    } catch {
      setVoiceStatus("idle");
      setError("Microphone permission was not granted.");
    }
  }

  async function previewContext() {
    const query = (promptRef.current?.value ?? input).trim();
    if (!query || isPreviewingContext) return;
    setError("");
    setIsPreviewingContext(true);
    try {
      const preview = await api.contextPreview({ query, use_file_context: useFileContext, memory_enabled: memoryEnabled });
      setContextPreview(preview);
      setActivities([{ tool: "context_preview", status: "ready", detail: { memory: preview.memory_count, files: preview.file_count } }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Context preview failed.");
    } finally {
      setIsPreviewingContext(false);
    }
  }

  async function saveMemory(event: FormEvent) {
    event.preventDefault();
    if (!memoryDraft.trim()) return;
    await api.createMemory(memoryDraft);
    setMemoryDraft("");
    await refreshMemories();
  }

  async function deleteMemory(id: number) {
    await api.deleteMemory(id);
    await refreshMemories();
  }

  async function uploadFile(fileList: FileList | null) {
    const file = fileList?.[0];
    if (!file) return;
    setError("");
    try {
      const indexed = await api.uploadFile(file);
      setActivities([{ tool: "index_file", status: "indexed", detail: `${indexed.filename} (${indexed.chunk_count} chunks)` }]);
      await refreshFiles();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    }
  }

  async function searchFiles(event: FormEvent) {
    event.preventDefault();
    if (!fileQuery.trim()) return;
    setFileHits(await api.searchFiles(fileQuery));
  }

  async function saveTask(event: FormEvent) {
    event.preventDefault();
    if (!taskTitle.trim()) return;
    await api.createTask(taskTitle, taskDetails, taskDueDate || undefined);
    setTaskTitle("");
    setTaskDetails("");
    setTaskDueDate("");
    await Promise.all([refreshTasks(), refreshToday()]);
  }

  async function setTaskDone(task: TaskItem) {
    await api.updateTask(task.id, { status: task.status === "done" ? "open" : "done" });
    await Promise.all([refreshTasks(), refreshToday()]);
  }

  async function deleteTask(item: TaskItem) {
    await api.deleteTask(item.id);
    await Promise.all([refreshTasks(), refreshToday()]);
  }

  async function saveReminder(event: FormEvent) {
    event.preventDefault();
    if (!reminderTitle.trim()) return;
    await api.createReminder(reminderTitle, reminderAt || undefined);
    setReminderTitle("");
    setReminderAt("");
    await Promise.all([refreshReminders(), refreshToday()]);
  }

  async function setReminderDone(reminder: ReminderItem) {
    await api.updateReminder(reminder.id, { status: reminder.status === "done" ? "open" : "done" });
    await Promise.all([refreshReminders(), refreshToday()]);
  }

  async function deleteReminder(item: ReminderItem) {
    await api.deleteReminder(item.id);
    await Promise.all([refreshReminders(), refreshToday()]);
  }
  async function saveNote(event: FormEvent) {
    event.preventDefault();
    if (!noteContent.trim()) return;
    await api.createNote(noteTitle || "Untitled note", noteContent);
    setNoteTitle("");
    setNoteContent("");
    await refreshNotes();
  }

  async function searchNotes(event: FormEvent) {
    event.preventDefault();
    setNotes(noteQuery.trim() ? await api.searchNotes(noteQuery) : await api.notes());
  }

  return (
    <main className="cosmos-app flex h-screen min-h-[640px] w-full overflow-hidden text-slate-100">
      <aside className="cyber-sidebar hidden w-72 shrink-0 p-5 md:block">
        <div className="mb-8">
          <div className="brand-wordmark text-xl font-semibold">Sidro</div>
          <div className="mt-1 text-xs text-slate-400">Local command center</div>
        </div>
        <nav className="space-y-1.5">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`cyber-nav-item ${activeTab === tab.id ? "is-active" : ""}`}
              >
                <Icon size={18} />
                {tab.label}
              </button>
            );
          })}
        </nav>
        <div className="cyber-status-chip mt-8">
          AI: {settings?.chat_provider || "auto"} / {settings?.api_key_configured ? "OpenAI key found" : "local fallback"}
        </div>
        <div className="conversation-library mt-5">
          <div className="conversation-library-header">
            <span>Recent chats</span>
            <button type="button" onClick={startNewChat} title="Start new chat">
              <MessageSquarePlus size={15} />
            </button>
          </div>
          <div className="conversation-search" role="search">
            <Search size={14} />
            <input
              value={conversationQuery}
              onChange={(event) => setConversationQuery(event.target.value)}
              placeholder="Search chats..."
              aria-label="Search recent chats"
            />
            {conversationQuery && (
              <button type="button" onClick={() => setConversationQuery("")} title="Clear chat search" aria-label="Clear chat search">
                <X size={13} />
              </button>
            )}
          </div>
          <div className="conversation-list">
            {isSearchingConversations && <div className="conversation-empty">Searching chats...</div>}
            {!isSearchingConversations && conversations.length === 0 && (
              <div className="conversation-empty">{conversationQuery ? "No matching chats found." : "No saved chats yet."}</div>
            )}
            {conversations.slice(0, 8).map((conversation) => (
              <div key={conversation.id} className={`conversation-row ${conversation.id === conversationId ? "is-current" : ""}`}>
                <button type="button" onClick={() => void openConversation(conversation.id)} title={conversation.title}>
                  <span>{conversation.title}</span>
                  <small>{conversation.message_count} messages</small>
                  {conversation.matched_snippet && <em>{conversation.matched_snippet}</em>}
                </button>
                <button type="button" onClick={() => void removeConversation(conversation.id)} title="Delete chat" aria-label="Delete chat">
                  <X size={13} />
                </button>
              </div>
            ))}
          </div>
        </div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b border-slate-800 bg-slate-950/70 p-2 md:hidden">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <IconButton key={tab.id} title={tab.label} onClick={() => setActiveTab(tab.id)} tone={activeTab === tab.id ? "primary" : "neutral"}>
                <Icon size={18} />
              </IconButton>
            );
          })}
        </div>

        {activeTab === "today" && (
          <Panel title="Today" subtitle="Your local command dashboard for tasks, reminders, notes, files, and memory.">
            <div className="dashboard-grid">
              <div className="metric-card"><span>Open tasks</span><strong>{today?.counts.tasks ?? tasks.filter((task) => task.status === "open").length}</strong></div>
              <div className="metric-card"><span>Reminders</span><strong>{today?.counts.reminders ?? reminders.filter((item) => item.status === "open").length}</strong></div>
              <div className="metric-card"><span>Notes</span><strong>{today?.counts.notes ?? notes.length}</strong></div>
              <div className="metric-card"><span>Files</span><strong>{today?.counts.files ?? files.length}</strong></div>
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <section className="cyber-surface p-4">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <h2 className="cyber-heading cyber-heading-small">Today tasks</h2>
                  <TextButton onClick={() => setActiveTab("tasks")}>Manage</TextButton>
                </div>
                <div className="space-y-2">
                  {(today?.open_tasks || tasks.filter((task) => task.status === "open")).slice(0, 6).map((task) => (
                    <div key={task.id} className="productivity-row">
                      <button type="button" onClick={() => void setTaskDone(task)} title="Mark task done"><CheckCircle2 size={17} /></button>
                      <div><strong>{task.title}</strong>{task.due_date && <small>Due {task.due_date}</small>}</div>
                    </div>
                  ))}
                  {(today?.open_tasks || tasks.filter((task) => task.status === "open")).length === 0 && <p className="text-sm text-slate-500">No open tasks yet.</p>}
                </div>
              </section>
              <section className="cyber-surface p-4">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <h2 className="cyber-heading cyber-heading-small">Sidro reminders</h2>
                  <Clock size={18} />
                </div>
                <div className="space-y-2">
                  {(today?.open_reminders || reminders.filter((item) => item.status === "open")).slice(0, 6).map((reminder) => (
                    <div key={reminder.id} className="productivity-row">
                      <button type="button" onClick={() => void setReminderDone(reminder)} title="Mark reminder done"><CheckCircle2 size={17} /></button>
                      <div><strong>{reminder.title}</strong>{reminder.remind_at && <small>{reminder.remind_at}</small>}</div>
                    </div>
                  ))}
                  {(today?.open_reminders || reminders.filter((item) => item.status === "open")).length === 0 && <p className="text-sm text-slate-500">No open reminders yet.</p>}
                </div>
              </section>
            </div>
          </Panel>
        )}

        {activeTab === "tasks" && (
          <Panel title="Tasks" subtitle="Create local tasks and internal Sidro reminders.">
            <div className="grid gap-4 lg:grid-cols-2">
              <form onSubmit={saveTask} className="cyber-surface space-y-3 p-4">
                <h2 className="cyber-heading cyber-heading-small">New task</h2>
                <input value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} placeholder="Task title" className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none" />
                <textarea value={taskDetails} onChange={(event) => setTaskDetails(event.target.value)} placeholder="Details" rows={3} className="w-full resize-none rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none" />
                <input type="date" value={taskDueDate} onChange={(event) => setTaskDueDate(event.target.value)} className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none" />
                <TextButton type="submit" disabled={!taskTitle.trim()}>Add task</TextButton>
              </form>
              <form onSubmit={saveReminder} className="cyber-surface space-y-3 p-4">
                <h2 className="cyber-heading cyber-heading-small">New reminder</h2>
                <input value={reminderTitle} onChange={(event) => setReminderTitle(event.target.value)} placeholder="Reminder title" className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none" />
                <input type="datetime-local" value={reminderAt} onChange={(event) => setReminderAt(event.target.value)} className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none" />
                <TextButton type="submit" disabled={!reminderTitle.trim()}>Add reminder</TextButton>
              </form>
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <section className="space-y-2">
                <h2 className="cyber-heading cyber-heading-small">Task list</h2>
                {tasks.map((task) => (
                  <div key={task.id} className={`productivity-item ${task.status === "done" ? "is-done" : ""}`}>
                    <button type="button" onClick={() => void setTaskDone(task)} title="Toggle task status"><CheckCircle2 size={18} /></button>
                    <div className="min-w-0 flex-1"><strong>{task.title}</strong>{task.details && <p>{task.details}</p>}{task.due_date && <small>Due {task.due_date}</small>}</div>
                    <IconButton title="Delete task" onClick={() => void deleteTask(task)} tone="danger"><Trash2 size={15} /></IconButton>
                  </div>
                ))}
                {tasks.length === 0 && <p className="text-sm text-slate-500">No tasks yet.</p>}
              </section>
              <section className="space-y-2">
                <h2 className="cyber-heading cyber-heading-small">Reminder list</h2>
                {reminders.map((reminder) => (
                  <div key={reminder.id} className={`productivity-item ${reminder.status === "done" ? "is-done" : ""}`}>
                    <button type="button" onClick={() => void setReminderDone(reminder)} title="Toggle reminder status"><Clock size={18} /></button>
                    <div className="min-w-0 flex-1"><strong>{reminder.title}</strong>{reminder.remind_at && <small>{reminder.remind_at}</small>}</div>
                    <IconButton title="Delete reminder" onClick={() => void deleteReminder(reminder)} tone="danger"><Trash2 size={15} /></IconButton>
                  </div>
                ))}
                {reminders.length === 0 && <p className="text-sm text-slate-500">No reminders yet.</p>}
              </section>
            </div>
          </Panel>
        )}
        {activeTab === "chat" && (
          <div className="flex min-h-0 flex-1 flex-col">
            <header className="cyber-header px-5 py-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h1 className="cyber-heading">Chat</h1>
                  <p className="text-xs text-slate-400">Ask, plan, search files, create notes, remember useful details.</p>
                </div>
                <div className="flex items-center gap-3 text-xs text-slate-300">
                  <button
                    type="button"
                    onClick={startNewChat}
                    className="cyber-text-button cyber-text-button-small inline-flex items-center gap-2"
                    title="Start a clean chat"
                  >
                    <MessageSquarePlus size={14} />
                    New chat
                  </button>
                  <button
                    type="button"
                    onClick={startBrainstormChat}
                    className="cyber-text-button cyber-text-button-small inline-flex items-center gap-2"
                    title="Start a fresh brainstorming chat"
                  >
                    <Lightbulb size={14} />
                    Brainstorm
                  </button>
                  <button
                    type="button"
                    onClick={clearChatView}
                    className="cyber-text-button cyber-text-button-small"
                  >
                    Clear
                  </button>
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={memoryEnabled} onChange={(event) => setMemoryEnabled(event.target.checked)} />
                    Memory
                  </label>
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={useFileContext} onChange={(event) => setUseFileContext(event.target.checked)} />
                    Files
                  </label>
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={voiceReplies} onChange={(event) => setVoiceReplies(event.target.checked)} />
                    Voice
                  </label>
                </div>
              </div>
            </header>

            <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
              <div className="flex min-h-0 flex-1 flex-col">
                <div ref={chatScrollRef} onScroll={updateScrollStickiness} className="cyber-chat-area chat-scroll min-h-0 flex-1 overflow-y-auto px-5 py-6">
                  <div className="mx-auto flex max-w-4xl flex-col gap-4">
                    {messages.length === 0 && (
                      <div className="cyber-surface p-4 text-sm text-slate-300">
                        Sidro is ready. Try "remember that I prefer concise plans", upload a text file, or ask for today's plan.
                      </div>
                    )}
                    {messages.map((message, index) => (
                      <div key={`${message.role}-${index}`} className={`flex gap-3 ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                        {message.role !== "user" && (
                          <div className="cyber-avatar cyber-avatar-bot">
                            <Bot size={18} />
                          </div>
                        )}
                        <div
                          className={`message-bubble ${message.role === "user" ? "message-user" : "message-assistant"}`}
                        >
                          <div>{message.content}</div>
                          {message.role === "assistant" && <ContextBadges message={message} />}
                        </div>
                        {message.role === "user" && (
                          <div className="cyber-avatar cyber-avatar-user">
                            <User size={18} />
                          </div>
                        )}
                      </div>
                    ))}
                    {isLoading && <div className="text-sm text-teal-200">Sidro is thinking...</div>}
                    <div ref={messagesEndRef} />
                  </div>
                </div>

                <form onSubmit={sendMessage} autoComplete="off" className="cyber-composer-shell px-5 py-4">
                  {error && <div className="mb-3 rounded-md border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-100">{error}</div>}
                  {voiceStatus !== "idle" && (
                    <div className="cyber-voice-status mx-auto mb-3 flex max-w-4xl items-center gap-3 px-3 py-2 text-sm text-teal-50">
                      <div className="flex h-5 items-center gap-1" aria-hidden="true">
                        {[0, 1, 2, 3].map((bar) => (
                          <span
                            key={bar}
                            className="h-2 w-1 rounded-full bg-teal-200 animate-pulse"
                            style={{ animationDelay: `${bar * 120}ms` }}
                          />
                        ))}
                      </div>
                      <span className="font-medium">{voiceStatus === "listening" ? "Listening..." : "Transcribing..."}</span>
                      {liveTranscript && <span className="min-w-0 flex-1 truncate text-teal-100/80">{liveTranscript}</span>}
                    </div>
                  )}
                  {contextPreview && <ContextPreviewPanel summary={contextPreview} />}
                  <div className="cyber-composer mx-auto flex max-w-4xl items-end gap-2 p-2">
                    <textarea
                      key={composerKey}
                      ref={promptRef}
                      value={input}
                      onChange={(event) => {
                        setInput(event.target.value);
                        setContextPreview(null);
                      }}
                      autoComplete="new-password"
                      autoCorrect="off"
                      autoCapitalize="sentences"
                      spellCheck={false}
                      name="sidro-message"
                      placeholder="Message Sidro..."
                      rows={2}
                      className="cyber-textarea min-h-[52px] flex-1 resize-none border-0 bg-transparent px-3 py-3 text-sm leading-6 outline-none"
                      onKeyDown={(event) => {
                        if (event.key === "Enter" && !event.shiftKey) {
                          event.preventDefault();
                          void sendMessage(event);
                        }
                      }}
                    />
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => void previewContext()}
                        disabled={!input.trim() || isPreviewingContext}
                        className="cyber-text-button context-preview-button inline-flex items-center gap-2"
                        title="Preview matching memory and file context"
                      >
                        <Search size={15} />
                        {isPreviewingContext ? "Checking" : "Context"}
                      </button>
                      <IconButton title={recording ? "Stop recording" : "Record voice"} onClick={toggleRecording} tone={recording ? "danger" : "neutral"}>
                        {recording ? <Pause size={18} /> : <Mic size={18} />}
                      </IconButton>
                      {isLoading ? (
                        <IconButton title="Stop response" onClick={stopCurrentRequest} tone="danger">
                          <X size={18} />
                        </IconButton>
                      ) : (
                        <IconButton title="Send" type="submit" tone="primary" disabled={!input.trim()}>
                          <Send size={18} />
                        </IconButton>
                      )}
                    </div>
                  </div>
                </form>
              </div>

              <aside className="cyber-side-panel max-h-64 p-5 lg:max-h-none lg:w-80">
                <h2 className="cyber-heading cyber-heading-small">Tool activity</h2>
                <div className="mt-3 space-y-2">
                  {activities.length === 0 && actions.length === 0 && <p className="text-sm text-slate-500">No tools used yet.</p>}
                  {activities.map((activity, index) => (
                    <div key={index} className="cyber-surface p-3 text-xs text-slate-300">
                      <div className="font-medium text-slate-100">{activity.tool}</div>
                      <div className="mt-1 text-slate-400">{activity.status}</div>
                    </div>
                  ))}
                  {actions.map((action, index) => (
                    <button
                      key={index}
                      onClick={() => window.open(action.url, "_blank", "noopener,noreferrer")}
                      className="cyber-action flex w-full items-center justify-between px-3 py-2 text-sm"
                    >
                      {action.label}
                      <Play size={16} />
                    </button>
                  ))}
                </div>
              </aside>
            </div>
          </div>
        )}

        {activeTab === "memory" && (
          <Panel title="Memory" subtitle="Saved long-term preferences and facts.">
            <form onSubmit={saveMemory} className="flex gap-2">
              <input
                value={memoryDraft}
                onChange={(event) => setMemoryDraft(event.target.value)}
                placeholder="Remember that..."
                className="flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-teal-400"
              />
              <IconButton title="Save memory" type="submit" tone="primary">
                <Plus size={18} />
              </IconButton>
            </form>
            <div className="space-y-2">
              {memories.map((item) => (
                <div key={item.id} className="flex items-start gap-3 rounded-md border border-slate-800 bg-slate-900/80 p-3">
                  <div className="flex-1 text-sm text-slate-100">{item.content}</div>
                  <IconButton title="Delete memory" onClick={() => void deleteMemory(item.id)} tone="danger">
                    <Trash2 size={16} />
                  </IconButton>
                </div>
              ))}
            </div>
          </Panel>
        )}

        {activeTab === "files" && (
          <Panel title="Files" subtitle="Upload text, Markdown, PDF, or Word files and search their indexed text.">
            <label className="flex cursor-pointer items-center justify-center gap-2 rounded-md border border-dashed border-slate-700 bg-slate-900/70 px-4 py-5 text-sm text-slate-300 hover:border-teal-400/70">
              <Upload size={18} />
              Upload file
              <input type="file" className="hidden" accept=".txt,.md,.pdf,.docx" onChange={(event) => void uploadFile(event.target.files)} />
            </label>
            <form onSubmit={searchFiles} className="flex gap-2">
              <input
                value={fileQuery}
                onChange={(event) => setFileQuery(event.target.value)}
                placeholder="Search indexed files..."
                className="flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-teal-400"
              />
              <IconButton title="Search files" type="submit" tone="primary">
                <Search size={18} />
              </IconButton>
            </form>
            <div className="grid gap-3 lg:grid-cols-2">
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-slate-200">Indexed</h3>
                {files.map((item) => (
                  <div key={item.id} className="rounded-md border border-slate-800 bg-slate-900/80 p-3 text-sm">
                    <div className="font-medium text-white">{item.filename}</div>
                    <div className="mt-1 text-xs text-slate-400">{item.chunk_count} chunks</div>
                  </div>
                ))}
              </div>
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-slate-200">Matches</h3>
                {fileHits.map((hit) => (
                  <div key={hit.chunk_id} className="rounded-md border border-slate-800 bg-slate-900/80 p-3 text-sm">
                    <div className="font-medium text-white">{hit.filename}</div>
                    <p className="mt-2 max-h-28 overflow-hidden text-slate-300">{hit.content}</p>
                  </div>
                ))}
              </div>
            </div>
          </Panel>
        )}

        {activeTab === "notes" && (
          <Panel title="Notes" subtitle="Create notes directly or from chat with 'create note'.">
            <form onSubmit={saveNote} className="space-y-2">
              <input
                value={noteTitle}
                onChange={(event) => setNoteTitle(event.target.value)}
                placeholder="Title"
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-teal-400"
              />
              <textarea
                value={noteContent}
                onChange={(event) => setNoteContent(event.target.value)}
                placeholder="Note content"
                rows={4}
                className="w-full resize-none rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-teal-400"
              />
              <TextButton type="submit" disabled={!noteContent.trim()}>
                Save note
              </TextButton>
            </form>
            <form onSubmit={searchNotes} className="flex gap-2">
              <input
                value={noteQuery}
                onChange={(event) => setNoteQuery(event.target.value)}
                placeholder="Search notes..."
                className="flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-teal-400"
              />
              <IconButton title="Search notes" type="submit" tone="primary">
                <Search size={18} />
              </IconButton>
            </form>
            <div className="grid gap-3 lg:grid-cols-2">
              {notes.map((note) => (
                <article key={note.id} className="rounded-md border border-slate-800 bg-slate-900/80 p-3">
                  <h3 className="text-sm font-semibold text-white">{note.title}</h3>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-300">{note.content}</p>
                </article>
              ))}
            </div>
          </Panel>
        )}

        {activeTab === "settings" && (
          <Panel title="Settings" subtitle="Local configuration read from the backend and session controls for the browser.">
            <div className="grid gap-4 lg:grid-cols-2">
              <SettingRow label="OpenAI API key" value={settings?.api_key_configured ? "Configured in .env" : "Missing in .env"} />
              <SettingRow label="Chat provider" value={settings?.chat_provider || ""} />
              <SettingRow label="Chat model" value={settings?.chat_model || ""} />
              <SettingRow label="Ollama URL" value={settings?.ollama_base_url || ""} />
              <SettingRow label="Ollama model" value={settings?.ollama_model || ""} />
              <SettingRow label="STT provider" value={settings?.stt_provider || ""} />
              <SettingRow label="Whisper model" value={`${settings?.faster_whisper_model || ""} / ${settings?.faster_whisper_device || ""}`} />
              <SettingRow label="TTS provider" value={settings?.tts_provider || ""} />
              <SettingRow label="Piper" value={settings?.piper_configured ? "Configured" : "Not configured"} />
              <SettingRow label="Transcription model" value={settings?.transcription_model || ""} />
              <SettingRow label="TTS model" value={settings?.tts_model || ""} />
              <label className="rounded-md border border-slate-800 bg-slate-900/80 p-3">
                <span className="text-xs uppercase text-slate-500">TTS voice</span>
                <select
                  value={ttsVoice}
                  onChange={(event) => setTtsVoice(event.target.value)}
                  className="mt-2 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                >
                  {(settings?.voices || ["alloy"]).map((voice) => (
                    <option key={voice} value={voice}>
                      {voice}
                    </option>
                  ))}
                </select>
              </label>
              <div className="cyber-surface p-3">
                <span className="text-xs uppercase text-slate-500">Browser session</span>
                <div className="mt-3 space-y-3 text-sm">
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={voiceReplies} onChange={(event) => setVoiceReplies(event.target.checked)} />
                    Voice replies
                  </label>
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={memoryEnabled} onChange={(event) => setMemoryEnabled(event.target.checked)} />
                    Memory enabled
                  </label>
                </div>
              </div>
            </div>
          </Panel>
        )}
      </section>
    </main>
  );
}

function ContextPreviewPanel({ summary }: { summary: ChatContextSummary }) {
  const hasContext = summary.memory_count > 0 || summary.file_count > 0;
  return (
    <div className="context-preview-panel mx-auto mb-3 max-w-4xl">
      <div className="context-preview-header">
        <span>Context preview</span>
        <span>{summary.memory_count} memory / {summary.file_count} file matches</span>
      </div>
      {!hasContext && <p className="context-preview-empty">No matching saved memory or indexed file context found.</p>}
      {summary.memories.length > 0 && (
        <div className="context-preview-group">
          <div className="context-preview-label">Memory</div>
          {summary.memories.slice(0, 3).map((item) => (
            <div key={item.id} className="context-preview-item">{item.content}</div>
          ))}
        </div>
      )}
      {summary.files.length > 0 && (
        <div className="context-preview-group">
          <div className="context-preview-label">Files</div>
          {summary.files.slice(0, 3).map((item) => (
            <div key={item.chunk_id} className="context-preview-item">
              <strong>[{item.citation}] {item.filename}</strong>
              <span>{item.snippet}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ContextBadges({ message }: { message: ChatMessage }) {
  const summary = message.metadata?.context_summary;
  const usedMemory = Boolean(message.metadata?.used_memory_context || (summary?.memory_count || 0) > 0);
  const usedFiles = Boolean(message.metadata?.used_file_context || (summary?.file_count || 0) > 0);
  if (!usedMemory && !usedFiles) return null;

  const fileNames = Array.from(new Set((summary?.files || []).map((item) => `[${item.citation}] ${item.filename}`))).slice(0, 2).join(", ");

  return (
    <div className="context-badges" aria-label="Context used by this reply">
      {usedMemory && (
        <span className="context-badge" title="Sidro used saved memories for this answer">
          <Brain size={13} />
          Memory{summary?.memory_count ? ` ${summary.memory_count}` : ""}
        </span>
      )}
      {usedFiles && (
        <span className="context-badge" title={fileNames ? `Sidro used file context from ${fileNames}` : "Sidro used indexed file context for this answer"}>
          <FileText size={13} />
          Files{summary?.file_count ? ` ${summary.file_count}` : ""}
        </span>
      )}
    </div>
  );
}

function Panel({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="cyber-page min-h-0 flex-1 overflow-y-auto p-4 md:p-6">
      <div className="mx-auto max-w-5xl space-y-5">
        <header>
          <h1 className="cyber-heading">{title}</h1>
          <p className="mt-1 text-sm text-slate-400">{subtitle}</p>
        </header>
        {children}
      </div>
    </div>
  );
}

function SettingRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="cyber-surface p-3">
      <div className="text-xs uppercase text-slate-500">{label}</div>
      <div className="mt-2 break-words text-sm text-slate-100">{value || "Not set"}</div>
    </div>
  );
}

export default App;



