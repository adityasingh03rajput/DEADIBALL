from flask import Flask, request, jsonify
from collections import defaultdict, deque
import time
from datetime import datetime
import threading

app = Flask(__name__)

# Configuration
MESSAGE_HISTORY_LIMIT = 100  # Max messages per room
USER_TIMEOUT = 300  # 5 minutes

# Data storage
chat_rooms = defaultdict(deque)  # {room_name: deque(messages)}
active_users = {}  # {username: last_active}

@app.route('/ping', methods=['POST'])
def ping():
    """Update user activity"""
    username = request.json.get('username')
    if username:
        active_users[username] = time.time()
        return {'status': 'ok'}, 200
    return {'error': 'Invalid data'}, 400

@app.route('/send', methods=['POST'])
def send_message():
    """Send a message to a room"""
    data = request.json
    username = data.get('username')
    room = data.get('room')
    message = data.get('message')
    
    if not all([username, room, message]):
        return {'error': 'Missing data'}, 400
    
    # Create message
    msg_data = {
        'username': username,
        'message': message,
        'timestamp': datetime.now().isoformat(),
        'id': int(time.time() * 1000)  # Unique message ID
    }
    
    # Add to room and trim history
    chat_rooms[room].append(msg_data)
    if len(chat_rooms[room]) > MESSAGE_HISTORY_LIMIT:
        chat_rooms[room].popleft()
    
    active_users[username] = time.time()
    return {'status': 'sent', 'id': msg_data['id']}, 200

@app.route('/get_messages', methods=['GET'])
def get_messages():
    """Get new messages since last_id"""
    room = request.args.get('room')
    last_id = int(request.args.get('last_id', 0))
    
    if not room:
        return {'error': 'Room not specified'}, 400
    
    # Find messages newer than last_id
    new_messages = [
        msg for msg in chat_rooms.get(room, [])
        if msg['id'] > last_id
    ]
    
    latest_id = max((msg['id'] for msg in chat_rooms.get(room, [])), default=0)
    
    return {
        'messages': new_messages,
        'latest_id': latest_id
    }, 200

@app.route('/get_users', methods=['GET'])
def get_users():
    """Get active users in a room"""
    room = request.args.get('room')
    if not room:
        return {'error': 'Room not specified'}, 400
    
    # Get users active in the last USER_TIMEOUT seconds
    active_threshold = time.time() - USER_TIMEOUT
    users = [
        username for username, last_active in active_users.items()
        if last_active > active_threshold
    ]
    
    return {'users': users}, 200

def cleanup_users():
    """Periodically clean inactive users"""
    while True:
        current_time = time.time()
        inactive_threshold = current_time - USER_TIMEOUT
        
        # Clean inactive users
        for username, last_active in list(active_users.items()):
            if last_active < inactive_threshold:
                active_users.pop(username)
        
        time.sleep(60)

if __name__ == '__main__':
    threading.Thread(target=cleanup_users, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=True)
