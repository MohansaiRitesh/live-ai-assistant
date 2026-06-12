# DATABASE.PY - All database operations
# Our database has 2 tables:
#   1. sessions  - one row per conversation
#   2. messages  - one row per message

import sqlite3     
import os          
from datetime import datetime   

# Database Configuration
# __file__  = the path of THIS file (database.py)
# os.path.dirname(__file__)  = the folder containing this file
# os.path.join(...)  = combine folder + filename safely
DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

# Connection Helper
def get_connection():
    """
    Create and return a database connection.

    Why a function instead of one global connection?
    - Each request gets its own fresh connection
    - Avoids conflicts when multiple users use the app
    - Safer - connection is always properly opened/closed

    sqlite3.connect() does two things:
      - If database.db EXISTS  → opens it
      - If database.db MISSING → creates it automatically

    row_factory = sqlite3.Row lets us access columns by name:
      row['session_id']   instead of   row[1]
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Initialize Database 
def init_db():
    """
    Create the tables if they don't already exist.
    Called ONCE when the server starts.

    """
    conn = get_connection()
    cursor = conn.cursor()

    # ── Table 1: sessions ──────────────────────
    # One row = one full conversation
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL UNIQUE,
            title       TEXT    NOT NULL DEFAULT 'New Chat',
            created_at  TEXT    NOT NULL,
            updated_at  TEXT    NOT NULL
        )
    """)

    # ── Table 2: messages ──────────────────────
    # One row = one message (user or AI)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL,
            role        TEXT    NOT NULL,
            content     TEXT    NOT NULL,
            timestamp   TEXT    NOT NULL
        )
    """)

    conn.commit()   # Save the changes to the file
    conn.close()    # Release the connection

    print(f"✅ Database ready: {DATABASE_PATH}")

# Session Functions
def create_session(session_id, first_message):
    """
    Create a new session row when a conversation starts.

    Args:
        session_id    (str): Unique ID from the browser
        first_message (str): First user message - becomes the chat title

    The title is the first 60 characters of the first message.
    Example: "What is machine learning and how does it..." → "What is machine learning and how doe..."
    """
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # strftime formats datetime as a string
    # %Y = 4-digit year, %m = month, %d = day
    # %H = hour (24h), %M = minutes, %S = seconds

    title = first_message[:60]   # First 60 characters as title
    if len(first_message) > 60:
        title += '...'         

    try:
        cursor.execute("""
            INSERT INTO sessions (session_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, (session_id, title, now, now))
        # VALUES (?, ?, ?, ?) uses placeholders - WHY?
        # NEVER do this: f"VALUES ('{session_id}', '{title}')"
        # That's called SQL Injection - a major security vulnerability!
        # Placeholders (?) safely escape the values for you.

        conn.commit()
        print(f"🆕 New session created: {session_id[:20]}...")

    except sqlite3.IntegrityError:
        # IntegrityError happens when UNIQUE constraint fails
        pass

    finally:
        conn.close()


def update_session_time(session_id):
    """
    Update 'updated_at' every time a new message is sent.
    This lets us sort chats by most recently active.

    Args:
        session_id (str): Which session to update
    """
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("""
        UPDATE sessions
        SET updated_at = ?
        WHERE session_id = ?
    """, (now, session_id))

    conn.commit()
    conn.close()


def get_all_sessions():
    """
    Get all sessions sorted by most recently updated.
    Used by the chat history dashboard.

    Returns:
        list: List of session rows as dictionaries
              Example: [{'session_id': 'sess_abc', 'title': 'Hello...', ...}, ...]

    ORDER BY updated_at DESC means:
        Most recent chat appears first (DESC = descending = newest first)
        ASC would be oldest first
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM sessions
        ORDER BY updated_at DESC
    """)

    # fetchall() returns ALL matching rows as a list
    rows = cursor.fetchall()
    conn.close()

    # Convert sqlite3.Row objects to plain dictionaries
    # dict(row) turns row['session_id'] into {'session_id': 'sess_abc'}
    return [dict(row) for row in rows]


def delete_session(session_id):
    """
    Delete a session AND all its messages.
    Used when user clicks 'Delete' in the dashboard.

    Args:
        session_id (str): Which session to delete

    We delete messages FIRST then the session.
    Order matters here - good practice to delete
    child records before parent records.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Delete all messages for this session first
    cursor.execute("""
        DELETE FROM messages
        WHERE session_id = ?
    """, (session_id,))
    # Note: (session_id,) is a tuple with one item
    # Python requires a comma for single-item tuples

    # Then delete the session itself
    cursor.execute("""
        DELETE FROM sessions
        WHERE session_id = ?
    """, (session_id,))

    conn.commit()
    conn.close()

    print(f"🗑️ Session deleted: {session_id[:20]}...")


# Message Functions
def save_message(session_id, role, content):
    """
    Save one message to the database.
    Called every time a user sends a message OR AI responds.

    Args:
        session_id (str): Which conversation this belongs to
        role       (str): 'user' or 'assistant'
        content    (str): The actual message text
    """
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("""
        INSERT INTO messages (session_id, role, content, timestamp)
        VALUES (?, ?, ?, ?)
    """, (session_id, role, content, now))

    conn.commit()
    conn.close()


def get_session_messages(session_id):
    """
    Get all messages for one session, ordered by time.
    Used to:
      1. Load conversation history when server restarts
      2. Show messages in the dashboard

    Args:
        session_id (str): Which conversation to load

    Returns:
        list: Messages in chronological order (oldest first)
              Example: [
                  {'role': 'user',      'content': 'Hello'},
                  {'role': 'assistant', 'content': 'Hi there!'},
                  ...
              ]
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT role, content, timestamp
        FROM messages
        WHERE session_id = ?
        ORDER BY timestamp ASC
    """, (session_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_message_count(session_id):
    """
    Count how many messages are in a session.
    Useful for showing stats in the dashboard.

    Args:
        session_id (str): Which session to count

    Returns:
        int: Number of messages

    COUNT(*) is a SQL aggregate function
    It counts how many rows match the WHERE condition
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) as count
        FROM messages
        WHERE session_id = ?
    """, (session_id,))

    # fetchone() returns just ONE row
    row = cursor.fetchone()
    conn.close()

    return row['count'] if row else 0


def search_messages(query):
    """
    Search through all messages for a keyword.
    Used by the search feature in the dashboard.

    Args:
        query (str): What to search for

    Returns:
        list: Sessions that contain the search term

    LIKE is SQL's search operator:
        LIKE '%python%' matches anything containing 'python'
        % = wildcard (matches any characters)
        So '%python%' matches:
            "What is python?"       ✅
            "I love python coding"  ✅
            "python"                ✅
            "java"                  ❌

    DISTINCT means don't return duplicate session_ids
    """
    conn = get_connection()
    cursor = conn.cursor()

    search_term = f'%{query}%'   # Wrap in % wildcards

    cursor.execute("""
        SELECT DISTINCT m.session_id, s.title, s.updated_at
        FROM messages m
        JOIN sessions s ON m.session_id = s.session_id
        WHERE m.content LIKE ?
        ORDER BY s.updated_at DESC
    """, (search_term,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


if __name__ == '__main__':

    print("🧪 Testing database...")
    print("=" * 40)

    # Step 1: Initialize
    init_db()

    # Step 2: Create a test session
    create_session('test_session_001', 'Hello, what is Python programming?')

    # Step 3: Save some messages
    save_message('test_session_001', 'user', 'Hello, what is Python programming?')
    save_message('test_session_001', 'assistant', 'Python is a popular programming language!')
    save_message('test_session_001', 'user', 'What can I build with Python?')
    save_message('test_session_001', 'assistant', 'You can build web apps, AI tools, games and more!')

    # Step 4: Read them back
    print("\n📋 All sessions:")
    sessions = get_all_sessions()
    for s in sessions:
        print(f"  - {s['session_id']} | {s['title']}")

    print("\n💬 Messages in test session:")
    messages = get_session_messages('test_session_001')
    for m in messages:
        print(f"  [{m['role']}]: {m['content']}")

    print(f"\n📊 Message count: {get_message_count('test_session_001')}")

    # Step 5: Test search
    print("\n🔍 Search for 'Python':")
    results = search_messages('Python')
    for r in results:
        print(f"  Found in: {r['title']}")

    # Step 6: Clean up test data
    delete_session('test_session_001')
    print("\n✅ Test complete! database.db created successfully.")
