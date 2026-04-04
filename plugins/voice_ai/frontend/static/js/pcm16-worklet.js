class PCM16Worklet extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = new Float32Array(0);
    // Default: 20ms at 16kHz. The main thread will override this based on the
    // *actual* AudioContext sampleRate and configured frame_ms.
    this._targetFrames = 320;

    this.port.onmessage = (ev) => {
      const msg = ev.data || {};
      if (msg.type === "config") {
        const sr = Number(msg.sampleRate || 16000);
        const frameMs = Number(msg.frameMs || 20);
        const frames = Math.max(1, Math.round(sr * frameMs / 1000));
        this._targetFrames = frames;
      }
    };
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const chan = input[0];
    // Append to buffer
    const merged = new Float32Array(this._buffer.length + chan.length);
    merged.set(this._buffer, 0);
    merged.set(chan, this._buffer.length);
    this._buffer = merged;

    while (this._buffer.length >= this._targetFrames) {
      const frame = this._buffer.slice(0, this._targetFrames);
      this._buffer = this._buffer.slice(this._targetFrames);

      const pcm16 = new Int16Array(frame.length);
      for (let i = 0; i < frame.length; i++) {
        const s = Math.max(-1, Math.min(1, frame[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
    }

    return true;
  }
}

registerProcessor('pcm16-worklet', PCM16Worklet);
