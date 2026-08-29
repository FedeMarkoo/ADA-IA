FROM python:3.12-alpine
WORKDIR /app
COPY server.py .
COPY static ./static
RUN addgroup -S ada && adduser -S -G ada ada && mkdir -p /data && chown -R ada:ada /app /data
USER ada
ENV PORT=8088 DB_PATH=/data/test-manager.sqlite ADA_URL=http://ada:8080
EXPOSE 8088
CMD ["python", "server.py"]
