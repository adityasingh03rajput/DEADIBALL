# ws_server.py - WebSocket Server for DEADIBALL
import asyncio
import websockets
import json
from datetime import datetime
from collections import defaultdict

class GameServer:
    def __init__(self):
        self.connections = set()
        self.game_state = {
            "players": {},
            "ball": {"x": 400, "y": 300, "vx": 0, "vy": 0},
            "scores": {"red": 0, "blue": 0},
            "last_update": datetime.now().timestamp()
        }
        self.active_games = defaultdict(dict)

    async def register(self, websocket):
        """Register new WebSocket connection"""
        self.connections.add(websocket)
        print(f"New connection: {len(self.connections)} total")

    async def unregister(self, websocket):
        """Unregister disconnected WebSocket"""
        self.connections.remove(websocket)
        print(f"Connection closed: {len(self.connections)} remaining")

    async def handler(self, websocket, path):
        """Handle WebSocket connections"""
        await self.register(websocket)
        try:
            async for message in websocket:
                data = json.loads(message)
                await self.process_message(websocket, data)
        except websockets.exceptions.ConnectionClosed:
            print("Client disconnected normally")
        except Exception as e:
            print(f"Error: {str(e)}")
        finally:
            await self.unregister(websocket)

    async def process_message(self, websocket, data):
        """Process incoming game messages"""
        msg_type = data.get("type")
        
        if msg_type == "join":
            # Handle player joining a game
            game_id = data.get("game_id")
            player_id = data.get("player_id")
            role = data.get("role")
            
            if not all([game_id, player_id, role]):
                return await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Missing required fields"
                }))
            
            if game_id not in self.active_games:
                self.active_games[game_id] = {
                    "players": {},
                    "state": {
                        "ball": {"x": 400, "y": 300, "vx": 0, "vy": 0},
                        "scores": {"red": 0, "blue": 0}
                    }
                }
            
            self.active_games[game_id]["players"][player_id] = {
                "websocket": websocket,
                "role": role,
                "last_update": datetime.now().timestamp()
            }
            
            await websocket.send(json.dumps({
                "type": "joined",
                "game_id": game_id,
                "player_id": player_id,
                "role": role,
                "game_state": self.active_games[game_id]["state"]
            }))
            
        elif msg_type == "update":
            # Handle game state updates
            game_id = data.get("game_id")
            player_id = data.get("player_id")
            position = data.get("position")
            
            if game_id not in self.active_games:
                return await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Game not found"
                }))
            
            if player_id not in self.active_games[game_id]["players"]:
                return await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Player not registered"
                }))
            
            # Update player position
            self.active_games[game_id]["players"][player_id].update({
                "position": position,
                "last_update": datetime.now().timestamp()
            })
            
            # Broadcast update to all players in this game
            await self.broadcast_game_state(game_id)
            
        elif msg_type == "action":
            # Handle game actions (like shooting)
            game_id = data.get("game_id")
            action = data.get("action")
            
            if game_id not in self.active_games:
                return
            
            # Process game physics (simplified)
            if action == "shoot":
                ball = self.active_games[game_id]["state"]["ball"]
                ball["vx"] = random.uniform(-5, 5)
                ball["vy"] = random.uniform(-5, 5)
            
            await self.broadcast_game_state(game_id)

    async def broadcast_game_state(self, game_id):
        """Send game state to all players in a specific game"""
        if game_id not in self.active_games:
            return
            
        game = self.active_games[game_id]
        players_data = {}
        
        # Prepare player data
        for player_id, player in game["players"].items():
            players_data[player_id] = {
                "position": player.get("position"),
                "role": player["role"]
            }
        
        # Prepare message
        message = {
            "type": "state_update",
            "game_id": game_id,
            "players": players_data,
            "ball": game["state"]["ball"],
            "scores": game["state"]["scores"],
            "timestamp": datetime.now().timestamp()
        }
        
        # Send to all players in this game
        for player_id, player in game["players"].items():
            try:
                await player["websocket"].send(json.dumps(message))
            except:
                print(f"Failed to send to player {player_id}")

async def health_check(path, request_headers):
    """Handle health checks for Render"""
    if path == "/health":
        return 200, {}, b"OK\n"
    return None

async def start_server():
    """Start the WebSocket server"""
    server = GameServer()
    async with websockets.serve(
        server.handler,
        "0.0.0.0",
        8000,
        process_request=health_check,
        ping_interval=20,
        ping_timeout=40,
        max_size=2**20  # 1MB max message size
    ):
        print("DEADIBALL WebSocket server started on ws://0.0.0.0:8000")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(start_server())
