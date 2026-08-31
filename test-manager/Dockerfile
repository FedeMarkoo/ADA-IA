FROM python:3.12-alpine
WORKDIR /app
COPY server.py .
COPY static ./static
RUN addgroup -S -g 10001 ada && adduser -S -D -u 10001 -G ada ada && mkdir -p /data && chown -R ada:ada /app /data
USER ada
ENV PORT=8088 DB_PATH=/data/test-manager.sqlite ADA_URL=http://ada:8080
EXPOSE 8088
CMD ["python", "server.py"]
