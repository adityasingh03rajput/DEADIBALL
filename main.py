from flask import Flask, request, jsonify
from collections import defaultdict
import time
import threading

app = Flask(__name__)

# Store messages and users
chat_rooms = defaultdict(list)  # {room_name: [messages]}
users_last_seen = {}            # {username: last_active_time}

@app.route("/ping", methods=["POST"])
def ping():
    """Handle client heartbeats"""
    username = request.json.get('username')
    if username:
        users_last_seen[username] = time.time()
        return {"status": "ok"}, 200
    return {"error": "Invalid data"}, 400

@app.route("/send_message", methods=["POST"])
def send_message():
    """Handle new messages"""
    data = request.json
    username = data.get('username')
    room = data.get('room')
    message = data.get('message')
    
    if not all([username, room, message]):
        return {"error": "Missing data"}, 400
    
    timestamp = time.strftime("%H:%M:%S")
    chat_rooms[room].append({
        'username': username,
        'message': message,
        'timestamp': timestamp
    })
    
    # Keep only the last 100 messages per room
    if len(chat_rooms[room]) > 100:
        chat_rooms[room] = chat_rooms[room][-100:]
    
    return {"status": "sent", "timestamp": timestamp}, 200

@app.route("/get_messages", methods=["GET"])
def get_messages():
    """Get recent messages"""
    room = request.args.get('room')
    last_index = int(request.args.get('last_index', 0))
    
    if not room:
        return {"error": "Room not specified"}, 400
    
    messages = chat_rooms.get(room, [])
    new_messages = messages[last_index:]
    
    return {
        "messages": new_messages,
        "total_messages": len(messages)
    }, 200

def cleanup_users():
    """Remove inactive users"""
    while True:
        current_time = time.time()
        for username, last_seen in list(users_last_seen.items()):
            if current_time - last_seen > 60:  # 1 minute timeout
                users_last_seen.pop(username)
                print(f"Removed inactive user: {username}")
        time.sleep(30)

if __name__ == "__main__":
    threading.Thread(target=cleanup_users, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=True)
