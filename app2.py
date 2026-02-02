import os
import random
from datetime import datetime, timezone
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
# Use DATABASE_URL if provided (e.g. postgres on Railway), otherwise fallback to local sqlite
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///chat.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ฐานข้อมูล

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

#--- ระบบจัดการแชท ---
users = {}
admins = set()
# ADMIN_PASS should come from env in production. Keep a sensible default for local dev.
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'adminworakanjajakub')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return {'status': 'ok'}

@socketio.on('join')
def handle_join():
    nick = f"User-{random.randint(1000, 9999)}"
    users[request.sid] = nick
    emit('set_identity', {'name': nick, 'id': request.sid})
    print(f"[DEBUG] JOIN: sid={request.sid} nick={nick}")

    #โหลดประวัติเฉพาะที่ผู้ใช้ยังไม่กดลบ
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
    print(f"[DEBUG] MESSAGE from={request.sid} data={data}")
    if not msg_text: return

    #ล็อกอินแอดมิน
    if msg_text == f"/login {ADMIN_PASS}":
        admins.add(request.sid)
        users[request.sid] = f"ADMIN-{len(admins)}"
        emit('admin_status', {'is_admin' : True})
        emit('sys_msg', {'msg': "คุณเข้าสู่ระบบแอดมินแล้ว"})
        return
    new_msg = None
    if request.sid not in admins:
        new_msg = Message(sender_sid=request.sid, receiver_sid="ADMINS", sender_name=users[request.sid], text=msg_text)
        if not admins:
            emit('sys_msg', {'msg': "ขณะนี้ไม่มีแอดมินออนไลน์ กรุณารอสักครู่"})
        for a_sid in admins:
            emit('new_msg', {'user': users[request.sid], 'text': msg_text, 'from_sid': request.sid}, room=a_sid)
        emit('new_msg', {'user': "คุณ", 'text': msg_text}, room=request.sid)
        # acknowledge to sender that message was received/saved
        # (will be sent after DB commit below)
    else: # แอดมินตอบกลับ
        if target_sid:
            new_msg = Message(sender_sid=request.sid, receiver_sid=target_sid, sender_name="ADMIN", text=msg_text)
            emit('new_msg', {'user': "ADMIN", 'text': msg_text}, room=target_sid)
            for a_sid in admins: # แจ้งแอดมินทุกคนว่าตอบแล้ว
                emit('new_msg', {'user': f"ตอบถึง {users.get(target_sid)}", 'text': msg_text, 'from_sid': target_sid}, room=a_sid)
    if new_msg:
        db.session.add(new_msg)
        db.session.commit()
        print(f"[DEBUG] SAVED msg id={new_msg.id} from={new_msg.sender_sid} to={new_msg.receiver_sid} text={new_msg.text}")
        try:
            emit('message_ack', {'status': 'saved', 'id': new_msg.id}, room=request.sid)
        except Exception as _:
            print('[DEBUG] failed to emit ack to', request.sid)

@socketio.on('clear_my_chat')
def clear_chat():
    # ลบเฉพาะฝั่งผู้ใช้(ใน DB และฝั่งแอดมินอยู่ครบ)
    Message.query.filter(
        (Message.sender_sid == request.sid)
    ).update({Message.user_deleted: True})
    db.session.commit()
    emit('clear_screen')


@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in admins: admins.remove(request.sid)
    users.pop(request.sid, None)
#--- เพิ่มฟังก์ชันตรวจสอบสถานะแอดมินและระบบแจ้งเตือน ---

@socketio.on('join')
def handle_join():
    # ... โค้ดเดิม ...
    
    # แจ้งเตือนแอดมินทุกคนเมื่อมีคนใหม่เข้ามา
    if request.sid not in admins:
        for a_sid in admins:
            emit('sys_msg', {'msg': f"🔔 {nick} เข้าสู่ระบบแชทแล้ว"}, room=a_sid)

@socketio.on('message')
def handle_message(data):
    msg_text = data.get('text', '').strip()
    target_sid = data.get('target_sid')
    
    if not msg_text: return

    # ปรับปรุงระบบ Login ให้รักษาเซสชันได้ดีขึ้น
    if msg_text == f"/login {ADMIN_PASS}":
        admins.add(request.sid)
        users[request.sid] = f"ADMIN-{len(admins)}"
        emit('admin_status', {'is_admin' : True})
        emit('sys_msg', {'msg': "✅ คุณเป็นแอดมินแล้ว ระบบจะแจ้งเตือนเมื่อมีข้อความเข้า"})
        return

    new_msg = None
    if request.sid not in admins:
        new_msg = Message(sender_sid=request.sid, receiver_sid="ADMINS", sender_name=users[request.sid], text=msg_text)
        
        # แจ้งเตือนแอดมินแบบ Real-time
        if not admins:
            emit('sys_msg', {'msg': "ขณะนี้ไม่มีแอดมินออนไลน์ ข้อความของคุณจะถูกฝากไว้ในระบบ"})
        else:
            for a_sid in admins:
                # ส่งทั้งข้อความและเสียงแจ้งเตือน (ถ้าฝั่งเครื่องแอดมินทำไว้)
                emit('new_msg', {'user': users[request.sid], 'text': msg_text, 'from_sid': request.sid}, room=a_sid)
                emit('sys_msg', {'msg': "📩 มีข้อความใหม่จากลูกค้า!"}, room=a_sid)
        
        emit('new_msg', {'user': "คุณ", 'text': msg_text}, room=request.sid)
    
    # ... ส่วนของการบันทึก DB (เหมือนเดิม) ...

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in admins:
        admins.remove(sid)
        # แจ้งแอดมินที่เหลือว่ามีคนหลุด
        for a_sid in admins:
            emit('sys_msg', {'msg': f"⚠️ แอดมิน {users.get(sid)} ออกจากระบบ"}, room=a_sid)
    users.pop(sid, None)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    is_production = os.environ.get('ENVIRONMENT', 'development') == 'production'
    # Disable the reloader to avoid the server starting twice (which can cause WinError 10048)
    socketio.run(app, host='0.0.0.0', port=port, debug=not is_production, use_reloader=False)