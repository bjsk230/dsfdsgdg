import os
import random
from datetime import datetime, timezone
from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///chat.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
# manage_session=False ช่วยให้ SocketIO ใช้ร่วมกับ Flask Session ได้เสถียรขึ้น
socketio = SocketIO(app, cors_allowed_origins="*", manage_session=False)

# --- Database Model ---
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

# --- Chat Management ---
users = {}  # {sid: nickname}
admins = set() # {sid, sid, ...}
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'adminworakanjajakub')

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def handle_join():
    # 1. ตรวจสอบสถานะแอดมินจาก Session (ทำให้ Login ค้างไว้ได้)
    is_admin_session = session.get('is_admin', False)
    
    if is_admin_session:
        admins.add(request.sid)
        nick = session.get('admin_nick', 'ADMIN')
        users[request.sid] = nick
        emit('admin_status', {'is_admin': True})
    else:
        nick = f"User-{random.randint(1000, 9999)}"
        users[request.sid] = nick
        # แจ้งเตือนแอดมินทุกคนเมื่อมี User ใหม่เข้า
        for a_sid in admins:
            emit('sys_msg', {'msg': f"🔔 {nick} เชื่อมต่อเข้ามาแล้ว"}, room=a_sid)

    emit('set_identity', {'name': nick, 'id': request.sid})

    # 2. โหลดประวัติแชท (เฉพาะที่ยังไม่ถูกลบ)
    history = Message.query.filter(
        ((Message.sender_sid == request.sid) | (Message.receiver_sid == request.sid)),
        (Message.user_deleted == False)
    ).order_by(Message.timestamp.asc()).all()

    for msg in history:
        emit('new_msg', {'user': msg.sender_name, 'text': msg.text})

@socketio.on('message')
def handle_message(data):
    msg_text = data.get('text', '').strip()
    target_sid = data.get('target_sid')
    if not msg_text: return

    # --- ระบบล็อกอินแอดมิน ---
    if msg_text == f"/login {ADMIN_PASS}":
        session['is_admin'] = True
        session['admin_nick'] = f"ADMIN-{len(admins) + 1}"
        admins.add(request.sid)
        users[request.sid] = session['admin_nick']
        emit('admin_status', {'is_admin': True})
        emit('sys_msg', {'msg': "✅ ล็อกอินแอดมินสำเร็จ (สถานะจะคงอยู่แม้รีเฟรช)"})
        return

    new_msg = None
    # --- กรณีผู้ใช้ส่งหาแอดมิน ---
    if request.sid not in admins:
        new_msg = Message(sender_sid=request.sid, receiver_sid="ADMINS", sender_name=users[request.sid], text=msg_text)
        
        if not admins:
            emit('sys_msg', {'msg': "ขณะนี้ไม่มีแอดมินออนไลน์ กรุณารอสักครู่"})
        
        for a_sid in admins:
            emit('new_msg', {'user': users[request.sid], 'text': msg_text, 'from_sid': request.sid}, room=a_sid)
            emit('sys_msg', {'msg': "📩 มีข้อความใหม่จากลูกค้า!"}, room=a_sid) # แจ้งเตือนแอดมิน
            
        emit('new_msg', {'user': "คุณ", 'text': msg_text}, room=request.sid)

    # --- กรณีแอดมินตอบกลับ ---
    else:
        if target_sid:
            new_msg = Message(sender_sid=request.sid, receiver_sid=target_sid, sender_name="ADMIN", text=msg_text)
            emit('new_msg', {'user': "ADMIN", 'text': msg_text}, room=target_sid)
            # แจ้งแอดมินคนอื่นๆ ว่ามีการตอบแชทนี้แล้ว
            for a_sid in admins:
                emit('new_msg', {'user': f"ตอบถึง {users.get(target_sid, 'Unknown')}", 'text': msg_text, 'from_sid': target_sid}, room=a_sid)

    if new_msg:
        db.session.add(new_msg)
        db.session.commit()
        emit('message_ack', {'status': 'saved', 'id': new_msg.id}, room=request.sid)

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # ปิด reloader เพื่อป้องกัน WinError 10048 ใน Windows
    socketio.run(app, host='0.0.0.0', port=port, debug=True, use_reloader=False)
