# dsfdsgdg

Anonymous chat app with admin support. Real-time messaging using Flask+SocketIO.

## Features

- 💬 **Real-time Chat** — Socket.IO powered instant messaging
- 🔐 **Anonymous & Private** — No registration needed
- 👨‍💼 **Admin Dashboard** — Manage conversations and reply to users
- 📊 **Message History** — Full message logs stored in SQLite/PostgreSQL
- 🎯 **Targeted Replies** — Admin can reply to specific users or broadcast to all
- 📱 **Responsive UI** — Works on desktop and mobile

## Quick Start

### Local Development

```bash
python3 src/app2.py
```

Visit http://127.0.0.1:5000

### Docker

```bash
docker build -t dsfdsgdg:latest .
docker run -p 5000:5000 dsfdsgdg:latest
```

### Gunicorn (Production)

```bash
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 app2:app
```

## Endpoints

| Endpoint | Description |
|----------|-------------|
| `/` | Landing page (auto-redirects to `/chat`) |
| `/chat` | User chat interface |
| `/admin` | Admin dashboard |
| `/health` | Health check |
| `/api/messages` | Message history (JSON) |

## Admin Features

### Login

1. Open the chat at http://127.0.0.1:5000/chat
2. Type: `/login adminworakanjajakub`
3. You'll see the admin panel

### Admin Dashboard (`/admin`)

- **User List** — See all connected users
- **Chat History** — View full conversation thread
- **Reply Mode** — Click reply to target specific users
- **Broadcast** — Send message to all users (without target)

### Change Admin Password

```bash
export ADMIN_PASS="your-secure-password"
python3 src/app2.py
```

## Environment Variables

```bash
ADMIN_PASS          # Admin login password (default: adminworakanjajakub)
DATABASE_URL        # Database connection string (default: sqlite:///chat.db)
SECRET_KEY          # Flask session key (default: dev-key-change-in-production)
PORT                # Server port (default: 5000)
ENVIRONMENT         # Set to 'production' to disable debug mode
```

## Railway Deployment

1. Connect your GitHub repo to Railway
2. Railway auto-detects `Procfile` and deploys
3. Set environment variables in Railway dashboard:
   - `ADMIN_PASS=your-password`
   - `DATABASE_URL=postgresql://...` (optional)
4. Deploy!

Your app will get a live URL like: `https://dsfdsgdg-production.up.railway.app`

## Architecture

- **Backend**: Flask + Flask-SocketIO + SQLAlchemy
- **Frontend**: HTML5 + Socket.IO client
- **Database**: SQLite (local) or PostgreSQL (production)
- **Deployment**: Docker + Railway

## Notes

- Application code is in the `src/` folder
- Templates are under `src/templates/`
- Procfile uses `PYTHONPATH` to import from `src/`
- Socket.IO enables real-time bidirectional communication
- Admin tokens are session-based and secure

---

Built with ❤️ for real-time chat.
