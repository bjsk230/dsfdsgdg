import os
import random
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate # เพิ่ม Flask-Migrate เพื่อจัดการ DB ขั้นสูง (optional)

# --- App Initialization & Config ---
app = Flask(__name__)
# ใช้ os.getenv แทน os.environ.get ตามมาตรฐานขั้นสูง
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_dev_key_change_in_production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///chat.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=3650) # 10 ปี
app.config['SESSION_COOKIE_SECURE'] = True # ควรใช้ HTTPS (Railway จัดการให้)
app.config['SESSION_COOKIE_HTTPONLY'] = True 
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax' 

db = SQLAlchemy(app)
migrate = Migrate(app, db) # Initialize migrate
socketio = SocketIO(app, cors_allowed_origins="*", manage_session=False)

# --- Database Model ---
class Message(db.Model):
    __tablename__ = 'messages' # กำหนดชื่อตารางชัดเจน
    id = db.Column(db.Integer, primary_key=True)
    sender_sid = db.Column(db.String(100), nullable=False)
    receiver_sid = db.Column(db.String(100), nullable=False)
    sender_name = db.Column(db.String(100), nullable=False)
    text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user_deleted = db.Column(db.Boolean, default=False)

# สร้าง DB หากไม่มี
with app.app_context():
    db.create_all()

# --- Global State Management ---
# ใช้ sets และ dicts แยกกันเพื่อความชัดเจน
USERS = {}   # {sid: nickname}
ADMIN_SIDS = set() # {sid, sid, ...}
# อ่านรหัสผ่านจาก ENV เป็นหลัก
ADMIN_PASS = os.getenv('ADMIN_PASS', 'adminworakanjajakub')

# --- Helper Functions ---
def send_user_list_to_admins():
    """Compiles and sends a list of non-admin users to all active admins."""
    user_list = [{"sid": sid, "name": name} for sid, name in USERS.items() if sid not in ADMIN_SIDS]
    for admin_sid in ADMIN_SIDS:
        emit('update_user_list', {'users': user_list}, room=admin_sid)

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

# --- SocketIO Event Handlers ---

@socketio.on('join')
def handle_join():
    is_admin_session = session.get('is_admin', False)
    
    if is_admin_session:
        session.permanent = True
        ADMIN_SIDS.add(request.sid)
        nick = session.get('admin_nick', 'ADMIN')
        USERS[request.sid] = nick
        emit('admin_status', {'is_admin': True})
    else:
        nick = f"User-{random.randint(1000, 9999)}"
        USERS[request.sid] = nick
        for admin_sid in ADMIN_SIDS:
            emit('sys_msg', {'msg': f"🔔 {nick} เข้าสู่ระบบแล้ว"}, room=admin_sid)

    emit('set_identity', {'name': nick, 'id': request.sid})

    history = Message.query.filter(
        ((Message.sender_sid == request.sid) | (Message.receiver_sid == request.sid)),
        (Message.user_deleted == False)
    ).order_by(Message.timestamp.asc()).all()

    for msg in history:
        emit('new_msg', {'user': msg.sender_name, 'text': msg.text})
    
    send_user_list_to_admins()

# Event ใหม่สำหรับรับรหัสผ่านจาก Modal (Frontend)
@socketio.on('admin_login_attempt')
def handle_admin_login_attempt(data):
    password = data.get('password')
    if password == ADMIN_PASS:
        session.permanent = True 
        session['is_admin'] = True
        session['admin_nick'] = f"ADMIN-{random.randint(10, 99)}"
        # ต้องอัปเดตสถานะสำหรับ SID ปัจจุบันทันที
        ADMIN_SIDS.add(request.sid)
        USERS[request.sid] = session['admin_nick']
        emit('admin_status', {'is_admin': True, 'message': '✅ ล็อกอินแอดมินสำเร็จ'})
        send_user_list_to_admins()
    else:
        emit('sys_msg', {'msg': '❌ รหัสผ่านแอดมินไม่ถูกต้อง'})


@socketio.on('message')
def handle_message(data):
    msg_text = data.get('text', '').strip()
    target_sid = data.get('target_sid')
    if not msg_text: return

    # คำสั่ง /logout เป็นวิธีเดียวที่ใช้ในช่องแชท
    if msg_text == "/logout" and request.sid in ADMIN_SIDS:
        session.clear()
        ADMIN_SIDS.discard(request.sid) # ใช้ discard เพื่อป้องกัน KeyError หาก sid ไม่อยู่ใน set
        emit('admin_status', {'is_admin': False})
        emit('sys_msg', {'msg': "ออกจากระบบแอดมินแล้ว โปรดรีเฟรชหน้าจอเพื่อความสมบูรณ์"})
        send_user_list_to_admins()
        return

    new_msg = None
    if request.sid not in ADMIN_SIDS:
        new_msg = Message(sender_sid=request.sid, receiver_sid="ADMINS", sender_name=USERS[request.sid], text=msg_text)
        if not ADMIN_SIDS:
            emit('sys_msg', {'msg': "ขณะนี้แอดมินไม่อยู่ ข้อมูลของคุณถูกบันทึกไว้แล้ว"})
        for admin_sid in ADMIN_SIDS:
            emit('new_msg', {'user': USERS[request.sid], 'text': msg_text, 'from_sid': request.sid}, room=admin_sid)
            emit('sys_msg', {'msg': "📩 มีข้อความใหม่จากลูกค้า!"}, room=admin_sid)
        emit('new_msg', {'user': "คุณ", 'text': msg_text}, room=request.sid)
    else:
        if target_sid:
            new_msg = Message(sender_sid=request.sid, receiver_sid=target_sid, sender_name="ADMIN", text=msg_text)
            emit('new_msg', {'user': "ADMIN", 'text': msg_text}, room=target_sid)
            for admin_sid in ADMIN_SIDS:
                emit('new_msg', {'user': f"ตอบถึง {USERS.get(target_sid, 'User')}", 'text': msg_text, 'from_sid': target_sid}, room=admin_sid)

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
    ADMIN_SIDS.discard(sid) # ใช้ discard เพื่อความปลอดภัย
    USERS.pop(sid, None)
    send_user_list_to_admins()

# --- Main Runner ---
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    # ปิด reloader และใช้ log_output=True สำหรับ Production style
    socketio.run(app, host='0.0.0.0', port=port, debug=False, use_reloader=False, log_output=True)
