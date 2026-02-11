FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY database.py bot.py ./
COPY scripts/add-secret.sh /usr/local/bin/add-secret.sh
COPY scripts/remove-secret.sh /usr/local/bin/remove-secret.sh
COPY scripts/cleanup.sh /usr/local/bin/cleanup.sh
RUN chmod +x /usr/local/bin/add-secret.sh /usr/local/bin/remove-secret.sh /usr/local/bin/cleanup.sh
RUN apt-get update && apt-get install -y docker.io sqlite3 curl && rm -rf /var/lib/apt/lists/*
CMD ["python", "bot.py"]
