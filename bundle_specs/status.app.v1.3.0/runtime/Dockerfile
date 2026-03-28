FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn[standard]
COPY app.py /app/app.py
COPY static /app/static
EXPOSE 8131
CMD ["python","-m","uvicorn","app:app","--host","0.0.0.0","--port","8131"]
