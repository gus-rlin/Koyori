import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function go(page: Page, hash: string) {
  await page.goto(`/?demo=1#${hash}`);
}

test("overview is honest, responsive, and free of browser errors", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await go(page, "today");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Bonjour Alex",
  );
  await expect(page.getByText("Démonstration", { exact: true })).toBeVisible();
  await expect(page.locator(".welcome-image img")).toBeVisible();
  expect(
    await page
      .locator<HTMLImageElement>(".welcome-image img")
      .evaluate((image) => image.complete && image.naturalWidth > 0),
  ).toBe(true);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Faire le point" }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "Aucun microphone n’est activé",
  );
  await page.getByRole("button", { name: "Fermer", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Faire le point" }),
  ).toBeFocused();
  expect(errors).toEqual([]);
});

test("approval records a simulated decision without claiming a purchase", async ({
  page,
}) => {
  await go(page, "today");
  await page.getByRole("button", { name: "Voir le panier" }).click();
  await expect(page.getByRole("dialog")).toContainText("47,80 €");
  await page.getByRole("button", { name: "Approuver dans la démo" }).click();
  await expect(
    page.getByText("Votre accord est enregistré dans la démo."),
  ).toBeVisible();
  await expect(
    page.getByText("Aucun achat réel n’a été effectué."),
  ).toBeVisible();
  await page.getByRole("button", { name: /Les courses de la semaine/ }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "La confirmation commerçant reste indisponible",
  );
  await expect(page.getByRole("dialog")).toContainText("En cours");
});

test("decline pauses the request and cannot silently approve it", async ({
  page,
}) => {
  await go(page, "today");
  await page.getByRole("button", { name: "Voir le panier" }).click();
  await page.getByRole("button", { name: "Mettre le panier de côté" }).click();
  await expect(
    page.getByRole("button", { name: /Les courses de la semaine/ }),
  ).toContainText("En pause");
  await expect(
    page.getByRole("button", { name: "Voir le panier" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: /Les courses de la semaine/ }).click();
  await page.getByRole("button", { name: "Reprendre", exact: true }).click();
  await page.getByRole("button", { name: "Fermer", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Voir le panier" }),
  ).toBeVisible();
});

test("create, pause, resume and cancel a request", async ({ page }) => {
  await go(page, "tasks");
  await page
    .getByRole("button", { name: "Nouvelle demande", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "Que souhaitez-vous confier ?" })
    .fill("   ");
  await page.getByRole("button", { name: "Confier cette demande" }).click();
  await expect(page.getByRole("alert")).toContainText("au moins 5 caractères");
  await page
    .getByRole("textbox", { name: "Que souhaitez-vous confier ?" })
    .fill("Préparer notre départ samedi");
  await page.getByRole("button", { name: "Confier cette demande" }).click();
  await page
    .getByRole("button", { name: /Préparer notre départ samedi/ })
    .click();
  await page.getByRole("button", { name: "Mettre en pause" }).click();
  await expect(page.getByRole("dialog")).toContainText("En pause");
  await page.getByRole("button", { name: "Reprendre", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("En cours");
  await page.getByRole("button", { name: "Annuler la demande" }).click();
  await expect(page.getByRole("dialog")).toContainText("Annulé");
  await expect(
    page.getByRole("button", { name: "Reprendre", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Fermer", exact: true }).click();
  await page.getByRole("button", { name: "Annulées", exact: true }).click();
  await expect(page.locator(".task-card")).toHaveCount(1);
  await page.reload();
  await expect(
    page.getByRole("button", { name: /Préparer notre départ samedi/ }),
  ).toHaveCount(0);
});

test("memory can be searched, corrected and forgotten", async ({ page }) => {
  await go(page, "memory");
  await page
    .getByRole("textbox", { name: "Rechercher un souvenir" })
    .fill("introuvable");
  await expect(
    page.getByRole("heading", { name: "Aucun souvenir trouvé" }),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "Rechercher un souvenir" })
    .fill("chocolat");
  await page.getByRole("button", { name: "Corriger ce souvenir" }).click();
  await page
    .getByRole("textbox", { name: "Ce que vous souhaitez retenir" })
    .fill("Un thé sans sucre et une tartine.");
  await page.getByRole("button", { name: "Enregistrer la correction" }).click();
  await page
    .getByRole("textbox", { name: "Rechercher un souvenir" })
    .fill("thé");
  await expect(
    page.getByText("Un thé sans sucre et une tartine.", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Corriger ce souvenir" }).click();
  await page.getByRole("button", { name: "Oublier ce souvenir" }).click();
  await page.getByRole("button", { name: "Confirmer la suppression" }).click();
  await expect(
    page.getByRole("heading", { name: "Aucun souvenir trouvé" }),
  ).toBeVisible();
});

test("routine state and service limitations are explicit", async ({ page }) => {
  await go(page, "routines");
  const routine = page.getByRole("switch", { name: "Le point du matin" });
  await expect(routine).toBeChecked();
  await routine.click();
  await expect(routine).not.toBeChecked();
  await expect(page.getByText(/Aucun déclenchement réel/)).toBeVisible();
  await go(page, "services");
  await page
    .locator(".service-card")
    .filter({ has: page.getByRole("heading", { name: "Alexa", exact: true }) })
    .getByRole("button")
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "ne dispose pas encore d’une intégration Alexa",
  );
});

test("light and dark views meet automated accessibility checks", async ({
  page,
}) => {
  await go(page, "today");
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const mode of ["light", "dark"]) {
    if (mode === "dark")
      await page
        .getByRole("button", { name: "Activer le thème sombre" })
        .click();
    expect(
      (
        await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
    await page.screenshot({
      path: `test-results/overview-${test.info().project.name}-${mode}.png`,
      fullPage: true,
    });
  }
  await page.getByRole("button", { name: "Voir le panier" }).click();
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
});

test("mobile navigation and narrow layouts remain usable", async ({
  page,
}, info) => {
  await go(page, "today");
  if (info.project.name === "mobile") {
    await page.getByRole("button", { name: "Ouvrir la navigation" }).click();
    await page.getByRole("link", { name: "Ma mémoire" }).click();
    await expect(
      page.getByRole("heading", { name: "Ma mémoire" }),
    ).toBeVisible();
    await page.setViewportSize({ width: 320, height: 700 });
  }
  for (const hash of [
    "today",
    "tasks",
    "memory",
    "routines",
    "services",
    "settings",
    "activity",
  ]) {
    await go(page, hash);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
});
