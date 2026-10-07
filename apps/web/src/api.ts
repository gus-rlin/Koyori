export type Versioned = { id: string; rev: number };
export type Household = Versioned & { name: string; timeZone: string };
export type Goal = Versioned & {
  goal: string;
  status: string;
  planningMode?: string;
  plan?: {
    summary: string;
    clarification?: string;
    steps: { stepId: string; capability: string }[];
  };
  stepStates: Record<string, { status: string; quoteId?: string }>;
  actions: { id: string; status: string; mode: string; receipt?: unknown }[];
};
export type Memory = Versioned & {
  text: string;
  kind: string;
  visibility: string;
  source: { kind: string; id?: string };
};
export type Routine = Versioned & {
  text: string;
  paused: boolean;
  active: boolean;
  localTime: string;
  timeZone: string;
};
export type Connection = Versioned & {
  provider: string;
  mode: string;
  active: boolean;
  status?: string;
};
export type Activity = {
  id?: string;
  sequence?: number;
  type: string;
  aggregateId: string;
  occurredAt?: number;
};
export type Quote = Versioned & {
  expiresAt: number;
  conditions: {
    mode: string;
    operation: string;
    totalMinor: number;
    currency: string;
    deliveryAt: number;
    lines: { sku: string; quantity: number }[];
  };
};
export type Admission = {
  ticket: string;
  runtimeSessionId: string;
  connectionUrl: string;
  simulation: boolean;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
  ) {
    super(
      status === 401
        ? "Votre session a expiré. Reconnectez-vous."
        : status === 403
          ? "Vous n’avez pas accès à cette opération."
          : status === 409 || status === 412
            ? "Ces données ont changé. Actualisez avant de réessayer."
            : `Le serveur a refusé la demande (${code}).`,
    );
  }
}

/** Credentials live only in this instance. All HTTP traffic stays on the app origin. */
export class Api {
  private pending = new Map<string, string>();
  private controllers = new Set<AbortController>();
  private disposed = false;
  constructor(
    private token: string,
    readonly household = "",
  ) {}
  dispose() {
    this.disposed = true;
    this.token = "";
    this.pending.clear();
    this.controllers.forEach((controller) => controller.abort());
  }
  async request<T>(
    path: string,
    method = "GET",
    body?: unknown,
    revision?: number,
    grant?: string,
  ): Promise<T> {
    if (this.disposed) throw new Error("Session fermée.");
    const signature = JSON.stringify([path, method, body, revision]);
    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.token}`,
    };
    if (this.household) headers["X-Household-Id"] = this.household;
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (grant) headers["X-Step-Up-Grant"] = grant;
    if (revision !== undefined) headers["If-Match"] = `"${revision}"`;
    if (method !== "GET") {
      // Keep the same key after an ambiguous network failure: a retry cannot duplicate a write.
      const key = this.pending.get(signature) ?? crypto.randomUUID();
      this.pending.set(signature, key);
      headers["Idempotency-Key"] = key;
    }
    const controller = new AbortController();
    this.controllers.add(controller);
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(`/v1/${path}`, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal,
        cache: "no-store",
        redirect: "error",
      });
      const value = await response.json();
      if (!response.ok) {
        if (response.status < 500) this.pending.delete(signature);
        throw new ApiError(
          response.status,
          typeof value.code === "string" ? value.code : "HTTP_ERROR",
        );
      }
      this.pending.delete(signature);
      return value as T;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new Error(
        "Connexion interrompue. Le résultat peut avoir été enregistré ; réessayez la même opération pour le vérifier.",
      );
    } finally {
      clearTimeout(timer);
      this.controllers.delete(controller);
    }
  }
  async list<T>(path: string): Promise<T[]> {
    const items: T[] = [];
    let cursor: string | null = null;
    const seen = new Set<string>();
    do {
      const page: { items: T[]; nextCursor?: string | null } =
        await this.request(
          `${path}${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`,
        );
      items.push(...page.items);
      cursor = page.nextCursor ?? null;
      if (cursor && (seen.has(cursor) || seen.size >= 100))
        throw new Error(
          "La liste dépasse la limite de chargement. Réessayez plus tard.",
        );
      if (cursor) seen.add(cursor);
    } while (cursor);
    return items;
  }
}
export const objectPath = (resource: string, id: string) =>
  `${resource}/${encodeURIComponent(id)}`;
