import { translateSeverity } from "../utils/formatters";

interface Props {
  value?: string | null;
}

export default function StatusBadge({ value }: Props) {
  const text = value || "未知";
  const level = text.includes("失败") || text === "error" ? "danger" : text.includes("警告") || text === "warning" ? "warning" : text.includes("通过") || text.includes("已入库") ? "success" : "info";
  return <span className={`status-badge ${level}`}>{translateSeverity(text)}</span>;
}
