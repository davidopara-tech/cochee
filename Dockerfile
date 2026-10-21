FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/scripts/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]