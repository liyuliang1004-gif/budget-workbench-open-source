import { useEffect, useRef } from "react";
import * as echarts from "echarts";

export default function PieChart({ data, valueFormatter }: { data: Array<{ name: string; value: number }>; valueFormatter?: (value: number) => string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current);
    const styles = getComputedStyle(document.documentElement);
    const textColor = styles.getPropertyValue("--muted").trim();
    chart.setOption({
      tooltip: { trigger: "item", valueFormatter },
      series: [{ type: "pie", radius: ["45%", "70%"], label: { color: textColor }, data }]
    });
    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [data, valueFormatter]);
  return <div className="chart" ref={ref} />;
}
