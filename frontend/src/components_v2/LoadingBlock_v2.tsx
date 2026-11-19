export default function LoadingBlock_v2({ text = "加载中…" }: { text?: string }) {
  return (
    <div className="v2-empty" style={{ opacity: 0.8 }}>
      <div style={{ display: "grid", gap: 10, justifyItems: "center" }}>
        <div
          style={{
            width: 28,
            height: 28,
            border: "3px solid var(--v2-primary-weak)",
            borderTopColor: "var(--v2-primary)",
            borderRadius: "50%",
            animation: "v2-spin 0.9s linear infinite",
          }}
        />
        <div className="muted">{text}</div>
      </div>
      <style>{`@keyframes v2-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
