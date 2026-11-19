import { useEffect, useRef } from "react";
import * as echarts from "echarts";

type TooltipFormat = "amount" | "percent" | "number";
type LineChartVariant = "line" | "smooth_line" | "area" | "step_line" | "scatter";

interface TooltipExtraRow {
  label: string;
  value: number | null | undefined;
  format?: TooltipFormat;
}

interface MissingRange {
  start: number;
  end: number;
  label?: string;
}

interface LineSeries {
  name: string;
  data: Array<number | null>;
  rawData?: Array<number | null>;
  dashed?: boolean;
  format?: TooltipFormat;
  missingLabel?: string;
}

function formatTooltipValue(value: number | null | undefined, format: TooltipFormat = "number", missingLabel = "未上传实际数据") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return missingLabel;
  if (format === "amount") return `${(Number(value) / 10000).toFixed(2)} 万元`;
  if (format === "percent") return `${(Number(value) * 100).toFixed(2)}%`;
  return Number(value).toFixed(2);
}

function getSeriesColor(index: number, dashed?: boolean) {
  /**
   * V2 UI 折线调色板：
   *  1 → 费用/成本 → V2 主色 (teal/琥珀金 dark)
   *  2 → 实际/差异/预算2 → rose (红玫瑰，对比主色但不刺眼)
   *  3 → 销售/利润/收入 → sky
   *  4 → 基准/同期/对比 → slate
   * 非 V2 保持默认回退，但默认也不再用不协调的草绿/紫蓝
   */
  const FALLBACK = ["#0d9488", "#e11d48", "#0284c7", "#64748b"];
  const DASHED_FALLBACK = "#64748b";
  const styles =
    typeof document !== "undefined" && document.documentElement
      ? getComputedStyle(document.documentElement)
      : null;
  const isV2 =
    !!styles &&
    (document.documentElement.dataset?.ui === "v2" ||
      (styles.getPropertyValue("--v2-primary").trim() !== ""));
  if (!styles || !isV2) {
    if (dashed) return DASHED_FALLBACK;
    return FALLBACK[index % FALLBACK.length];
  }
  const palette = [
    styles.getPropertyValue("--v2-chart-line-palette-1").trim() || FALLBACK[0],
    styles.getPropertyValue("--v2-chart-line-palette-2").trim() || FALLBACK[1],
    styles.getPropertyValue("--v2-chart-line-palette-3").trim() || FALLBACK[2],
    styles.getPropertyValue("--v2-chart-line-palette-4").trim() || FALLBACK[3]
  ];
  if (dashed) {
    return styles.getPropertyValue("--v2-chart-line-palette-4").trim() || DASHED_FALLBACK;
  }
  return palette[index % palette.length];
}

const chartGrid = { left: 48, right: 18, bottom: 32, top: 48 };
const activeLineCharts = new Set<echarts.ECharts>();

function hideTooltip(chart: echarts.ECharts | null) {
  chart?.dispatchAction({ type: "hideTip" });
}

function hideTooltipDom(container: HTMLElement) {
  container.querySelectorAll<HTMLElement>(".line-chart-tooltip").forEach((tooltip) => {
    tooltip.style.display = "none";
  });
  container.querySelectorAll("div").forEach((element) => {
    const tooltip = element as HTMLElement;
    const style = getComputedStyle(tooltip);
    if (style.position === "absolute" && style.pointerEvents === "none" && style.zIndex === "9999999") {
      tooltip.style.display = "none";
    }
  });
}

export default function LineChart({
  labels,
  series,
  valueFormatter,
  extraTooltipRows = [],
  variant = "line",
  missingRanges = []
}: {
  labels: string[];
  series: LineSeries[];
  valueFormatter?: (value: number) => string;
  extraTooltipRows?: TooltipExtraRow[][];
  variant?: LineChartVariant;
  missingRanges?: MissingRange[];
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const metaRef = useRef({ labels, series, extraTooltipRows, missingRanges });

  useEffect(() => {
    metaRef.current = { labels, series, extraTooltipRows, missingRanges };
  }, [labels, series, extraTooltipRows, missingRanges]);

  useEffect(() => {
    if (!ref.current) return;
    const container = ref.current;
    const chart = echarts.init(container, undefined, { renderer: "canvas", useDirtyRect: true });
    const tooltipElement = document.createElement("div");
    tooltipElement.className = "line-chart-tooltip";
    tooltipElement.style.cssText = [
      "position:absolute",
      "display:none",
      "z-index:20",
      "max-width:260px",
      "padding:10px 12px",
      "border:1px solid #b7b9be",
      "border-radius:4px",
      "background:#fff",
      "box-shadow:1px 2px 10px rgba(0,0,0,.18)",
      "color:#4b5563",
      "font:14px/21px sans-serif",
      "pointer-events:none",
      "white-space:nowrap"
    ].join(";");
    container.appendChild(tooltipElement);
    tooltipRef.current = tooltipElement;
    chartRef.current = chart;
    activeLineCharts.add(chart);
    const hideOtherTooltips = () => {
      activeLineCharts.forEach((chart) => {
        if (chart !== chartRef.current) hideTooltip(chart);
      });
      document.querySelectorAll<HTMLElement>(".chart").forEach((chartContainer) => {
        if (chartContainer !== container) hideTooltipDom(chartContainer);
      });
    };
    const hideCurrentTooltip = () => {
      hideTooltip(chartRef.current);
      hideTooltipDom(container);
    };
    const tooltipMarker = (color: string) => `<span style="display:inline-block;width:9px;height:9px;margin-right:6px;border-radius:50%;background:${color};"></span>`;
    const tooltipHtmlForIndex = (index: number) => {
      const { labels: currentLabels, series: currentSeries, extraTooltipRows: currentExtraRows, missingRanges: currentMissingRanges } = metaRef.current;
      const missingRange = currentMissingRanges.find((range) => index >= range.start && index <= range.end);
      const lines = [`<strong style="display:block;margin-bottom:6px;color:#111827;">${currentLabels[index] || ""}</strong>`];
      currentSeries.forEach((item, seriesIndex) => {
        const rawValue = item.rawData?.[index] ?? item.data?.[index];
        if (rawValue === null || rawValue === undefined || Number.isNaN(Number(rawValue))) return;
        lines.push(`${tooltipMarker(getSeriesColor(seriesIndex, item.dashed))}${item.name}：${formatTooltipValue(rawValue, item.format || "amount", item.missingLabel)}`);
      });
      if (missingRange) {
        lines.push(`实际：${missingRange.label || "未上传实际数据"}`);
      } else {
        (currentExtraRows[index] || []).forEach((item) => {
          lines.push(`${item.label}：${formatTooltipValue(item.value, item.format || "amount", item.label.includes("达成") ? "无预算基数" : "暂无数据")}`);
        });
      }
      return lines.join("<br/>");
    };
    const showTooltipAtPointer = (event: { offsetX?: number; offsetY?: number; event?: { offsetX?: number; offsetY?: number } }) => {
      hideOtherTooltips();
      const tooltipElement = tooltipRef.current;
      if (!tooltipElement) return;
      const offsetX = event.offsetX ?? event.event?.offsetX;
      const offsetY = event.offsetY ?? event.event?.offsetY;
      if (offsetX === undefined || offsetY === undefined) return;
      const width = container.clientWidth;
      const height = container.clientHeight;
      const plotWidth = width - chartGrid.left - chartGrid.right;
      const plotHeight = height - chartGrid.top - chartGrid.bottom;
      if (plotWidth <= 0 || plotHeight <= 0) return;
      if (offsetX < chartGrid.left || offsetX > width - chartGrid.right || offsetY < chartGrid.top || offsetY > height - chartGrid.bottom) {
        hideCurrentTooltip();
        return;
      }
      const { labels: currentLabels, series: currentSeries } = metaRef.current;
      if (!currentLabels.length || !currentSeries.length) return;
      const dataIndex = Math.max(0, Math.min(currentLabels.length - 1, Math.round(((offsetX - chartGrid.left) / plotWidth) * (currentLabels.length - 1))));
      tooltipElement.innerHTML = tooltipHtmlForIndex(dataIndex);
      tooltipElement.style.display = "block";
      const tooltipWidth = tooltipElement.offsetWidth || 220;
      const tooltipHeight = tooltipElement.offsetHeight || 90;
      const left = Math.min(Math.max(8, offsetX + 12), Math.max(8, width - tooltipWidth - 8));
      const top = Math.min(Math.max(8, offsetY + 12), Math.max(8, height - tooltipHeight - 8));
      tooltipElement.style.left = `${left}px`;
      tooltipElement.style.top = `${top}px`;
    };
    const resize = () => chartRef.current?.resize();
    const resizeObserver = new ResizeObserver(resize);
    const zr = chart.getZr();
    resizeObserver.observe(container);
    container.addEventListener("pointerenter", hideOtherTooltips);
    container.addEventListener("pointermove", showTooltipAtPointer);
    container.addEventListener("click", showTooltipAtPointer);
    container.addEventListener("pointerleave", hideCurrentTooltip);
    container.addEventListener("blur", hideCurrentTooltip);
    zr.on("mousemove", showTooltipAtPointer);
    zr.on("click", hideOtherTooltips);
    zr.on("globalout", hideCurrentTooltip);
    window.addEventListener("resize", resize);
    requestAnimationFrame(resize);
    return () => {
      resizeObserver.disconnect();
      container.removeEventListener("pointerenter", hideOtherTooltips);
      container.removeEventListener("pointermove", showTooltipAtPointer);
      container.removeEventListener("click", showTooltipAtPointer);
      container.removeEventListener("pointerleave", hideCurrentTooltip);
      container.removeEventListener("blur", hideCurrentTooltip);
      zr.off("mousemove", showTooltipAtPointer);
      zr.off("click", hideOtherTooltips);
      zr.off("globalout", hideCurrentTooltip);
      window.removeEventListener("resize", resize);
      activeLineCharts.delete(chart);
      hideCurrentTooltip();
      tooltipElement.remove();
      tooltipRef.current = null;
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    hideTooltip(chart);
    if (ref.current) hideTooltipDom(ref.current);
    const styles = getComputedStyle(document.documentElement);
    const textColor = styles.getPropertyValue("--muted").trim();
    const gridColor = styles.getPropertyValue("--border").trim();
    const missingRangeForIndex = (index: number) => missingRanges.find((range) => index >= range.start && index <= range.end);
    const missingMarkArea = missingRanges.length ? {
      silent: true,
      itemStyle: { color: "rgba(148, 163, 184, 0.08)" },
      label: { show: false },
      data: missingRanges.map((range) => [
        { xAxis: labels[range.start], name: range.label || "未上传实际数据" },
        { xAxis: labels[range.end] }
      ])
    } : undefined;
    const missingMarkLine = missingRanges.length ? {
      silent: true,
      symbol: "none",
      lineStyle: { color: "#94a3b8", width: 1.2, type: "dashed" },
      label: { color: "#64748b", formatter: "未上传", position: "insideEndTop" },
      data: missingRanges.map((range) => ({ xAxis: labels[range.start] }))
    } : undefined;
    chart.setOption({
      animation: false,
      animationDuration: 0,
      animationDurationUpdate: 0,
      tooltip: {
        show: false
      },
      legend: { top: 0, textStyle: { color: textColor } },
      grid: chartGrid,
      xAxis: { type: "category", data: labels, axisLabel: { color: textColor }, axisLine: { lineStyle: { color: gridColor } } },
      yAxis: { type: "value", axisLabel: { color: textColor }, splitLine: { lineStyle: { color: gridColor } } },
      series: series.map((item, index) => ({
        name: item.name,
        data: item.data,
        type: variant === "scatter" ? "scatter" : "line",
        smooth: variant === "smooth_line",
        step: variant === "step_line" ? "middle" : false,
        areaStyle: variant === "area" ? { opacity: item.dashed ? 0.08 : 0.18 } : undefined,
        connectNulls: false,
        lineStyle: { width: item.dashed ? 2.2 : 2.6, type: item.dashed ? "dashed" : "solid", color: getSeriesColor(index, item.dashed) },
        itemStyle: { color: getSeriesColor(index, item.dashed), borderWidth: 1.5 },
        showSymbol: true,
        symbol: item.dashed ? "emptyCircle" : "circle",
        symbolSize: variant === "scatter" ? 7 : 5.5,
        emphasis: { scale: 1.15, lineStyle: { width: item.dashed ? 2.8 : 3.2 } },
        blur: { lineStyle: { opacity: 1 }, itemStyle: { opacity: 1 } },
        markArea: index === 0 ? missingMarkArea : undefined,
        markLine: index === 0 ? missingMarkLine : undefined
      }))
    }, true);
  }, [labels, series, valueFormatter, extraTooltipRows, variant, missingRanges]);

  return <div className="chart" ref={ref} />;
}
