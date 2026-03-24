# ============================================
# LIVE AI ASSISTANT - WITH CONVERSATION MEMORY
# ============================================
# Stable version with memory - web search removed for now

# --------------------------------------------
# STEP 1: Import Libraries
# --------------------------------------------
from flask import Flask, request, jsonify, session
from flask_cors import CORS
import google.generativeai as genai
import os
from dotenv import load_dotenv
from datetime import datetime
import secrets

# --------------------------------------------
# STEP 2: Load Environment Variables
# --------------------------------------------
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    print("❌ ERROR: Gemini API key not found!")
    exit()

# --------------------------------------------
# STEP 3: Configure Gemini
# --------------------------------------------
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('models/gemini-2.5-flash')

print("✅ Gemini API configured!")

# --------------------------------------------
# STEP 4: Conversation Memory Storage
# --------------------------------------------
# This stores conversation history for each user
# Key = session ID, Value = list of messages
conversation_memory = {}

# --------------------------------------------
# STEP 5: Initialize Flask App
# --------------------------------------------
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # For session management
CORS(app, supports_credentials=True)

# --------------------------------------------
# STEP 6: Home Endpoint
# --------------------------------------------
@app.route('/')
def home():
    """Home endpoint"""
    return jsonify({
        "message": "🤖 Live AI Assistant API is running!",
        "status": "online",
        "ai_model": "Google Gemini 2.5 Flash (FREE)",
        "features": ["Chat", "Conversation Memory", "Context-Aware"],
        "endpoints": {
            "/chat": "POST - Chat with memory",
            "/clear": "POST - Clear conversation memory"
        }
    })

# --------------------------------------------
# STEP 7: Chat Endpoint with Memory
# --------------------------------------------
@app.route('/chat', methods=['POST'])
def chat():
    """
    Chat with conversation memory
    
    How memory works:
    1. Store all previous messages in conversation_memory
    2. Send entire conversation history to Gemini
    3. Gemini understands context from previous messages
    4. User can have natural, flowing conversations
    """
    try:
        data = request.get_json()
        user_message = data.get('message')
        session_id = data.get('session_id', 'default')  # Track user sessions
        
        if not user_message:
            return jsonify({"error": "No message provided"}), 400
        
        print(f"💬 Chat (Session: {session_id}): {user_message}")
        
        # Get or create conversation history for this session
        if session_id not in conversation_memory:
            conversation_memory[session_id] = []
            print(f"🆕 New conversation session: {session_id}")
        
        # Add user message to history
        conversation_memory[session_id].append({
            "role": "user",
            "content": user_message
        })
        
        # Build the full conversation context for Gemini
        # Format: "User: message\nAssistant: response\nUser: message..."
        conversation_context = ""
        for msg in conversation_memory[session_id]:
            role = "User" if msg["role"] == "user" else "Assistant"
            conversation_context += f"{role}: {msg['content']}\n"
        
        # Create prompt with full context
        prompt = f"""You are a helpful AI assistant. Here is the conversation history:

{conversation_context}

Current date: {datetime.now().strftime('%B %d, %Y')}

Please respond to the user's latest message naturally, considering the entire conversation context."""
        
        # Send to Gemini
        response = model.generate_content(prompt)
        gemini_response = response.text
        
        # Add assistant response to history
        conversation_memory[session_id].append({
            "role": "assistant",
            "content": gemini_response
        })
        
        # Show memory stats
        memory_count = len(conversation_memory[session_id])
        print(f"✅ Response generated (Memory: {memory_count} messages)")
        
        return jsonify({
            "success": True,
            "response": gemini_response,
            "model": "gemini-2.5-flash",
            "memory_count": memory_count,
            "session_id": session_id
        })
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# --------------------------------------------
# STEP 8: Search Endpoint (Simplified)
# --------------------------------------------
@app.route('/search', methods=['POST'])
def search():
    """
    Search endpoint - for now, just uses Gemini with date context
    Web search can be added later when we find a working API
    """
    try:
        data = request.get_json()
        user_message = data.get('message')
        session_id = data.get('session_id', 'default')
        
        if not user_message:
            return jsonify({"error": "No message provided"}), 400
        
        print(f"🔍 Search (Session: {session_id}): {user_message}")
        
        # Get conversation history
        if session_id not in conversation_memory:
            conversation_memory[session_id] = []
        
        # Add to history
        conversation_memory[session_id].append({
            "role": "user",
            "content": user_message
        })
        
        # Build context
        conversation_context = ""
        for msg in conversation_memory[session_id]:
            role = "User" if msg["role"] == "user" else "Assistant"
            conversation_context += f"{role}: {msg['content']}\n"
        
        # Enhanced prompt with current date
        prompt = f"""You are a helpful AI assistant. Here is the conversation history:

{conversation_context}

Current date: {datetime.now().strftime('%B %d, %Y, %A')}

Please respond to the user's latest message. If the question requires current/recent information that you don't have, explain that you don't have real-time data but provide the best answer you can based on your knowledge."""
        
        response = model.generate_content(prompt)
        gemini_response = response.text
        
        # Add to history
        conversation_memory[session_id].append({
            "role": "assistant",
            "content": gemini_response
        })
        
        memory_count = len(conversation_memory[session_id])
        print(f"✅ Response generated (Memory: {memory_count} messages)")
        
        return jsonify({
            "success": True,
            "response": gemini_response,
            "model": "gemini-2.5-flash",
            "memory_count": memory_count,
            "session_id": session_id,
            "note": "Web search not available - using AI knowledge with date context"
        })
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# --------------------------------------------
# STEP 9: Clear Memory Endpoint
# --------------------------------------------
@app.route('/clear', methods=['POST'])
def clear_memory():
    """Clear conversation memory for a session"""
    try:
        data = request.get_json()
        session_id = data.get('session_id', 'default')
        
        if session_id in conversation_memory:
            message_count = len(conversation_memory[session_id])
            del conversation_memory[session_id]
            print(f"🗑️ Cleared {message_count} messages from session: {session_id}")
            return jsonify({
                "success": True,
                "message": f"Cleared {message_count} messages from memory"
            })
        else:
            return jsonify({
                "success": True,
                "message": "No memory to clear"
            })
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# --------------------------------------------
# STEP 10: Run Server
# --------------------------------------------
if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Starting Live AI Assistant Server...")
    print("=" * 50)
    print("🤖 AI: Google Gemini 2.5 Flash")
    print("🧠 Feature: Conversation Memory")
    print("💰 Cost: 100% FREE!")
    print("=" * 50)
    print("📍 http://localhost:5000")
    print("=" * 50)
    print("💡 The AI remembers your conversation!")
    print("   Ask follow-up questions naturally.")
    print("=" * 50)
    print("Press CTRL+C to stop")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
