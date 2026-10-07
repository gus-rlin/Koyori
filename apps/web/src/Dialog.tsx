import { useEffect, useRef, type ReactNode } from "react";
import { XIcon } from "@phosphor-icons/react";

export function Dialog({
  title,
  onClose,
  children,
  demo = false,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  demo?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  // Native modal supplies focus containment, Escape handling and background inertness.
  useEffect(() => {
    const dialog = ref.current!;
    const trigger = document.activeElement as HTMLElement | null;
    dialog.showModal();
    return () => {
      dialog.close();
      trigger?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={(event) => {
        // React owns closure; the caller may keep the modal open during a mutation.
        event.preventDefault();
        onClose();
      }}
      aria-labelledby="dialog-title"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="dialog-content">
        <header className="dialog-header">
          <span className="small-label">
            {demo ? "Koyori / démonstration" : "Koyori / espace personnel"}
          </span>
          <button className="icon-button" onClick={onClose} aria-label="Fermer">
            <XIcon size={20} />
          </button>
        </header>
        <h2 id="dialog-title">{title}</h2>
        {children}
      </div>
    </dialog>
  );
}
