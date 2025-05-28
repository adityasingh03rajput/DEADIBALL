# Server Code (Flask API)
from flask import Flask, request, jsonify
import sqlite3
import hashlib
import random
from datetime import datetime, timedelta
import threading
import time

app = Flask(__name__)

# Database setup
def init_db():
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    
    # Create tables
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id TEXT PRIMARY KEY, name TEXT, email TEXT, 
                  password TEXT, role TEXT, active INTEGER)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS students
                 (id TEXT PRIMARY KEY, name TEXT, class TEXT,
                  device_type TEXT, last_seen TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS attendance
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  student_id TEXT, date TEXT, status TEXT,
                  check_in TEXT, check_out TEXT, session_id TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS sessions
                 (id TEXT PRIMARY KEY, teacher_id TEXT,
                  start_time TEXT, end_time TEXT, class TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS authorized_bssids
                 (bssid TEXT PRIMARY KEY, location TEXT,
                  added_by TEXT, added_at TEXT)''')
    
    conn.commit()
    conn.close()

init_db()

# Helper functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_db():
    conn = sqlite3.connect('attendance.db')
    conn.row_factory = sqlite3.Row
    return conn

# API Endpoints
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'student')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    conn = get_db()
    c = conn.cursor()
    
    # Check if user exists
    c.execute("SELECT * FROM users WHERE id=?", (username,))
    if c.fetchone():
        conn.close()
        return jsonify({'error': 'Username already exists'}), 400
    
    # Insert new user
    c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
              (username, data.get('name', ''), data.get('email', ''),
               hash_password(password), role, 1))
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success'}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (username,))
    user = c.fetchone()
    conn.close()
    
    if not user or user['password'] != hash_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    return jsonify({
        'status': 'success',
        'user': {
            'id': user['id'],
            'name': user['name'],
            'role': user['role']
        }
    })

@app.route('/api/bssids', methods=['GET', 'POST'])
def manage_bssids():
    if request.method == 'POST':
        # Teacher adding a new authorized BSSID
        data = request.json
        teacher_id = data.get('teacher_id')
        bssid = data.get('bssid')
        location = data.get('location', '')
        
        if not teacher_id or not bssid:
            return jsonify({'error': 'Teacher ID and BSSID required'}), 400
        
        conn = get_db()
        c = conn.cursor()
        
        try:
            c.execute("INSERT INTO authorized_bssids VALUES (?, ?, ?, ?)",
                      (bssid.lower(), location, teacher_id, datetime.now().isoformat()))
            conn.commit()
            conn.close()
            return jsonify({'status': 'success'}), 201
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({'error': 'BSSID already exists'}), 400
    
    else:
        # Get list of all authorized BSSIDs
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM authorized_bssids")
        bssids = [dict(row) for row in c.fetchall()]
        conn.close()
        return jsonify({'bssids': bssids})

@app.route('/api/start_session', methods=['POST'])
def start_session():
    data = request.json
    teacher_id = data.get('teacher_id')
    class_name = data.get('class')
    
    if not teacher_id or not class_name:
        return jsonify({'error': 'Teacher ID and class required'}), 400
    
    session_id = f"SESSION_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    start_time = datetime.now().isoformat()
    
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
              (session_id, teacher_id, start_time, None, class_name))
    conn.commit()
    conn.close()
    
    return jsonify({
        'status': 'success',
        'session_id': session_id,
        'start_time': start_time
    })

@app.route('/api/end_session', methods=['POST'])
def end_session():
    data = request.json
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({'error': 'Session ID required'}), 400
    
    end_time = datetime.now().isoformat()
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE sessions SET end_time=? WHERE id=?",
              (end_time, session_id))
    conn.commit()
    conn.close()
    
    return jsonify({
        'status': 'success',
        'end_time': end_time
    })

@app.route('/api/mark_attendance', methods=['POST'])
def mark_attendance():
    data = request.json
    student_id = data.get('student_id')
    session_id = data.get('session_id')
    bssid = data.get('bssid')
    
    if not student_id or not session_id:
        return jsonify({'error': 'Student ID and session ID required'}), 400
    
    # Verify BSSID is authorized
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM authorized_bssids WHERE bssid=?", (bssid.lower(),))
    if not c.fetchone():
        conn.close()
        return jsonify({'error': 'Unauthorized WiFi network'}), 403
    
    # Check if already marked
    c.execute('''SELECT * FROM attendance 
                 WHERE student_id=? AND session_id=?''', 
              (student_id, session_id))
    if c.fetchone():
        conn.close()
        return jsonify({'error': 'Attendance already marked'}), 400
    
    # Mark attendance
    now = datetime.now()
    c.execute('''INSERT INTO attendance 
                 (student_id, date, status, check_in, session_id)
                 VALUES (?, ?, ?, ?, ?)''',
              (student_id, now.date().isoformat(), 'present', 
               now.time().isoformat(), session_id))
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success'})

@app.route('/api/random_ring', methods=['POST'])
def random_ring():
    data = request.json
    session_id = data.get('session_id')
    count = data.get('count', 2)
    
    if not session_id:
        return jsonify({'error': 'Session ID required'}), 400
    
    conn = get_db()
    c = conn.cursor()
    
    # Get students present in this session
    c.execute('''SELECT student_id FROM attendance 
                 WHERE session_id=? AND status='present' ''', 
              (session_id,))
    present_students = [row[0] for row in c.fetchall()]
    
    if len(present_students) < count:
        conn.close()
        return jsonify({'error': 'Not enough present students'}), 400
    
    # Select random students
    selected = random.sample(present_students, min(count, len(present_students)))
    
    # Update their status to "ringed"
    for student_id in selected:
        c.execute('''UPDATE attendance SET status='ringed' 
                     WHERE student_id=? AND session_id=?''',
                  (student_id, session_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'status': 'success',
        'selected_students': selected
    })

def cleanup_sessions():
    """Periodically clean up old sessions"""
    while True:
        conn = get_db()
        c = conn.cursor()
        
        # End sessions older than 8 hours
        cutoff = (datetime.now() - timedelta(hours=8)).isoformat()
        c.execute('''UPDATE sessions SET end_time=?
                     WHERE end_time IS NULL AND start_time < ?''',
                  (datetime.now().isoformat(), cutoff))
        conn.commit()
        conn.close()
        
        time.sleep(3600)  # Run every hour

if __name__ == '__main__':
    # Start cleanup thread
    threading.Thread(target=cleanup_sessions, daemon=True).start()
    
    app.run(host='0.0.0.0', port=5000, debug=True)
