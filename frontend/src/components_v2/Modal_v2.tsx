import type { ReactNode } from "react";

export default function Modal_v2({
  title,
  children,
  onClose,
  resizable = false,
  showClose = true,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  resizable?: boolean;
  showClose?: boolean;
}) {
  return (
    <div className="v2-modal-backdrop" role="dialog" aria-modal="true">
      <div
        className="v2-modal-panel"
        style={
          resizable
            ? { resize: "both", minWidth: "min(560px, 96vw)", minHeight: 420, overflow: "hidden" as const }
            : undefined
        }
      >
        <div className="v2-modal-header">
          <h2>{title}</h2>
          {showClose && (
            <button
              type="button"
              className="v2-close-btn"
              onClick={onClose}
              aria-label="关闭"
            >
              ×
            </button>
          )}
        </div>
        {children}
      </div>
    </div>
  );
}
