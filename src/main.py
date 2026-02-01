import sys
sys.path.insert(0, '/app/src')

from app2 import app

# Expose `app` at module level so Gunicorn can import `app2:app`.
