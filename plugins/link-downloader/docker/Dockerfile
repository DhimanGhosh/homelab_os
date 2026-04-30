FROM nandyalu/python-ffmpeg:latest

WORKDIR /app

RUN pip install --no-cache-dir flask

COPY app          /app/app
COPY templates    /app/templates
COPY static       /app/static
COPY app.py       /app/app.py

CMD ["python3", "/app/app.py"]
