import { test, expect, type Page } from "@playwright/test";

test.use({
  launchOptions: {
    args: [
      "--use-fake-device-for-media-stream",
      "--use-fake-ui-for-media-stream",
    ],
  },
  permissions: ["microphone"],
});
async function setup(page: Page) {
  await page.route("**/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/v1/households")
      return route.fulfill({
        json: {
          items: [
            { id: "audio-home", name: "Audio test", timeZone: "Europe/Paris" },
          ],
        },
      });
    if (path === "/v1/sessions")
      return route.fulfill({
        json: {
          simulation: false,
          connectionUrl: "ws://127.0.0.1:8099/ws",
          ticket: "audio-ticket",
          runtimeSessionId: "audio-session",
        },
      });
    return route.fulfill({ json: { items: [] } });
  });
  await page.goto("/");
  await page.getByLabel("Jeton d’accès Koyori").fill("test-audio");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Bienvenue",
  );
}
const ready = {
  type: "session.ready",
  simulation: false,
  generation: 0,
  inputFormat: "pcm16-16000-mono",
  outputFormat: "pcm16-16000-mono",
};

test("real browser audio graph emits framed PCM and stops tracks and playback on exit", async ({
  page,
}) => {
  const frames: Buffer[] = [];
  let closed = false;
  await page.addInitScript(() => {
    const state = window as unknown as {
      testStream: MediaStream;
      played: number;
      stopped: number;
    };
    state.played = 0;
    state.stopped = 0;
    const original = navigator.mediaDevices.getUserMedia.bind(
      navigator.mediaDevices,
    );
    navigator.mediaDevices.getUserMedia = async (options) => {
      state.testStream = await original(options);
      return state.testStream;
    };
    const start = AudioBufferSourceNode.prototype.start,
      stop = AudioBufferSourceNode.prototype.stop;
    AudioBufferSourceNode.prototype.start = function (...args) {
      state.played++;
      start.apply(this, args);
    };
    AudioBufferSourceNode.prototype.stop = function (...args) {
      state.stopped++;
      stop.apply(this, args);
    };
  });
  await page.routeWebSocket("ws://127.0.0.1:8099/ws", (ws) =>
    ws.onMessage((raw) => {
      if (typeof raw !== "string") {
        frames.push(Buffer.from(raw));
        return;
      }
      const value = JSON.parse(raw);
      if (value.type === "session.bootstrap") {
        ws.send(JSON.stringify(ready));
        ws.send(
          JSON.stringify({
            type: "speech.result",
            generation: 0,
            text: "Annonce sourcée du test",
          }),
        );
        for (let i = 0; i < 10; i++) {
          const pcm = Buffer.alloc(3208);
          pcm.writeUInt32LE(i, 0);
          ws.send(pcm);
        }
      }
      if (value.type === "playback.interrupt")
        ws.send(JSON.stringify({ type: "playback.stopped", generation: 1 }));
      if (value.type === "session.close") closed = true;
    }),
  );
  await setup(page);
  await page.getByRole("button", { name: "Démarrer la voix" }).click();
  await expect(page.getByText(/Microphone actif —/)).toBeVisible();
  await expect.poll(() => frames.length).toBeGreaterThan(2);
  expect(frames[0].length).toBe(648);
  expect(frames[0].readUInt32LE(0)).toBe(0);
  expect(frames[1].readUInt32LE(0)).toBe(1);
  expect(frames[0].readUInt32LE(4)).toBe(0);
  expect(
    await page.evaluate(() => (window as unknown as { played: number }).played),
  ).toBeGreaterThan(0);
  await page.getByRole("button", { name: "Interrompre la réponse" }).click();
  await expect
    .poll(() => frames.some((frame) => frame.readUInt32LE(4) === 1))
    .toBe(true);
  await page.getByRole("button", { name: "Arrêter la voix" }).click();
  await expect.poll(() => closed).toBe(true);
  expect(
    await page.evaluate(() =>
      (window as unknown as { testStream: MediaStream }).testStream
        .getTracks()
        .every((track) => track.readyState === "ended"),
    ),
  ).toBe(true);
  const finalCount = frames.length;
  await page.waitForTimeout(150);
  expect(frames.length).toBe(finalCount);
});

test("microphone denial closes the admitted socket without claiming to listen", async ({
  page,
}) => {
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = async () => {
      throw new DOMException("Denied", "NotAllowedError");
    };
  });
  let closed = false;
  await page.routeWebSocket("ws://127.0.0.1:8099/ws", (ws) =>
    ws.onMessage((raw) => {
      const value = JSON.parse(raw.toString());
      if (value.type === "session.bootstrap") ws.send(JSON.stringify(ready));
      if (value.type === "session.close") closed = true;
    }),
  );
  await setup(page);
  await page.getByRole("button", { name: "Démarrer la voix" }).click();
  await expect(
    page.getByText(
      "Accès au microphone refusé. Autorisez-le dans votre navigateur pour réessayer.",
    ),
  ).toBeVisible();
  await expect.poll(() => closed).toBe(true);
  await expect(
    page.getByRole("button", { name: "Démarrer la voix" }),
  ).toBeVisible();
});

test("late microphone permission after stop cannot restart capture", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const state = window as unknown as {
      allowMicrophone: () => void;
      testStream: MediaStream;
    };
    const original = navigator.mediaDevices.getUserMedia.bind(
      navigator.mediaDevices,
    );
    navigator.mediaDevices.getUserMedia = async (options) => {
      await new Promise<void>((resolve) => {
        state.allowMicrophone = resolve;
      });
      state.testStream = await original(options);
      return state.testStream;
    };
  });
  let audioFrames = 0;
  await page.routeWebSocket("ws://127.0.0.1:8099/ws", (ws) =>
    ws.onMessage((raw) => {
      if (typeof raw !== "string") {
        audioFrames++;
        return;
      }
      if (JSON.parse(raw).type === "session.bootstrap")
        ws.send(JSON.stringify(ready));
    }),
  );
  await setup(page);
  await page.getByRole("button", { name: "Démarrer la voix" }).click();
  await expect(
    page.getByText("Autorisez le microphone pour commencer."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Arrêter la voix" }).click();
  await page.evaluate(() =>
    (window as unknown as { allowMicrophone: () => void }).allowMicrophone(),
  );
  await expect
    .poll(() =>
      page.evaluate(() =>
        (window as unknown as { testStream?: MediaStream }).testStream
          ?.getTracks()
          .every((track) => track.readyState === "ended"),
      ),
    )
    .toBe(true);
  expect(audioFrames).toBe(0);
});
