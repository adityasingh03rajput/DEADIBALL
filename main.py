from flask import Flask, request, jsonify
from collections import defaultdict, deque
import time
import threading
from datetime import datetime

app = Flask(__name__)

# Configuration
MESSAGE_HISTORY_LIMIT = 200  # Max messages per room
MESSAGE_TTL = 120  # Messages expire after 2 minutes
USER_TIMEOUT = 300  # Users timeout after 5 minutes

# Data storage
chat_rooms = defaultdict(lambda: deque(maxlen=MESSAGE_HISTORY_LIMIT))
active_users = {}  # {username: last_active}

@app.route("/ping", methods=["POST"])
def ping():
    """Update user activity"""
    username = request.json.get('username')
    if username:
        active_users[username] = time.time()
        return {"status": "ok"}, 200
    return {"error": "Invalid data"}, 400

@app.route("/send", methods=["POST"])
def send_message():
    """Send a message with auto-cleanup"""
    data = request.json
    username = data.get('username')
    room = data.get('room')
    message = data.get('message')
    
    if not all([username, room, message]):
        return {"error": "Missing data"}, 400
    
    # Create message with expiration
    msg_data = {
        'username': username,
        'message': message,
        'timestamp': datetime.now().isoformat(),
        'expires': time.time() + MESSAGE_TTL
    }
    chat_rooms[room].append(msg_data)
    active_users[username] = time.time()  # Update activity
    
    return {"status": "sent"}, 200

@app.route("/receive", methods=["GET"])
def get_messages():
    """Get messages with auto-cleanup"""
    room = request.args.get('room')
    if not room:
        return {"error": "Room not specified"}, 400
    
    # Filter expired messages
    current_time = time.time()
    valid_messages = [
        msg for msg in chat_rooms[room]
        if msg['expires'] > current_time
    ]
    chat_rooms[room] = deque(valid_messages, maxlen=MESSAGE_HISTORY_LIMIT)
    
    return {"messages": valid_messages}, 200

def cleanup_task():
    """Background cleanup of inactive users"""
    while True:
        current_time = time.time()
        # Clean inactive users
        for user, last_active in list(active_users.items()):
            if current_time - last_active > USER_TIMEOUT:
                active_users.pop(user)
        time.sleep(60)

if __name__ == "__main__":
    threading.Thread(target=cleanup_task, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=True)
