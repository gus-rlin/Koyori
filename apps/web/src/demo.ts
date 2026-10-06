// Synthetic fixtures only. No provider request or backend authorization is implied.
export type TaskStatus = "active" | "paused" | "done" | "cancelled";
export type Task = {
  id: string;
  title: string;
  description: string;
  category: "shopping" | "dinner" | "home";
  time: string;
  status: TaskStatus;
  steps: string[];
  completed: number;
};
export type Memory = {
  id: string;
  title: string;
  text: string;
  source: string;
  shared: boolean;
};
export const initialTasks: Task[] = [
  {
    id: "groceries",
    title: "Les courses de la semaine",
    description: "Votre liste habituelle, avec quelques attentions.",
    category: "shopping",
    time: "Aujourd’hui, 16 h - 17 h",
    status: "active",
    steps: [
      "Liste et préférences retrouvées",
      "Panier préparé : 12 articles",
      "Attendre votre accord",
      "Confirmer avec le service",
    ],
    completed: 2,
  },
  {
    id: "dinner",
    title: "Un dîner pour quatre",
    description: "Quelque chose de simple. Et une option végétarienne.",
    category: "dinner",
    time: "Ce soir, 20 h",
    status: "active",
    steps: [
      "Préférences du foyer retrouvées",
      "Menu végétarien proposé",
      "Vérifier les disponibilités",
      "Vous présenter les options",
    ],
    completed: 1,
  },
  {
    id: "weekend",
    title: "Préparer le week-end",
    description: "Quelques idées pour profiter de la maison ensemble.",
    category: "home",
    time: "Samedi, 10 h",
    status: "done",
    steps: ["Agenda consulté", "Idées rassemblées", "Proposition prête"],
    completed: 3,
  },
];
export const initialMemories: Memory[] = [
  {
    id: "food",
    title: "À table",
    text: "Une option végétarienne quand Julie est là.",
    source: "Préférence partagée dans le scénario du 5 octobre",
    shared: true,
  },
  {
    id: "breakfast",
    title: "Votre petit déjeuner",
    text: "Un chocolat chaud peu sucré et un croissant.",
    source: "Correction d’Alex dans le scénario du 4 octobre",
    shared: false,
  },
  {
    id: "evening",
    title: "En semaine",
    text: "Des dîners simples, prêts en moins de 30 minutes.",
    source: "Préférence d’Alex dans le scénario du 3 octobre",
    shared: true,
  },
];
export const initialRoutines = [
  {
    id: "morning",
    title: "Le point du matin",
    description: "L’agenda, les priorités et ce qui peut attendre.",
    when: "Du lundi au vendredi, 8 h",
    enabled: true,
  },
  {
    id: "shopping",
    title: "Penser aux courses",
    description: "Préparer la liste en tenant compte des repas prévus.",
    when: "Chaque mardi, 10 h",
    enabled: true,
  },
  {
    id: "quiet",
    title: "Une soirée tranquille",
    description: "Regrouper les informations non urgentes pour le lendemain.",
    when: "Tous les jours, à partir de 21 h",
    enabled: false,
  },
];
export const statusLabels: Record<TaskStatus, string> = {
  active: "En cours",
  paused: "En pause",
  done: "Terminé",
  cancelled: "Annulé",
};

export type Activity = {
  id: string;
  title: string;
  detail: string;
  time: string;
};
export const initialActivity: Activity[] = [
  {
    id: "a1",
    title: "Le panier est prêt à être vérifié",
    detail: "Courses de la semaine",
    time: "10:24",
  },
  {
    id: "a2",
    title: "Le dîner s’adapte à vos invités",
    detail: "Une option végétarienne pour Julie",
    time: "09:45",
  },
  {
    id: "a3",
    title: "Votre semaine a été passée en revue",
    detail: "Les priorités sont rassemblées",
    time: "08:00",
  },
];
