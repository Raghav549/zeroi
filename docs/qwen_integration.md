
---

# 4. Docker and deployment

## `deploy/Dockerfile`

```dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    unzip \
    ffmpeg \
    imagemagick \
    pandoc \
    jq \
    adb \
    scrot \
    xdotool \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip && pip install .
RUN playwright install --with-deps chromium || true

EXPOSE 8000

CMD ["python", "-m", "zeroi.services.harness"]
