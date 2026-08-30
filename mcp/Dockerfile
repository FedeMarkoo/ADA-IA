FROM python:3.13-alpine

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY filesystem /app/filesystem
COPY web-search /app/web-search
COPY weather /app/weather
COPY google-calendar /app/google-calendar
COPY server.py /app/server.py
RUN addgroup -S ada && adduser -S -G ada ada
USER ada
EXPOSE 8000
ENTRYPOINT ["python", "/app/server.py"]
