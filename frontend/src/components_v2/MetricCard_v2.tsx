interface Props {
  label: string;
  value: string | number;
  hint?: string;
  valueColor?: "default" | "primary" | "success" | "warning" | "danger";
  footerTrend?: "up" | "down" | "warn" | "neutral";
  footerText?: string;
  /** 可选：卡片左上角或底部的装饰图标（emoji），例如 "📦" / "💰" / "⚠️"，不传入则自动匹配 */
  decorIcon?: string;
  /** 可选：指定装饰颜色变体，不传则按 footerText 内容自动判断 */
  decorVariant?: "tag" | "info" | "purple" | "amber";
}

/**
 * MetricCard_v2 —— 指标卡装饰升级版
 * Props 完全向后兼容（新增 decorIcon / decorVariant 可省略）。
 * 不改变布局结构、不改变外部数据和逻辑，只在指标卡底部加小色块装饰：
 * - footerText 含「完成率 / 达成率 / %」→ 箭头胶囊
 * - 含「偏低」→ 黄警告方框
 * - 含「实际件数 / 订单 / 销售额 / 利润率 / 费用率」→ 📦/💰/💵/📈/📊 图标方框
 * - 或通过 decorIcon 显式传入
 */
export default function MetricCard_v2({
  label,
  value,
  hint,
  valueColor = "default",
  footerTrend = "neutral",
  footerText,
  decorIcon,
  decorVariant,
}: Props) {
  const hasFooter = Boolean(hint || footerText);
  const footerContent = hint ?? footerText ?? "";

  // 自动装饰：根据 label / footerText 匹配图标和变体
  let autoIcon: string | null = decorIcon ?? null;
  let autoVariant: NonNullable<Props["decorVariant"]> = decorVariant ?? "tag";
  if (!autoIcon) {
    const l = `${label}${footerContent || ""}`;
    if (l.includes("销售额") || l.includes("销售表现") || l.includes("客单价")) {
      autoIcon = "💵";
      autoVariant = "tag";
    } else if (l.includes("销售成本") || l.includes("成本额")) {
      autoIcon = "📦";
      autoVariant = "amber";
    } else if (l.includes("费用") || l.includes("支出") || l.includes("费用率")) {
      autoIcon = "📊";
      autoVariant = "amber";
    } else if (l.includes("净利润") || l.includes("利润额") || l.includes("毛利") || l.includes("利润率")) {
      autoIcon = "📈";
      autoVariant = "purple";
    } else if (l.includes("销售数量") || l.includes("件数")) {
      autoIcon = "📦";
      autoVariant = "tag";
    } else if (l.includes("订单") || l.includes("平均订单") || l.includes("客单")) {
      autoIcon = "💰";
      autoVariant = "tag";
    } else if (l.includes("预算")) {
      autoIcon = "🎯";
      autoVariant = "info";
    }
  }

  const arrow =
    footerTrend === "up"
      ? "↑"
      : footerTrend === "down"
      ? "↓"
      : footerTrend === "warn"
      ? "⚠️"
      : "";

  // 渲染 footer chip：根据内容自动选样式
  const footerChip = (() => {
    if (!hasFooter) return null;
    const f = footerContent;

    if (f.includes("偏低")) {
      return <span className="v2-warn-chip">{f}</span>;
    }

    if (
      f.includes("完成率") ||
      f.includes("达成率") ||
      f.match(/\d+(\.\d+)?%/)
    ) {
      let dir: "up" | "down" | "neutral" = "neutral";
      if (
        footerTrend === "up" ||
        f.includes("↑") ||
        f.includes("增长") ||
        f.includes("增加")
      )
        dir = "up";
      if (
        footerTrend === "down" ||
        f.includes("↓") ||
        f.includes("低于") ||
        f.includes("下降") ||
        f.includes("节省")
      )
        dir = "down";
      return (
        <span className={`v2-trend-chip ${dir !== "neutral" ? dir : ""}`}>
          {dir === "up" && <span className="arrow">↑</span>}
          {dir === "down" && <span className="arrow">↓</span>}
          {!dir && footerTrend !== "neutral" && footerTrend !== "warn" ? (
            <span className="arrow">{arrow}</span>
          ) : null}
          {f}
        </span>
      );
    }

    if (
      f.includes("实际件数") ||
      f.includes("件数") ||
      f.includes("平均订单") ||
      f.includes("订单金额") ||
      f.includes("销售数据")
    ) {
      const icon =
        f.includes("件数") ? "📦" : f.includes("订单") ? "💰" : "📊";
      const v: NonNullable<Props["decorVariant"]> =
        decorVariant ?? (f.includes("销售数据") ? "tag" : "tag");
      return (
        <span className={`v2-tag-box ${v}`} data-icon={icon}>
          {f}
        </span>
      );
    }

    // 兜底：普通文字 footer，带趋势颜色
    return (
      <div className={`v2-metric-footer ${footerTrend !== "neutral" ? footerTrend : ""}`}>
        {footerTrend !== "neutral" && footerTrend !== "warn" ? (
          <span className="arrow">{arrow}</span>
        ) : null}
        <span>{footerContent}</span>
      </div>
    );
  })();

  return (
    <div className="v2-metric-card">
      <span className="v2-metric-label">{label}</span>
      <strong
        className={`v2-metric-value ${valueColor !== "default" ? valueColor : ""}`}
      >
        {value}
      </strong>
      <div className="v2-metric-footer-slot" style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "6px" }}>
        {autoIcon ? (
          <span
            className={`v2-tag-box ${autoVariant}`}
            data-icon={autoIcon}
            style={{ padding: "2px 7px 2px 5px", fontSize: "10.8px" }}
          >
            {label}
          </span>
        ) : null}
        {footerChip}
      </div>
    </div>
  );
}
