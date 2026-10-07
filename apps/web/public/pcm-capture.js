// Streaming mono resampling preserves phase across render quanta and emits 20 ms PCM16 frames.
class Capture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.phase = 0;
    this.sum = 0;
    this.count = 0;
    this.samples = [];
  }
  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;
    for (const value of channel) {
      this.sum += value;
      this.count++;
      this.phase += 16000;
      if (this.phase >= sampleRate) {
        this.phase -= sampleRate;
        const sample = Math.max(-1, Math.min(1, this.sum / this.count));
        this.samples.push(Math.round(sample * (sample < 0 ? 32768 : 32767)));
        this.sum = 0;
        this.count = 0;
        if (this.samples.length === 320) {
          const pcm = new Int16Array(this.samples);
          this.port.postMessage(pcm.buffer, [pcm.buffer]);
          this.samples = [];
        }
      }
    }
    return true;
  }
}
registerProcessor("koyori-capture", Capture);
