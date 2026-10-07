import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

test.use({ trace: "off", screenshot: "off", video: "off" });

test("Docker backend persists browser edits and admits a simulated voice turn", async ({
  page,
  request,
}, testInfo) => {
  test.skip(
    process.env.KOYORI_WEB_LIVE !== "1",
    "Opt-in integration requires running local Docker backend.",
  );
  test.setTimeout(90000);
  // Keep credentials out of reports, console output and retained traces.
  const localPython = (source: string, ...args: string[]) =>
    execFileSync(
      "docker",
      [
        "compose",
        ...(process.env.KOYORI_WEB_COMPOSE_ENV
          ? ["--env-file", process.env.KOYORI_WEB_COMPOSE_ENV]
          : []),
        "run",
        "--rm",
        "--no-deps",
        "demo",
        "python",
        "-c",
        source,
        ...args,
      ],
      {
        cwd: resolve("../.."),
        encoding: "utf8",
        stdio: ["ignore", "pipe", "pipe"],
      },
    ).trim();
  const principal = `web-test-${crypto.randomUUID()}`;
  const token = localPython(
    "import sys; from koyori.demo import token; from koyori.config import Settings; print(token(Settings.from_env(), sys.argv[1]))",
    principal,
  );
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    "Idempotency-Key": crypto.randomUUID(),
  };
  const homeResponse = await request.post("/v1/households", {
    headers,
    data: { name: `Test interface ${testInfo.project.name} ${Date.now()}` },
  });
  expect(homeResponse.status()).toBe(201);
  const home = await homeResponse.json();
  headers["X-Household-Id"] = home.id;
  headers["Idempotency-Key"] = crypto.randomUUID();
  const memoryResponse = await request.post("/v1/memories", {
    headers,
    data: {
      kind: "preference",
      key: "drink",
      text: "Préférence synthétique de recette",
    },
  });
  expect(memoryResponse.status()).toBe(201);
  const memory = await memoryResponse.json();
  async function login() {
    await page.goto("/");
    await page.getByLabel("Jeton d’accès Koyori").fill(token);
    await page
      .getByRole("button", { name: "Se connecter", exact: true })
      .click();
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "Bienvenue",
    );
    await expect(page.getByText("Chargement du foyer…")).toHaveCount(0);
  }
  await login();
  await page.getByRole("button", { name: "Confier une demande" }).click();
  await page
    .getByLabel("Votre demande")
    .fill("Prépare un résumé de mes préférences");
  await page.getByRole("button", { name: "Confier à Koyori" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByText("Prépare un résumé de mes préférences", { exact: true }),
  ).toBeVisible();
  await page.evaluate(() => {
    location.hash = "memory";
  });
  await page
    .getByRole("button", { name: /Préférence synthétique de recette/ })
    .click();
  await page
    .getByLabel("Ce que vous souhaitez retenir")
    .fill("Préférence corrigée par le navigateur");
  await page.getByRole("button", { name: "Enregistrer la correction" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const persisted = await request.get(`/v1/memories/${memory.id}`, { headers });
  expect((await persisted.json()).text).toBe(
    "Préférence corrigée par le navigateur",
  );
  await page.reload();
  await login();
  await expect(
    page.getByText("Prépare un résumé de mes préférences", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Démarrer la voix" }).click();
  await expect(page.getByText(/Voix simulée : aucun microphone/)).toBeVisible();
  await page
    .getByLabel("Tour vocal simulé (texte de test)")
    .fill("Rappelle mes habitudes de la maison");
  await page.getByRole("button", { name: "Envoyer le tour de test" }).click();
  await expect(page.getByText(/Tour de test enregistré/)).toBeVisible();
  await expect(
    page.getByText("Rappelle mes habitudes de la maison", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Arrêter la voix" }).click();

  const budget = {
    schemaVersion: "1.0",
    currency: "EUR",
    limitMinor: 10000,
    perActionMinor: 10000,
    enabled: true,
    approvalRequired: true,
  };
  const grant = JSON.parse(
    localPython(
      "import json, sys; from koyori.demo import step_up; from koyori.config import Settings; print(json.dumps(step_up(Settings.from_env(), sys.argv[3], sys.argv[1], 'PUT /v1/budget', json.loads(sys.argv[2]), 0, 'http://api:8080')))",
      home.id,
      JSON.stringify(budget),
      principal,
    ),
  ).grant;
  const budgetResult = await request.put("/v1/budget", {
    headers: {
      ...headers,
      "Idempotency-Key": crypto.randomUUID(),
      "If-Match": '\"0\"',
      "X-Step-Up-Grant": grant,
    },
    data: budget,
  });
  expect(budgetResult.status()).toBe(200);
  const connection = await request.post("/v1/connections/simulated", {
    headers: { ...headers, "Idempotency-Key": crypto.randomUUID() },
    data: {},
  });
  expect(connection.status()).toBe(201);
  await page.getByRole("button", { name: "Confier une demande" }).click();
  await page.getByLabel("Votre demande").fill("Prépare les courses à 23 h");
  await page.getByRole("button", { name: "Confier à Koyori" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect
    .poll(
      async () => {
        const response = await request.get("/v1/goals", { headers });
        return (await response.json()).items.find(
          (item: { goal: string }) =>
            item.goal === "Prépare les courses à 23 h",
        )?.status;
      },
      { timeout: 30000 },
    )
    .toBe("WAITING_APPROVAL");
  await page.getByRole("button", { name: "Actualiser", exact: true }).click();
  await page
    .getByRole("button", {
      name: /Votre accord est attendu Prépare les courses/,
    })
    .click();
  await page.getByRole("button", { name: "Voir le panier" }).click();
  await page
    .getByRole("button", { name: "Vérifier mon identité pour approuver" })
    .click();
  const nonce = await page.locator(".identity-nonce").textContent();
  const proof = localPython(
    "import sys; from koyori.demo import token; from koyori.config import Settings; print(token(Settings.from_env(), sys.argv[2], nonce=sys.argv[1]))",
    nonce!,
    principal,
  );
  await page
    .getByLabel("Preuve d’identité récente (jeton ID lié au nonce)")
    .fill(proof);
  await page
    .getByRole("button", { name: "Approuver ce panier", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect
    .poll(
      async () => {
        const response = await request.get("/v1/goals", { headers });
        return (await response.json()).items.find(
          (item: { goal: string }) =>
            item.goal === "Prépare les courses à 23 h",
        )?.actions[0]?.status;
      },
      { timeout: 30000 },
    )
    .toBe("CONFIRMED");
});
