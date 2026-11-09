FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY alembic.ini ./

ENV PYTHONPATH=/app
ENV PORT=8000
ENV HOST=0.0.0.0

EXPOSE 8000

CMD ["python3", "-m", "backend.app.start"]
