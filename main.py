import socket
import threading
import json
from collections import defaultdict
import random

class GameServer:
    def __init__(self, host='localhost', port=5555):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((host, port))
        self.server.listen()
        
        self.games = defaultdict(dict)
        self.player_count = 0
        self.width = 800
        self.height = 600
        
        print(f"Server started on {host}:{port}")

    def handle_client(self, conn, addr):
        print(f"New connection from {addr}")
        player_id = None
        
        try:
            while True:
                data = conn.recv(1024).decode('utf-8')
                if not data:
                    break
                
                try:
                    msg = json.loads(data)
                    response = self.process_message(conn, msg)
                    if response:
                        conn.send(json.dumps(response).encode('utf-8'))
                except json.JSONDecodeError:
                    print("Invalid JSON received")
        
        except ConnectionResetError:
            print(f"Client {addr} disconnected")
        finally:
            if player_id:
                self.remove_player(player_id)
            conn.close()

    def process_message(self, conn, msg):
        msg_type = msg.get('type')
        
        if msg_type == 'join':
            return self.handle_join(conn, msg)
        elif msg_type == 'update':
            return self.handle_update(msg)
        elif msg_type == 'chat':
            return self.handle_chat(msg)
        elif msg_type == 'shoot':
            return self.handle_shoot(msg)
        return None

    def handle_join(self, conn, msg):
        game_id = msg.get('game_id', 'default')
        name = msg.get('name', 'Player')
        
        self.player_count += 1
        player_id = f"player{self.player_count}"
        role = 'player1' if len(self.games[game_id].get('players', {})) < 1 else 'player2'
        
        if game_id not in self.games:
            self.init_game(game_id)
        
        self.games[game_id]['players'][player_id] = {
            'conn': conn,
            'name': name,
            'role': role,
            'position': {'x': 100 if role == 'player1' else 700, 'y': 300}
        }
        
        # Notify all players in game
        self.broadcast_game_state(game_id)
        self.broadcast_chat(game_id, f"{name} joined as {role}!", "System")
        
        return {
            'type': 'joined',
            'player_id': player_id,
            'role': role,
            'game_state': self.games[game_id]['state'],
            'players': self.get_player_list(game_id)
        }

    def handle_update(self, msg):
        game_id = msg.get('game_id')
        player_id = msg.get('player_id')
        position = msg.get('position')
        
        if game_id in self.games and player_id in self.games[game_id]['players']:
            self.games[game_id]['players'][player_id]['position'] = position
            self.update_ball(game_id)
            self.broadcast_game_state(game_id)
        
        return None

    def handle_chat(self, msg):
        game_id = msg.get('game_id')
        player_id = msg.get('player_id')
        message = msg.get('message')
        
        if game_id in self.games and player_id in self.games[game_id]['players']:
            name = self.games[game_id]['players'][player_id]['name']
            self.broadcast_chat(game_id, message, name)
        
        return None

    def handle_shoot(self, msg):
        game_id = msg.get('game_id')
        player_id = msg.get('player_id')
        
        if game_id in self.games and player_id in self.games[game_id]['players']:
            player = self.games[game_id]['players'][player_id]
            ball = self.games[game_id]['state']['ball']
            
            # Simple shoot logic
            dx = ball['x'] - player['position']['x']
            dy = ball['y'] - player['position']['y']
            dist = (dx**2 + dy**2)**0.5
            
            if dist < 50:  # If close enough to ball
                ball['vx'] = dx * 0.2
                ball['vy'] = dy * 0.2
            
            self.broadcast_game_state(game_id)
        
        return None

    def update_ball(self, game_id):
        if game_id not in self.games:
            return
        
        ball = self.games[game_id]['state']['ball']
        
        # Update position
        ball['x'] += ball['vx']
        ball['y'] += ball['vy']
        
        # Wall collision
        if ball['x'] <= 0 or ball['x'] >= self.width:
            ball['vx'] *= -0.9
        if ball['y'] <= 0 or ball['y'] >= self.height:
            ball['vy'] *= -0.9
        
        # Score detection
        if ball['x'] <= 0:
            self.games[game_id]['state']['scores']['blue'] += 1
            self.reset_ball(game_id, 'right')
        elif ball['x'] >= self.width:
            self.games[game_id]['state']['scores']['red'] += 1
            self.reset_ball(game_id, 'left')
        
        # Friction
        ball['vx'] *= 0.99
        ball['vy'] *= 0.99

    def reset_ball(self, game_id, direction):
        ball = self.games[game_id]['state']['ball']
        ball['x'] = self.width // 2
        ball['y'] = self.height // 2
        ball['vx'] = 5 if direction == 'right' else -5
        ball['vy'] = random.uniform(-2, 2)

    def broadcast_game_state(self, game_id):
        if game_id not in self.games:
            return
        
        players = {pid: {'name': p['name'], 'position': p['position'], 'role': p['role']} 
                  for pid, p in self.games[game_id]['players'].items()}
        
        msg = {
            'type': 'state_update',
            'players': players,
            'ball': self.games[game_id]['state']['ball'],
            'scores': self.games[game_id]['state']['scores']
        }
        
        for player in self.games[game_id]['players'].values():
            try:
                player['conn'].send(json.dumps(msg).encode('utf-8'))
            except:
                pass

    def broadcast_chat(self, game_id, message, sender):
        msg = {
            'type': 'chat',
            'sender': sender,
            'message': message
        }
        
        for player in self.games[game_id]['players'].values():
            try:
                player['conn'].send(json.dumps(msg).encode('utf-8'))
            except:
                pass

    def init_game(self, game_id):
        self.games[game_id] = {
            'players': {},
            'state': {
                'ball': {'x': self.width//2, 'y': self.height//2, 'vx': 0, 'vy': 0},
                'scores': {'red': 0, 'blue': 0}
            }
        }

    def get_player_list(self, game_id):
        return {pid: {'name': p['name'], 'role': p['role']} 
                for pid, p in self.games[game_id]['players'].items()}

    def remove_player(self, player_id):
        for game_id, game in self.games.items():
            if player_id in game['players']:
                name = game['players'][player_id]['name']
                del game['players'][player_id]
                self.broadcast_chat(game_id, f"{name} left the game", "System")
                break

    def start(self):
        while True:
            conn, addr = self.server.accept()
            thread = threading.Thread(target=self.handle_client, args=(conn, addr))
            thread.start()

if __name__ == "__main__":
    server = GameServer()
    server.start()
