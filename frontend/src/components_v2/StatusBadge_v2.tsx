/**
 * StatusBadge_v2 —— 状态胶囊 + 装饰点缀升级版
 * 保持外部 value 输入不变，自动根据 value 内容匹配：
 * - 通过 / 已入库 / 完成 → ✅ 绿胶囊
 * - 警告 / 待处理 / 偏低 / 检查中 / 未上传 / 有警告 / 待检查 → ⚠️ 黄胶囊
 * - 错误 / 失败 / 超支 / 风险 / 异常 / 未通过 → 🔴 红胶囊
 * - 进行 / 运行 / 当前 / 视角 → 🔵 蓝胶囊
 * - info / 提示 / 说明 → ℹ️ 紫胶囊
 *
 *   —— 额外语义（📦实际件数 💰平均订单金额 等 → 图标方框）
 *   —— 完成率 / 达成率 → 带↑↓箭头胶囊
 *
 * 不改变布局、数据和功能逻辑，仅加装饰层。
 */
export default function StatusBadge_v2({ value }: { value: string }) {
  const text = String(value ?? "");
  let kind:
    | "success"
    | "warning"
    | "danger"
    | "info"
    | "primary"
    | "default" = "default";
  let decorative: "warn-box" | "info-tag" | "trend-chip" | "status-pill" = "status-pill";
  let iconEmoji: string | null = null;
  let tagVariant: "tag" | "info" | "purple" | "amber" = "tag";

  const t = text;

  // ---- 先匹配装饰类型（具体语义装饰优先）----
  if (t.includes("完成率") || t.includes("达成率") || t.match(/\d+(\.\d+)?%/)) {
    decorative = "trend-chip";
  } else if (
    t.includes("实际件数") ||
    t.includes("平均订单金额") ||
    t.includes("件数") ||
    t.includes("销售数据") ||
    t.includes("销售额") ||
    t.includes("销售数量") ||
    t.includes("销售表现") ||
    t.includes("客单价") ||
    t.includes("毛利率") ||
    t.includes("利润率") ||
    t.includes("费用率")
  ) {
    decorative = "info-tag";
    if (t.includes("件数") || t.includes("销售") || t.includes("销售数量")) iconEmoji = "📦";
    else if (t.includes("订单")) iconEmoji = "💰";
    else if (t.includes("销售额") || t.includes("销售表现") || t.includes("客单价")) iconEmoji = "💵";
    else if (t.includes("利率")) iconEmoji = "📈";
    else if (t.includes("费用")) iconEmoji = "📊";
    if (t.includes("利率") || t.includes("利润")) tagVariant = "purple";
    else if (t.includes("费用") || t.includes("费用率")) tagVariant = "amber";
    else tagVariant = "tag";
  } else if (t.includes("偏低")) {
    decorative = "warn-box";
  }

  // ---- 匹配状态颜色（胶囊）----
  if (
    t.includes("通过") ||
    t.includes("已入库") ||
    t.includes("完成") ||
    t.includes("成功") ||
    t.includes("导入成功") ||
    t.includes("导入完成") ||
    t.includes("已完成")
  ) {
    kind = "success";
  } else if (
    t.includes("警告") ||
    t.includes("待处理") ||
    t.includes("偏低") ||
    t.includes("检查中") ||
    t.includes("未上传") ||
    t.includes("有警告") ||
    t.includes("待检查")
  ) {
    kind = "warning";
  } else if (
    t.includes("错误") ||
    t.includes("失败") ||
    t.includes("超支") ||
    t.includes("风险") ||
    t.includes("异常") ||
    t.includes("未通过")
  ) {
    kind = "danger";
  } else if (
    t.includes("进行") ||
    t.includes("运行") ||
    t.includes("当前") ||
    t.includes("视角")
  ) {
    kind = "primary";
  } else if (t.includes("info") || t.includes("提示") || t.includes("说明")) {
    kind = "info";
  }

  if (decorative === "warn-box") {
    return <span className="v2-warn-chip">{text}</span>;
  }

  if (decorative === "info-tag" && iconEmoji) {
    return (
      <span
        className={`v2-tag-box ${tagVariant}`}
        data-icon={iconEmoji}
      >
        {text}
      </span>
    );
  }

  if (decorative === "trend-chip") {
    let arrowDir: "up" | "down" | "neutral" = "neutral";
    if (t.includes("↑") || t.includes("上升") || t.includes("增长") || t.includes("增加")) {
      arrowDir = "up";
    } else if (t.includes("↓") || t.includes("下降") || t.includes("低于") || t.includes("减少") || t.includes("节省")) {
      arrowDir = "down";
    }
    return (
      <span className={`v2-trend-chip ${arrowDir !== "neutral" ? arrowDir : ""}`}>
      {arrowDir === "up" && <span className="arrow">↑</span>}
      {arrowDir === "down" && <span className="arrow">↓</span>}
      {text}
    </span>
    );
  }

  // ---- 默认：状态胶囊 + kind 匹配 emoji 图标由 CSS ::before 自动加

  return <span className={`v2-status-pill ${kind}`}>{text}</span>;
}
