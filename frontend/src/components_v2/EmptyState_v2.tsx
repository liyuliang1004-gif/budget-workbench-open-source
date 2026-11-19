export default function EmptyState_v2({ text = "暂无数据" }: { text?: string }) {
  return <div className="v2-empty">{text}</div>;
}
