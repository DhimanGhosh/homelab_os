FROM python:3.11

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    unzip && \
    rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh && \
    ln -sf /usr/local/bin/deno /usr/bin/deno && \
    deno --version

RUN pip install --no-cache-dir flask requests "yt-dlp[default]"

COPY app.py /app/app.py
COPY templates /app/templates
COPY static /app/static

EXPOSE 8145

CMD ["/usr/local/bin/python3", "/app/app.py"]
