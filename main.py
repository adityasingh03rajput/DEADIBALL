# server.py - Minimal WebSocket Server
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
        """Main connection handler"""
        self.connections.add(websocket)
        print(f"New connection: {websocket.remote_address}")

        try:
            async for message in websocket:
                await self.process_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            print(f"Connection closed: {websocket.remote_address}")
        finally:
            self.connections.remove(websocket)

    async def process_message(self, websocket, message):
        """Process incoming messages"""
        try:
            data = json.loads(message)
            print(f"Received: {data}")

            # Update game state
            self.game_state["last_update"] = datetime.now().timestamp()
            
            # Broadcast to all connections
            await self.broadcast({
                "type": "state_update",
                "data": data,
                "timestamp": self.game_state["last_update"]
            })

        except json.JSONDecodeError:
            print("Invalid JSON received")

    async def broadcast(self, message):
        """Send message to all connected clients"""
        if self.connections:
            await asyncio.wait([
                ws.send(json.dumps(message)) 
                for ws in self.connections
            ])

async def start_server(host='0.0.0.0', port=8000):
    """Start the WebSocket server"""
    server = GameServer()
    async with websockets.serve(
        server.handle_connection,
        host,
        port,
        ping_interval=20,
        ping_timeout=40
    ):
        print(f"Server started on ws://{host}:{port}")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(start_server())
