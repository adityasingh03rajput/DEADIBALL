from flask import Flask, request, jsonify
from collections import defaultdict, deque
import time
import threading
from datetime import datetime

app = Flask(__name__)

# Store messages with auto-cleanup (max 100 messages per room)
chat_rooms = defaultdict(lambda: deque(maxlen=100))
active_users = {}  # {username: last_active}

# Message expiration time (seconds)
MESSAGE_TTL = 60  # Messages auto-delete after 1 minute

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
    """Send a self-destructing message"""
    data = request.json
    username = data.get('username')
    room = data.get('room')
    message = data.get('message')
    
    if not all([username, room, message]):
        return {"error": "Missing data"}, 400
    
    # Add message with expiration timestamp
    msg_data = {
        'username': username,
        'message': message,
        'timestamp': datetime.now().isoformat(),
        'expires': time.time() + MESSAGE_TTL
    }
    chat_rooms[room].append(msg_data)
    
    return {"status": "sent"}, 200

@app.route("/receive", methods=["GET"])
def get_messages():
    """Get messages and auto-clean expired ones"""
    room = request.args.get('room')
    if not room:
        return {"error": "Room not specified"}, 400
    
    # Filter out expired messages
    current_time = time.time()
    valid_messages = [
        msg for msg in chat_rooms[room]
        if msg['expires'] > current_time
    ]
    chat_rooms[room] = deque(valid_messages, maxlen=100)
    
    return {"messages": valid_messages}, 200

def cleanup():
    """Periodically clean inactive users and old messages"""
    while True:
        current_time = time.time()
        # Clean inactive users (5 minute timeout)
        for user, last_active in list(active_users.items()):
            if current_time - last_active > 300:
                active_users.pop(user)
        
        time.sleep(60)

if __name__ == "__main__":
    threading.Thread(target=cleanup, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=True)
