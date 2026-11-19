import { useEffect, useRef } from "react";
import * as echarts from "echarts";

type TooltipFormat = "amount" | "percent" | "number";

function formatTooltipValue(value: number | null | undefined, format: TooltipFormat = "amount") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "暂无数据";
  if (format === "amount") return `${(Number(value) / 10000).toFixed(2)} 万元`;
  if (format === "percent") return `${(Number(value) * 100).toFixed(2)}%`;
  return Number(value).toFixed(2);
}

/**
 * V2 UI：浅 Pastel 语义色选色 + 费用多色循环。
 * 1) 非 V2 → 维持旧默认 Amber #f59e0b（对老 UI 完全不影响）。
 * 2) V2 但不是费用排名类 → 按 name 语义（预算/超支/销售/费用/…）选浅 pastel 色。
 * 3) V2 且是费用/成本/使用进度这类排名 → 每根柱子按 dataIndex 循环 rainbow 6 pastel 色。
 */
function resolveBaseBarColor(name: string, fallback: string): string {
  const styles =
    typeof document !== "undefined" && document.documentElement
      ? getComputedStyle(document.documentElement)
      : null;
  if (!styles) return fallback;
  const isV2 =
    document.documentElement.dataset?.ui === "v2" ||
    styles.getPropertyValue("--v2-primary").trim() !== "";
  if (!isV2) return fallback;

  const css = (k: string) => styles.getPropertyValue(k).trim();
  const primary = css("--v2-chart-bar-primary") || fallback;
  const secondary = css("--v2-chart-bar-secondary") || "#94a3b8";
  const danger = css("--v2-chart-bar-danger") || "#fb7185";
  const success = css("--v2-chart-bar-success") || "#34d399";
  const info = css("--v2-chart-bar-info") || "#38bdf8";
  const n = (name || "").toLowerCase();

  if (/预算|budget|baseline|基线|目标/.test(name) || /budget|baseline/.test(n)) return secondary;
  if (
    /超支|overrun|risk|danger|差异(为负)?|未达标|负向|缺口|浪费|未上传|异常|失败|警告/.test(name) ||
    /overrun|danger|warning|fail|missed|gap|risk/.test(n)
  )
    return danger;
  if (/节省|正向|save|good|ok|达标|完成|success|良好/.test(name) || /save|good|done|achieved/.test(n))
    return success;
  if (
    /销售|sale|收入|revenue|利润|profit|毛利|gmv/.test(name) ||
    /sale|revenue|profit|gmv|income/.test(n)
  )
    return info;
  return primary;
}

/** 判断是不是"费用多色"场景：费用项目、成本、使用进度、overrun、排名 + 横向条形图 */
function shouldUseRainbow(name: string): boolean {
  if (!document.documentElement || document.documentElement.dataset?.ui !== "v2") return false;
  const n = (name || "").toLowerCase();
  return (
    /费用|成本|使用|overrun|expense|cost|progress|使用率|进度|排名/.test(name) ||
    /expense|cost|overrun|usage|progress|rank/.test(n)
  );
}

/** 读取 6 色 Pastel 调色板（V2） */
function getRainbowPalette(): string[] {
  const styles =
    typeof document !== "undefined" && document.documentElement
      ? getComputedStyle(document.documentElement)
      : null;
  if (!styles) return ["#2dd4bf", "#60a5fa", "#a78bfa", "#34d399", "#fb923c", "#f472b6"];
  const css = (k: string) =>
    styles.getPropertyValue(k).trim() || "";
  const palette = [
    css("--v2-chart-rainbow-1"),
    css("--v2-chart-rainbow-2"),
    css("--v2-chart-rainbow-3"),
    css("--v2-chart-rainbow-4"),
    css("--v2-chart-rainbow-5"),
    css("--v2-chart-rainbow-6")
  ].filter(Boolean);
  return palette.length
    ? palette
    : ["#2dd4bf", "#60a5fa", "#a78bfa", "#34d399", "#fb923c", "#f472b6"];
}

export default function BarChart({
  labels,
  values,
  rawValues,
  name = "金额",
  valueFormatter,
  horizontal = false,
  format = "amount"
}: {
  labels: string[];
  values: number[];
  rawValues?: Array<number | null>;
  name?: string;
  valueFormatter?: (value: number) => string;
  horizontal?: boolean;
  format?: TooltipFormat;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const container = ref.current;
    chartRef.current = echarts.init(container, undefined, { renderer: "canvas", useDirtyRect: true });
    const resize = () => chartRef.current?.resize();
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(container);
    window.addEventListener("resize", resize);
    requestAnimationFrame(resize);
    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("resize", resize);
      chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const styles =
      typeof document !== "undefined" ? getComputedStyle(document.documentElement) : null;
    const textColor = (styles?.getPropertyValue("--muted").trim()) || "#64748b";
    const gridColor = (styles?.getPropertyValue("--border").trim()) || "#e2e8f0";
    const DEFAULT_FALLBACK = "#f59e0b";
    const baseColor = resolveBaseBarColor(name, DEFAULT_FALLBACK);
    const isV2 =
      !!styles && document.documentElement.dataset?.ui === "v2";
    const useRainbow = isV2 && shouldUseRainbow(name);
    const rainbow = useRainbow ? getRainbowPalette() : [];

    /**
     * 逐柱颜色：
     * - 费用多色场景 → dataIndex 循环 rainbow（但超支/负值仍然改 danger，节省改 success）
     * - 非费用多色但 V2 或含"差异/节省"语义 → 负值 danger，节省改 success，其余 baseColor
     * - 否则 → baseColor（老 UI 仍是 Amber fallback）
     */
    const hasSignedSemantic = /差异|diff|节省|超支|正负|gap|delta|利润差|销售差/i.test(name || "");
    const perBarColorFn =
      useRainbow || hasSignedSemantic || isV2
        ? (params: { dataIndex: number; value: number }) => {
            const v = Number(params.value);
            const isNaN = Number.isNaN(v);
            if (isV2 && !isNaN && v < 0) {
              const danger = styles?.getPropertyValue("--v2-chart-bar-danger").trim();
              return danger || "#fb7185";
            }
            if (isV2 && !isNaN && /节省|save|正向|良好|完成|达标/.test(name || "") && v >= 0) {
              const success = styles?.getPropertyValue("--v2-chart-bar-success").trim();
              return success || "#34d399";
            }
            if (useRainbow) return rainbow[params.dataIndex % rainbow.length];
            return baseColor;
          }
        : undefined;

    const borderRadius: [number, number, number, number] = horizontal
      ? [0, 6, 6, 0]
      : [6, 6, 0, 0];

    chart.setOption(
      {
        animation: false,
        animationDuration: 0,
        animationDurationUpdate: 0,
        tooltip: {
          trigger: "axis",
          confine: true,
          transitionDuration: 0,
          axisPointer: { animation: false, type: "shadow" },
          valueFormatter,
          formatter: (params: unknown) => {
            const item = Array.isArray(params)
              ? (params[0] as {
                  dataIndex: number;
                  marker: string;
                  seriesName: string;
                  value: number;
                })
              : (params as { dataIndex: number; marker: string; seriesName: string; value: number });
            const rawValue = rawValues?.[item.dataIndex] ?? item.value;
            return `<strong>${
              labels[item.dataIndex] || ""
            }</strong><br/>${item.marker}${item.seriesName}：${formatTooltipValue(
              rawValue,
              format
            )}`;
          }
        },
        grid: horizontal
          ? { left: 96, right: 28, bottom: 28, top: 18 }
          : { left: 48, right: 18, bottom: 48, top: 24 },
        xAxis: horizontal
          ? {
              type: "value",
              axisLabel: { color: textColor },
              splitLine: { lineStyle: { color: gridColor } }
            }
          : {
              type: "category",
              data: labels,
              axisLabel: { rotate: labels.length > 6 ? 28 : 0, color: textColor },
              axisLine: { lineStyle: { color: gridColor } }
            },
        yAxis: horizontal
          ? {
              type: "category",
              data: labels,
              axisLabel: { color: textColor, width: 82, overflow: "truncate" },
              axisLine: { lineStyle: { color: gridColor } }
            }
          : {
              type: "value",
              axisLabel: { color: textColor },
              splitLine: { lineStyle: { color: gridColor } }
            },
        series: [
          {
            name,
            type: "bar",
            data: values,
            itemStyle: perBarColorFn
              ? ({
                  color: perBarColorFn as any,
                  borderRadius,
                  borderWidth: 0
                } as any)
              : { color: baseColor, borderRadius, borderWidth: 0 },
            barMaxWidth: 36
          }
        ]
      },
      true
    );
  }, [labels, values, rawValues, name, valueFormatter, horizontal, format]);
  return <div className="chart" ref={ref} />;
}
