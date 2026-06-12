# ============================================
# APP.PY - Live AI Assistant (with Database)
# ============================================
# Changes from previous version:
#   - Removed in-memory conversation_memory dict
#   - All messages now saved to database.db
#   - History loaded from database on each request
#   - New /history endpoints for dashboard (Phase 3)
# ============================================


# ─────────────────────────────────────────────
# SECTION 1: Imports
# ─────────────────────────────────────────────

from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import os
from dotenv import load_dotenv
from datetime import datetime
import secrets
from serpapi import GoogleSearch

# File handling
import PyPDF2
from PIL import Image
import docx
import io

# ★ NEW: Import all our database functions
# 'from database import ...' means:
#   go into database.py and bring these functions here
from database import (
    init_db,                # Initialize tables on startup
    create_session,         # Create new conversation record
    update_session_time,    # Update 'last active' time
    save_message,           # Save one message to DB
    get_session_messages,   # Load all messages for a session
    get_all_sessions,       # Get all conversations (for dashboard)
    delete_session,         # Delete a conversation
    search_messages,        # Search through messages
    get_message_count       # Count messages in a session
)


# ─────────────────────────────────────────────
# SECTION 2: Load Environment Variables
# ─────────────────────────────────────────────

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SERPAPI_KEY    = os.getenv("SERPAPI_KEY")

if not GEMINI_API_KEY:
    print("❌ ERROR: Gemini API key not found!")
    exit()


# ─────────────────────────────────────────────
# SECTION 3: Configure Gemini
# ─────────────────────────────────────────────

genai.configure(api_key=GEMINI_API_KEY)
model        = genai.GenerativeModel('models/gemini-2.5-flash')
vision_model = genai.GenerativeModel('models/gemini-2.5-flash')

print("✅ Gemini configured!")


# ─────────────────────────────────────────────
# SECTION 4: Flask App Setup
# ─────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
CORS(app, supports_credentials=True)

# Upload folder setup
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'docx', 'txt'}
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024


# ─────────────────────────────────────────────
# SECTION 5: Initialize Database on Startup
# ─────────────────────────────────────────────

# ★ NEW: This runs ONCE when server starts
# Creates the tables if they don't exist yet
# If tables already exist, it skips silently
init_db()


# ─────────────────────────────────────────────
# SECTION 6: Helper Functions (unchanged)
# ─────────────────────────────────────────────

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_extension(filename):
    return filename.rsplit('.', 1)[1].lower()

def extract_text_from_pdf(file_path):
    print(f"📄 Reading PDF: {file_path}")
    text = ""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num in range(len(pdf_reader.pages)):
                page_text = pdf_reader.pages[page_num].extract_text()
                if page_text:
                    text += f"\n--- Page {page_num + 1} ---\n"
                    text += page_text
        return text
    except Exception as e:
        print(f"❌ PDF error: {e}")
        return None

def extract_text_from_docx(file_path):
    try:
        doc = docx.Document(file_path)
        full_text = [p.text for p in doc.paragraphs if p.text.strip()]
        return '\n'.join(full_text)
    except Exception as e:
        print(f"❌ Docx error: {e}")
        return None

def extract_text_from_txt(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print(f"❌ Txt error: {e}")
        return None

def analyze_image_with_gemini(file_path, user_question):
    try:
        image = Image.open(file_path)
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        prompt = f"Analyze this image. User question: {user_question}"
        response = vision_model.generate_content([
            prompt,
            {"mime_type": "image/png", "data": img_byte_arr}
        ])
        return response.text
    except Exception as e:
        print(f"❌ Image error: {e}")
        return None

def search_web(query, num_results=5):
    if not SERPAPI_KEY:
        return None, []
    try:
        params = {
            "q": query,
            "api_key": SERPAPI_KEY,
            "num": num_results,
            "engine": "google"
        }
        search    = GoogleSearch(params)
        results   = search.get_dict()
        organic   = results.get("organic_results", [])
        if not organic:
            return None, []
        search_text = ""
        urls = []
        for i, result in enumerate(organic[:num_results], 1):
            search_text += f"Result {i}:\nTitle: {result.get('title','')}\n"
            search_text += f"Description: {result.get('snippet','')}\n"
            search_text += f"URL: {result.get('link','')}\n\n"
            urls.append(result.get('link', ''))
        return search_text, urls
    except Exception as e:
        print(f"❌ Search error: {e}")
        return None, []


# ─────────────────────────────────────────────
# SECTION 7: Build Conversation Context
# ─────────────────────────────────────────────

def build_context(session_id):
    """
    ★ NEW FUNCTION: Load conversation history from DATABASE
    and format it as a string for Gemini.

    Before: we read from conversation_memory dict (RAM)
    Now:    we read from database.db (disk)

    The format is the same Gemini expects:
        "User: Hello\nAssistant: Hi!\nUser: ..."

    Args:
        session_id (str): Which conversation to load

    Returns:
        str: Formatted conversation history
    """
    # Load messages from database
    messages = get_session_messages(session_id)

    # Format as conversation string
    context = ""
    for msg in messages:
        role = "User" if msg['role'] == 'user' else "Assistant"
        context += f"{role}: {msg['content']}\n"

    return context


# ─────────────────────────────────────────────
# SECTION 8: Chat Endpoint
# ─────────────────────────────────────────────

@app.route('/chat', methods=['POST'])
def chat():
    """
    Regular chat endpoint - now saves to database.

    Changes from before:
      - No more conversation_memory dict
      - create_session() called for new conversations
      - save_message() called for every message
      - build_context() loads history from database
      - update_session_time() called after each exchange
    """
    try:
        data       = request.get_json()
        user_msg   = data.get('message')
        session_id = data.get('session_id', 'default')

        if not user_msg:
            return jsonify({"error": "No message provided"}), 400

        print(f"💬 Chat [{session_id[:15]}...]: {user_msg[:50]}")

        # ★ NEW: Create session if this is the first message
        # create_session() handles duplicates gracefully (try/except inside)
        create_session(session_id, user_msg)

        # ★ NEW: Save user message to database
        save_message(session_id, 'user', user_msg)

        # ★ NEW: Load full history from database
        context = build_context(session_id)

        # Build prompt with history
        prompt = f"""You are a helpful AI assistant.

Conversation history:
{context}

Current date: {datetime.now().strftime('%B %d, %Y')}

Respond naturally to the user's latest message."""

        # Send to Gemini
        response      = model.generate_content(prompt)
        ai_response   = response.text

        # ★ NEW: Save AI response to database
        save_message(session_id, 'assistant', ai_response)

        # ★ NEW: Update session's last-active timestamp
        update_session_time(session_id)

        msg_count = get_message_count(session_id)
        print(f"✅ Response saved (total messages: {msg_count})")

        return jsonify({
            "success"      : True,
            "response"     : ai_response,
            "memory_count" : msg_count,
            "session_id"   : session_id,
            "search_used"  : False
        })

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────
# SECTION 9: Search Endpoint
# ─────────────────────────────────────────────

@app.route('/search', methods=['POST'])
def chat_with_search():
    """
    Web search chat - also saves to database now.
    Same database logic as /chat above.
    """
    try:
        data       = request.get_json()
        user_msg   = data.get('message')
        session_id = data.get('session_id', 'default')

        if not user_msg:
            return jsonify({"error": "No message provided"}), 400

        print(f"🔍 Search [{session_id[:15]}...]: {user_msg[:50]}")

        create_session(session_id, user_msg)
        save_message(session_id, 'user', user_msg)

        search_results, urls = search_web(user_msg)
        context = build_context(session_id)

        if search_results:
            prompt = f"""You are a helpful AI assistant with web search access.

Conversation history:
{context}

Current date: {datetime.now().strftime('%B %d, %Y')}

Google search results for "{user_msg}":
{search_results}

Answer using the search results. Cite sources when relevant."""
        else:
            prompt = f"""You are a helpful AI assistant.

Conversation history:
{context}

Current date: {datetime.now().strftime('%B %d, %Y')}

Answer: {user_msg}"""

        response    = model.generate_content(prompt)
        ai_response = response.text

        save_message(session_id, 'assistant', ai_response)
        update_session_time(session_id)

        return jsonify({
            "success"     : True,
            "response"    : ai_response,
            "memory_count": get_message_count(session_id),
            "session_id"  : session_id,
            "search_used" : bool(search_results),
            "sources"     : urls
        })

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────
# SECTION 10: File Upload Endpoint
# ─────────────────────────────────────────────

@app.route('/upload', methods=['POST'])
def upload_file():
    """
    File upload - also saves to database now.
    """
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "No file uploaded"}), 400

        file          = request.files['file']
        user_question = request.form.get('message', 'Please analyze this file')
        session_id    = request.form.get('session_id', 'default')

        if file.filename == '' or not allowed_file(file.filename):
            return jsonify({"success": False, "error": "Invalid file"}), 400

        timestamp     = datetime.now().strftime('%Y%m%d_%H%M%S')
        extension     = get_file_extension(file.filename)
        safe_filename = f"{timestamp}_{file.filename}"
        file_path     = os.path.join(UPLOAD_FOLDER, safe_filename)
        file.save(file_path)

        ai_response = None
        file_type   = None

        if extension == 'pdf':
            file_type      = "PDF Document"
            extracted_text = extract_text_from_pdf(file_path)
            if extracted_text:
                prompt      = f"PDF Content:\n{extracted_text[:10000]}\n\nUser question: {user_question}\n\nSummarize and answer."
                ai_response = model.generate_content(prompt).text

        elif extension in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
            file_type   = "Image"
            ai_response = analyze_image_with_gemini(file_path, user_question)

        elif extension == 'docx':
            file_type      = "Word Document"
            extracted_text = extract_text_from_docx(file_path)
            if extracted_text:
                prompt      = f"Document:\n{extracted_text[:10000]}\n\nUser question: {user_question}"
                ai_response = model.generate_content(prompt).text

        elif extension == 'txt':
            file_type      = "Text File"
            extracted_text = extract_text_from_txt(file_path)
            if extracted_text:
                prompt      = f"File content:\n{extracted_text[:10000]}\n\nUser question: {user_question}"
                ai_response = model.generate_content(prompt).text

        try:
            os.remove(file_path)
        except:
            pass

        if not ai_response:
            ai_response = "Sorry, I couldn't process this file."

        # ★ NEW: Save file interaction to database
        create_session(session_id, user_question)
        save_message(session_id, 'user', f"[Uploaded {file_type}: {file.filename}] {user_question}")
        save_message(session_id, 'assistant', ai_response)
        update_session_time(session_id)

        return jsonify({
            "success"     : True,
            "response"    : ai_response,
            "file_name"   : file.filename,
            "file_type"   : file_type,
            "memory_count": get_message_count(session_id),
            "session_id"  : session_id
        })

    except Exception as e:
        print(f"❌ Upload error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────
# SECTION 11: ★ NEW History Endpoints
# ─────────────────────────────────────────────
# These are NEW endpoints used by Phase 3 dashboard

@app.route('/history', methods=['GET'])
def get_history():
    """
    GET /history
    Returns all conversations for the dashboard.

    Returns:
        JSON list of all sessions with message counts
        Example:
        [
            {
                "session_id": "sess_abc",
                "title": "What is Python?",
                "created_at": "2026-03-18 14:00:00",
                "updated_at": "2026-03-18 14:05:00",
                "message_count": 6
            },
            ...
        ]
    """
    try:
        sessions = get_all_sessions()

        # Add message count to each session
        for session in sessions:
            session['message_count'] = get_message_count(session['session_id'])

        print(f"📋 Returning {len(sessions)} sessions")
        return jsonify({"success": True, "sessions": sessions})

    except Exception as e:
        print(f"❌ History error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/history/<session_id>', methods=['GET'])
def get_session_history(session_id):
    """
    GET /history/<session_id>
    Returns all messages for one specific session.

    <session_id> in the URL is a variable - Flask
    captures it and passes it to the function.

    Example URL: /history/sess_abc123
    Flask calls: get_session_history('sess_abc123')

    Returns:
        JSON list of messages
        Example:
        {
            "success": true,
            "messages": [
                {"role": "user", "content": "Hello", "timestamp": "..."},
                {"role": "assistant", "content": "Hi!", "timestamp": "..."}
            ]
        }
    """
    try:
        messages = get_session_messages(session_id)
        print(f"📋 Returning {len(messages)} messages for {session_id[:15]}...")
        return jsonify({"success": True, "messages": messages})

    except Exception as e:
        print(f"❌ Session history error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/history/<session_id>', methods=['DELETE'])
def delete_session_endpoint(session_id):
    """
    DELETE /history/<session_id>
    Deletes a session and all its messages.

    Same URL as GET above but different HTTP method (DELETE).
    Flask routes to a different function based on method.

    This is called when user clicks delete in the dashboard.
    """
    try:
        delete_session(session_id)
        return jsonify({"success": True, "message": "Session deleted"})

    except Exception as e:
        print(f"❌ Delete error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/history/search', methods=['GET'])
def search_history():
    """
    GET /history/search?q=python
    Search through all messages.

    'q' is a query parameter in the URL.
    request.args.get('q') reads it.

    Example: /history/search?q=python
    Returns all sessions containing the word 'python'
    """
    try:
        query = request.args.get('q', '')

        if not query:
            return jsonify({"success": False, "error": "No search query"}), 400

        results = search_messages(query)
        print(f"🔍 Search '{query}': {len(results)} results")
        return jsonify({"success": True, "results": results, "query": query})

    except Exception as e:
        print(f"❌ Search error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/clear', methods=['POST'])
def clear_memory():
    """
    Clear conversation - now deletes from database too.
    """
    try:
        data       = request.get_json()
        session_id = data.get('session_id', 'default')
        delete_session(session_id)
        return jsonify({"success": True, "message": "Session cleared"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/')
def home():
    return jsonify({
        "message" : "🤖 Live AI Assistant - with Database",
        "status"  : "online",
        "features": ["Chat", "Web Search", "File Upload", "Persistent History"],
        "endpoints": {
            "POST /chat"                    : "Regular chat",
            "POST /search"                  : "Chat with web search",
            "POST /upload"                  : "Upload file",
            "GET  /history"                 : "All conversations",
            "GET  /history/<session_id>"    : "One conversation",
            "DELETE /history/<session_id>"  : "Delete conversation",
            "GET  /history/search?q=term"   : "Search conversations"
        }
    })


# ─────────────────────────────────────────────
# SECTION 12: Run Server
# ─────────────────────────────────────────────

if __name__ == '__main__':
    print("=" * 55)
    print("🚀 Live AI Assistant - Database Edition")
    print("=" * 55)
    print("🤖 AI      : Google Gemini 2.5 Flash")
    print("🗄️  Database: SQLite (database.db)")
    print("💬 Memory  : Permanent (survives restarts!)")
    print("📁 Files   : PDF, Images, Word, Text")
    print("=" * 55)
    print("📍 http://localhost:5000")
    print("=" * 55)
    app.run(debug=True, host='0.0.0.0', port=5000)
