from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from collections import defaultdict
import time
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Store active users and their rooms
active_users = {}  # {username: {'sid': socket_id, 'room': room_name}}
message_history = defaultdict(list)  # {room_name: [messages]}

@app.route('/ping', methods=['POST'])
def ping():
    """Handle client heartbeats"""
    username = request.json.get('username')
    if username in active_users:
        return {'status': 'ok'}, 200
    return {'error': 'User not active'}, 400

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    for username, data in list(active_users.items()):
        if data['sid'] == request.sid:
            room = data['room']
            del active_users[username]
            emit('user_left', {'username': username}, room=room)
            print(f"{username} disconnected")

@socketio.on('join_room')
def handle_join(data):
    username = data.get('username')
    room = data.get('room')
    
    if username and room:
        active_users[username] = {
            'sid': request.sid,
            'room': room
        }
        socketio.server.enter_room(request.sid, room)
        
        # Send last 10 messages to the new user
        emit('message_history', {
            'messages': message_history.get(room, [])[-10:]
        }, room=request.sid)
        
        emit('user_joined', {
            'username': username,
            'timestamp': datetime.now().isoformat()
        }, room=room)
        
        print(f"{username} joined room {room}")

@socketio.on('send_message')
def handle_message(data):
    username = data.get('username')
    room = data.get('room')
    message = data.get('message')
    
    if username and room and message:
        if username not in active_users:
            return
        
        # Create message data
        msg_data = {
            'username': username,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        
        # Store in history (limited to 100 messages per room)
        message_history[room].append(msg_data)
        if len(message_history[room]) > 100:
            message_history[room] = message_history[room][-100:]
        
        # Broadcast to room
        emit('new_message', msg_data, room=room)
        
        # Schedule message cleanup after delivery
        socketio.start_background_task(cleanup_message, room, msg_data)

def cleanup_message(room, msg_data):
    """Optional: Cleanup message after some time"""
    time.sleep(60)  # Keep messages for 60 seconds after sending
    if msg_data in message_history.get(room, []):
        message_history[room].remove(msg_data)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
