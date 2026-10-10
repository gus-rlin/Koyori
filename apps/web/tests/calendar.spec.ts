import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const household = {
  id: "home-a",
  rev: 1,
  name: "Maison test",
  timeZone: "Europe/Paris",
};
const google = {
  id: "google-a",
  rev: 1,
  provider: "google-calendar",
  mode: "real",
  active: true,
  capabilities: ["calendar.read", "calendar.write"],
  account: "alex@example.invalid",
  calendarIds: ["alex@example.invalid"],
};
// Server-side request_hash of {"calendarIds":["primary"]} with no revision.
const AUTHORIZE_HASH =
  "720f2e47070adccd5878e2d6e804c8f593e3fcfdedc2dbc61280742490995cc6";

type Proposal = Record<string, unknown> & { id: string; rev: number };
type Sent = {
  path: string;
  method: string;
  body: unknown;
  headers: Record<string, string>;
};

/** Calendar endpoints of the backend contract; no Google account is involved. */
async function mockCalendar(
  page: Page,
  {
    connected = true,
    writable = true,
    truncated = false,
    loseFirstDecision = false,
  }: {
    connected?: boolean;
    writable?: boolean;
    truncated?: boolean;
    loseFirstDecision?: boolean;
  } = {},
) {
  const sent: Sent[] = [];
  const state = {
    connections: connected
      ? [
          {
            ...google,
            capabilities: writable ? google.capabilities : ["calendar.read"],
          },
        ]
      : [],
    proposals: [] as Proposal[],
  };
  const now = Math.floor(Date.now() / 1000);
  state.proposals.push({
    id: "proposal-a",
    rev: 1,
    origin: "assistant",
    status: "PENDING",
    title: "Récupérer le colis",
    startAt: now + 86400,
    endAt: now + 86400 + 1800,
    location: "Relais du marché",
    notes: null,
    createdAt: now,
  });
  await page.route("**/v1/**", async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname.slice(4);
    const json = (value: unknown, status = 200) =>
      route.fulfill({ json: value, status });
    if (req.method() !== "GET")
      sent.push({
        path,
        method: req.method(),
        body: req.postDataJSON(),
        headers: req.headers(),
      });
    if (path === "households") return json({ items: [household] });
    if (path === "connections") return json({ items: state.connections });
    if (path === "agenda")
      return json({
        items: state.connections.length
          ? [
              {
                id: "evt-1",
                connectionId: google.id,
                title: "Café avec Sam",
                startAt: now + 60,
                endAt: now + 3600,
                allDay: false,
              },
            ]
          : [],
        truncated,
      });
    if (path === "calendar-proposals" && req.method() === "GET")
      return json({ items: state.proposals });
    if (path === "calendar-proposals") {
      const created = {
        id: `proposal-${state.proposals.length + 1}`,
        rev: 1,
        origin: "person",
        status: "PENDING",
        createdAt: now,
        ...req.postDataJSON(),
      };
      state.proposals.push(created);
      return json(created, 201);
    }
    const decision = path.match(/^calendar-proposals\/([^/]+)\/decision$/);
    if (decision) {
      const item = state.proposals.find((p) => p.id === decision[1])!;
      const replay = sent.find(
        (s, i) =>
          i < sent.length - 1 &&
          s.headers["idempotency-key"] === req.headers()["idempotency-key"],
      );
      if (replay) return json(item);
      expect(req.headers()["if-match"]).toBe(`"${item.rev}"`);
      Object.assign(item, {
        rev: item.rev + 1,
        status:
          req.postDataJSON().decision === "approve" ? "APPROVED" : "REJECTED",
      });
      if (loseFirstDecision) {
        // Applied by the server, but the response never reaches the browser.
        loseFirstDecision = false;
        return route.abort();
      }
      return json(item);
    }
    if (path === "auth/step-up")
      return json(
        { id: "challenge-a", nonce: "nonce-a", expiresAt: now + 300 },
        201,
      );
    if (path === "auth/step-up/challenge-a/complete")
      return json({ grant: "grant-a" });
    if (path === "connections/google-calendar/authorize") {
      state.connections = [google];
      return json(
        {
          id: google.id,
          authorizationUrl:
            "https://accounts.google.com/o/oauth2/v2/auth?state=fixture",
        },
        201,
      );
    }
    return json({ items: [] });
  });
  return sent;
}
async function login(page: Page) {
  await page.goto("/");
  await page.getByLabel("Jeton d’accès Koyori").fill("test-access");
  await page.getByRole("button", { name: "Se connecter", exact: true }).click();
  await expect(page.getByText("Chargement du foyer…")).toHaveCount(0);
}
async function navigate(page: Page, hash: string) {
  await page.evaluate((hash) => {
    location.hash = hash;
  }, hash);
}

test.describe("Google Agenda", () => {
  test.use({ timezoneId: "America/Los_Angeles" });

  test("today's panel and agenda show synced events and an assistant proposal awaits consent", async ({
    page,
  }) => {
    const sent = await mockCalendar(page);
    await login(page);
    const panel = page.getByRole("region", {
      name: "Votre agenda aujourd’hui",
    });
    await expect(panel.getByText("Café avec Sam")).toBeVisible();
    await panel.getByRole("button", { name: "1 ajout à confirmer" }).click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Agenda");
    const card = page
      .getByRole("article")
      .filter({ hasText: "Récupérer le colis" });
    await expect(card.getByText("Proposé par Koyori")).toBeVisible();
    expect(sent.filter((s) => s.path.includes("decision"))).toEqual([]);
    await card.getByRole("button", { name: "Ajouter à mon agenda" }).click();
    await expect(page.getByText("Ajout en cours")).toBeVisible();
    expect(sent.at(-1)).toMatchObject({
      path: "calendar-proposals/proposal-a/decision",
      body: { decision: "approve" },
    });
  });

  test("a new event is placed in the household timezone across a daylight-saving change", async ({
    page,
  }) => {
    const sent = await mockCalendar(page);
    await login(page);
    await navigate(page, "agenda");
    await page.getByRole("button", { name: "Nouvel événement" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Titre").fill("Brunch");
    await dialog.getByLabel("Date").fill("2027-03-28");
    await dialog.getByLabel("Début").fill("09:00");
    await dialog.getByLabel("Fin").fill("10:30");
    await dialog.getByLabel("Lieu (facultatif)").fill("Chez Robin");
    await dialog
      .getByRole("button", { name: "Ajouter à Google Agenda" })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    // 28 March 2027 is the switch to summer time in Paris: 09:00 is UTC+2.
    expect(sent.find((s) => s.path === "calendar-proposals")?.body).toEqual({
      connectionId: google.id,
      title: "Brunch",
      startAt: Date.UTC(2027, 2, 28, 7, 0) / 1000,
      endAt: Date.UTC(2027, 2, 28, 8, 30) / 1000,
      location: "Chez Robin",
    });
    expect(sent.at(-1)).toMatchObject({
      path: "calendar-proposals/proposal-2/decision",
      body: { decision: "approve" },
    });
  });

  test("a time skipped by the spring change is refused and a repeated one takes its first occurrence", async ({
    page,
  }) => {
    const sent = await mockCalendar(page);
    await login(page);
    await navigate(page, "agenda");
    await page.getByRole("button", { name: "Nouvel événement" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Titre").fill("Garde");
    await dialog.getByLabel("Date").fill("2027-03-28");
    await dialog.getByLabel("Début").fill("02:30");
    await dialog.getByLabel("Fin").fill("04:00");
    const add = dialog.getByRole("button", { name: "Ajouter à Google Agenda" });
    await add.click();
    await expect(dialog.getByRole("alert")).toContainText("n’existe pas");
    expect(sent.filter((s) => s.path === "calendar-proposals")).toHaveLength(0);
    // 25 October 2026: 02:30 happens twice in Paris; the first is still UTC+2.
    await dialog.getByLabel("Date").fill("2026-10-25");
    await dialog.getByLabel("Fin").fill("03:30");
    await add.click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    expect(
      sent.find((s) => s.path === "calendar-proposals")?.body,
    ).toMatchObject({
      startAt: Date.UTC(2026, 9, 25, 0, 30) / 1000,
      endAt: Date.UTC(2026, 9, 25, 2, 30) / 1000,
    });
  });

  test("retrying after a lost approval approves the same proposal", async ({
    page,
  }) => {
    const sent = await mockCalendar(page, { loseFirstDecision: true });
    await login(page);
    await navigate(page, "agenda");
    await page.getByRole("button", { name: "Nouvel événement" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Titre").fill("Brunch");
    const add = dialog.getByRole("button", { name: "Ajouter à Google Agenda" });
    await add.click();
    await expect(page.getByRole("alert").first()).toBeVisible();
    await add.click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    expect(sent.filter((s) => s.path === "calendar-proposals")).toHaveLength(1);
    const decisions = sent.filter((s) => s.path.endsWith("/decision"));
    expect(decisions.map((s) => s.path)).toEqual([
      "calendar-proposals/proposal-2/decision",
      "calendar-proposals/proposal-2/decision",
    ]);
    expect(decisions[1].headers["idempotency-key"]).toBe(
      decisions[0].headers["idempotency-key"],
    );
  });

  test("an incomplete agenda scan is announced, not shown as empty", async ({
    page,
  }) => {
    await mockCalendar(page, { truncated: true });
    await login(page);
    await expect(page.getByText("Agenda incomplet").first()).toBeVisible();
    await navigate(page, "agenda");
    await expect(page.getByText("Agenda incomplet")).toBeVisible();
  });

  test("a read-only account cannot start an addition", async ({ page }) => {
    await mockCalendar(page, { writable: false });
    await login(page);
    await navigate(page, "agenda");
    await expect(
      page.getByRole("button", { name: "Nouvel événement" }),
    ).toBeDisabled();
    await expect(
      page.getByText("Reconnectez votre compte pour autoriser"),
    ).toBeVisible();
    await navigate(page, "services");
    await expect(page.getByText("Lecture seule")).toBeVisible();
  });

  test("connecting binds a fresh identity proof and completes Google consent in a popup", async ({
    page,
  }) => {
    const sent = await mockCalendar(page, { connected: false });
    await page.context().route("https://accounts.google.com/**", (route) =>
      route.fulfill({
        contentType: "text/html",
        body: "<title>Google</title><p>Consentement</p>",
      }),
    );
    await login(page);
    await navigate(page, "services");
    await page.getByRole("button", { name: "Connecter Google Agenda" }).click();
    const dialog = page.getByRole("dialog", {
      name: "Connecter Google Agenda",
    });
    await dialog.getByRole("button", { name: "Vérifier mon identité" }).click();
    expect(sent.at(-1)?.body).toEqual({
      operation: "POST /v1/connections/google-calendar/authorize",
      requestHash: AUTHORIZE_HASH,
    });
    await dialog.getByLabel("Preuve d’identité récente").fill("id-token");
    const popupOpened = page.waitForEvent("popup");
    await dialog.getByRole("button", { name: "Continuer avec Google" }).click();
    const popup = await popupOpened;
    await popup.waitForURL(/accounts\.google\.com/);
    const authorize = sent.find(
      (s) => s.path === "connections/google-calendar/authorize",
    )!;
    expect(authorize.body).toEqual({ calendarIds: ["primary"] });
    expect(authorize.headers["x-step-up-grant"]).toBe("grant-a");
    await expect(
      dialog.getByText("Terminez la connexion dans la fenêtre Google"),
    ).toBeVisible();
    await popup.close();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page.getByText("alex@example.invalid")).toBeVisible();
    await expect(page.getByText("Lecture et ajout d’événements")).toBeVisible();
  });

  test("a blocked popup leaves the identity proof unspent", async ({
    page,
  }) => {
    const sent = await mockCalendar(page, { connected: false });
    await page.addInitScript(() => {
      window.open = () => null;
    });
    await login(page);
    await navigate(page, "services");
    await page.getByRole("button", { name: "Connecter Google Agenda" }).click();
    const dialog = page.getByRole("dialog", {
      name: "Connecter Google Agenda",
    });
    await dialog.getByRole("button", { name: "Vérifier mon identité" }).click();
    await dialog.getByLabel("Preuve d’identité récente").fill("id-token");
    await dialog.getByRole("button", { name: "Continuer avec Google" }).click();
    await expect(dialog.getByRole("alert")).toContainText("pop-up");
    expect(sent.map((s) => s.path)).toEqual(["auth/step-up"]);
  });

  test("agenda screens are accessible in both themes and fit a narrow viewport", async ({
    page,
  }) => {
    await mockCalendar(page);
    await login(page);
    await page.emulateMedia({ reducedMotion: "reduce" });
    for (const hash of ["today", "agenda", "services"]) {
      await navigate(page, hash);
      await expect(page.getByText("Chargement du foyer…")).toHaveCount(0);
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    }
    await navigate(page, "agenda");
    await page.getByRole("button", { name: "Nouvel événement" }).click();
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await page.keyboard.press("Escape");
    await navigate(page, "settings");
    await page.getByRole("button", { name: "Thème sombre" }).click();
    await navigate(page, "agenda");
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await page.setViewportSize({ width: 320, height: 760 });
    for (const hash of ["today", "agenda", "services"]) {
      await navigate(page, hash);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
    }
    await page.screenshot({
      path: "test-results/agenda-mobile.png",
      fullPage: true,
    });
  });
});
