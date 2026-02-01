# dsfdsgdg

Quick start
-----------

Run locally (development):

```bash
python3 src/app2.py
```

Visit http://127.0.0.1:5000/

Run with Gunicorn (as used in `Procfile` / Docker):

```bash
# from repository root
gunicorn --worker-class eventlet -w 1 --chdir src main:app
```

Docker build & run:

```bash
docker build -t dsfdsgdg:latest .
docker run -p 5000:5000 dsfdsgdg:latest
```

Notes
-----
- Application code is in the `src/` folder. Templates are under `src/templates/`.
- `Procfile` and `Dockerfile` updated to run from `src/`.
