FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/* && pip install --no-cache-dir -r requirements.txt
COPY app /app/app
EXPOSE 8134
CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8134"]
