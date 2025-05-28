from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import socket
import threading

app = Flask(__name__)

devices = {}
messages = {}

DEVICE_TIMEOUT = timedelta(seconds=60)
MESSAGE_RETENTION = timedelta(hours=24)

def find_available_port(start_port=20000, end_port=30000):
    """Find an available port in the given range"""
    for port in range(start_port, end_port):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', port))
                return port
        except:
            continue
    raise Exception("No available ports found")

@app.route("/register", methods=["POST"])
def register_device():
    data = request.json
    device_id = data.get("device_id")
    name = data.get("name", f"User-{device_id[-4:]}")
    status = "online"
    
    if not device_id:
        return jsonify({"error": "Missing device_id"}), 400
    
    # Get client's IP and find an available port for them
    client_ip = request.remote_addr
    client_port = find_available_port()
    
    devices[device_id] = {
        "ip": client_ip,
        "port": client_port,
        "last_seen": datetime.now(),
        "name": name,
        "status": status
    }
    
    return jsonify({
        "status": "registered",
        "device_id": device_id,
        "assigned_port": client_port,
        "server_ip": socket.gethostbyname(socket.gethostname())
    }), 200

# ... [keep all other server endpoints the same as previous implementation] ...

if __name__ == "__main__":
    server_port = find_available_port(20000, 21000)
    print(f"Starting server on port {server_port}")
    app.run(host="0.0.0.0", port=server_port, threaded=True)
