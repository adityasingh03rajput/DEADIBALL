from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from collections import defaultdict
import time
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# Store connected users and their last active time
connected_users = {}
active_rooms = defaultdict(list)  # {room_name: [user1, user2]}

@app.route("/ping", methods=["POST"])
def ping():
    """Handle client heartbeats"""
    data = request.json
    username = data.get('username')
    
    if username:
        connected_users[username] = time.time()
        return {"status": "ok"}, 200
    return {"error": "Invalid data"}, 400

def cleanup_users():
    """Remove inactive users"""
    while True:
        current_time = time.time()
        for username, last_active in list(connected_users.items()):
            if current_time - last_active > 60:  # 1 minute timeout
                connected_users.pop(username)
                print(f"Removed inactive user: {username}")
        time.sleep(30)

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    for room, users in list(active_rooms.items()):
        for user in users[:]:
            if user['sid'] == request.sid:
                users.remove(user)
                emit('user_left', {'username': user['username']}, room=room)
                print(f"{user['username']} left room {room}")

@socketio.on('join_room')
def handle_join(data):
    username = data.get('username')
    room = data.get('room')
    
    if username and room:
        active_rooms[room].append({
            'username': username,
            'sid': request.sid
        })
        socketio.server.enter_room(request.sid, room)
        emit('user_joined', {'username': username}, room=room)
        print(f"{username} joined room {room}")

@socketio.on('send_message')
def handle_message(data):
    username = data.get('username')
    room = data.get('room')
    message = data.get('message')
    
    if username and room and message:
        emit('new_message', {
            'username': username,
            'message': message,
            'timestamp': time.strftime("%H:%M:%S")
        }, room=room)

if __name__ == "__main__":
    threading.Thread(target=cleanup_users, daemon=True).start()
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
