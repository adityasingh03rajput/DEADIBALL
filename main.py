# server.py - Fixed WebSocket Server for Render
import asyncio
import websockets
import json
from datetime import datetime

class GameServer:
    def __init__(self):
        self.connections = set()
        self.game_state = {
            "players": {},
            "last_update": datetime.now().timestamp()
        }

    async def handle_connection(self, websocket, path):
        """Handle WebSocket connections and reject HTTP requests"""
        # Check if it's a WebSocket request
        if path == "/ws" and "Upgrade" in websocket.request_headers:
            self.connections.add(websocket)
            print(f"New WebSocket connection: {websocket.remote_address}")
            
            try:
                async for message in websocket:
                    await self.process_message(websocket, message)
            except websockets.exceptions.ConnectionClosed:
                print(f"WebSocket closed: {websocket.remote_address}")
            finally:
                self.connections.remove(websocket)
        else:
            # Reject non-WebSocket requests
            print(f"Rejected non-WebSocket request to {path}")
            await websocket.close(code=4001)

    async def process_message(self, websocket, message):
        """Process incoming WebSocket messages"""
        try:
            data = json.loads(message)
            print(f"Received: {data}")
            
            self.game_state["last_update"] = datetime.now().timestamp()
            
            await self.broadcast({
                "type": "state_update",
                "data": data,
                "timestamp": self.game_state["last_update"]
            })

        except json.JSONDecodeError:
            print("Invalid JSON received")
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Invalid JSON format"
            }))

    async def broadcast(self, message):
        """Send message to all connected clients"""
        if self.connections:
            await asyncio.wait([
                ws.send(json.dumps(message)) 
                for ws in self.connections
                if ws.open
            ])

async def health_check(path, request_headers):
    """Handle health checks from Render"""
    if path == "/health":
        return 200, {}, b"OK\n"
    return None

async def start_server(host='0.0.0.0', port=8000):
    """Start the WebSocket server with health check support"""
    server = GameServer()
    
    async with websockets.serve(
        server.handle_connection,
        host,
        port,
        process_request=health_check,
        ping_interval=20,
        ping_timeout=40,
        # Important for Render compatibility:
        max_size=2**20,  # 1MB max message size
        max_queue=16
    ):
        print(f"Server started on ws://{host}:{port}/ws")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(start_server())
