# Live AI Assistant with Conversation Memory

This is a simple Flask-based API that exposes a live AI assistant powered by Google Gemini with per-session conversation memory.

## Features

- Flask REST API with JSON responses.
- Endpoints for chat, search-style queries, and clearing memory.
- In-memory conversation history per `session_id`.
- Uses Google Gemini 2.5 Flash via `google-generativeai`.
- CORS enabled for frontend integration.
- Environment-based configuration for the Gemini API key (using `python-dotenv`).

## Project Structure

- `app.py` – Main Flask application with all API endpoints.
- `index.html` – Frontend page to interact with the assistant.
- `requirements.txt` – Python dependencies.

## Prerequisites

- Python 3.10+ recommended.
- A Google Gemini API key stored in an environment variable `GEMINI_API_KEY`.

## Setup

1. Clone the repository and move into the project directory.
2. (Optional but recommended) Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux / macOS
   # or
   venv\Scriptsctivate      # Windows
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file in the project root and add your Gemini API key:
   ```env
   GEMINI_API_KEY=your_api_key_here
   ```

## Running the App

Start the Flask server:

```bash
python app.py
```

By default, it runs in debug mode on:

- URL: `http://localhost:5000`

## API Endpoints

### `GET /`

Health/status endpoint for the API that returns a JSON payload with status, model name, and available endpoints.

### `POST /chat`

Chat with memory for a given `session_id`.

**Request body:**

```json
{
  "message": "Your question here",
  "session_id": "optional-session-id"
}
```

- If `session_id` is omitted, it defaults to `"default"`.
- The server keeps conversation history in memory for each `session_id`.

**Response body (simplified):**

```json
{
  "success": true,
  "response": "Model reply here",
  "model": "gemini-2.5-flash",
  "memory_count": 4,
  "session_id": "your-session-id"
}
```

### `POST /search`

Search-style endpoint that uses the same model but with explicit date context, intended for queries that feel like “search”.

**Request body:**

```json
{
  "message": "Your search-like query",
  "session_id": "optional-session-id"
}
```

**Response body (simplified):**

```json
{
  "success": true,
  "response": "Model reply here",
  "model": "gemini-2.5-flash",
  "memory_count": 3,
  "session_id": "your-session-id",
  "note": "Web search not available - using AI knowledge with date context"
}
```

### `POST /clear`

Clear conversation memory for a `session_id`.

**Request body:**

```json
{
  "session_id": "your-session-id"
}
```

**Response body (simplified):**

```json
{
  "success": true,
  "message": "Cleared X messages from memory"
}
```

If the `session_id` has no memory, it returns `"No memory to clear"`.

## Frontend (index.html)

`index.html` can be served from any static server or opened directly in the browser, as long as it points to the Flask backend (`http://localhost:5000` by default). It is intended as a simple UI to send chat/search requests and view responses.

## Notes

- Conversation memory is stored in a Python dictionary in memory and resets when the server restarts.
- For production, consider:
  - Using a persistent store (Redis, database) for conversation history
  - Disabling `debug=True`
  - Securing your API key and backend endpoints
