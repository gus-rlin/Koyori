import {
  ShoppingBagIcon,
  ForkKnifeIcon,
  HouseLineIcon,
  ClockIcon,
  ArrowUpRightIcon,
  LeafIcon,
  CheckIcon,
  type Icon,
} from "@phosphor-icons/react";
import { statusLabels, type Task, type Activity } from "./demo";
const taskIcons: Record<Task["category"], Icon> = {
  shopping: ShoppingBagIcon,
  dinner: ForkKnifeIcon,
  home: HouseLineIcon,
};
export function TaskCard({ task, onOpen }: { task: Task; onOpen: () => void }) {
  const Symbol = taskIcons[task.category];
  return (
    <button className="task-card" onClick={onOpen}>
      <div className="task-top">
        <span className={`tile-icon ${task.category}`}>
          <Symbol size={23} weight="light" />
        </span>
        <span className={`badge ${task.status}`}>
          {task.status === "active" && <span className="status-dot" />}
          {statusLabels[task.status]}
        </span>
      </div>
      <h3>{task.title}</h3>
      <p>{task.description}</p>
      <div
        className="task-progress"
        aria-label={`${task.completed} étapes sur ${task.steps.length}`}
      >
        {task.steps.map((step, i) => (
          <span key={step} className={i < task.completed ? "complete" : ""} />
        ))}
      </div>
      <div className="task-bottom">
        <span>
          <ClockIcon size={15} />
          {task.time}
        </span>
        <ArrowUpRightIcon size={19} />
      </div>
    </button>
  );
}
export function Empty({ title, text }: { title: string; text: string }) {
  return (
    <div className="empty">
      <LeafIcon size={32} weight="light" />
      <h2>{title}</h2>
      <p>{text}</p>
    </div>
  );
}
export function Timeline({ activities }: { activities: Activity[] }) {
  return (
    <ol className="timeline">
      {activities.map((a) => (
        <li key={a.id}>
          <time>{a.time}</time>
          <span className="timeline-mark">
            <CheckIcon size={12} />
          </span>
          <div>
            <strong>{a.title}</strong>
            <p>{a.detail}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}
