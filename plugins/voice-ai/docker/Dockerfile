FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y curl ffmpeg build-essential gcc g++ make cmake python3-dev git ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN git clone --depth 1 https://github.com/ggerganov/whisper.cpp /opt/whisper.cpp \
    && cmake -S /opt/whisper.cpp -B /opt/whisper.cpp/build -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_EXAMPLES=ON \
    && cmake --build /opt/whisper.cpp/build -j"$(nproc)" \
    && if [ -f /opt/whisper.cpp/build/bin/whisper-cli ]; then cp /opt/whisper.cpp/build/bin/whisper-cli /opt/whisper.cpp/whisper-cli; fi \
    && if [ ! -f /opt/whisper.cpp/whisper-cli ] && [ -f /opt/whisper.cpp/build/bin/main ]; then cp /opt/whisper.cpp/build/bin/main /opt/whisper.cpp/whisper-cli; fi \
    && test -f /opt/whisper.cpp/whisper-cli \
    && bash /opt/whisper.cpp/models/download-ggml-model.sh tiny.en \
    && test -f /opt/whisper.cpp/models/ggml-tiny.en.bin
COPY app /app/app
COPY static /app/static
COPY config.json /app/config.json
COPY start.sh /start.sh
RUN chmod +x /start.sh
EXPOSE 8124
CMD ["/start.sh"]
