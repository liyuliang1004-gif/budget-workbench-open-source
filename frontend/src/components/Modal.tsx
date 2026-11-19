import type { ReactNode } from "react";

export default function Modal({ title, children, onClose, resizable = false, showClose = true }: { title: string; children: ReactNode; onClose: () => void; resizable?: boolean; showClose?: boolean }) {
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className={resizable ? "modal-panel resizable-modal" : "modal-panel"}>
        <div className="section-heading">
          <h2>{title}</h2>
          {showClose && <button className="secondary icon-button" onClick={onClose} aria-label="关闭">×</button>}
        </div>
        {children}
      </div>
    </div>
  );
}
