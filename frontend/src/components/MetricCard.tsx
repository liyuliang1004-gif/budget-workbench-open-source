interface Props {
  label: string;
  value: string | number;
  hint?: string;
}

export default function MetricCard({ label, value, hint }: Props) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
      {hint && <small>{hint}</small>}
    </div>
  );
}
