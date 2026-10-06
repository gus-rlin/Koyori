export type Page =
  | "today"
  | "tasks"
  | "memory"
  | "routines"
  | "services"
  | "activity"
  | "settings";
export type Modal =
  | {
      type: "new" | "briefing" | "approval" | "household" | "service";
      name?: string;
    }
  | { type: "task"; id: string }
  | { type: "memory"; id: string }
  | null;
