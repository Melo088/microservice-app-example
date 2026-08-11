# syntax=docker/dockerfile:1

FROM python:3.11-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim
RUN useradd --create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder /root/.local /home/app/.local
COPY main.py .
RUN chown -R app:app /home/app/.local
USER app
ENV PATH=/home/app/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

CMD ["python", "-u", "main.py"]