import { useEffect, useState, type FormEvent } from "react";
import {
  ArrowRightIcon,
  ArrowUpRightIcon,
  BellIcon,
  BookOpenIcon,
  CalendarBlankIcon,
  CaretDownIcon,
  CheckIcon,
  CheckCircleIcon,
  ClockIcon,
  GearSixIcon,
  HouseLineIcon,
  LeafIcon,
  ListIcon,
  MicrophoneIcon,
  MoonIcon,
  PauseIcon,
  PlayIcon,
  PlusIcon,
  PlugsConnectedIcon,
  ShoppingBagIcon,
  SparkleIcon,
  SunIcon,
  TrashIcon,
  UsersIcon,
  WaveformIcon,
  XIcon,
  ArrowClockwiseIcon,
  PencilSimpleIcon,
  MagnifyingGlassIcon,
  ShieldCheckIcon,
} from "@phosphor-icons/react";
import { Overview } from "./Overview";
import { TaskCard, Empty, Timeline } from "./components";
import { initialActivity } from "./demo";
import type { Page, Modal } from "./ui-types";
import { Dialog } from "./Dialog";
import {
  initialTasks,
  initialMemories,
  initialRoutines,
  statusLabels,
  type Task,
} from "./demo";

const pages = [
  { id: "today", label: "Aujourd’hui", icon: HouseLineIcon },
  { id: "tasks", label: "Mes demandes", icon: SparkleIcon },
  { id: "memory", label: "Ma mémoire", icon: BookOpenIcon },
  { id: "routines", label: "Routines", icon: ArrowClockwiseIcon },
  { id: "services", label: "Services", icon: PlugsConnectedIcon },
] as const;
function currentPage(): Page {
  const hash = window.location.hash.slice(1);
  return [...pages.map((p) => p.id), "activity", "settings"].includes(hash)
    ? (hash as Page)
    : "today";
}
export default function App() {
  const [page, setPage] = useState<Page>(currentPage);
  const [mobileNav, setMobileNav] = useState(false);
  const [tasks, setTasks] = useState(initialTasks);
  const [memories, setMemories] = useState(initialMemories);
  const [routines, setRoutines] = useState(initialRoutines);
  const [activities, setActivities] = useState(initialActivity);
  const [approval, setApproval] = useState<"pending" | "approved" | "declined">(
    "pending",
  );
  const [modal, setModal] = useState<Modal>(null);
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [toast, setToast] = useState("");
  const [theme, setTheme] = useState<"light" | "dark">(() =>
    window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light",
  );
  const [newTitle, setNewTitle] = useState("");
  const [formError, setFormError] = useState("");
  const [memoryText, setMemoryText] = useState("");
  const [deleteMemory, setDeleteMemory] = useState(false);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  useEffect(() => {
    const change = () => {
      setPage(currentPage());
      setMobileNav(false);
    };
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 4500);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    if (!mobileNav) return;
    const dismiss = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMobileNav(false);
        document.querySelector<HTMLButtonElement>(".mobile-menu")?.focus();
      }
    };
    document.addEventListener("keydown", dismiss);
    return () => document.removeEventListener("keydown", dismiss);
  }, [mobileNav]);
  const navigate = (next: Page) => {
    window.location.hash = next;
    setPage(next);
    setMobileNav(false);
    window.scrollTo({ top: 0 });
    document.getElementById("main")?.focus();
  };
  const log = (title: string, detail: string) =>
    setActivities((prev) => [
      { id: crypto.randomUUID(), title, detail, time: "À l’instant" },
      ...prev,
    ]);
  const open = (next: Modal) => {
    setFormError("");
    setNewTitle("");
    setDeleteMemory(false);
    if (next?.type === "memory")
      setMemoryText(memories.find((m) => m.id === next.id)?.text ?? "");
    setModal(next);
  };
  const close = () => setModal(null);
  const activeTasks = tasks.filter(
    (t) => t.status === "active" || t.status === "paused",
  );
  const selectedTask =
    modal?.type === "task" ? tasks.find((t) => t.id === modal.id) : undefined;
  const selectedMemory =
    modal?.type === "memory"
      ? memories.find((m) => m.id === modal.id)
      : undefined;
  const awaitingApproval =
    approval === "pending" &&
    tasks.find((t) => t.id === "groceries")?.status === "active";
  const changeTask = (task: Task, status: Task["status"]) => {
    setTasks((prev) =>
      prev.map((t) => (t.id === task.id ? { ...t, status } : t)),
    );
    if (
      task.id === "groceries" &&
      status === "active" &&
      approval === "declined"
    )
      setApproval("pending");
    log(
      `${task.title} : ${statusLabels[status].toLocaleLowerCase("fr")}`,
      "Modification dans la démonstration",
    );
    setToast("La demande de démonstration a été mise à jour.");
  };
  const decideApproval = (decision: "approved" | "declined") => {
    if (!awaitingApproval) return;
    setApproval(decision);
    setTasks((prev) =>
      prev.map((t) =>
        t.id !== "groceries"
          ? t
          : {
              ...t,
              status: decision === "declined" ? "paused" : "active",
              completed: decision === "approved" ? 3 : 2,
            },
      ),
    );
    log(
      decision === "approved"
        ? "Le panier a été approuvé dans la démo"
        : "Le panier a été mis de côté",
      "Aucune commande transmise à un commerçant",
    );
    setToast(
      decision === "approved"
        ? "Accord simulé enregistré. Aucun achat effectué."
        : "Panier mis de côté. La demande est en pause.",
    );
    close();
  };
  const createTask = (event: FormEvent) => {
    event.preventDefault();
    const title = newTitle.trim();
    if (title.length < 5) {
      setFormError("Décrivez votre demande en au moins 5 caractères.");
      return;
    }
    setTasks((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        title,
        description: "Demande ajoutée au scénario. En attente d’un plan.",
        category: "home",
        time: "Sans échéance",
        status: "active",
        steps: [
          "Demande enregistrée localement",
          "Préparer un plan",
          "Vérifier les prochaines actions",
        ],
        completed: 1,
      },
    ]);
    log("Une nouvelle demande a été ajoutée", title);
    close();
    navigate("tasks");
    setToast("Demande ajoutée à la démonstration.");
  };
  const saveMemory = (event: FormEvent) => {
    event.preventDefault();
    if (!memoryText.trim()) {
      setFormError("Ajoutez une préférence avant d’enregistrer.");
      return;
    }
    setMemories((prev) =>
      prev.map((m) =>
        m.id === selectedMemory?.id
          ? {
              ...m,
              text: memoryText.trim(),
              source: "Corrigée par vous pendant cette démonstration",
            }
          : m,
      ),
    );
    log("Une préférence a été corrigée", selectedMemory?.title ?? "Mémoire");
    close();
    setToast("Préférence corrigée dans la démonstration.");
  };
  const heading =
    pages.find((p) => p.id === page)?.label ??
    (page === "settings" ? "Réglages" : "Activité");
  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">
        Aller au contenu
      </a>
      {mobileNav && (
        <button
          className="nav-backdrop"
          aria-label="Fermer la navigation"
          onClick={() => setMobileNav(false)}
        />
      )}
      <aside
        className={`sidebar ${mobileNav ? "is-open" : ""}`}
        aria-label="Navigation principale"
      >
        <a className="brand" href="#today" onClick={() => navigate("today")}>
          <span className="brand-mark">
            <WaveformIcon weight="bold" size={27} />
          </span>
          koyori<span className="brand-period">.</span>
        </a>
        <button
          className="household"
          onClick={() => open({ type: "household" })}
        >
          <span className="household-icon">
            <HouseLineIcon size={19} />
          </span>
          <span>
            À la maison<small>Foyer de démonstration</small>
          </span>
          <CaretDownIcon size={13} />
        </button>
        <nav>
          {pages.map(({ id, label, icon: Symbol }) => (
            <a
              key={id}
              href={`#${id}`}
              onClick={() => navigate(id)}
              aria-current={page === id ? "page" : undefined}
            >
              <Symbol size={20} weight={page === id ? "fill" : "regular"} />
              <span>{label}</span>
              {id === "tasks" && activeTasks.length > 0 && (
                <span className="nav-count">{activeTasks.length}</span>
              )}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="presence-note">
            <span className="presence-symbol">
              <LeafIcon size={24} weight="light" />
            </span>
            <p>
              Un peu moins à penser.
              <br />
              <strong>Un peu plus à vivre.</strong>
            </p>
          </div>
          <button
            className={`settings-link ${page === "settings" ? "selected" : ""}`}
            onClick={() => navigate("settings")}
          >
            <GearSixIcon size={20} />
            Réglages
          </button>
          <button
            className="profile"
            onClick={() => open({ type: "household" })}
          >
            <span className="avatar">A</span>
            <span>
              Alex<small>Espace personnel</small>
            </span>
            <CaretDownIcon size={14} />
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label="Ouvrir la navigation"
              aria-expanded={mobileNav}
              onClick={() => setMobileNav((v) => !v)}
            >
              <ListIcon size={23} />
            </button>
            <span>Mon espace</span>
            <span className="breadcrumb-slash">/</span>
            <strong>{heading}</strong>
          </div>
          <div className="top-actions">
            <span className="demo-label">Démonstration</span>
            <button
              className="icon-button"
              onClick={() => setTheme(theme === "light" ? "dark" : "light")}
              aria-label={
                theme === "light"
                  ? "Activer le thème sombre"
                  : "Activer le thème clair"
              }
            >
              {theme === "light" ? (
                <MoonIcon size={20} />
              ) : (
                <SunIcon size={20} />
              )}
            </button>
            <button
              className="icon-button"
              aria-label="Voir l’activité"
              onClick={() => navigate("activity")}
            >
              <BellIcon size={20} />
            </button>
            <span className="avatar small" aria-label="Profil Alex">
              A
            </span>
          </div>
        </header>
        <main id="main" tabIndex={-1}>
          {page === "today" ? (
            <Overview
              activeTasks={activeTasks}
              memories={memories}
              activities={activities}
              awaitingApproval={awaitingApproval}
              approval={approval}
              open={open}
              navigate={navigate}
            />
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <span className="small-label">Votre espace personnel</span>
                  <h1>{heading}</h1>
                  <p>
                    {page === "tasks"
                      ? "Ce que vous confiez, ce qui avance, ce qui vous attend."
                      : page === "memory"
                        ? "Les petites choses que Koyori retient. Vous gardez le dernier mot."
                        : page === "routines"
                          ? "Un quotidien plus léger, une habitude à la fois."
                          : page === "services"
                            ? "Les liens entre votre quotidien et Koyori."
                            : page === "settings"
                              ? "Une présence qui s’adapte à vous."
                              : "Retrouvez le fil de vos demandes et de vos décisions."}
                  </p>
                </div>
                {page === "tasks" && (
                  <button
                    className="primary-button"
                    onClick={() => open({ type: "new" })}
                  >
                    <PlusIcon size={18} />
                    Nouvelle demande
                  </button>
                )}
              </div>
              {page === "tasks" && (
                <>
                  <div className="filter-bar" aria-label="Filtrer les demandes">
                    {[
                      ["all", "Toutes"],
                      ["active", "En cours"],
                      ["paused", "En pause"],
                      ["done", "Terminées"],
                      ["cancelled", "Annulées"],
                    ].map(([id, label]) => (
                      <button
                        key={id}
                        aria-pressed={filter === id}
                        className={filter === id ? "selected" : ""}
                        onClick={() => setFilter(id)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <div className="task-grid full-grid">
                    {tasks
                      .filter((t) => filter === "all" || t.status === filter)
                      .map((t) => (
                        <TaskCard
                          key={t.id}
                          task={t}
                          onOpen={() => open({ type: "task", id: t.id })}
                        />
                      ))}
                  </div>
                  {!tasks.some(
                    (t) => filter === "all" || t.status === filter,
                  ) && (
                    <Empty
                      title="Tout est tranquille ici"
                      text="Aucune demande dans cette catégorie pour le moment."
                    />
                  )}
                </>
              )}
              {page === "memory" && (
                <>
                  <label className="search-field">
                    <MagnifyingGlassIcon size={20} />
                    <input
                      aria-label="Rechercher un souvenir"
                      placeholder="Retrouver une préférence…"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </label>
                  <div className="memory-grid">
                    {memories
                      .filter((m) =>
                        `${m.title} ${m.text}`
                          .toLocaleLowerCase("fr")
                          .includes(query.toLocaleLowerCase("fr")),
                      )
                      .map((m) => (
                        <article className="memory-card" key={m.id}>
                          <div className="memory-card-top">
                            <BookOpenIcon size={22} />
                            <span className="badge">
                              {m.shared ? "Partagé avec le foyer" : "Personnel"}
                            </span>
                          </div>
                          <h2>{m.title}</h2>
                          <p>{m.text}</p>
                          <small>{m.source}</small>
                          <button
                            className="text-button"
                            onClick={() => open({ type: "memory", id: m.id })}
                          >
                            Corriger ce souvenir
                            <PencilSimpleIcon size={16} />
                          </button>
                        </article>
                      ))}
                  </div>
                  {!memories.some((m) =>
                    `${m.title} ${m.text}`
                      .toLocaleLowerCase("fr")
                      .includes(query.toLocaleLowerCase("fr")),
                  ) && (
                    <Empty
                      title="Aucun souvenir trouvé"
                      text="Essayez un autre mot ou effacez votre recherche."
                    />
                  )}
                  <p className="privacy-note">
                    <ShieldCheckIcon size={18} />
                    Préférences fictives. Leur modification ne change aucune
                    autorisation.
                  </p>
                </>
              )}
              {page === "routines" && (
                <div className="rows-panel">
                  {routines.map((r) => (
                    <article className="routine-row" key={r.id}>
                      <span className="tile-icon">
                        <ArrowClockwiseIcon size={24} />
                      </span>
                      <div>
                        <h2>{r.title}</h2>
                        <p>{r.description}</p>
                        <small>
                          <ClockIcon size={14} />
                          {r.when}
                        </small>
                      </div>
                      <button
                        role="switch"
                        aria-checked={r.enabled}
                        aria-label={r.title}
                        className={`switch ${r.enabled ? "on" : ""}`}
                        onClick={() => {
                          setRoutines((prev) =>
                            prev.map((item) =>
                              item.id === r.id
                                ? { ...item, enabled: !item.enabled }
                                : item,
                            ),
                          );
                          log(
                            `${r.title} : ${r.enabled ? "en pause" : "activée"}`,
                            "Routine simulée, aucun réveil réel",
                          );
                          setToast("Routine modifiée dans la démonstration.");
                        }}
                      >
                        <span />
                      </button>
                    </article>
                  ))}
                  <p className="panel-note">
                    Ces routines illustrent le fonctionnement prévu. Aucun
                    déclenchement réel n’est programmé.
                  </p>
                </div>
              )}
              {page === "services" && (
                <>
                  <div className="service-grid">
                    {[
                      {
                        name: "Google Calendar",
                        icon: CalendarBlankIcon,
                        copy: "Un agenda pour préparer votre journée.",
                        state: "Agenda d’exemple",
                      },
                      {
                        name: "Courses & repas",
                        icon: ShoppingBagIcon,
                        copy: "Vos habitudes, du panier à la table.",
                        state: "Commerce simulé",
                      },
                      {
                        name: "Alexa",
                        icon: WaveformIcon,
                        copy: "Parler naturellement, depuis la maison.",
                        state: "Intégration à venir",
                      },
                    ].map((s) => (
                      <article className="service-card" key={s.name}>
                        <span className="tile-icon">
                          <s.icon size={26} />
                        </span>
                        <h2>{s.name}</h2>
                        <p>{s.copy}</p>
                        <span className="badge">{s.state}</span>
                        <button
                          className="text-button"
                          onClick={() =>
                            open({ type: "service", name: s.name })
                          }
                        >
                          Voir les possibilités
                          <ArrowUpRightIcon size={16} />
                        </button>
                      </article>
                    ))}
                  </div>
                  <p className="privacy-note">
                    <ShieldCheckIcon size={18} />
                    Aucun compte externe connecté à cette interface.
                  </p>
                </>
              )}
              {page === "activity" && (
                <section className="rows-panel activity-page">
                  <Timeline activities={activities} />
                </section>
              )}
              {page === "settings" && (
                <div className="rows-panel">
                  <div className="setting-row">
                    <div>
                      <h2>Apparence</h2>
                      <p>Un espace agréable, de jour comme de nuit.</p>
                    </div>
                    <button
                      className="light-button"
                      onClick={() =>
                        setTheme(theme === "light" ? "dark" : "light")
                      }
                    >
                      {theme === "light" ? (
                        <MoonIcon size={18} />
                      ) : (
                        <SunIcon size={18} />
                      )}
                      {theme === "light"
                        ? "Passer au thème sombre"
                        : "Passer au thème clair"}
                    </button>
                  </div>
                  <div className="setting-row">
                    <div>
                      <h2>Votre foyer</h2>
                      <p>Alex et Sam, profils fictifs du scénario.</p>
                    </div>
                    <button
                      className="text-button"
                      onClick={() => open({ type: "household" })}
                    >
                      Voir le foyer
                      <ArrowRightIcon size={16} />
                    </button>
                  </div>
                  <div className="setting-row">
                    <div>
                      <h2>À propos de cette démonstration</h2>
                      <p>
                        Les modifications restent en mémoire dans cet onglet et
                        sont réinitialisées au rechargement. Aucun achat, compte
                        connecté ou enregistrement audio.
                      </p>
                    </div>
                    <ShieldCheckIcon size={25} />
                  </div>
                </div>
              )}
            </>
          )}
          <footer className="page-footer">
            <span>
              <LeafIcon size={14} />
              De la place pour l’essentiel.
            </span>
            <span>Données fictives · Modifications limitées à cet onglet</span>
          </footer>
        </main>
        <div className="voice-dock">
          <button
            onClick={() => open({ type: "briefing" })}
            className="voice-orb"
            aria-label="Explorer la démonstration vocale"
          >
            <WaveformIcon size={24} />
          </button>
          <button className="dock-prompt" onClick={() => open({ type: "new" })}>
            Qu’avez-vous en tête ?<span>Confiez-le à Koyori</span>
          </button>
          <button
            className="icon-button"
            onClick={() => open({ type: "briefing" })}
            aria-label="Disponibilité du microphone"
          >
            <MicrophoneIcon size={21} />
          </button>
        </div>
      </div>
      <div className={`toast ${toast ? "visible" : ""}`} role="status">
        {toast && (
          <>
            <CheckCircleIcon size={20} />
            {toast}
            <button
              className="icon-button"
              aria-label="Masquer le message"
              onClick={() => setToast("")}
            >
              <XIcon size={16} />
            </button>
          </>
        )}
      </div>
      {modal && (
        <Dialog
          title={
            modal.type === "new"
              ? "Une chose en moins à penser."
              : modal.type === "briefing"
                ? "On fait le point ?"
                : modal.type === "approval"
                  ? "Votre panier de la semaine"
                  : modal.type === "household"
                    ? "À la maison"
                    : modal.type === "service"
                      ? modal.name!
                      : modal.type === "task"
                        ? (selectedTask?.title ?? "Demande")
                        : (selectedMemory?.title ?? "Souvenir")
          }
          onClose={close}
        >
          {modal.type === "new" && (
            <form onSubmit={createTask}>
              <p>Ajoutez une demande au scénario pour découvrir son suivi.</p>
              <label className="field-label" htmlFor="request">
                Que souhaitez-vous confier ?
              </label>
              <textarea
                id="request"
                value={newTitle}
                onChange={(e) => {
                  setNewTitle(e.target.value);
                  setFormError("");
                }}
                placeholder="Prépare un dîner simple pour samedi…"
                maxLength={240}
                rows={4}
                aria-describedby={formError ? "form-error" : "request-help"}
                autoFocus
              />
              <div className="input-help" id="request-help">
                <span>Aucun service externe ne sera sollicité.</span>
                <span>{newTitle.length}/240</span>
              </div>
              {formError && (
                <p className="form-error" role="alert" id="form-error">
                  {formError}
                </p>
              )}
              <button className="primary-button wide" type="submit">
                Confier cette demande
                <ArrowRightIcon size={18} />
              </button>
            </form>
          )}
          {modal.type === "briefing" && (
            <>
              <div className="briefing-visual">
                <WaveformIcon size={48} weight="light" />
              </div>
              <p className="dialog-lead">Votre journée, en quelques mots.</p>
              <p>
                Dans ce scénario, vous avez un rendez-vous à 11 h,{" "}
                {activeTasks.length} demande{activeTasks.length > 1 ? "s" : ""}{" "}
                à suivre et un dîner prévu à quatre ce soir.
              </p>
              {awaitingApproval && (
                <div className="inline-note">
                  <ShoppingBagIcon size={22} />
                  Le panier de courses attend votre accord.
                </div>
              )}
              <div className="voice-disclosure">
                <MicrophoneIcon size={18} />
                <p>
                  La voix n’est pas encore connectée. Aucun microphone n’est
                  activé. Vous pouvez découvrir le parcours par écrit.
                </p>
              </div>
              <button
                className="primary-button wide"
                onClick={() =>
                  open({ type: awaitingApproval ? "approval" : "new" })
                }
              >
                {awaitingApproval
                  ? "Vérifier mon panier"
                  : "Confier une demande"}
                <ArrowRightIcon size={18} />
              </button>
            </>
          )}
          {modal.type === "approval" && (
            <>
              <p>
                Livraison proposée aujourd’hui entre 16 h et 17 h. Panier fictif
                du commerce de démonstration.
              </p>
              <ul className="basket">
                {[
                  ["Fruits et légumes", "5 articles", "16,40 €"],
                  ["Produits frais", "4 articles", "18,90 €"],
                  ["Épicerie", "3 articles", "9,50 €"],
                  ["Livraison", "Créneau proposé", "3,00 €"],
                ].map(([name, quantity, price]) => (
                  <li key={name}>
                    <span>
                      <strong>{name}</strong>
                      <small>{quantity}</small>
                    </span>
                    <strong>{price}</strong>
                  </li>
                ))}
              </ul>
              <div className="basket-total">
                <span>Total, livraison comprise</span>
                <strong>47,80 €</strong>
              </div>
              <div className="inline-note">
                <ShieldCheckIcon size={20} />
                <span>
                  Votre accord est simulé. Aucun paiement ni commande réelle.
                </span>
              </div>
              <button
                className="primary-button wide"
                onClick={() => decideApproval("approved")}
              >
                <CheckIcon size={19} />
                Approuver dans la démo
              </button>
              <button
                className="text-button centered"
                onClick={() => decideApproval("declined")}
              >
                Mettre le panier de côté
              </button>
            </>
          )}
          {modal.type === "task" && selectedTask && (
            <>
              <span className={`badge ${selectedTask.status}`}>
                {statusLabels[selectedTask.status]}
              </span>
              <p>{selectedTask.description}</p>
              <ol className="task-steps">
                {selectedTask.steps.map((step, index) => (
                  <li
                    key={step}
                    className={
                      index < selectedTask.completed ? "completed" : ""
                    }
                  >
                    <span>
                      {index < selectedTask.completed ? (
                        <CheckIcon size={15} />
                      ) : (
                        index + 1
                      )}
                    </span>
                    {step}
                  </li>
                ))}
              </ol>
              {selectedTask.id === "groceries" && approval === "approved" && (
                <div className="inline-note">
                  Accord simulé reçu. La confirmation commerçant reste
                  indisponible.
                </div>
              )}
              {(selectedTask.status === "active" ||
                selectedTask.status === "paused") && (
                <div className="dialog-actions">
                  <button
                    className="light-button"
                    onClick={() =>
                      changeTask(
                        selectedTask,
                        selectedTask.status === "paused" ? "active" : "paused",
                      )
                    }
                  >
                    {selectedTask.status === "paused" ? (
                      <PlayIcon size={18} />
                    ) : (
                      <PauseIcon size={18} />
                    )}
                    {selectedTask.status === "paused"
                      ? "Reprendre"
                      : "Mettre en pause"}
                  </button>
                  <button
                    className="text-button danger"
                    onClick={() => changeTask(selectedTask, "cancelled")}
                  >
                    Annuler la demande
                  </button>
                </div>
              )}
              <p className="panel-note">
                Suivi de démonstration. Aucune opération auprès d’un
                prestataire.
              </p>
            </>
          )}
          {modal.type === "memory" && selectedMemory && (
            <form onSubmit={saveMemory}>
              <p className="source-line">{selectedMemory.source}</p>
              <label className="field-label" htmlFor="memory-text">
                Ce que vous souhaitez retenir
              </label>
              <textarea
                id="memory-text"
                value={memoryText}
                onChange={(e) => {
                  setMemoryText(e.target.value);
                  setFormError("");
                }}
                maxLength={400}
                rows={4}
                aria-describedby={formError ? "memory-error" : undefined}
              />
              {formError && (
                <p className="form-error" id="memory-error" role="alert">
                  {formError}
                </p>
              )}
              <p className="privacy-note">
                <UsersIcon size={17} />
                {selectedMemory.shared
                  ? "Partagé avec le foyer fictif"
                  : "Personnel, profil fictif d’Alex"}
              </p>
              <button className="primary-button wide" type="submit">
                Enregistrer la correction
                <CheckIcon size={18} />
              </button>
              {deleteMemory ? (
                <div className="delete-confirm">
                  <p>Oublier ce souvenir dans la démonstration ?</p>
                  <button
                    className="light-button"
                    type="button"
                    onClick={() => {
                      setMemories((prev) =>
                        prev.filter((m) => m.id !== selectedMemory.id),
                      );
                      log("Un souvenir a été supprimé", selectedMemory.title);
                      close();
                      setToast("Souvenir oublié dans la démonstration.");
                    }}
                  >
                    Confirmer la suppression
                  </button>
                  <button
                    className="text-button"
                    type="button"
                    onClick={() => setDeleteMemory(false)}
                  >
                    Conserver
                  </button>
                </div>
              ) : (
                <button
                  className="text-button danger centered"
                  type="button"
                  onClick={() => setDeleteMemory(true)}
                >
                  <TrashIcon size={16} />
                  Oublier ce souvenir
                </button>
              )}
            </form>
          )}
          {modal.type === "household" && (
            <>
              <p>
                Un foyer fictif pour explorer Koyori. Vous consultez l’espace
                personnel d’Alex.
              </p>
              <div className="person-row">
                <span className="avatar">A</span>
                <div>
                  <strong>Alex</strong>
                  <small>Profil actif / administrateur fictif</small>
                </div>
                <CheckCircleIcon size={20} />
              </div>
              <div className="person-row">
                <span className="avatar sam">S</span>
                <div>
                  <strong>Sam</strong>
                  <small>Membre fictif du foyer</small>
                </div>
              </div>
              <div className="inline-note">
                <ShieldCheckIcon size={22} />
                <span>
                  L’authentification et le changement de membre ne sont pas
                  connectés dans cette interface.
                </span>
              </div>
            </>
          )}
          {modal.type === "service" && (
            <>
              <div className="briefing-visual">
                <PlugsConnectedIcon size={42} weight="light" />
              </div>
              <p>
                {modal.name === "Alexa"
                  ? "L’accès vocal via Alexa est l’ambition de Koyori. Cette interface ne dispose pas encore d’une intégration Alexa ou d’un transport vocal connecté."
                  : modal.name === "Google Calendar"
                    ? "Le backend prévoit un connecteur Google Calendar. Cette interface utilise uniquement un agenda fictif ; aucun compte Google n’est connecté."
                    : "Les paniers et les repas sont des scénarios de démonstration. Aucun commerçant réel, paiement ou service de livraison n’est connecté."}
              </p>
              <div className="inline-note">
                <ShieldCheckIcon size={20} />
                Aucune autorisation externe n’a été accordée.
              </div>
              <button className="light-button wide" onClick={close}>
                J’ai compris
              </button>
            </>
          )}
        </Dialog>
      )}
    </div>
  );
}
