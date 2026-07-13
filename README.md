# Sidro Assistant

Sidro is a local-first personal AI assistant for Siddharth. It runs on a Windows machine, opens in a browser, stores data locally in SQLite, and can use Ollama for local chat so the app does not depend on OpenAI quota for normal use.

Current status: Sidro v1 local MVP is mostly built and is in refinement/testing. The active app uses a FastAPI backend, a React/Vite frontend, SQLite storage, Ollama chat fallback, local faster-whisper speech-to-text, memory, notes, file upload/search, and a cyberpunk/cosmos UI theme.

## Tech Stack

- Frontend: React, Vite, TypeScript, Tailwind CSS, Lucide icons
- Backend: Python, FastAPI, SQLite
- Local LLM: Ollama with `qwen2.5:7b`
- Speech-to-text: faster-whisper, currently English-focused
- Optional cloud AI: OpenAI API if `OPENAI_API_KEY` is configured
- Local ports:
  - Frontend: `http://127.0.0.1:5180`
  - Backend: `http://127.0.0.1:8020`
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

## UI Guide: What Every Tab and Button Does

### Sidebar

- `Sidro`: App name and local command center identity.
- `Chat`: Opens the main assistant conversation screen. This is the default first screen.
- `Memory`: Opens saved long-term memories and preferences.
- `Files`: Opens document upload and search.
- `Notes`: Opens local note creation and note search.
- `Settings`: Opens session/configuration information.
- `AI: ollama / local fallback`: Shows the active AI route. In local mode, Sidro uses Ollama instead of OpenAI quota.

### Chat Tab

The Chat tab is the main assistant console.

- `Message area`: Shows your messages on the right and Sidro's replies on the left.
- `User bubble`: Shows what you sent.
- `Assistant bubble`: Shows Sidro's response.
- `Sidro is thinking...`: Appears while the backend is generating a response.
- `Tool activity` panel: Shows internal actions such as transcription, file search, note creation, or other safe local tools.
- `No tools used yet`: Means the current chat has not triggered a tool call.

Header controls:

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
- `POST /api/chat`: Sends a user message, optional memory context, optional file context, and returns Sidro's response.
- `POST /api/transcribe`: Receives microphone audio and returns transcript text.
- `POST /api/speak`: Converts text to audio when a TTS provider is configured.
- `GET/POST/DELETE /api/memories`: Manage saved memories.
- `GET/POST /api/files`: Upload and list indexed files.
- `POST /api/files/search`: Search indexed file chunks.
- `GET/POST /api/notes`: List and create notes.
- `POST /api/notes/search`: Search notes.
- Tool actions are logged into `tool_logs` where supported.

## Current Known Limitations

- Telugu/bilingual mode was removed to keep v1 stable and English-focused.
- Voice input currently targets English transcription.
- Local LLM quality depends on the installed Ollama model and available RAM/CPU/GPU.
- Voice replies need a configured TTS provider. OpenAI TTS needs an API key; Piper needs local model paths.
- `frontend-dev/` is ignored and should not be used for future source changes.

## GitHub Daily Update Workflow

After the remote repository is created and connected, daily updates should follow this pattern:

```powershell
cd "C:\Users\siddh\Documents\ai assistant\sidro-run"
git status
git add .
git commit -m "Update Sidro daily progress"
git push
```

A good daily commit message is specific:

```powershell
git commit -m "Improve Sidro voice input and cyberpunk UI"
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
