import { test, expect, type Page, type Route } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const household = {
  id: "home-a",
  rev: 1,
  name: "Maison test",
  timeZone: "Europe/Paris",
};
const initialGoal = {
  id: "goal-a",
  rev: 4,
  goal: "Préparer ma journée",
  status: "READY",
  plan: null,
  stepStates: {},
  actions: [],
};
async function mockBackend(
  page: Page,
  extra?: (route: Route, path: string) => Promise<boolean>,
) {
  const goals = [{ ...initialGoal }];
  const memories = [
    {
      id: "memory-a",
      rev: 2,
      text: "Je préfère le thé",
      kind: "preference",
      visibility: "private",
      source: { kind: "declaration" },
    },
  ];
  await page.route("**/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.slice(4);
    if (extra && (await extra(route, path))) return;
    const req = route.request();
    expect(req.headers().authorization).toBe("Bearer test-access");
    if (path !== "households")
      expect(req.headers()["x-household-id"]).toBe(household.id);
    const json = (value: unknown) => route.fulfill({ json: value });
    if (path === "households") return json({ items: [household] });
    if (path === "goals" && req.method() === "POST") {
      expect(req.headers()["idempotency-key"]).toBeTruthy();
      goals.push({
        ...initialGoal,
        id: "goal-b",
        goal: req.postDataJSON().text,
      });
      return json(goals[1]);
    }
    if (path === "goals") return json({ items: goals });
    if (path === "memories") return json({ items: memories });
    if (path === "memories/memory-a" && req.method() === "PATCH") {
      expect(req.headers()["if-match"]).toBe('"2"');
      memories[0].text = req.postDataJSON().text;
      return json(memories[0]);
    }
    if (path.startsWith("goals/goal-a/")) {
      expect(req.headers()["if-match"]).toBe('"4"');
      goals[0].status = path.endsWith("pause") ? "PAUSED" : "READY";
      return json(goals[0]);
    }
    if (path === "connections")
      return json({
        items: [
          {
            id: "connection",
            rev: 1,
            provider: "commerce-simulator",
            mode: "simulated",
            active: true,
          },
        ],
      });
    return json({ items: [] });
  });
}
async function login(page: Page) {
  await page.goto("/");
  await page.getByLabel("Jeton d’accès Koyori").fill("test-access");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Bienvenue",
  );
  await expect(page.getByText("Chargement du foyer…")).toHaveCount(0);
}
async function navigate(page: Page, hash: string) {
  await page.evaluate((hash) => {
    location.hash = hash;
  }, hash);
}

test("connected views read and mutate authoritative state, without persisting credentials", async ({
  page,
}) => {
  await mockBackend(page);
  await login(page);
  await expect(
    page.getByText("Préparer ma journée", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Préparer ma journée/ }).click();
  await page.getByRole("button", { name: "Mettre en pause" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: /En pause Préparer ma journée/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Confier une demande" }).click();
  await page.getByLabel("Votre demande").fill("Organiser le week-end");
  await page.getByRole("button", { name: "Confier à Koyori" }).click();
  await expect(
    page.getByText("Organiser le week-end", { exact: true }),
  ).toBeVisible();
  await navigate(page, "memory");
  await page.getByRole("button", { name: /Je préfère le thé/ }).click();
  await page
    .getByLabel("Ce que vous souhaitez retenir")
    .fill("Je préfère le café");
  await page.getByRole("button", { name: "Enregistrer la correction" }).click();
  await expect(
    page.getByText("Je préfère le café", { exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
  await page.reload();
  await expect(page.getByLabel("Jeton d’accès Koyori")).toHaveValue("");
  await expect(page.getByText("Je préfère le café")).toHaveCount(0);
});

test("network failures never invent success and a retry keeps the idempotency key", async ({
  page,
}) => {
  const keys: string[] = [];
  await mockBackend(page, async (route, path) => {
    if (path !== "goals" || route.request().method() !== "POST") return false;
    keys.push(route.request().headers()["idempotency-key"]);
    await route.abort("failed");
    return true;
  });
  await login(page);
  await page.getByRole("button", { name: "Confier une demande" }).click();
  await page.getByLabel("Votre demande").fill("Une demande réseau");
  for (let i = 0; i < 2; i++) {
    await page.getByRole("button", { name: "Confier à Koyori" }).click();
    await expect(page.getByRole("dialog").getByRole("alert")).toContainText(
      "Connexion interrompue",
    );
  }
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
  await expect(
    page.getByText("Modification enregistrée par le serveur."),
  ).toHaveCount(0);
});

test("expired session clears private data and paginated lists load through empty pages", async ({
  page,
}) => {
  let expired = false;
  await mockBackend(page, async (route, path) => {
    if (path === "households") return false;
    if (expired) {
      await route.fulfill({ status: 401, json: { code: "INVALID_TOKEN" } });
      return true;
    }
    if (
      path === "memories" &&
      !new URL(route.request().url()).searchParams.has("cursor")
    ) {
      await route.fulfill({ json: { items: [], nextCursor: "next-page" } });
      return true;
    }
    return false;
  });
  await login(page);
  await navigate(page, "memory");
  await expect(page.getByText("Je préfère le thé")).toBeVisible();
  expired = true;
  await page.getByRole("button", { name: "Actualiser", exact: true }).click();
  await expect(page.getByLabel("Jeton d’accès Koyori")).toBeVisible();
  await expect(page.getByText("Je préfère le thé")).toHaveCount(0);
  await expect(page.getByRole("alert")).toContainText("session a expiré");
});

test("revision conflicts remain visible, and initial failure never falls back to fixtures", async ({
  page,
}) => {
  await mockBackend(page, async (route, path) => {
    if (!path.endsWith("/pause")) return false;
    await route.fulfill({ status: 412, json: { code: "VERSION_CONFLICT" } });
    return true;
  });
  await login(page);
  await page.getByRole("button", { name: /Préparer ma journée/ }).click();
  await page.getByRole("button", { name: "Mettre en pause" }).click();
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText(
    "données ont changé",
  );
  await page.getByRole("button", { name: "Fermer", exact: true }).click();
  await page.route("**/v1/goals", (route) => route.abort());
  await page.getByRole("button", { name: "Actualiser", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Connexion interrompue");
  await expect(
    page.getByText("Préparer ma journée", { exact: true }),
  ).toHaveCount(0);
  await expect(page.getByText("Bonjour Alex")).toHaveCount(0);
});

test("simulated voice uses ticket bootstrap and never opens a microphone", async ({
  page,
}) => {
  let microphoneCalls = 0;
  await page.exposeFunction("microphoneCalled", () => microphoneCalls++);
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = async () => {
      await (
        window as unknown as { microphoneCalled: () => Promise<void> }
      ).microphoneCalled();
      throw new Error("Unexpected microphone");
    };
  });
  await mockBackend(page, async (route, path) => {
    if (path !== "sessions") return false;
    expect(route.request().postDataJSON()).toMatchObject({
      mode: "personal",
      microphoneConsent: true,
    });
    await route.fulfill({
      json: {
        ticket: "test-ticket",
        runtimeSessionId: "session",
        connectionUrl: "ws://127.0.0.1:8099/ws",
        simulation: true,
      },
    });
    return true;
  });
  const received: Record<string, unknown>[] = [];
  await page.routeWebSocket("ws://127.0.0.1:8099/ws", (ws) => {
    ws.onMessage((raw) => {
      const value = JSON.parse(raw.toString());
      received.push(value);
      if (value.type === "session.bootstrap")
        ws.send(
          JSON.stringify({
            type: "session.ready",
            simulation: true,
            generation: 0,
            inputFormat: "pcm16-16000-mono",
            outputFormat: "pcm16-16000-mono",
          }),
        );
      if (value.type === "turn.final")
        ws.send(JSON.stringify({ type: "turn.finalized", taskId: "goal-a" }));
    });
  });
  await login(page);
  await page.getByRole("button", { name: "Démarrer la voix" }).click();
  await expect(page.getByText(/Voix simulée : aucun microphone/)).toBeVisible();
  await page
    .getByLabel("Tour vocal simulé (texte de test)")
    .fill("Préparer demain");
  await page.getByRole("button", { name: "Envoyer le tour de test" }).click();
  await expect(page.getByText(/Tour de test enregistré/)).toBeVisible();
  await page.getByRole("button", { name: "Arrêter la voix" }).click();
  await expect
    .poll(() => received.some((value) => value.type === "session.close"))
    .toBe(true);
  expect(received[0]).toMatchObject({
    type: "session.bootstrap",
    ticket: "test-ticket",
    protocolVersion: "1.0",
  });
  expect(microphoneCalls).toBe(0);
});

test("connected screens remain accessible in both themes and fit narrow viewports", async ({
  page,
}) => {
  await mockBackend(page);
  await login(page);
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const hash of [
    "today",
    "tasks",
    "memory",
    "routines",
    "services",
    "activity",
    "settings",
  ]) {
    await navigate(page, hash);
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  }
  await page.getByRole("button", { name: "Thème sombre" }).click();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.setViewportSize({ width: 320, height: 760 });
  for (const hash of ["today", "tasks", "memory", "services"]) {
    await navigate(page, hash);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  await page.screenshot({
    path: "test-results/connected-mobile.png",
    fullPage: true,
  });
});

test("approval binds a fresh identity proof and retries only the unresolved decision", async ({
  page,
}) => {
  const { createHash } = await import("node:crypto");
  let approvals = 0;
  const decisionKeys: string[] = [];
  await mockBackend(page, async (route, path) => {
    const json = async (value: unknown) => {
      await route.fulfill({ json: value });
      return true;
    };
    if (path === "goals")
      return json({
        items: [
          {
            ...initialGoal,
            status: "WAITING_APPROVAL",
            plan: {
              summary: "Panier à valider",
              steps: [{ stepId: "shop", capability: "commerce.groceries" }],
            },
            stepStates: {
              shop: { status: "WAITING_APPROVAL", quoteId: "quote-a" },
            },
          },
        ],
      });
    if (path === "quotes/quote-a")
      return json({
        id: "quote-a",
        rev: 1,
        expiresAt: 2000000000,
        conditions: {
          mode: "simulated",
          operation: "create",
          totalMinor: 1050,
          currency: "EUR",
          deliveryAt: 2000000000,
          lines: [{ sku: "bread", quantity: 2 }],
        },
      });
    if (path === "auth/step-up") {
      const canonical = JSON.stringify({
        body: { quoteId: "quote-a", schemaVersion: "1.0" },
        version: null,
      });
      expect(route.request().postDataJSON()).toMatchObject({
        operation: "POST /v1/approvals",
        requestHash: createHash("sha256").update(canonical).digest("hex"),
      });
      return json({
        id: "challenge-a",
        nonce: "test-nonce",
        expiresAt: 2000000000,
      });
    }
    if (path === "auth/step-up/challenge-a/complete") {
      expect(route.request().postDataJSON()).toEqual({
        identityProof: "test-id-proof",
      });
      return json({ grant: "test-grant" });
    }
    if (path === "approvals") {
      approvals++;
      expect(route.request().headers()["x-step-up-grant"]).toBe("test-grant");
      return json({ id: "approval-a" });
    }
    if (path === "goals/goal-a/decisions") {
      decisionKeys.push(route.request().headers()["idempotency-key"]);
      expect(route.request().headers()["if-match"]).toBe('"4"');
      expect(route.request().postDataJSON()).toEqual({
        stepId: "shop",
        approvalId: "approval-a",
      });
      if (decisionKeys.length === 1) {
        await route.abort();
        return true;
      }
      return json({ ...initialGoal, status: "READY" });
    }
    return false;
  });
  await login(page);
  await page.getByRole("button", { name: /Préparer ma journée/ }).click();
  await page.getByRole("button", { name: "Voir le panier" }).click();
  await expect(page.getByRole("dialog")).toContainText("10,50");
  await expect(page.getByRole("dialog")).toContainText("Panier simulé");
  await page
    .getByRole("button", { name: "Vérifier mon identité pour approuver" })
    .click();
  await page
    .getByLabel("Preuve d’identité récente (jeton ID lié au nonce)")
    .fill("test-id-proof");
  await page
    .getByRole("button", { name: "Approuver ce panier", exact: true })
    .click();
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText(
    "Connexion interrompue",
  );
  await page
    .getByRole("button", { name: "Approuver ce panier", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(approvals).toBe(1);
  expect(decisionKeys).toHaveLength(2);
  expect(decisionKeys[0]).toBe(decisionKeys[1]);
});

test.describe("review regressions", () => {
  test.use({ timezoneId: "America/Los_Angeles" });

  test("server timestamps use the household timezone for activity and quote dates", async ({
    page,
  }) => {
    await mockBackend(page, async (route, path) => {
      if (path === "activity") {
        await route.fulfill({
          json: {
            items: [
              {
                id: "winter-event",
                type: "koyori.task.changed.v1",
                aggregateId: "goal-a",
                occurredAt: Date.parse("2026-01-07T23:30:00Z") / 1000,
              },
            ],
          },
        });
        return true;
      }
      if (path === "goals") {
        await route.fulfill({
          json: {
            items: [
              {
                ...initialGoal,
                status: "WAITING_APPROVAL",
                plan: {
                  summary: "Panier à valider",
                  steps: [{ stepId: "shop", capability: "commerce.groceries" }],
                },
                stepStates: {
                  shop: { status: "WAITING_APPROVAL", quoteId: "quote-a" },
                },
              },
            ],
          },
        });
        return true;
      }
      if (path === "quotes/quote-a") {
        await route.fulfill({
          json: {
            id: "quote-a",
            rev: 1,
            expiresAt: Date.parse("2026-07-07T23:45:00Z") / 1000,
            conditions: {
              mode: "simulated",
              operation: "create",
              totalMinor: 1050,
              currency: "EUR",
              deliveryAt: Date.parse("2026-07-07T23:30:00Z") / 1000,
              lines: [{ sku: "bread", quantity: 2 }],
            },
          },
        });
        return true;
      }
      return false;
    });
    await login(page);
    await expect(page.locator(".timeline time")).toHaveText(
      "08/01/2026 00:30:00",
    );
    await page.getByRole("button", { name: /Préparer ma journée/ }).click();
    await page.getByRole("button", { name: "Voir le panier" }).click();
    await expect(page.getByRole("dialog")).toContainText(
      "Livraison : 08/07/2026 01:30:00",
    );
    await expect(page.getByRole("dialog")).toContainText(
      "Valable jusqu’au 08/07/2026 01:45:00",
    );
  });

  test("Escape during a pending mutation keeps the dialog open and its eventual error recoverable", async ({
    page,
  }) => {
    let release!: () => void;
    const pending = new Promise<void>((resolve) => {
      release = resolve;
    });
    let intercepted = false;
    await mockBackend(page, async (route, path) => {
      if (
        path !== "goals" ||
        route.request().method() !== "POST" ||
        intercepted
      )
        return false;
      intercepted = true;
      await pending;
      await route.abort("failed");
      return true;
    });
    await login(page);
    await page.getByRole("button", { name: "Confier une demande" }).click();
    await page
      .getByLabel("Votre demande")
      .fill("Demande avec réponse différée");
    await page.getByRole("button", { name: "Confier à Koyori" }).click();
    await expect.poll(() => intercepted).toBe(true);
    try {
      await page.keyboard.press("Escape");
      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(
        page.getByRole("button", { name: "Confier à Koyori" }),
      ).toBeDisabled();
    } finally {
      release();
    }
    await expect(page.getByRole("dialog").getByRole("alert")).toContainText(
      "Connexion interrompue",
    );
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Confier une demande" }),
    ).toBeFocused();
    await page.getByRole("button", { name: "Confier une demande" }).click();
    await page.getByLabel("Votre demande").fill("Demande après récupération");
    await page.getByRole("button", { name: "Confier à Koyori" }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(
      page.getByText("Demande après récupération", { exact: true }),
    ).toBeVisible();
  });
});
