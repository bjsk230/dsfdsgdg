import os
import random
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-very-secret')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///chat.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=3650)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", manage_session=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_sid = db.Column(db.String(100))
    receiver_sid = db.Column(db.String(100))
    sender_name = db.Column(db.String(100))
    text = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user_deleted = db.Column(db.Boolean, default=False)

with app.app_context():
    db.create_all()

users = {}   # {sid: nick}
admins = set() # {sid, sid, ...}
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'adminworakanjajakub')

# --- Helper Function: ส่งรายชื่อผู้ใช้ให้แอดมินทุกคน ---
def send_user_list_to_admins():
    # กรองเฉพาะ User ทั่วไป ไม่ใช่ Admin
    user_list = [{"sid": sid, "name": name} for sid, name in users.items() if sid not in admins]
    for a_sid in admins:
        emit('update_user_list', {'users': user_list}, room=a_sid)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def handle_join():
    is_admin_session = session.get('is_admin', False)
    
    if is_admin_session:
        session.permanent = True
        admins.add(request.sid)
        nick = session.get('admin_nick', 'ADMIN')
        users[request.sid] = nick
        emit('admin_status', {'is_admin': True})
        print(f"[ADMIN] {nick} reconnected.")
    else:
        nick = f"User-{random.randint(1000, 9999)}"
        users[request.sid] = nick
        for a_sid in admins:
            emit('sys_msg', {'msg': f"🔔 {nick} เข้าสู่ระบบแล้ว"}, room=a_sid)

    emit('set_identity', {'name': nick, 'id': request.sid})

    history = Message.query.filter(
        ((Message.sender_sid == request.sid) | (Message.receiver_sid == request.sid)),
        (Message.user_deleted == False)
    ).order_by(Message.timestamp.asc()).all()

    for msg in history:
        emit('new_msg', {'user': msg.sender_name, 'text': msg.text})
    
    # อัปเดตรายชื่อให้แอดมินทันทีที่มีคน Join
    send_user_list_to_admins()

@socketio.on('message')
def handle_message(data):
    msg_text = data.get('text', '').strip()
    target_sid = data.get('target_sid')
    if not msg_text: return

    if msg_text == f"/login {ADMIN_PASS}":
        session.permanent = True
        session['is_admin'] = True
        session['admin_nick'] = f"ADMIN-{random.randint(10, 99)}"
        admins.add(request.sid)
        users[request.sid] = session['admin_nick']
        emit('admin_status', {'is_admin': True})
        emit('sys_msg', {'msg': "✅ ล็อกอินแอดมินสำเร็จ ระบบจะจดจำแอดมินไว้ตลอดไป"})
        send_user_list_to_admins() # อัปเดตรายชื่อเมื่อมีแอดมินคนใหม่
        return

    if msg_text == "/logout" and request.sid in admins:
        session.clear()
        if request.sid in admins: admins.remove(request.sid)
        emit('admin_status', {'is_admin': False})
        emit('sys_msg', {'msg': "ออกจากระบบแอดมินแล้ว โปรดรีเฟรชหน้าจอ"})
        send_user_list_to_admins() # อัปเดตรายชื่อเมื่อแอดมิน Logout
        return

    new_msg = None
    if request.sid not in admins:
        new_msg = Message(sender_sid=request.sid, receiver_sid="ADMINS", sender_name=users[request.sid], text=msg_text)
        if not admins:
            emit('sys_msg', {'msg': "ขณะนี้แอดมินไม่อยู่ ข้อมูลของคุณถูกบันทึกไว้แล้ว"})
        for a_sid in admins:
            emit('new_msg', {'user': users[request.sid], 'text': msg_text, 'from_sid': request.sid}, room=a_sid)
            emit('sys_msg', {'msg': "📩 มีข้อความใหม่จากลูกค้า!"}, room=a_sid)
        emit('new_msg', {'user': "คุณ", 'text': msg_text}, room=request.sid)
    else:
        if target_sid:
            new_msg = Message(sender_sid=request.sid, receiver_sid=target_sid, sender_name="ADMIN", text=msg_text)
            emit('new_msg', {'user': "ADMIN", 'text': msg_text}, room=target_sid)
            for a_sid in admins:
                emit('new_msg', {'user': f"ตอบถึง {users.get(target_sid, 'User')}", 'text': msg_text, 'from_sid': target_sid}, room=a_sid)

    if new_msg:
        db.session.add(new_msg)
        db.session.commit()

@socketio.on('clear_my_chat')
def clear_chat():
    Message.query.filter(Message.sender_sid == request.sid).update({Message.user_deleted: True})
    db.session.commit()
    emit('clear_screen')

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in admins:
        admins.remove(sid)
    users.pop(sid, None)
    # อัปเดตรายชื่อให้แอดมินทันทีที่มีคน Disconnect
    send_user_list_to_admins()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True, use_reloader=False)

