import { Api, type Admission } from "./api";

type Events = {
  status: (text: string) => void;
  result: (text: string) => void;
  changed: () => void;
  ended: () => void;
};
/** One explicit session. No reconnect or microphone restart without another user gesture. */
export class Voice {
  private socket?: WebSocket;
  private context?: AudioContext;
  private stream?: MediaStream;
  private capture?: AudioWorkletNode;
  private source?: MediaStreamAudioSourceNode;
  private closed = false;
  private generation = 0;
  private sequence = 0;
  private outputSequence = 0;
  private mutedPlayback = false;
  private nextPlayback = 0;
  private sources = new Set<AudioBufferSourceNode>();
  private heartbeat?: ReturnType<typeof setInterval>;
  private timeout?: ReturnType<typeof setTimeout>;
  simulation = false;
  ready = false;
  constructor(
    private api: Api,
    private events: Events,
  ) {}
  async start() {
    try {
      // Create/resume in the click gesture so browser autoplay policy permits later PCM playback.
      this.context = new AudioContext({ sampleRate: 16000 });
      await this.context.resume();
      if (this.closed) return;
      const admission = await this.api.request<Admission>("sessions", "POST", {
        mode: "personal",
        microphoneConsent: true,
        locale: "fr-FR",
      });
      if (this.closed) return;
      this.simulation = admission.simulation;
      const url = new URL(admission.connectionUrl);
      if (
        url.protocol !== "wss:" &&
        !(
          url.protocol === "ws:" &&
          ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)
        )
      )
        throw new Error("Adresse vocale non sécurisée.");
      const ws = (this.socket = new WebSocket(url));
      ws.binaryType = "arraybuffer";
      this.timeout = setTimeout(
        () => this.fail("Le service vocal ne répond pas."),
        15000,
      );
      ws.onopen = () =>
        ws.send(
          JSON.stringify({
            type: "session.bootstrap",
            protocolVersion: "1.0",
            runtimeSessionId: admission.runtimeSessionId,
            ticket: admission.ticket,
            inputFormat: "pcm16-16000-mono",
          }),
        );
      ws.onmessage = (event) => {
        void this.message(event.data).catch((error) =>
          this.fail(
            error instanceof DOMException && error.name === "NotAllowedError"
              ? "Accès au microphone refusé. Autorisez-le dans votre navigateur pour réessayer."
              : "Le flux vocal est indisponible ou invalide.",
          ),
        );
      };
      ws.onerror = () => this.fail("Connexion vocale impossible.");
      ws.onclose = () => {
        if (!this.closed)
          this.fail("Session vocale terminée. Vous pouvez vous reconnecter.");
      };
    } catch (error) {
      if (!this.closed)
        this.fail(
          error instanceof Error ? error.message : "Microphone indisponible.",
        );
    }
  }
  private send(value: object) {
    if (this.socket?.readyState === WebSocket.OPEN)
      this.socket.send(JSON.stringify(value));
  }
  private async message(raw: string | ArrayBuffer) {
    if (this.closed) return;
    if (raw instanceof ArrayBuffer) {
      this.play(raw);
      return;
    }
    const event = JSON.parse(raw);
    if (event.type === "session.ready") {
      clearTimeout(this.timeout);
      if (
        event.inputFormat !== "pcm16-16000-mono" ||
        event.outputFormat !== "pcm16-16000-mono" ||
        event.simulation !== this.simulation
      )
        throw new Error("Protocole incompatible.");
      this.generation = event.generation;
      this.ready = true;
      this.heartbeat = setInterval(
        () => this.send({ type: "session.heartbeat" }),
        20000,
      );
      if (this.simulation) {
        this.events.status(
          "Voix simulée : aucun microphone activé. Saisissez un tour de test.",
        );
      } else {
        await this.microphone();
      }
    } else if (event.type === "session.error") {
      this.fail(`Le service vocal a refusé la session (${event.code}).`);
    } else if (event.type === "playback.stopped") {
      this.stopPlayback();
      this.generation = event.generation;
      this.mutedPlayback = false;
    } else if (event.type === "speech.result") {
      if (event.generation < this.generation) return;
      if (event.generation > this.generation) this.stopPlayback();
      this.generation = event.generation;
      this.events.result(event.text ?? "Résultat reçu du serveur.");
    } else if (
      event.type === "turn.finalized" ||
      event.type === "tool.result"
    ) {
      this.events.changed();
      if (this.simulation)
        this.events.status(
          "Tour de test enregistré par le backend. Microphone inactif.",
        );
    }
  }
  private async microphone() {
    if (!navigator.mediaDevices?.getUserMedia)
      throw new Error("Microphone non pris en charge.");
    this.events.status("Autorisez le microphone pour commencer.");
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
      video: false,
    });
    if (this.closed) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }
    this.stream = stream;
    stream.getTracks().forEach((track) => {
      track.onended = () => this.fail("Le microphone a été déconnecté.");
    });
    const context = this.context!;
    await context.audioWorklet.addModule("/pcm-capture.js");
    if (this.closed) return;
    this.source = context.createMediaStreamSource(stream);
    this.capture = new AudioWorkletNode(context, "koyori-capture");
    this.capture.port.onmessage = ({ data }: MessageEvent<ArrayBuffer>) => {
      const ws = this.socket;
      if (
        this.closed ||
        this.mutedPlayback ||
        ws?.readyState !== WebSocket.OPEN
      )
        return;
      if (ws.bufferedAmount > 64000) {
        this.fail("Réseau trop lent : le microphone a été arrêté.");
        return;
      }
      const frame = new ArrayBuffer(data.byteLength + 8);
      const view = new DataView(frame);
      view.setUint32(0, this.sequence++, true);
      view.setUint32(4, this.generation, true);
      const samples = new Int16Array(data);
      samples.forEach((sample, index) =>
        view.setInt16(8 + index * 2, sample, true),
      );
      ws.send(frame);
    };
    this.source.connect(this.capture);
    // Worklet has silent output; connect it to keep processing without microphone feedback.
    this.capture.connect(context.destination);
    this.events.status(
      "Microphone actif — votre voix est transmise au service vocal.",
    );
  }
  private play(raw: ArrayBuffer) {
    if (raw.byteLength < 10 || raw.byteLength > 6408 || raw.byteLength % 2)
      throw new Error("PCM invalide.");
    const view = new DataView(raw);
    const sequence = view.getUint32(0, true),
      generation = view.getUint32(4, true);
    if (sequence !== this.outputSequence++)
      throw new Error("Séquence audio invalide.");
    if (generation !== this.generation || this.mutedPlayback) return;
    const context = this.context!;
    if (this.nextPlayback - context.currentTime > 2) {
      this.interrupt();
      return;
    }
    const buffer = context.createBuffer(1, (raw.byteLength - 8) / 2, 16000);
    const samples = buffer.getChannelData(0);
    for (let i = 0; i < samples.length; i++)
      samples[i] = view.getInt16(8 + i * 2, true) / 32768;
    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(context.destination);
    this.sources.add(source);
    source.onended = () => {
      this.sources.delete(source);
      source.disconnect();
    };
    this.nextPlayback = Math.max(this.nextPlayback, context.currentTime);
    source.start(this.nextPlayback);
    this.nextPlayback += buffer.duration;
  }
  submit(text: string) {
    if (!this.ready || !this.simulation || !text.trim()) return;
    this.send({
      type: "turn.final",
      turnId: crypto.randomUUID().replaceAll("-", ""),
      text: text.trim(),
    });
  }
  interrupt() {
    if (this.mutedPlayback) return;
    this.mutedPlayback = true;
    this.stopPlayback();
    this.send({ type: "playback.interrupt" });
  }
  private stopPlayback() {
    this.sources.forEach((source) => {
      source.stop();
      source.disconnect();
    });
    this.sources.clear();
    this.nextPlayback = 0;
  }
  private fail(message: string) {
    if (this.closed) return;
    this.events.status(message);
    this.close();
  }
  close() {
    if (this.closed) return;
    this.closed = true;
    this.ready = false;
    clearInterval(this.heartbeat);
    clearTimeout(this.timeout);
    this.send({ type: "session.close" });
    if (this.socket) {
      this.socket.onopen = null;
      this.socket.onmessage = null;
      this.socket.onerror = null;
      this.socket.onclose = null;
      this.socket.close();
    }
    this.stream?.getTracks().forEach((track) => {
      track.onended = null;
      track.stop();
    });
    this.capture?.disconnect();
    this.source?.disconnect();
    this.stopPlayback();
    void this.context?.close();
    this.events.ended();
  }
}
