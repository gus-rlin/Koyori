import { useEffect, useRef, useState, type FormEvent } from "react";
import { CalendarBlankIcon, GoogleLogoIcon } from "@phosphor-icons/react";
import {
  Api,
  objectPath,
  stepUpHash,
  type AgendaEvent,
  type CalendarProposal,
  type Connection,
} from "./api";
import { Empty } from "./components";

type Mutate = (work: (api: Api) => Promise<unknown>) => Promise<void>;

const decide = (
  api: Api,
  item: CalendarProposal,
  decision: "approve" | "reject",
) =>
  api.request(
    `${objectPath("calendar-proposals", item.id)}/decision`,
    "POST",
    { decision },
    item.rev,
  );

const proposalStatus: Record<string, string> = {
  PENDING: "À confirmer",
  APPROVED: "Ajout en cours",
  CREATED: "Ajouté à Google Agenda",
  REJECTED: "Refusé",
  FAILED: "Non ajouté",
};
const failures: Record<string, string> = {
  CALENDAR_NOT_WRITABLE:
    "Koyori ne peut ajouter qu’aux agendas dont vous êtes propriétaire.",
  PROVIDER_ACCESS_REVOKED:
    "L’accès Google a été retiré. Reconnectez votre agenda.",
  CALENDAR_READ_ONLY: "Ce compte est connecté en lecture seule.",
  CONNECTION_REVOKED: "Ce compte n’est plus connecté.",
};

export const isCalendar = (item: Connection) =>
  item.provider === "google-calendar" && item.active;
const canWrite = (item: Connection) =>
  isCalendar(item) && !!item.capabilities?.includes("calendar.write");

/** Seconds since epoch for a wall-clock date and time in an IANA zone. */
function zonedEpoch(day: string, time: string, timeZone: string) {
  const [y, m, d] = day.split("-").map(Number);
  const [hh, mm] = time.split(":").map(Number);
  const wall = Date.UTC(y, m - 1, d, hh, mm);
  const offset = (at: number) => {
    const parts = Object.fromEntries(
      new Intl.DateTimeFormat("en-US", {
        timeZone,
        hourCycle: "h23",
        year: "numeric",
        month: "numeric",
        day: "numeric",
        hour: "numeric",
        minute: "numeric",
      })
        .formatToParts(at)
        .map((part) => [part.type, Number(part.value)]),
    );
    return (
      Date.UTC(
        parts.year,
        parts.month - 1,
        parts.day,
        parts.hour,
        parts.minute,
      ) - at
    );
  };
  // Second pass settles instants near a daylight-saving change.
  const first = wall - offset(wall);
  return Math.round((wall - offset(first)) / 1000);
}

const clock = (seconds: number, timeZone: string) =>
  new Date(seconds * 1000).toLocaleTimeString("fr-FR", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
  });
const dayLabel = (seconds: number, timeZone: string) =>
  new Date(seconds * 1000).toLocaleDateString("fr-FR", {
    timeZone,
    weekday: "long",
    day: "numeric",
    month: "long",
  });
const dayKey = (seconds: number, timeZone: string) =>
  new Date(seconds * 1000).toLocaleDateString("en-CA", { timeZone });

function EventRow({
  event,
  timeZone,
}: {
  event: AgendaEvent;
  timeZone: string;
}) {
  return (
    <li>
      <time>{event.allDay ? "Journée" : clock(event.startAt, timeZone)}</time>
      <div>
        <strong>{event.title || "Sans titre"}</strong>
        {!event.allDay && <p>jusqu’à {clock(event.endAt, timeZone)}</p>}
      </div>
    </li>
  );
}

/** Today's events, in the spirit of the home panels of a personal assistant. */
export function TodaySchedule({
  events,
  connected,
  timeZone,
  pending,
  openAgenda,
}: {
  events: AgendaEvent[];
  connected: boolean;
  timeZone: string;
  pending: number;
  openAgenda: () => void;
}) {
  const now = Date.now() / 1000;
  const today = dayKey(now, timeZone);
  const items = events.filter(
    (event) => dayKey(event.startAt, timeZone) <= today && event.endAt > now,
  );
  return (
    <section className="schedule" aria-label="Votre agenda aujourd’hui">
      <div className="section-heading">
        <h2>Dans votre journée</h2>
        <CalendarBlankIcon size={19} />
      </div>
      {!connected ? (
        <p>Connectez Google Agenda pour retrouver vos rendez-vous ici.</p>
      ) : items.length ? (
        <ol className="agenda">
          {items.slice(0, 5).map((event) => (
            <EventRow
              key={event.connectionId + event.id}
              event={event}
              timeZone={timeZone}
            />
          ))}
        </ol>
      ) : (
        <p>Rien d’autre de prévu aujourd’hui.</p>
      )}
      <div className="schedule-foot">
        <CalendarBlankIcon size={15} />
        <button className="text-button" onClick={openAgenda}>
          {pending
            ? `${pending} ajout${pending > 1 ? "s" : ""} à confirmer`
            : connected
              ? "Voir l’agenda"
              : "Connecter un agenda"}
        </button>
      </div>
    </section>
  );
}

export function AgendaPage({
  events,
  proposals,
  connections,
  timeZone,
  mutate,
  newEvent,
  connect,
}: {
  events: AgendaEvent[];
  proposals: CalendarProposal[];
  connections: Connection[];
  timeZone: string;
  mutate: Mutate;
  newEvent: () => void;
  connect: () => void;
}) {
  const accounts = connections.filter(isCalendar);
  const writable = accounts.some(canWrite);
  const days = new Map<string, AgendaEvent[]>();
  for (const event of events) {
    const key = dayKey(event.startAt, timeZone);
    if (!days.has(key)) days.set(key, []);
    days.get(key)!.push(event);
  }
  const waiting = proposals.filter((item) => item.status === "PENDING");
  const recent = proposals
    .filter((item) => item.status !== "PENDING")
    .sort((a, b) => b.createdAt - a.createdAt)
    .slice(0, 6);
  if (!accounts.length)
    return (
      <>
        <Empty
          title="Aucun agenda connecté"
          text="Connectez Google Agenda : Koyori lira vos rendez-vous et pourra en ajouter avec votre accord."
        />
        <div className="connected-actions">
          <button className="primary-button" onClick={connect}>
            Connecter Google Agenda
          </button>
        </div>
      </>
    );
  return (
    <>
      <div className="connected-actions">
        <button
          className="primary-button"
          onClick={newEvent}
          disabled={!writable}
        >
          Nouvel événement
        </button>
        {!writable && (
          <span className="panel-note">
            Reconnectez votre compte pour autoriser l’ajout d’événements.
          </span>
        )}
      </div>
      {!!waiting.length && (
        <section aria-label="Ajouts à confirmer">
          <h2>À confirmer</h2>
          <div className="connected-list">
            {waiting.map((item) => (
              <article className="connected-card" key={item.id}>
                <span className="badge">
                  {item.origin === "assistant"
                    ? "Proposé par Koyori"
                    : "Votre ajout"}
                </span>
                <h3>{item.title}</h3>
                <p>
                  {dayLabel(item.startAt, timeZone)},{" "}
                  {clock(item.startAt, timeZone)} –{" "}
                  {clock(item.endAt, timeZone)}
                  {item.location && <> · {item.location}</>}
                </p>
                {item.notes && <p>{item.notes}</p>}
                <div className="connected-actions">
                  <button
                    className="primary-button"
                    onClick={() =>
                      void mutate((api) => decide(api, item, "approve"))
                    }
                  >
                    Ajouter à mon agenda
                  </button>
                  <button
                    className="text-button"
                    onClick={() =>
                      void mutate((api) => decide(api, item, "reject"))
                    }
                  >
                    Refuser
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}
      <section aria-label="Les sept prochains jours" className="week">
        <h2>Les sept prochains jours</h2>
        {days.size ? (
          [...days.entries()].map(([key, items]) => (
            <div key={key} className="week-day">
              <h3>{dayLabel(items[0].startAt, timeZone)}</h3>
              <ol className="agenda">
                {items.map((event) => (
                  <EventRow
                    key={event.connectionId + event.id}
                    event={event}
                    timeZone={timeZone}
                  />
                ))}
              </ol>
            </div>
          ))
        ) : (
          <p>Aucun événement synchronisé sur cette période.</p>
        )}
      </section>
      {!!recent.length && (
        <section aria-label="Derniers ajouts">
          <h2>Derniers ajouts</h2>
          <ul className="proposal-history">
            {recent.map((item) => (
              <li key={item.id}>
                <span className="badge">
                  {proposalStatus[item.status] ?? item.status}
                </span>{" "}
                {item.title}, {dayLabel(item.startAt, timeZone)}
                {item.status === "FAILED" && item.error && (
                  <> — {failures[item.error] ?? "Google a refusé l’ajout."}</>
                )}
                {item.link && (
                  <>
                    {" "}
                    <a
                      href={item.link}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Ouvrir dans Google Agenda
                    </a>
                  </>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

export function EventForm({
  connections,
  timeZone,
  mutate,
}: {
  connections: Connection[];
  timeZone: string;
  mutate: Mutate;
}) {
  const accounts = connections.filter(canWrite);
  const today = dayKey(Date.now() / 1000, timeZone);
  const [form, setForm] = useState({
    title: "",
    day: today,
    start: "09:00",
    end: "10:00",
    location: "",
    notes: "",
    connectionId: accounts[0]?.id ?? "",
  });
  const [invalid, setInvalid] = useState("");
  const field =
    (name: keyof typeof form) => (event: { target: { value: string } }) =>
      setForm({ ...form, [name]: event.target.value });
  function submit(event: FormEvent) {
    event.preventDefault();
    const startAt = zonedEpoch(form.day, form.start, timeZone);
    const endAt = zonedEpoch(form.day, form.end, timeZone);
    if (endAt <= startAt) {
      setInvalid("L’heure de fin doit suivre l’heure de début.");
      return;
    }
    setInvalid("");
    const body = {
      connectionId: form.connectionId,
      title: form.title.trim(),
      startAt,
      endAt,
      ...(form.location.trim() && { location: form.location.trim() }),
      ...(form.notes.trim() && { notes: form.notes.trim() }),
    };
    // Filling in the form is the person's decision: propose, then confirm at once.
    void mutate(async (api) => {
      const proposal = await api.request<CalendarProposal>(
        "calendar-proposals",
        "POST",
        body,
      );
      await decide(api, proposal, "approve");
    });
  }
  return (
    <form onSubmit={submit}>
      {invalid && (
        <p role="alert" className="form-error">
          {invalid}
        </p>
      )}
      <label className="field-label" htmlFor="event-title">
        Titre
      </label>
      <input
        id="event-title"
        value={form.title}
        maxLength={200}
        required
        onChange={field("title")}
      />
      <label className="field-label" htmlFor="event-day">
        Date
      </label>
      <input
        id="event-day"
        type="date"
        value={form.day}
        min={today}
        required
        onChange={field("day")}
      />
      <div className="field-pair">
        <span>
          <label className="field-label" htmlFor="event-start">
            Début
          </label>
          <input
            id="event-start"
            type="time"
            value={form.start}
            required
            onChange={field("start")}
          />
        </span>
        <span>
          <label className="field-label" htmlFor="event-end">
            Fin
          </label>
          <input
            id="event-end"
            type="time"
            value={form.end}
            required
            onChange={field("end")}
          />
        </span>
      </div>
      <label className="field-label" htmlFor="event-location">
        Lieu (facultatif)
      </label>
      <input
        id="event-location"
        value={form.location}
        maxLength={200}
        onChange={field("location")}
      />
      <label className="field-label" htmlFor="event-notes">
        Notes (facultatif)
      </label>
      <textarea
        id="event-notes"
        value={form.notes}
        maxLength={1000}
        rows={3}
        onChange={field("notes")}
      />
      {accounts.length > 1 && (
        <>
          <label className="field-label" htmlFor="event-account">
            Agenda
          </label>
          <select
            id="event-account"
            value={form.connectionId}
            onChange={field("connectionId")}
          >
            {accounts.map((item) => (
              <option key={item.id} value={item.id}>
                {item.account ?? "Google Agenda"}
              </option>
            ))}
          </select>
        </>
      )}
      <p className="panel-note">
        Heure de {timeZone}. L’événement est ajouté sans prévenir d’invités.
      </p>
      <button className="primary-button">Ajouter à Google Agenda</button>
    </form>
  );
}

export function CalendarAccounts({
  connections,
  mutate,
  connect,
}: {
  connections: Connection[];
  mutate: Mutate;
  connect: () => void;
}) {
  const accounts = connections.filter(
    (item) => item.provider === "google-calendar",
  );
  return (
    <section aria-label="Google Agenda" className="connected-card">
      <h2>
        <GoogleLogoIcon size={20} /> Google Agenda
      </h2>
      <p>
        Koyori lit vos agendas pour préparer vos journées et n’ajoute un
        événement qu’après votre confirmation.
      </p>
      {accounts.map((item) => (
        <div key={item.id} className="account-row">
          <div>
            <strong>{item.account ?? "Compte Google"}</strong>
            <p>
              {!item.active
                ? "Déconnecté"
                : canWrite(item)
                  ? "Lecture et ajout d’événements"
                  : "Lecture seule"}
            </p>
          </div>
          {item.active && (
            <div className="connected-actions">
              <button
                className="light-button"
                onClick={() =>
                  void mutate((api) =>
                    api.request(
                      `${objectPath("connections", item.id)}/sync`,
                      "POST",
                      {},
                    ),
                  )
                }
              >
                Synchroniser
              </button>
              <button
                className="text-button danger"
                onClick={() =>
                  void mutate((api) =>
                    api.request(
                      objectPath("connections", item.id),
                      "DELETE",
                      undefined,
                      item.rev,
                    ),
                  )
                }
              >
                Déconnecter
              </button>
            </div>
          )}
        </div>
      ))}
      <button className="primary-button" onClick={connect}>
        {accounts.some((item) => item.active)
          ? "Connecter un autre compte"
          : "Connecter Google Agenda"}
      </button>
    </section>
  );
}

const AUTHORIZE = "connections/google-calendar/authorize";
const AUTHORIZE_BODY = { calendarIds: ["primary"] };

/** Fresh identity proof, then Google consent in a popup so this tab keeps its in-memory session. */
export function ConnectCalendar({
  api,
  connected,
}: {
  api: Api;
  connected: () => void;
}) {
  const [challenge, setChallenge] = useState<{
    id: string;
    nonce: string;
  } | null>(null);
  const [proof, setProof] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [waiting, setWaiting] = useState(false);
  const grant = useRef("");
  const watcher = useRef<ReturnType<typeof setInterval>>(undefined);
  useEffect(() => () => clearInterval(watcher.current), []);
  async function prepare() {
    setBusy(true);
    setError("");
    try {
      setChallenge(
        await api.request("auth/step-up", "POST", {
          operation: `POST /v1/${AUTHORIZE}`,
          requestHash: await stepUpHash({
            ...AUTHORIZE_BODY,
            schemaVersion: "1.0",
          }),
        }),
      );
      grant.current = "";
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Vérification indisponible.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function consent() {
    // Opened during the click so the browser does not block it; filled once the URL exists.
    const popup = window.open(
      "",
      "koyori-google",
      "popup,width=520,height=720",
    );
    setBusy(true);
    setError("");
    try {
      if (!grant.current) {
        const value = await api.request<{ grant: string }>(
          `${objectPath("auth/step-up", challenge!.id)}/complete`,
          "POST",
          { identityProof: proof.trim() },
        );
        grant.current = value.grant;
        setProof("");
      }
      const { authorizationUrl } = await api.request<{
        authorizationUrl: string;
      }>(AUTHORIZE, "POST", AUTHORIZE_BODY, undefined, grant.current);
      if (!authorizationUrl.startsWith("https://accounts.google.com/"))
        throw new Error("Adresse de consentement inattendue.");
      if (!popup)
        throw new Error(
          "Autorisez les fenêtres pop-up pour continuer avec Google.",
        );
      popup.location.href = authorizationUrl;
      setWaiting(true);
      watcher.current = setInterval(() => {
        if (!popup.closed) return;
        clearInterval(watcher.current);
        setWaiting(false);
        connected();
      }, 800);
    } catch (error) {
      popup?.close();
      setError(
        error instanceof Error ? error.message : "Connexion indisponible.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <p>Google vous demandera d’autoriser Koyori à :</p>
      <ul>
        <li>voir vos agendas et leurs événements ;</li>
        <li>ajouter des événements aux agendas dont vous êtes propriétaire.</li>
      </ul>
      <p className="panel-note">
        Aucun ajout n’est fait sans votre confirmation dans Koyori. Vous pouvez
        déconnecter le compte à tout moment.
      </p>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {waiting ? (
        <p role="status">
          Terminez la connexion dans la fenêtre Google, puis fermez-la pour
          revenir ici.
        </p>
      ) : !challenge ? (
        <button
          className="primary-button"
          disabled={busy}
          onClick={() => void prepare()}
        >
          Vérifier mon identité
        </button>
      ) : (
        <>
          <p>
            Nonce à transmettre à votre émetteur :{" "}
            <code className="identity-nonce">{challenge.nonce}</code>
          </p>
          <label className="field-label" htmlFor="calendar-proof">
            Preuve d’identité récente (jeton ID lié au nonce)
          </label>
          <input
            id="calendar-proof"
            type="password"
            autoComplete="off"
            value={proof}
            onChange={(event) => setProof(event.target.value)}
          />
          <button
            className="primary-button"
            disabled={busy || (!proof.trim() && !grant.current)}
            onClick={() => void consent()}
          >
            Continuer avec Google
          </button>
        </>
      )}
    </div>
  );
}
