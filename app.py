from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import sqlite3
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# SQLite for message history
DB = 'chat.db'
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (room TEXT, user TEXT, text TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        session['username'] = request.form['username']
        room = request.form['room']
        return redirect(url_for('chat', room=room))
    return render_template('home.html')

@app.route('/chat/<room>')
def chat(room):
    messages = sqlite3.connect(DB).execute(
        "SELECT user, text FROM messages WHERE room=? ORDER BY timestamp", (room,)
    ).fetchall()
    return render_template('chat.html', room=room, messages=messages)

@app.route('/uploads/<filename>')
def upload_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@socketio.on('join')
def on_join(data):
    join_room(data['room'])
    emit('status', {'msg': f"{data['user']} joined."}, room=data['room'])

@socketio.on('leave')
def on_leave(data):
    leave_room(data['room'])
    emit('status', {'msg': f"{data['user']} left."}, room=data['room'])

@socketio.on('typing')
def on_typing(data):
    emit('typing', {'user': data['user']}, room=data['room'], include_self=False)

@socketio.on('stop_typing')
def on_stop_typing(data):
    emit('stop_typing', {'user': data['user']}, room=data['room'], include_self=False)

@socketio.on('message')
def on_message(data):
    room = data['room']
    user = data['user']
    text = data['text']
    # Save message
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("INSERT INTO messages(room,user,text) VALUES (?,?,?)", (room, user, text))
    conn.commit(); conn.close()
    emit('message', {'user': user, 'text': text}, room=room)

@socketio.on('file_upload')
def on_file_upload(data):
    room = data['room']; user = data['user']
    file = request.files['file']
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    url = url_for('upload_file', filename=filename)
    emit('file', {'user': user, 'url': url, 'filename': filename}, room=room)

if __name__ == '__main__':
    socketio.run(app, debug=True)
