import type { ReactNode } from "react";

export default function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="chart-card">
      <h3>{title}</h3>
      {children}
    </section>
  );
}
