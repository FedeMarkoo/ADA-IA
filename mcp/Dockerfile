FROM python:3.13-alpine

WORKDIR /app
COPY filesystem /app/filesystem
COPY web-search /app/web-search
COPY server.py /app/server.py
RUN addgroup -S ada && adduser -S -G ada ada
USER ada
EXPOSE 8000
ENTRYPOINT ["python", "/app/server.py"]
