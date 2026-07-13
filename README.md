# Sidro Assistant

Sidro is a local-first personal AI assistant for Siddharth. It runs on a Windows machine, opens in a browser, stores data locally in SQLite, and can use Ollama for local chat so the app does not depend on OpenAI quota for normal use.

Current status: Sidro v1 roadmap Phases 1 through 8 are 100% complete for the current local scope. The active app uses a FastAPI backend, a React/Vite frontend, SQLite storage, Ollama chat fallback, local faster-whisper speech-to-text, memory, notes, file upload/search, browser TTS fallback, and a polished light neon coral UI with responsive navigation, keyboard shortcuts, and accessibility support.

## Phase Status

| Phase | Status | Notes |
|---|---:|---|
| Phase 1: Local MVP | 100% complete | Local frontend/backend, chat, Ollama fallback, memory, notes, file upload/search, English voice input, voice reply fallback, cyberpunk UI, GitHub workflow, and v1 verification are implemented. |
| Phase 2: Assistant Quality | 100% complete | Stronger response rules, capability boundaries, counted-list/planning/summary guidance, better file-context behavior, and no-overpromise safeguards are implemented. |
| Phase 3: Voice Experience | 100% complete | English voice input, browser live transcript preview where available, listening/transcribing states, push-to-talk flow, short-recording guard, and browser TTS fallback are implemented. |
| Phase 4: Personal Productivity Core | 100% complete | Local tasks, internal Sidro reminders, Today dashboard, activity history foundation, notes-to-task chat commands, and task/reminder APIs are implemented. |
| Phase 5: Files And Knowledge Base | 100% complete | PDF/DOCX/text upload and search, file context, source citations, context preview, document summary command, and chat search/resume are implemented. |
| Phase 6: Local Tools And Actions | 100% complete | Safe website-open actions, local note/task/reminder creation, confirmed local file creation, tool logs, and verification coverage are implemented. |
| Phase 7: Long-Term Memory | 100% complete | Memory review/edit UI, categories, privacy marking, pinned memories, duplicate merge flow, similar-memory lookup, approval-based memory suggestions, and verification coverage are implemented. |

| Phase 8: UI/UX Polish | 100% complete | Responsive mobile navigation, labeled mobile tabs, skip link, screen-reader live status, keyboard shortcuts, improved loading states, settings polish, reduced-motion support, and verification coverage are implemented. |
Next roadmap target: Phase 9 Reliability And Testing.

## Tech Stack

- Frontend: React, Vite, TypeScript, Tailwind CSS, Lucide icons
- Backend: Python, FastAPI, SQLite
- Local LLM: Ollama with `qwen2.5:7b`
- Speech-to-text: faster-whisper, currently English-focused
- Optional cloud AI: OpenAI API if `OPENAI_API_KEY` is configured
- Local ports:
  - Frontend: `http://127.0.0.1:5180`
  - Backend: `http://127.0.0.1:8022`
  - Ollama: `http://127.0.0.1:11434`

## Folder Structure

```text
sidro-run/
  backend/
    app/
      ai.py
      config.py
      db.py
      files.py
      language.py
      main.py
      memory.py
      notes.py
      tools.py
      voice.py
    requirements.txt
  frontend/
    src/
      api/client.ts
      App.tsx
      index.css
      main.tsx
    package.json
  scripts/
    run-backend.ps1
    run-frontend.ps1
    start-ollama.ps1
    ollama.ps1
  data/
    uploads/.gitkeep
    audio/.gitkeep
  .env.example
  .gitignore
  README.md
```

`frontend-dev/` was used as a temporary development copy during early fixes. The GitHub-ready active frontend is `frontend/`.

## Setup

### 1. Copy environment file

Create `.env` from `.env.example`:

```powershell
cd "C:\Users\siddh\Documents\ai assistant\sidro-run"
copy .env.example .env
```

For local/free mode, keep:

```text
SIDRO_CHAT_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5:7b
SIDRO_STT_PROVIDER=faster_whisper
SIDRO_ALLOWED_ORIGIN=http://127.0.0.1:5180
```

`OPENAI_API_KEY` is optional. Do not commit `.env`.

### 2. Backend install

```powershell
cd "C:\Users\siddh\Documents\ai assistant\sidro-run\backend"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Frontend install

```powershell
cd "C:\Users\siddh\Documents\ai assistant\sidro-run\frontend"
npm install
```

### 4. Ollama model

Make sure Ollama is installed/running and the model exists:

```powershell
ollama pull qwen2.5:7b
```

If using the portable local Ollama setup, start it with:

```powershell
cd "C:\Users\siddh\Documents\ai assistant\sidro-run"
.\scripts\start-ollama.ps1
```

## Run Sidro

Open three PowerShell windows.

### Window 1: Ollama

```powershell
cd "C:\Users\siddh\Documents\ai assistant\sidro-run"
.\scripts\start-ollama.ps1
```

### Window 2: Backend

```powershell
cd "C:\Users\siddh\Documents\ai assistant\sidro-run"
.\scripts\run-backend.ps1
```

### Window 3: Frontend

```powershell
cd "C:\Users\siddh\Documents\ai assistant\sidro-run"
.\scripts\run-frontend.ps1
```

Then open:

```text
http://127.0.0.1:5180
```

## Verify V1

With the backend running, run the acceptance script:

```powershell
cd "C:\Users\siddh\Documents\ai assistant\sidro-run"
.\scripts\verify-v1.ps1
```

The script checks Phase 1 through Phase 8 acceptance items:

- Backend health and settings
- Phase 8 roadmap health/settings marker
- Local chat memory tool
- Phase 2 capability-boundary behavior
- Phase 3 memory duplicate handling and context preview
- Note creation and note search
- Text file upload and indexed file search
- Voice short-recording error handling
- TTS backend or frontend fallback path
- Keyboard shortcut and accessibility settings

It uses small safe test records in the local SQLite database and does not require OpenAI quota.

## UI Guide: What Every Tab and Button Does

### Sidebar

- `Sidro`: App name and local command center identity.
- `Today`: Opens the productivity dashboard with open tasks, reminders, and local data counts.
- `Chat`: Opens the main assistant conversation screen.
- `Tasks`: Opens local tasks and internal Sidro reminders.
- `Memory`: Opens the long-term memory control center for saved memories, categories, privacy, pins, suggestions, similar-memory checks, and merge review.
- `Files`: Opens document upload and search.
- `Notes`: Opens local note creation and note search.
- `Settings`: Opens session/configuration information.
- `AI: ollama / local fallback`: Shows the active AI route. In local mode, Sidro uses Ollama instead of OpenAI quota.
- Recent chats: Shows recent saved conversations.
- Search chats...: Filters recent chats by title or message text.
- `New chat` icon in Recent chats: Starts a clean chat session.
- `Recent chat row`: Opens that saved conversation.
- `Delete chat` icon: Removes that saved conversation and its messages.

### Chat Tab

The Chat tab is the main assistant console.

- `Message area`: Shows your messages on the right and Sidro's replies on the left.
- `User bubble`: Shows what you sent.
- `Assistant bubble`: Shows Sidro's response.
- `Memory` badge on a reply: Means Sidro used saved memories while answering.
- `Files` badge on a reply: Means Sidro used indexed uploaded file context while answering.
- `Sources` section in a reply: Lists file chunks Sidro used, with labels like `[F1]`.
- `Sidro is thinking...`: Appears while the backend is generating a response.
- `Tool activity` panel: Shows internal actions such as transcription, file search, note creation, or other safe local tools.
- `No tools used yet`: Means the current chat has not triggered a tool call.

Header controls:

- `New chat`: Starts a clean chat session while leaving memories, files, and notes intact.
- `Clear`: Clears the visible chat screen and resets the current conversation view. It does not delete the app code or your uploaded files.
- `Memory` checkbox: When enabled, Sidro can use saved memories while answering.
- `Files` checkbox: When enabled, Sidro can include indexed file context in answers.
- `Voice` checkbox: When enabled, Sidro can attempt voice replies through the configured TTS provider.

Composer controls:

- `Message Sidro...` text box: Type your prompt here.
- `Enter`: Sends the message.
- `Shift + Enter`: Adds a new line inside the prompt box.
- `Microphone` button: Starts voice recording. Speak into the mic; Sidro transcribes the audio into the prompt box.
- `Pause/Stop recording` button: Stops the current voice recording and sends the audio for transcription.
- `Context` button: Previews matching saved memories and indexed file snippets before sending.
- `Send` button: Sends the current text in the prompt box.
- `Stop response` button: Appears while Sidro is responding. It cancels the current response request.
- `Listening...` animation: Appears when the microphone is active.
- `Transcribing...` animation: Appears while recorded audio is being converted into text.

### Memory Tab

The Memory tab stores durable facts and preferences that Sidro can reuse.

- `Remember that...` input: Type a fact or preference to save.
- `Save memory` button: Stores the typed memory in SQLite.
- `Saved memory cards`: Show each saved memory.
- `Delete memory` button: Removes that memory from SQLite.

Example memories:

```text
I prefer concise plans.
I am building Sidro as a local personal assistant.
Use simple Windows commands when explaining setup.
```

### Files Tab

The Files tab lets Sidro index and search local documents.

- `Upload file`: Opens a file picker. Supports text/Markdown and, where libraries are available, PDF/DOCX extraction.
- `Search indexed files...` input: Type a search query for uploaded documents.
- `Search files` button: Searches indexed chunks in SQLite.
- `Indexed` column: Shows uploaded files and chunk counts.
- `Matches` column: Shows matching file chunks for your query.
- `Files` checkbox in Chat: Lets Sidro include this indexed file context when answering.

### Notes Tab

The Notes tab stores quick local notes.

- `Title` input: Optional note title.
- `Note content` box: Main note body.
- `Save note` button: Saves the note to SQLite.
- `Search notes...` input: Type a query to search saved notes.
- `Search notes` button: Filters notes by search text.
- `Note cards`: Show saved notes with title and content.

### Settings Tab

The Settings tab shows the current backend/session configuration.

- `OpenAI API key`: Shows whether `.env` has an OpenAI key configured. It does not display the secret.
- `Chat provider`: Shows the current chat provider, such as `ollama` or `auto`.
- `Chat model`: Shows the configured OpenAI chat model if OpenAI is used.
- `Ollama URL`: Shows where the backend sends local Ollama requests.
- `Ollama model`: Shows the active local model, currently `qwen2.5:7b`.
- `STT provider`: Shows speech-to-text provider, currently local faster-whisper.
- `Whisper model`: Shows the local transcription model and device.
- `TTS provider`: Shows text-to-speech provider selection.
- `Piper`: Shows whether Piper local TTS is configured.
- `Transcription model`: Shows the OpenAI transcription model name if OpenAI transcription is used.
- `TTS model`: Shows the OpenAI TTS model name if OpenAI TTS is used.
- `TTS voice` dropdown: Chooses the OpenAI voice name when cloud TTS is used.
- `Voice replies` checkbox: Turns voice replies on/off for the browser session.
- `Memory enabled` checkbox: Turns memory usage on/off for the browser session.

## Backend API Summary

- `GET /api/settings`: Reads safe config details for the Settings tab.
- `GET /api/today`: Reads the Today dashboard summary.
- `GET/POST/PATCH/DELETE /api/tasks`: Manage local Sidro tasks.
- `GET/POST/PATCH/DELETE /api/reminders`: Manage internal Sidro reminders.
- `POST /api/chat`: Sends a user message, optional memory context, optional file context, and returns Sidro's response with context metadata.
- `POST /api/context/preview`: Shows which memories/files match a question without generating a full assistant reply. File matches include source labels such as `[F1]`.
- `GET /api/conversations`: Lists recent saved conversations. Add `?query=...` to search saved chat titles and messages.
- `GET /api/conversations/{conversation_id}/messages`: Loads a saved conversation and its messages.
- `PATCH /api/conversations/{conversation_id}`: Renames a saved conversation.
- `DELETE /api/conversations/{conversation_id}`: Deletes a saved conversation and its messages.
- `POST /api/transcribe`: Receives microphone audio and returns transcript text.
- `POST /api/speak`: Converts text to audio when a TTS provider is configured.
- `GET/POST/DELETE /api/memories`: Manage saved memories.
- `PATCH /api/memories/{memory_id}`: Edit memory content, category, privacy, and pin status.
- `POST /api/memories/merge`: Merge duplicate memories into one reviewed memory.
- `POST /api/memories/similar`: Find similar memories before saving or merging.
- `GET/POST /api/memory-suggestions`: Review pending memory suggestions.
- `POST /api/memory-suggestions/{suggestion_id}/accept`: Save a suggestion as an approved memory.
- `POST /api/memory-suggestions/{suggestion_id}/dismiss`: Dismiss a suggestion without saving it.
- `GET/POST /api/files`: Upload and list indexed files.
- `POST /api/files/search`: Search indexed file chunks.
- `GET/POST /api/notes`: List and create notes.
- `POST /api/notes/search`: Search notes.
- `POST /api/local-actions/create-file`: Creates a local generated file only after confirmation.
- Tool actions are logged into `tool_logs` where supported.

## V1 Acceptance Checklist

- Done: Backend and frontend run locally on Windows.
- Done: Chat works through Ollama/local fallback without OpenAI quota.
- Done: Sidro uses a stronger response-quality prompt and larger local answer budget.
- Done: Prompt box clears after send and does not bring back stale text.
- Done: English voice input records, previews live transcript where the browser supports it, and sends audio to faster-whisper.
- Done: Voice input has a short-recording guard with a helpful error.
- Done: Voice replies use backend TTS when configured and browser speech fallback when backend TTS is unavailable.
- Done: Memories can be created, listed, deleted, and used in chat.
- Done: Notes can be created and searched.
- Done: Text, Markdown, PDF, and DOCX uploads are supported when extraction libraries can read the file.
- Done: Indexed file search returns matching chunks and can be used by chat when Files is enabled.
- Done: Assistant replies show Memory/Files badges when those context sources are used.
- Done: Phase 3 context preview shows matching memory/file context without requiring a full AI answer.
- Done: Phase 4 source labels and automatic file source lists make document answers easier to verify.
- Done: Chat composer has a Context preview button for checking memory/file matches before sending.
- Done: Phase 5 conversation library supports New Chat, recent chat resume, rename API, and delete.
- Done: Phase 6 conversation search filters saved chats and shows matched snippets.
- Done: Phase 6 answer guidance improves summaries, comparisons, document extraction, planning, and counted lists.
- Done: Settings explains the active provider/model/voice configuration without exposing secrets.
- Done: `.env`, local SQLite data, audio recordings, model files, logs, `node_modules`, and build output are ignored by Git.
- Done: `scripts/verify-v1.ps1` provides repeatable v1 verification.


### Keyboard Shortcuts

- `Ctrl+K`: Focuses the chat composer.
- `Ctrl+N`: Starts a new chat.
- `Ctrl+B`: Starts a brainstorming chat.
- `Escape`: Stops the current response or closes the active draft/context state.

### Accessibility And Responsive Polish

- Skip link: Keyboard users can jump past navigation directly into the main content.
- Live status: Assistive technology gets quiet updates for loading, listening, thinking, and stopped states.
- Reduced motion: The UI respects system reduced-motion preferences.
- Mobile layout: Navigation compresses into labeled icon tabs and the chat composer keeps usable spacing on small screens.

## Current Known Limitations

- Telugu/bilingual mode was removed to keep v1 stable and English-focused.
- Voice input currently targets English transcription.
- Local LLM quality depends on the installed Ollama model and available RAM/CPU/GPU.
- Browser TTS fallback depends on browser speech support and installed system voices.
- Piper TTS is supported by configuration, but a Piper executable/model is not bundled in Git.
- `frontend-dev/` is ignored and should not be used for future source changes.

## GitHub Daily Update Workflow

After the remote repository is created and connected, daily updates can be pushed with the helper script:

```powershell
cd "C:\Users\siddh\Documents\ai assistant\sidro-run"
.\scripts\daily-github-update.ps1 -Message "Improve Sidro voice input and cyberpunk UI"
```

The script checks for local changes, stages them, creates a commit, and pushes to GitHub. If there are no changes, it exits without creating an empty commit.

Manual daily update commands still work too:

```powershell
cd "C:\Users\siddh\Documents\ai assistant\sidro-run"
git status
git add .
git commit -m "Update Sidro daily progress"
git push
```

## GitHub Remote Setup

Recommended repository name:

```text
sidro-assistant
```

Once the empty GitHub repository exists, connect it like this:

```powershell
cd "C:\Users\siddh\Documents\ai assistant\sidro-run"
git remote add origin https://github.com/SiddhiRohith29/sidro-assistant.git
git branch -M main
git push -u origin main
```

Do not commit `.env`, `data/sidro.sqlite`, `node_modules`, local model files, or logs. The `.gitignore` is set up to keep those out.

