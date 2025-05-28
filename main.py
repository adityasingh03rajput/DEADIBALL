import asyncio
import websockets
import json
import random
from datetime import datetime
from collections import defaultdict

class GameServer:
    def __init__(self):
        self.connections = set()
        self.active_games = defaultdict(dict)
        self.GAME_WIDTH = 800
        self.GAME_HEIGHT = 600
        self.PLAYER_TIMEOUT = 30  # seconds
        self.BALL_RADIUS = 15
        self.PLAYER_RADIUS = 20
        self.MAX_SCORE = 5

    async def register(self, websocket):
        self.connections.add(websocket)
        print(f"New connection: {len(self.connections)} total")

    async def unregister(self, websocket):
        self.connections.remove(websocket)
        print(f"Connection closed: {len(self.connections)} remaining")

    async def handler(self, websocket, path):
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
        msg_type = data.get("type")
        
        if msg_type == "join":
            await self.handle_join(websocket, data)
        elif msg_type == "update":
            await self.handle_update(websocket, data)
        elif msg_type == "action":
            await self.handle_action(websocket, data)
        elif msg_type == "chat":
            await self.handle_chat(websocket, data)

    async def handle_join(self, websocket, data):
        game_id = data.get("game_id")
        player_id = data.get("player_id")
        role = data.get("role", "player")
        name = data.get("name", "Anonymous")
        
        if not all([game_id, player_id]):
            return await self.send_error(websocket, "Missing required fields")
        
        if game_id not in self.active_games:
            self.initialize_game(game_id)
        
        self.active_games[game_id]["players"][player_id] = {
            "websocket": websocket,
            "role": role,
            "name": name,
            "position": {"x": 100, "y": 300} if role == "player1" else {"x": 700, "y": 300},
            "last_update": datetime.now().timestamp()
        }
        
        await websocket.send(json.dumps({
            "type": "joined",
            "game_id": game_id,
            "player_id": player_id,
            "role": role,
            "name": name,
            "game_state": self.active_games[game_id]["state"],
            "players": self.get_player_list(game_id)
        }))
        
        await self.broadcast_game_state(game_id)
        await self.broadcast_chat(game_id, f"{name} has joined the game!", "system")

    async def handle_update(self, websocket, data):
        game_id = data.get("game_id")
        player_id = data.get("player_id")
        position = data.get("position")
        
        if not self.validate_game_player(game_id, player_id):
            return await self.send_error(websocket, "Invalid game or player")
        
        # Validate position
        if not (0 <= position["x"] <= self.GAME_WIDTH and 
                0 <= position["y"] <= self.GAME_HEIGHT):
            return await self.send_error(websocket, "Invalid position")
        
        self.active_games[game_id]["players"][player_id].update({
            "position": position,
            "last_update": datetime.now().timestamp()
        })
        
        await self.update_ball_position(game_id)
        await self.broadcast_game_state(game_id)

    async def handle_action(self, websocket, data):
        game_id = data.get("game_id")
        player_id = data.get("player_id")
        action = data.get("action")
        
        if not self.validate_game_player(game_id, player_id):
            return
        
        game = self.active_games[game_id]
        ball = game["state"]["ball"]
        
        if action == "shoot":
            player = game["players"][player_id]
            dx = ball["x"] - player["position"]["x"]
            dy = ball["y"] - player["position"]["y"]
            distance = (dx**2 + dy**2)**0.5
            
            if distance < self.PLAYER_RADIUS + self.BALL_RADIUS:
                ball["vx"] = dx * 0.1
                ball["vy"] = dy * 0.1
        
        await self.broadcast_game_state(game_id)

    async def handle_chat(self, websocket, data):
        game_id = data.get("game_id")
        player_id = data.get("player_id")
        message = data.get("message")
        
        if not self.validate_game_player(game_id, player_id) or not message:
            return
        
        player = self.active_games[game_id]["players"][player_id]
        await self.broadcast_chat(game_id, message, player["name"])

    async def broadcast_chat(self, game_id, message, sender):
        if game_id not in self.active_games:
            return
            
        chat_msg = {
            "type": "chat",
            "sender": sender,
            "message": message,
            "timestamp": datetime.now().timestamp()
        }
        
        for player in self.active_games[game_id]["players"].values():
            try:
                await player["websocket"].send(json.dumps(chat_msg))
            except:
                print("Failed to send chat message")

    async def broadcast_game_state(self, game_id):
        if game_id not in self.active_games:
            return
            
        game = self.active_games[game_id]
        players_data = {}
        
        for player_id, player in game["players"].items():
            players_data[player_id] = {
                "name": player["name"],
                "position": player.get("position"),
                "role": player["role"]
            }
        
        message = {
            "type": "state_update",
            "game_id": game_id,
            "players": players_data,
            "ball": game["state"]["ball"],
            "scores": game["state"]["scores"],
            "timestamp": datetime.now().timestamp()
        }
        
        for player in game["players"].values():
            try:
                await player["websocket"].send(json.dumps(message))
            except:
                print("Failed to send game state")

    async def update_ball_position(self, game_id):
        game = self.active_games[game_id]
        ball = game["state"]["ball"]
        
        # Update position
        ball["x"] += ball["vx"]
        ball["y"] += ball["vy"]
        
        # Wall collision
        if ball["x"] <= 0 or ball["x"] >= self.GAME_WIDTH:
            ball["vx"] *= -0.9
        if ball["y"] <= 0 or ball["y"] >= self.GAME_HEIGHT:
            ball["vy"] *= -0.9
        
        # Score detection
        if ball["x"] <= 0:
            game["state"]["scores"]["blue"] += 1
            self.reset_ball(game_id, "right")
        elif ball["x"] >= self.GAME_WIDTH:
            game["state"]["scores"]["red"] += 1
            self.reset_ball(game_id, "left")
        
        # Friction
        ball["vx"] *= 0.99
        ball["vy"] *= 0.99

    def reset_ball(self, game_id, direction):
        game = self.active_games[game_id]
        ball = game["state"]["ball"]
        
        ball["x"] = self.GAME_WIDTH // 2
        ball["y"] = self.GAME_HEIGHT // 2
        ball["vx"] = 5 if direction == "right" else -5
        ball["vy"] = random.uniform(-2, 2)
        
        # Check for winner
        if game["state"]["scores"]["red"] >= self.MAX_SCORE:
            game["state"]["winner"] = "red"
        elif game["state"]["scores"]["blue"] >= self.MAX_SCORE:
            game["state"]["winner"] = "blue"

    def initialize_game(self, game_id):
        self.active_games[game_id] = {
            "players": {},
            "state": {
                "ball": {
                    "x": self.GAME_WIDTH // 2,
                    "y": self.GAME_HEIGHT // 2,
                    "vx": 0,
                    "vy": 0
                },
                "scores": {"red": 0, "blue": 0},
                "winner": None
            }
        }

    def validate_game_player(self, game_id, player_id):
        return (game_id in self.active_games and 
                player_id in self.active_games[game_id]["players"])

    async def send_error(self, websocket, message):
        await websocket.send(json.dumps({
            "type": "error",
            "message": message
        }))

    def get_player_list(self, game_id):
        return {
            pid: {
                "name": p["name"],
                "role": p["role"]
            } for pid, p in self.active_games[game_id]["players"].items()
        }

    async def cleanup_inactive_players(self):
        while True:
            await asyncio.sleep(10)
            now = datetime.now().timestamp()
            for game_id, game in list(self.active_games.items()):
                for player_id, player in list(game["players"].items()):
                    if now - player["last_update"] > self.PLAYER_TIMEOUT:
                        name = player["name"]
                        del game["players"][player_id]
                        await self.broadcast_chat(game_id, f"{name} has timed out", "system")
                
                if not game["players"]:
                    del self.active_games[game_id]

async def health_check(path, request_headers):
    if path == "/health":
        return 200, {}, b"OK\n"
    return None

async def start_server():
    server = GameServer()
    asyncio.create_task(server.cleanup_inactive_players())
    
    async with websockets.serve(
        server.handler,
        "0.0.0.0",
        8000,
        process_request=health_check,
        ping_interval=20,
        ping_timeout=40,
        max_size=2**20
    ):
        print("DEADIBALL WebSocket server started on ws://0.0.0.0:8000")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(start_server())
