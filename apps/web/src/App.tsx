import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import {
  WaveformIcon,
  HouseLineIcon,
  SparkleIcon,
  BookOpenIcon,
  ArrowClockwiseIcon,
  PlugsConnectedIcon,
  GearSixIcon,
  ListIcon,
  MicrophoneIcon,
  ArrowRightIcon,
  SunIcon,
  MoonIcon,
} from "@phosphor-icons/react";
import {
  Api,
  ApiError,
  objectPath,
  type Household,
  type Goal,
  type Memory,
  type Routine,
  type Connection,
  type Activity,
  type Quote,
} from "./api";
import { Dialog } from "./Dialog";
import { Empty } from "./components";
import { Voice } from "./voice";
import { QuoteApproval } from "./QuoteApproval";
import type { Page } from "./ui-types";
const Demo = lazy(() => import("./DemoApp"));
const pages = [
  { id: "today", label: "Aujourd’hui", icon: HouseLineIcon },
  { id: "tasks", label: "Mes demandes", icon: SparkleIcon },
  { id: "memory", label: "Ma mémoire", icon: BookOpenIcon },
  { id: "routines", label: "Routines", icon: ArrowClockwiseIcon },
  { id: "services", label: "Services", icon: PlugsConnectedIcon },
  { id: "activity", label: "Activité", icon: ListIcon },
  { id: "settings", label: "Réglages", icon: GearSixIcon },
] as const;
const statuses: Record<string, string> = {
  ACCEPTED: "Enregistrée",
  READY: "À traiter",
  RUNNING: "En cours",
  PLANNING: "Préparation du plan",
  WAITING_APPROVAL: "Votre accord est attendu",
  WAITING: "En attente",
  PAUSED: "En pause",
  SUCCEEDED: "Terminée",
  FAILED: "Échec",
  CANCELLED: "Annulée",
  CANCELLING: "Annulation en cours",
  NEEDS_ATTENTION: "À préciser",
};
const currentPage = () =>
  (pages.find((page) => page.id === location.hash.slice(1))?.id ??
    "today") as Page;
const message = (error: unknown) =>
  error instanceof Error ? error.message : "Opération indisponible.";
const dateTime = (value: number, timeZone: string) =>
  new Date(value * 1000).toLocaleString("fr-FR", { timeZone });
type Data = {
  goals: Goal[];
  memories: Memory[];
  routines: Routine[];
  connections: Connection[];
  activity: Activity[];
};
const empty: Data = {
  goals: [],
  memories: [],
  routines: [],
  connections: [],
  activity: [],
};
type Selection =
  | { kind: "goal"; item: Goal }
  | { kind: "memory"; item: Memory }
  | { kind: "quote"; item: Quote; goal: Goal; stepId: string }
  | { kind: "new" }
  | null;

export default function App() {
  return new URLSearchParams(location.search).get("demo") === "1" ? (
    <Suspense fallback={<p>Chargement de la démonstration…</p>}>
      <Demo />
    </Suspense>
  ) : (
    <ConnectedApp />
  );
}
function ConnectedApp() {
  const [token, setToken] = useState("");
  const [credentials, setCredentials] = useState("");
  const [households, setHouseholds] = useState<Household[]>([]);
  const [household, setHousehold] = useState<Household | null>(null);
  const [authError, setAuthError] = useState("");
  const [connecting, setConnecting] = useState(false);
  const loginApi = useRef<Api | null>(null);
  async function login(event: FormEvent) {
    event.preventDefault();
    if (connecting || loginApi.current || !token.trim()) return;
    setConnecting(true);
    setAuthError("");
    setHouseholds([]);
    setCredentials("");
    const supplied = token.trim();
    const client = (loginApi.current = new Api(supplied));
    try {
      const items = await client.list<Household>("households");
      setHouseholds(items);
      setCredentials(supplied);
      setToken("");
      if (items.length === 1) setHousehold(items[0]);
      if (!items.length)
        setAuthError("Aucun foyer accessible pour cette identité.");
    } catch (error) {
      setAuthError(message(error));
    } finally {
      client.dispose();
      loginApi.current = null;
      setConnecting(false);
    }
  }
  useEffect(() => () => loginApi.current?.dispose(), []);
  const logout = useCallback((reason = "") => {
    setCredentials("");
    setToken("");
    setHousehold(null);
    setHouseholds([]);
    setAuthError(reason);
  }, []);
  if (household && credentials)
    return (
      <Home
        key={household.id}
        token={credentials}
        household={household}
        logout={logout}
      />
    );
  return (
    <main className="connection-page">
      <a className="brand" href="/">
        {" "}
        <WaveformIcon size={32} /> koyori.
      </a>
      <h1>Retrouver votre maison</h1>
      <p>
        Connectez votre espace personnel au backend Koyori. Vos demandes et
        souvenirs restent enregistrés côté serveur.
      </p>
      <form onSubmit={login} className="connection-form">
        <label className="field-label" htmlFor="access-token">
          Jeton d’accès Koyori
        </label>
        <input
          id="access-token"
          type="password"
          autoComplete="off"
          spellCheck={false}
          required
          value={token}
          onChange={(event) => setToken(event.target.value)}
        />
        <p className="panel-note">
          Utilisez un jeton d’accès émis par votre environnement. Il reste en
          mémoire et sera oublié au rechargement.
        </p>
        <button className="primary-button" disabled={connecting}>
          {connecting ? "Connexion…" : "Se connecter"}
          <ArrowRightIcon size={18} />
        </button>
      </form>
      {authError && (
        <p role="alert" className="form-error">
          {authError}
        </p>
      )}
      {households.length > 0 && (
        <section aria-label="Choisir un foyer">
          <h2>Choisir votre foyer</h2>
          {households.map((item) => (
            <button
              className="light-button"
              key={item.id}
              onClick={() => setHousehold(item)}
            >
              {item.name}
            </button>
          ))}
        </section>
      )}
      <p className="panel-note">
        L’environnement Docker utilise des identités et fournisseurs simulés.
        Aucun accès Alexa natif.
      </p>
      <a className="text-button" href="/?demo=1">
        Explorer la démonstration sans connexion
      </a>
    </main>
  );
}
function Home({
  token,
  household,
  logout,
}: {
  token: string;
  household: Household;
  logout: (reason?: string) => void;
}) {
  // New instance for every mounted identity/household. StrictMode cleanup never reuses a disposed API.
  const apiRef = useRef<Api | null>(null);
  const [data, setData] = useState<Data>(empty);
  const [page, setPage] = useState<Page>(currentPage);
  const [mobile, setMobile] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const mutationBusy = useRef(false);
  const [selection, setSelection] = useState<Selection>(null);
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [dark, setDark] = useState(
    () => matchMedia("(prefers-color-scheme: dark)").matches,
  );
  const [voiceStatus, setVoiceStatus] = useState("Microphone inactif.");
  const [voiceText, setVoiceText] = useState("");
  const [voiceResult, setVoiceResult] = useState("");
  const [voiceActive, setVoiceActive] = useState(false);
  const voice = useRef<Voice | null>(null);
  const refreshRun = useRef(0);
  const refresh = useCallback(
    async (client: Api) => {
      const run = ++refreshRun.current;
      try {
        const [goals, memories, routines, connections, activity] =
          await Promise.all([
            client.list<Goal>("goals"),
            client.list<Memory>("memories"),
            client.list<Routine>("routines"),
            client.list<Connection>("connections"),
            client.list<Activity>("activity"),
          ]);
        if (apiRef.current !== client || run !== refreshRun.current) return;
        setData({ goals, memories, routines, connections, activity });
        setError("");
      } catch (error) {
        if (apiRef.current !== client || run !== refreshRun.current) return;
        setData(empty);
        setSelection(null);
        setError(message(error));
        if (
          error instanceof ApiError &&
          (error.status === 401 || error.status === 403)
        )
          logout(message(error));
      } finally {
        if (apiRef.current === client && run === refreshRun.current)
          setLoading(false);
      }
    },
    [logout],
  );
  useEffect(() => {
    const client = (apiRef.current = new Api(token, household.id));
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      if (!document.hidden && !mutationBusy.current) await refresh(client);
      if (!stopped) timer = setTimeout(poll, 10000);
    };
    void poll();
    const leave = () => voice.current?.close();
    window.addEventListener("pagehide", leave);
    return () => {
      stopped = true;
      clearTimeout(timer);
      apiRef.current = null;
      client.dispose();
      voice.current?.close();
      window.removeEventListener("pagehide", leave);
    };
  }, [token, household.id, refresh]);
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);
  useEffect(() => {
    const change = () => {
      setPage(currentPage());
      setMobile(false);
      setSelection(null);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobile(false);
    };
    window.addEventListener("hashchange", change);
    window.addEventListener("keydown", escape);
    return () => {
      window.removeEventListener("hashchange", change);
      window.removeEventListener("keydown", escape);
    };
  }, []);
  const navigate = (next: Page) => {
    location.hash = next;
    setPage(next);
    setMobile(false);
    document.getElementById("main")?.focus();
  };
  const open = (next: Selection) => {
    setSelection(next);
    setError("");
    setNotice("");
    setConfirmDelete(false);
    setDraft(next?.kind === "memory" ? next.item.text : "");
  };
  async function mutate(work: (api: Api) => Promise<unknown>) {
    const client = apiRef.current;
    if (!client || mutationBusy.current) return;
    mutationBusy.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    ++refreshRun.current; // A pre-write poll must not replace a confirmed write with an older snapshot.
    try {
      await work(client);
      if (apiRef.current !== client) return;
      setSelection(null);
      setNotice("Modification enregistrée par le serveur.");
      await refresh(client);
    } catch (error) {
      if (apiRef.current !== client) return;
      setError(message(error));
      if (error instanceof ApiError && error.status === 401)
        logout(message(error));
    } finally {
      mutationBusy.current = false;
      setBusy(false);
    }
  }
  const control = (
    resource: string,
    item: { id: string; rev: number },
    action: string,
  ) =>
    void mutate((api) =>
      api.request(
        `${objectPath(resource, item.id)}/${action}`,
        "POST",
        {},
        item.rev,
      ),
    );
  async function showQuote(goal: Goal, stepId: string, quoteId: string) {
    const client = apiRef.current;
    if (!client) return;
    try {
      const quote = await client.request<Quote>(objectPath("quotes", quoteId));
      if (apiRef.current === client)
        open({ kind: "quote", item: quote, goal, stepId });
    } catch (error) {
      if (apiRef.current === client) setError(message(error));
    }
  }
  function startVoice() {
    if (voice.current || !apiRef.current) return;
    setVoiceActive(true);
    setVoiceResult("");
    setVoiceStatus("Connexion au service vocal…");
    const client = apiRef.current;
    const session = new Voice(client, {
      status: setVoiceStatus,
      result: setVoiceResult,
      changed: () => {
        void refresh(client);
      },
      ended: () => {
        voice.current = null;
        setVoiceActive(false);
      },
    });
    voice.current = session;
    void session.start();
  }
  const tasks = data.goals.filter(
    (goal) =>
      filter === "all" ||
      (filter === "finished"
        ? ["SUCCEEDED", "CANCELLED", "FAILED"].includes(goal.status)
        : !["SUCCEEDED", "CANCELLED", "FAILED"].includes(goal.status)),
  );
  const goalCards = (goals: Goal[]) =>
    goals.length ? (
      <div className="task-grid">
        {goals.map((goal) => (
          <button
            className="task-card"
            key={goal.id}
            onClick={() => open({ kind: "goal", item: goal })}
          >
            <span className="badge">
              {statuses[goal.status] ?? goal.status}
            </span>
            <h2>{goal.goal}</h2>
            <p>
              {goal.plan?.summary ??
                "Le backend prépare la suite de votre demande."}
            </p>
          </button>
        ))}
      </div>
    ) : (
      <Empty
        title="Aucune demande à afficher"
        text="Confiez une nouvelle demande à Koyori."
      />
    );
  const activities = (
    <>
      {data.activity.length ? (
        <ol className="timeline">
          {[...data.activity].reverse().map((item, index) => (
            <li key={item.id ?? `${item.sequence}-${index}`}>
              <time>
                {item.occurredAt
                  ? dateTime(item.occurredAt, household.timeZone)
                  : ""}
              </time>
              <div>
                <strong>{item.type}</strong>
                <p>Référence : {item.aggregateId}</p>
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <Empty
          title="Aucune activité disponible"
          text="Les événements du backend apparaîtront ici."
        />
      )}
    </>
  );
  const heading = pages.find((item) => item.id === page)!.label;
  return (
    <div className="app-shell connected">
      <a href="#main" className="skip-link">
        Aller au contenu
      </a>
      {mobile && (
        <button
          className="nav-backdrop"
          aria-label="Fermer la navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <aside
        className={`sidebar ${mobile ? "is-open" : ""}`}
        aria-label="Navigation principale"
      >
        <a className="brand" href="#today" onClick={() => navigate("today")}>
          <span className="brand-mark">
            <WaveformIcon size={27} />
          </span>
          koyori<span className="brand-period">.</span>
        </a>
        <div className="household">
          <HouseLineIcon size={22} />
          <span>
            {household.name}
            <small>Espace personnel connecté</small>
          </span>
        </div>
        <nav>
          {pages.map(({ id, label, icon: Icon }) => (
            <a
              key={id}
              href={`#${id}`}
              onClick={() => navigate(id)}
              aria-current={page === id ? "page" : undefined}
            >
              <Icon size={20} />
              <span>{label}</span>
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <p className="panel-note">
            Vos données viennent du backend. Les modes simulés restent indiqués.
          </p>
          <button className="text-button" onClick={() => logout()}>
            Se déconnecter
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            aria-label="Ouvrir la navigation"
            aria-expanded={mobile}
            onClick={() => setMobile(!mobile)}
          >
            <ListIcon size={24} />
          </button>
          <strong>{heading}</strong>
          <button
            className="light-button"
            disabled={loading || busy}
            onClick={() => {
              if (apiRef.current) {
                setLoading(true);
                void refresh(apiRef.current);
              }
            }}
          >
            Actualiser
          </button>
        </header>
        <main id="main" tabIndex={-1}>
          {loading && <p role="status">Chargement du foyer…</p>}
          {error && (
            <p role="alert" className="form-error">
              {error}
            </p>
          )}
          {notice && (
            <p role="status" className="inline-note">
              {notice}
            </p>
          )}
          {page === "today" && (
            <>
              <div className="day-heading">
                {new Date().toLocaleDateString("fr-FR", {
                  weekday: "long",
                  day: "numeric",
                  month: "long",
                  timeZone: household.timeZone,
                })}
              </div>
              <section className="welcome">
                <div className="welcome-copy">
                  <div className="greeting-label">
                    Votre quotidien, en bonne compagnie
                  </div>
                  <h1>
                    Bienvenue chez vous<span>.</span>
                    <br />
                    L’esprit un peu plus libre.
                  </h1>
                  <p>
                    {data.goals.length} demandes enregistrées dans votre espace.
                  </p>
                  <button
                    className="primary-button"
                    onClick={() => open({ kind: "new" })}
                  >
                    Confier une demande
                    <ArrowRightIcon size={18} />
                  </button>
                </div>
                <div className="welcome-image">
                  <img
                    src="/home.webp"
                    srcSet="/home-small.webp 800w, /home.webp 1200w"
                    sizes="(max-width: 767px) calc(100vw - 40px), 45vw"
                    alt="Un salon lumineux ouvert sur un jardin"
                    width="768"
                    height="512"
                  />
                </div>
              </section>
              <section className="requests-section">
                <div className="section-heading">
                  <h2>Je m’en occupe</h2>
                  <button
                    className="text-button"
                    onClick={() => navigate("tasks")}
                  >
                    Tout voir
                  </button>
                </div>
                {goalCards(data.goals.slice(0, 4))}
              </section>
              <section className="activity-section">
                <h2>Les dernières attentions</h2>
                {activities}
              </section>
            </>
          )}
          {page !== "today" && (
            <div className="page-heading">
              <h1>{heading}</h1>
            </div>
          )}
          {page === "tasks" && (
            <>
              <div className="connected-actions">
                <button
                  className="primary-button"
                  onClick={() => open({ kind: "new" })}
                >
                  Nouvelle demande
                </button>
                <label>
                  Afficher{" "}
                  <select
                    value={filter}
                    onChange={(event) => setFilter(event.target.value)}
                  >
                    <option value="all">Toutes</option>
                    <option value="active">À suivre</option>
                    <option value="finished">Terminées</option>
                  </select>
                </label>
              </div>
              {goalCards(tasks)}
            </>
          )}
          {page === "memory" && (
            <>
              <label className="field-label" htmlFor="memory-search">
                Rechercher dans les souvenirs chargés
              </label>
              <input
                id="memory-search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              <div className="connected-list">
                {data.memories
                  .filter((item) =>
                    item.text
                      .toLocaleLowerCase("fr")
                      .includes(query.toLocaleLowerCase("fr")),
                  )
                  .map((item) => (
                    <button
                      className="task-card"
                      key={item.id}
                      onClick={() => open({ kind: "memory", item })}
                    >
                      <span className="badge">
                        {item.visibility === "private" ? "Personnel" : "Foyer"}{" "}
                        / {item.kind}
                      </span>
                      <p>{item.text}</p>
                      <small>Source : {item.source?.kind}</small>
                    </button>
                  ))}
              </div>
              {!data.memories.length && (
                <Empty
                  title="Aucun souvenir disponible"
                  text="Vos souvenirs enregistrés par Koyori apparaîtront ici."
                />
              )}
            </>
          )}
          {page === "routines" && (
            <div className="connected-list">
              {data.routines.map((item) => (
                <article className="connected-card" key={item.id}>
                  <h2>{item.text}</h2>
                  <p>
                    {item.localTime} · {item.timeZone}
                  </p>
                  <p>
                    {!item.active
                      ? "Désactivée"
                      : item.paused
                        ? "En pause"
                        : "Active"}
                  </p>
                  {item.active && (
                    <button
                      className="light-button"
                      disabled={busy}
                      onClick={() =>
                        control(
                          "routines",
                          item,
                          item.paused ? "resume" : "pause",
                        )
                      }
                    >
                      {item.paused ? "Reprendre" : "Mettre en pause"}
                    </button>
                  )}
                </article>
              ))}
              {!data.routines.length && (
                <Empty
                  title="Aucune routine enregistrée"
                  text="Les routines configurées dans le backend apparaîtront ici."
                />
              )}
            </div>
          )}
          {page === "services" && (
            <>
              <p>
                Connexions enregistrées pour votre profil. L’état affiché ne
                garantit pas la disponibilité du fournisseur.
              </p>
              <div className="connected-list">
                {data.connections.map((item) => (
                  <article className="connected-card" key={item.id}>
                    <h2>{item.provider}</h2>
                    <span className="badge">
                      {item.mode === "simulated"
                        ? "Simulé"
                        : "Connexion réelle"}
                    </span>
                    <p>
                      {item.active ? "Active" : "Révoquée"} {item.status}
                    </p>
                  </article>
                ))}
              </div>
              {!data.connections.length && (
                <Empty
                  title="Aucun service connecté"
                  text="Configurez les connecteurs dans votre environnement backend."
                />
              )}
              <p className="panel-note">
                L’intégration Alexa native et la connexion de nouveaux comptes
                ne sont pas disponibles dans cet écran.
              </p>
            </>
          )}
          {page === "activity" && activities}
          {page === "settings" && (
            <section className="connected-card">
              <h2>Votre espace</h2>
              <p>
                {household.name} · {household.timeZone}
              </p>
              <p>
                Authentification par jeton d’accès. Aucun jeton ni donnée métier
                n’est enregistré dans le stockage du navigateur. Un rechargement
                demande une nouvelle connexion.
              </p>
              <button className="light-button" onClick={() => setDark(!dark)}>
                {dark ? <SunIcon size={18} /> : <MoonIcon size={18} />}
                {dark ? "Thème clair" : "Thème sombre"}
              </button>
              <button className="text-button" onClick={() => logout()}>
                Changer de foyer ou se déconnecter
              </button>
            </section>
          )}
          <section className="voice-panel" aria-label="Conversation vocale">
            <h2>
              <MicrophoneIcon size={22} /> Parler à Koyori
            </h2>
            <p>
              En mode vocal réel, votre microphone sera transmis au service
              configuré après votre autorisation. La session est personnelle et
              les tours finalisés sont conservés dans votre mémoire.
            </p>
            <p role="status">{voiceStatus}</p>
            <div className="connected-actions">
              {!voiceActive ? (
                <button className="primary-button" onClick={startVoice}>
                  Démarrer la voix
                </button>
              ) : (
                <>
                  <button
                    className="light-button"
                    onClick={() => voice.current?.interrupt()}
                  >
                    Interrompre la réponse
                  </button>
                  <button
                    className="light-button"
                    onClick={() => {
                      voice.current?.close();
                      setVoiceStatus("Microphone inactif.");
                    }}
                  >
                    Arrêter la voix
                  </button>
                </>
              )}
            </div>
            {voiceActive &&
              voice.current?.simulation &&
              voice.current?.ready && (
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    voice.current?.submit(voiceText);
                    setVoiceText("");
                  }}
                >
                  <label className="field-label" htmlFor="voice-test">
                    Tour vocal simulé (texte de test)
                  </label>
                  <input
                    id="voice-test"
                    value={voiceText}
                    maxLength={2000}
                    required
                    onChange={(event) => setVoiceText(event.target.value)}
                  />
                  <button className="light-button">
                    Envoyer le tour de test
                  </button>
                </form>
              )}
            {voiceResult && <p>{voiceResult}</p>}
          </section>
        </main>
      </div>
      {selection && (
        <Dialog
          title={
            selection.kind === "new"
              ? "Confier une demande"
              : selection.kind === "memory"
                ? "Corriger un souvenir"
                : selection.kind === "quote"
                  ? "Vérifier le panier"
                  : "Suivre la demande"
          }
          onClose={() => {
            if (!busy) setSelection(null);
          }}
        >
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <fieldset disabled={busy} className="connected-fieldset">
            {selection.kind === "new" && (
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  if (draft.trim())
                    void mutate((api) =>
                      api.request("goals", "POST", { text: draft.trim() }),
                    );
                }}
              >
                <label className="field-label" htmlFor="goal-text">
                  Votre demande
                </label>
                <textarea
                  id="goal-text"
                  value={draft}
                  maxLength={2000}
                  required
                  rows={4}
                  onChange={(event) => setDraft(event.target.value)}
                />
                <button className="primary-button">Confier à Koyori</button>
              </form>
            )}
            {selection.kind === "goal" && (
              <>
                <span className="badge">
                  {statuses[selection.item.status] ?? selection.item.status}
                </span>
                <p>{selection.item.goal}</p>
                <p>{selection.item.plan?.summary}</p>
                <p>{selection.item.plan?.clarification}</p>
                <ol>
                  {selection.item.plan?.steps.map((step) => (
                    <li key={step.stepId}>
                      {step.capability} —{" "}
                      {selection.item.stepStates[step.stepId]?.status ??
                        "En attente"}
                      {selection.item.stepStates[step.stepId]?.status ===
                        "WAITING_APPROVAL" &&
                        selection.item.stepStates[step.stepId]?.quoteId && (
                          <button
                            className="light-button"
                            onClick={() =>
                              void showQuote(
                                selection.item,
                                step.stepId,
                                selection.item.stepStates[step.stepId].quoteId!,
                              )
                            }
                          >
                            Voir le panier
                          </button>
                        )}
                    </li>
                  ))}
                </ol>
                {!["SUCCEEDED", "FAILED", "CANCELLED", "CANCELLING"].includes(
                  selection.item.status,
                ) && (
                  <div className="connected-actions">
                    <button
                      className="light-button"
                      onClick={() =>
                        control(
                          "goals",
                          selection.item,
                          selection.item.status === "PAUSED"
                            ? "resume"
                            : "pause",
                        )
                      }
                    >
                      {selection.item.status === "PAUSED"
                        ? "Reprendre"
                        : "Mettre en pause"}
                    </button>
                    <button
                      className="text-button danger"
                      onClick={() => control("goals", selection.item, "cancel")}
                    >
                      Annuler la demande
                    </button>
                  </div>
                )}
                {selection.item.actions.map((action) => (
                  <p key={action.id}>
                    Action {action.id} : {action.status}{" "}
                    {action.mode === "simulated"
                      ? "(simulée, aucun achat réel)"
                      : ""}
                  </p>
                ))}
              </>
            )}
            {selection.kind === "memory" && (
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  if (draft.trim())
                    void mutate((api) =>
                      api.request(
                        objectPath("memories", selection.item.id),
                        "PATCH",
                        { text: draft.trim() },
                        selection.item.rev,
                      ),
                    );
                }}
              >
                <p>
                  Source : {selection.item.source?.kind} ·{" "}
                  {selection.item.visibility === "private"
                    ? "Personnel"
                    : "Foyer"}
                </p>
                <label className="field-label" htmlFor="memory-text">
                  Ce que vous souhaitez retenir
                </label>
                <textarea
                  id="memory-text"
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  maxLength={6000}
                  required
                  rows={4}
                />
                <button className="primary-button">
                  Enregistrer la correction
                </button>
                {confirmDelete ? (
                  <div>
                    <p>Oublier ce souvenir dans le backend ?</p>
                    <button
                      type="button"
                      className="light-button"
                      onClick={() =>
                        void mutate((api) =>
                          api.request(
                            objectPath("memories", selection.item.id),
                            "DELETE",
                            undefined,
                            selection.item.rev,
                          ),
                        )
                      }
                    >
                      Confirmer la suppression
                    </button>
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => setConfirmDelete(false)}
                    >
                      Conserver
                    </button>
                  </div>
                ) : (
                  <button
                    className="text-button danger"
                    type="button"
                    onClick={() => setConfirmDelete(true)}
                  >
                    Oublier ce souvenir
                  </button>
                )}
              </form>
            )}
            {selection.kind === "quote" && (
              <>
                <p>
                  {selection.item.conditions.mode === "simulated"
                    ? "Panier simulé : aucun achat réel."
                    : "Panier fournisseur"}
                </p>
                <p>Opération : {selection.item.conditions.operation}</p>
                <ul>
                  {selection.item.conditions.lines.map((line) => (
                    <li key={line.sku}>
                      {line.sku} × {line.quantity}
                    </li>
                  ))}
                </ul>
                <strong>
                  {new Intl.NumberFormat("fr-FR", {
                    style: "currency",
                    currency: selection.item.conditions.currency,
                  }).format(selection.item.conditions.totalMinor / 100)}
                </strong>
                <p>
                  Livraison :{" "}
                  {dateTime(
                    selection.item.conditions.deliveryAt,
                    household.timeZone,
                  )}
                </p>
                <p>
                  Valable jusqu’au{" "}
                  {dateTime(selection.item.expiresAt, household.timeZone)}
                </p>
                <QuoteApproval
                  api={apiRef.current!}
                  quote={selection.item}
                  goal={selection.goal}
                  stepId={selection.stepId}
                  approve={mutate}
                />
                <button
                  className="text-button"
                  onClick={() => control("goals", selection.goal, "pause")}
                >
                  Mettre de côté
                </button>
              </>
            )}
          </fieldset>
        </Dialog>
      )}
    </div>
  );
}
