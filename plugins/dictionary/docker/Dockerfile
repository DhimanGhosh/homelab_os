FROM python:3.11-slim
WORKDIR /opt/offline-dictionary
COPY requirements.txt .
RUN apt-get update \
    && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt
COPY app /opt/offline-dictionary/app
COPY static /opt/offline-dictionary/static
RUN mkdir -p /opt/offline-dictionary/data /opt/offline-dictionary/data/nltk_data
EXPOSE 8133
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8133"]
