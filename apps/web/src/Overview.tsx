import {
  ArrowRightIcon,
  ArrowUpRightIcon,
  CalendarBlankIcon,
  CheckCircleIcon,
  LeafIcon,
  PlusIcon,
  ShoppingBagIcon,
  SunIcon,
  WaveformIcon,
} from "@phosphor-icons/react";
import { TaskCard, Empty, Timeline } from "./components";
import type { Task, Memory, Activity } from "./demo";
import type { Page, Modal } from "./ui-types";
type Props = {
  activeTasks: Task[];
  memories: Memory[];
  activities: Activity[];
  awaitingApproval: boolean;
  approval: string;
  open: (modal: Modal) => void;
  navigate: (page: Page) => void;
};
export function Overview({
  activeTasks,
  memories,
  activities,
  awaitingApproval,
  approval,
  open,
  navigate,
}: Props) {
  return (
    <>
      <div className="day-heading">
        <span>
          Mardi 6 octobre <span className="muted">/ Journée d’exemple</span>
        </span>
        <span className="day-caption">
          <SunIcon size={17} />À votre rythme.
        </span>
      </div>
      <section className="welcome" aria-labelledby="welcome-title">
        <div className="welcome-copy">
          <div className="greeting-label">
            <span className="mini-mark">
              <WaveformIcon size={17} />
            </span>
            Votre quotidien, en bonne compagnie
          </div>
          <h1 id="welcome-title">
            Bonjour Alex<span>.</span>
            <br />
            L’esprit un peu plus libre.
          </h1>
          <p>
            {activeTasks.length > 0
              ? `${activeTasks.length} demandes à suivre, vos habitudes en tête.`
              : "Vos demandes sont à jour."}
            <br />
            On fait le point sur votre journée ?
          </p>
          <button
            className="primary-button"
            onClick={() => open({ type: "briefing" })}
          >
            <WaveformIcon size={20} />
            Faire le point
            <ArrowRightIcon size={17} />
          </button>
        </div>
        <div className="welcome-image">
          <img
            src="/home.webp"
            srcSet="/home-small.webp 800w, /home.webp 1200w"
            sizes="(max-width: 767px) calc(100vw - 40px), 45vw"
            alt="Un salon lumineux ouvert sur un jardin, un moment de calme à la maison"
            width="768"
            height="512"
            fetchPriority="high"
          />
        </div>
      </section>
      <div className="daily-layout">
        <div className="daily-main">
          {awaitingApproval ? (
            <section
              className="approval-strip"
              aria-label="Décision en attente"
            >
              <span className="approval-symbol">
                <ShoppingBagIcon size={22} />
              </span>
              <div>
                <span className="small-label">Un petit point à valider</span>
                <h2>Les courses sont prêtes.</h2>
                <p>12 articles pour 47,80 €. À vous de donner le feu vert.</p>
              </div>
              <button
                className="light-button"
                onClick={() => open({ type: "approval" })}
              >
                Voir le panier
                <ArrowUpRightIcon size={17} />
              </button>
            </section>
          ) : (
            <section className="all-clear">
              <CheckCircleIcon size={24} />
              <div>
                <strong>
                  {approval === "approved"
                    ? "Votre accord est enregistré dans la démo."
                    : "Aucune décision en attente."}
                </strong>
                <p>
                  {approval === "approved"
                    ? "Aucun achat réel n’a été effectué."
                    : "Vous pouvez suivre vos demandes ci-dessous."}
                </p>
              </div>
            </section>
          )}
          <section className="requests-section">
            <div className="section-heading">
              <h2>
                Je m’en occupe
                <span className="heading-count">{activeTasks.length}</span>
              </h2>
              <button className="text-button" onClick={() => navigate("tasks")}>
                Tout voir
                <ArrowRightIcon size={16} />
              </button>
            </div>
            <div className="task-grid">
              {activeTasks.slice(0, 2).map((t) => (
                <TaskCard
                  key={t.id}
                  task={t}
                  onOpen={() => open({ type: "task", id: t.id })}
                />
              ))}
            </div>
            {activeTasks.length === 0 && (
              <Empty
                title="Rien à suivre pour le moment"
                text="Confiez une nouvelle demande à Koyori pour commencer."
              />
            )}
            <button
              className="add-request"
              onClick={() => open({ type: "new" })}
            >
              <PlusIcon size={17} />
              Confier une nouvelle demande
              <span>Un dîner, une sortie, une chose à ne pas oublier…</span>
            </button>
          </section>
          <section className="activity-section">
            <div className="section-heading">
              <h2>Les dernières attentions</h2>
              <button
                className="text-button"
                onClick={() => navigate("activity")}
              >
                Toute l’activité
                <ArrowRightIcon size={16} />
              </button>
            </div>
            <Timeline activities={activities.slice(0, 3)} />
          </section>
        </div>
        <aside
          className="daily-aside"
          aria-label="Votre journée et vos préférences"
        >
          <section className="schedule">
            <div className="section-heading">
              <h2>Dans votre journée</h2>
              <CalendarBlankIcon size={19} />
            </div>
            <div className="schedule-date">
              <strong>06</strong>
              <span>
                Mardi
                <br />
                <span className="muted">Octobre 2026</span>
              </span>
            </div>
            <ol className="agenda">
              <li>
                <time>11:00</time>
                <div>
                  <strong>Un rendez-vous en ville</strong>
                  <p>Votre agenda personnel</p>
                </div>
              </li>
              <li>
                <time>16:00</time>
                <div>
                  <strong>Un créneau pour les courses</strong>
                  <p>
                    {approval === "approved"
                      ? "Accord simulé, sans réservation"
                      : "À confirmer avec votre accord"}
                  </p>
                </div>
              </li>
              <li>
                <time>20:00</time>
                <div>
                  <strong>À quatre autour de la table</strong>
                  <p>Un dîner en préparation</p>
                </div>
              </li>
            </ol>
            <div className="schedule-foot">
              <CalendarBlankIcon size={15} />
              Agenda d’exemple
            </div>
          </section>
          <section className="memory-peek">
            <span className="memory-leaf">
              <LeafIcon size={24} weight="light" />
            </span>
            <h2>
              Les petites choses
              <br /> qui comptent.
            </h2>
            <p>
              {memories[0]?.text ??
                "Vos préférences trouveront leur place ici."}
            </p>
            <button className="text-button" onClick={() => navigate("memory")}>
              Explorer ma mémoire
              <ArrowUpRightIcon size={17} />
            </button>
          </section>
        </aside>
      </div>
    </>
  );
}
