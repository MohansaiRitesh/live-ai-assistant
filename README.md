# Live AI Assistant

A Flask-powered AI assistant backend with Google Gemini, web search support, file uploads, and persistent conversation history via SQLite.

## What this project does

- Provides a JSON REST API for chat, search, file upload, and history management.
- Stores conversation sessions in `database.db` using SQLite.
- Supports processing of uploaded PDF, DOCX, TXT, and image files.
- Optionally enriches answers with Google search results via SerpApi.
- Includes a simple frontend in `index.html`.

## Project Structure

- `app.py` — Flask application and API endpoints.
- `database.py` — SQLite session/message persistence.
- `index.html` — Frontend chat UI.
- `requirements.txt` — Python dependencies.
- `uploads/` — Temporary upload folder for processing files.

## Requirements

- Python 3.10+
- A Google Gemini API key stored in `GEMINI_API_KEY`
- Optional: a SerpApi key stored in `SERPAPI_KEY` for live search results

## Setup

1. Create and activate a virtual environment:

```bash
python -m venv venv
venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key
SERPAPI_KEY=your_serpapi_api_key
```

4. Run the app:

```bash
python app.py
```

The server starts on `http://localhost:5000` by default.

## API Endpoints

### `GET /`

Returns API metadata and available endpoints.

### `POST /chat`

Send a chat message and maintain session memory.

Request body:

```json
{
  "message": "Hello",
  "session_id": "optional-session-id"
}
```

Response sample:

```json
{
  "success": true,
  "response": "AI reply...",
  "memory_count": 4,
  "session_id": "optional-session-id",
  "search_used": false
}
```

### `POST /search`

Send a search-style query. If `SERPAPI_KEY` is configured, it will try to include web search results.

Request body:

```json
{
  "message": "What is the latest on AI?",
  "session_id": "optional-session-id"
}
```

Response sample:

```json
{
  "success": true,
  "response": "AI reply...",
  "memory_count": 5,
  "session_id": "optional-session-id",
  "search_used": true,
  "sources": ["https://example.com"]
}
```

### `POST /upload`

Upload a supported file and ask a question about it.

Form fields:
- `file` — the uploaded file
- `message` — question or prompt
- `session_id` — optional session identifier

Supported file types:
- `pdf`
- `docx`
- `txt`
- `png`, `jpg`, `jpeg`, `gif`, `webp`

Response sample:

```json
{
  "success": true,
  "response": "AI analysis...",
  "file_name": "document.pdf",
  "file_type": "PDF Document",
  "memory_count": 3,
  "session_id": "optional-session-id"
}
```

### `GET /history`

Returns all sessions with metadata and message counts.

### `GET /history/<session_id>`

Returns message history for a specific session.

### `DELETE /history/<session_id>`

Deletes a conversation session and its messages.

### `GET /history/search?q=term`

Searches stored conversation messages for `term`.

### `POST /clear`

Clears a session by deleting it from the database.

Request body:

```json
{
  "session_id": "optional-session-id"
}
```

## Notes

- Conversation history is persisted in `database.db`.
- Uploaded files are temporarily stored in `uploads/` and removed after processing.
- For production use, disable Flask debug mode and secure your API keys.
- If `SERPAPI_KEY` is not present, `/search` still works but without live web search results.
