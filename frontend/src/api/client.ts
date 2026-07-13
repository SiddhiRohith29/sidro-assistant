const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8022";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(options.headers || {})
    }
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      // Keep the HTTP status fallback.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export type ChatContextSummary = {
  memory_count: number;
  file_count: number;
  memories: Array<{ id: number; content: string; score?: number }>;
  files: Array<{ citation: string; file_id: number; filename: string; chunk_id: number; chunk_index: number; snippet: string }>;
};

export type ChatMessageMetadata = {
  used_file_context?: boolean;
  used_memory_context?: boolean;
  context_summary?: ChatContextSummary;
  tool_activities?: ToolActivity[];
  actions?: Array<{ type: "open_url"; url: string; label: string }>;
};

export type ChatMessage = {
  id?: number;
  role: "user" | "assistant" | "system";
  content: string;
  created_at?: string;
  metadata?: ChatMessageMetadata;
};

export type ToolActivity = {
  tool: string;
  status: string;
  detail?: unknown;
};

export type ChatResponse = {
  conversation_id: string;
  reply: string;
  language: string;
  tool_activities: ToolActivity[];
  actions: Array<{ type: "open_url"; url: string; label: string }>;
  used_file_context: boolean;
  used_memory_context: boolean;
  context_summary: ChatContextSummary;
};

export type Settings = {
  api_key_configured: boolean;
  chat_provider: string;
  chat_model: string;
  ollama_base_url: string;
  ollama_model: string;
  stt_provider: string;
  faster_whisper_model: string;
  faster_whisper_device: string;
  tts_provider: string;
  piper_configured: boolean;
  transcription_model: string;
  tts_model: string;
  tts_voice: string;
  voices: string[];
};

export type Conversation = { id: string; title: string; created_at: string; updated_at: string; message_count: number; matched_snippet?: string | null };
export type Memory = { id: number; content: string; source: string; created_at: string };
export type Note = { id: number; title: string; content: string; created_at: string; updated_at: string };
export type IndexedFile = {
  id: number;
  filename: string;
  size_bytes: number;
  created_at: string;
  chunk_count: number;
};
export type FileHit = {
  file_id: number;
  filename: string;
  chunk_id: number;
  chunk_index: number;
  content: string;
};

export const api = {
  settings: () => request<Settings>("/api/settings"),
  conversations: (query = "") => {
    const search = query.trim();
    const suffix = search ? `?query=${encodeURIComponent(search)}` : "";
    return request<Conversation[]>(`/api/conversations${suffix}`);
  },
  latestConversation: () => request<Record<string, string>>("/api/conversations/latest"),
  messages: (conversationId: string) =>
    request<{ conversation_id: string; messages: ChatMessage[] }>(`/api/conversations/${conversationId}/messages`),
  renameConversation: (conversationId: string, title: string) =>
    request<Conversation>(`/api/conversations/${conversationId}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  deleteConversation: (conversationId: string) =>
    request<{ deleted: boolean }>(`/api/conversations/${conversationId}`, { method: "DELETE" }),
  chat: (body: { message: string; conversation_id?: string; use_file_context: boolean; memory_enabled: boolean }, signal?: AbortSignal) =>
    request<ChatResponse>("/api/chat", { method: "POST", body: JSON.stringify(body), signal }),
  contextPreview: (body: { query: string; use_file_context: boolean; memory_enabled: boolean }) =>
    request<ChatContextSummary>("/api/context/preview", { method: "POST", body: JSON.stringify(body) }),
  transcribe: (audio: Blob, filename = "recording.webm") => {
    const form = new FormData();
    form.append("audio", audio, filename);
    return request<{ text: string; language: string; provider: string }>("/api/transcribe", { method: "POST", body: form });
  },
  speak: async (text: string, voice: string, language?: string) => {
    const response = await fetch(`${API_BASE}/api/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voice, language })
    });
    if (!response.ok) throw new Error((await response.json()).detail || "Speech failed.");
    return response.blob();
  },
  memories: () => request<Memory[]>("/api/memories"),
  createMemory: (content: string) => request<Memory>("/api/memories", { method: "POST", body: JSON.stringify({ content }) }),
  deleteMemory: (id: number) => request<{ deleted: boolean }>(`/api/memories/${id}`, { method: "DELETE" }),
  notes: () => request<Note[]>("/api/notes"),
  createNote: (title: string, content: string) => request<Note>("/api/notes", { method: "POST", body: JSON.stringify({ title, content }) }),
  searchNotes: (query: string) => request<Note[]>("/api/notes/search", { method: "POST", body: JSON.stringify({ query }) }),
  files: () => request<IndexedFile[]>("/api/files"),
  uploadFile: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<IndexedFile>("/api/files/upload", { method: "POST", body: form });
  },
  searchFiles: (query: string) => request<FileHit[]>("/api/files/search", { method: "POST", body: JSON.stringify({ query }) })
};
