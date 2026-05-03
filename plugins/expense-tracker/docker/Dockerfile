FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        "fastapi>=0.115.0,<1" \
        "uvicorn>=0.30.0,<1" \
        "sqlalchemy>=2.0.0,<3" \
        "pydantic>=2.9.0,<3" \
        "jinja2>=3.1.2,<4" \
        "python-multipart>=0.0.9" \
        "apscheduler>=3.10.4,<4"

# app.py is copied as main.py to avoid shadowing the app/ package on import
COPY app.py /app/main.py
COPY app /app/app
COPY templates /app/templates
COPY static /app/static

EXPOSE 8161

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8161"]
