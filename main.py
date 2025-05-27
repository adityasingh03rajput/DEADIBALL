# server.py
import os
import asyncio
import websockets
import json
import random
from datetime import datetime, timedelta

# Game constants
BALL_FRICTION = 0.98
PORT = int(os.environ.get("PORT", 8000))  # For cloud hosting

class GameServer:
    def __init__(self):
        self.players = {}
        self.game_state = {
            "ball": {"x": 400, "y": 300, "vx": 0, "vy": 0},
            "scores": {"red": 0, "blue": 0},
            "players": {}
        }
        self.game_active = False
        self.last_reset = datetime.now()

    async def handler(self, websocket, path):
        try:
            # Assign player role
            if "red" not in self.players:
                role = "red"
                self.players[role] = websocket
                start_pos = {"x": 100, "y": 300}
            elif "blue" not in self.players:
                role = "blue"
                self.players[role] = websocket
                start_pos = {"x": 700, "y": 300}
            else:
                await websocket.send(json.dumps({"type": "error", "message": "Game is full"}))
                await websocket.close()
                return

            # Initialize player
            self.game_state["players"][role] = {
                **start_pos,
                "vx": 0, "vy": 0,
                "angle": 0,
                "score": 0
            }

            # Send initialization data
            await websocket.send(json.dumps({
                "type": "init", 
                "role": role,
                "game_state": self.game_state
            }))

            # Start game if 2 players
            if len(self.players) == 2 and not self.game_active:
                self.game_active = True
                await self.reset_ball()
                await self.broadcast({"type": "game_start"})
                asyncio.create_task(self.game_loop())

            # Handle incoming messages
            async for message in websocket:
                data = json.loads(message)
                if data["type"] == "player_update":
                    self.game_state["players"][role].update(data["data"])
                elif data["type"] == "goal":
                    scorer = "red" if data["scorer"] == "blue" else "blue"
                    self.game_state["scores"][scorer] += 1
                    await self.reset_ball()
                    await self.broadcast({
                        "type": "score_update",
                        "scores": self.game_state["scores"]
                    })

        except websockets.exceptions.ConnectionClosed:
            print(f"{role} disconnected")
            if role in self.players:
                del self.players[role]
                if len(self.players) < 2:
                    self.game_active = False
                    await self.broadcast({"type": "player_disconnected", "role": role})

    async def broadcast(self, message):
        for player in self.players.values():
            try:
                await player.send(json.dumps(message))
            except:
                pass

    async def game_loop(self):
        while self.game_active:
            self.update_physics()
            await self.broadcast({
                "type": "game_update",
                "ball": self.game_state["ball"],
                "players": self.game_state["players"]
            })
            await asyncio.sleep(0.05)  # 20 FPS

    def update_physics(self):
        # Ball physics
        self.game_state["ball"]["vx"] *= BALL_FRICTION
        self.game_state["ball"]["vy"] *= BALL_FRICTION
        self.game_state["ball"]["x"] += self.game_state["ball"]["vx"]
        self.game_state["ball"]["y"] += self.game_state["ball"]["vy"]

        # Boundary checks
        self.game_state["ball"]["x"] = max(20, min(780, self.game_state["ball"]["x"]))
        self.game_state["ball"]["y"] = max(20, min(580, self.game_state["ball"]["y"]))

    async def reset_ball(self):
        now = datetime.now()
        if (now - self.last_reset) < timedelta(seconds=1):
            return
        self.last_reset = now
        
        self.game_state["ball"] = {
            "x": 400, 
            "y": 300,
            "vx": random.choice([-3, 3]),
            "vy": random.choice([-3, 3])
        }

if __name__ == "__main__":
    server = GameServer()
    start_server = websockets.serve(server.handler, "0.0.0.0", PORT)
    
    print(f"Server running on ws://0.0.0.0:{PORT}")
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
