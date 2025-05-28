from flask import Flask, request, jsonify
from collections import defaultdict
import time
from datetime import datetime
import threading

app = Flask(__name__)

# Store messages and active users
messages = defaultdict(list)  # {room: [messages]}
active_users = {}  # {username: last_active}

@app.route('/send', methods=['POST'])
def send_message():
    data = request.json
    username = data.get('username')
    room = data.get('room')
    message = data.get('message')
    
    if not all([username, room, message]):
        return {'error': 'Missing data'}, 400
    
    # Add message with timestamp
    msg_data = {
        'username': username,
        'message': message,
        'timestamp': datetime.now().isoformat()
    }
    messages[room].append(msg_data)
    active_users[username] = time.time()
    
    return {'status': 'sent'}, 200

@app.route('/get_messages', methods=['GET'])
def get_messages():
    room = request.args.get('room')
    if not room:
        return {'error': 'Room not specified'}, 400
    
    return {'messages': messages.get(room, [])}, 200

@app.route('/active_users', methods=['GET'])
def get_active_users():
    room = request.args.get('room')
    if not room:
        return {'error': 'Room not specified'}, 400
    
    # Get users active in last 60 seconds
    active = [
        user for user, last_active in active_users.items()
        if time.time() - last_active < 60
    ]
    return {'users': active}, 200

def cleanup_users():
    """Remove inactive users"""
    while True:
        current_time = time.time()
        inactive = [
            user for user, last_active in active_users.items()
            if current_time - last_active > 60
        ]
        for user in inactive:
            del active_users[user]
        time.sleep(30)

if __name__ == '__main__':
    threading.Thread(target=cleanup_users, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=True)
