FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Add src/ to PYTHONPATH so Gunicorn can import app2 module
ENV PYTHONPATH=/app/src:$PYTHONPATH
EXPOSE 5000
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:5000", "app2:app"]