/**
 * decorateChips_v2
 * --------------------------------------------------------------
 * 纯装饰层：对真实 DOM（非 V2 自定义组件渲染的老组件）自动注入
 * "小图标 emoji + 克制的色块" 点缀，不改变：
 *   - 原数据 / 原逻辑 / 事件回调 / 布局结构
 *   - 不新建父级容器，只对 span / strong / textNode 内联 wrap
 *
 * 装饰点：
 *   1) 指标卡 hero-summary-item / metric-card / .summary-item
 *      - 标题行（小标签）：销售额/成本/费用/利润 → 💵/📦/📊/📈 小图标方框
 *      - 底部辅助文字：完成率/达成率 → 箭头胶囊；偏低 → ⚠️黄方块
 *   2) 状态文本 badge / status / 状态列 → StatusBadge_v2 风格的 emoji 前缀胶囊
 *   3) 表格 td/span：百分比、金额、件数 → 小图标方框/箭头胶囊
 *   4) 经营提醒 / 异常提醒 list-item → 前缀 emoji
 *
 * 挂载方式：
 *   在各页面 useEffect 调用 decorateChips_v2()；返回 dispose() 清理。
 *   自动用 MutationObserver 跟踪 DOM 变化，对新内容追加装饰。
 */

const DECORATED_ATTR = "data-v2-decorated";
const OBSERVER_ATTR = "data-v2-decorate-observer";

function hasDecorated(el: Element): boolean {
  return el.hasAttribute(DECORATED_ATTR);
}
function markDecorated(el: Element) {
  el.setAttribute(DECORATED_ATTR, "true");
}

function createChip(
  text: string,
  type:
    | "tag-green"
    | "tag-info"
    | "tag-purple"
    | "tag-amber"
    | "warn-box"
    | "trend-up"
    | "trend-down"
    | "status-success"
    | "status-warning"
    | "status-danger"
    | "status-primary"
    | "status-info",
  icon?: string
): HTMLSpanElement {
  const span = document.createElement("span");
  span.setAttribute(DECORATED_ATTR, "true");
  let classes = "";
  switch (type) {
    case "tag-green":
      classes = "v2-tag-box tag";
      break;
    case "tag-info":
      classes = "v2-tag-box info";
      break;
    case "tag-purple":
      classes = "v2-tag-box purple";
      break;
    case "tag-amber":
      classes = "v2-tag-box amber";
      break;
    case "warn-box":
      classes = "v2-warn-chip";
      break;
    case "trend-up":
      classes = "v2-trend-chip up";
      break;
    case "trend-down":
      classes = "v2-trend-chip down";
      break;
    case "status-success":
      classes = "v2-status-pill success";
      break;
    case "status-warning":
      classes = "v2-status-pill warning";
      break;
    case "status-danger":
      classes = "v2-status-pill danger";
      break;
    case "status-primary":
      classes = "v2-status-pill primary";
      break;
    case "status-info":
      classes = "v2-status-pill info";
      break;
  }
  span.className = classes;
  if (icon && /tag-/.test(type)) span.setAttribute("data-icon", icon);
  // 箭头
  if (type === "trend-up") {
    const a = document.createElement("span");
    a.className = "arrow";
    a.textContent = "↑";
    span.appendChild(a);
  }
  if (type === "trend-down") {
    const a = document.createElement("span");
    a.className = "arrow";
    a.textContent = "↓";
    span.appendChild(a);
  }
  const txt = document.createElement("span");
  txt.textContent = text;
  span.appendChild(txt);
  return span;
}

/**
 * 判断文本类型，返回装饰方案；null = 不装饰
 * 原则：只对 18 字以内的短词/短状态做胶囊；长整句不做整句包装
 */
function detectDecoration(text: string): null | {
  type: Parameters<typeof createChip>[1];
  text?: string;
  icon?: string;
} {
  const t = text.trim();
  if (!t) return null;
  // 长整句（含中文标点或长度>18）=> 不做整段替换；外面的提醒前缀 emoji 会单独加
  if (t.length > 18 || /[,，.。;；:：！!？?（）()【】\[\]<>《》"“”'‘']/.test(t)) {
    // 唯一例外：单独的"偏低"、短标签、单独数字百分比可以过
  }

  // 1) 警告偏低类（单独的 warn 词）
  if (t === "偏低" || t === "低") return { type: "warn-box", text: t };

  // 2) 完成率/达成率/使用率（短语 或 单独数字百分比）
  const isShortPhrase = t.length <= 18 && !/[,，.。;；:：]/.test(t);
  if (isShortPhrase) {
    if (
      t === "完成率" ||
      t === "达成率" ||
      t === "使用率" ||
      /^\d{1,3}(\.\d{1,2})?%$/.test(t)
    ) {
      const dir: "trend-up" | "trend-down" =
        /^\d/.test(t) ? "trend-down" : "trend-down"; // 缺省方向
      return { type: dir, text: t };
    }
  }

  // 2b) 方向词短语：可以做趋势胶囊
  if (isShortPhrase) {
    let dir: "trend-up" | "trend-down" | null = null;
    if (t.includes("↑") || t.includes("上升") || t.includes("增长") || t.includes("增加")) dir = "trend-up";
    else if (t.includes("↓") || t.includes("下降") || t.includes("低于") || t.includes("减少") || t.includes("节省") || t.includes("负")) dir = "trend-down";
    // 但必须包含"率"或"%"，否则只是普通词不 trend
    if (dir && (t.includes("率") || /%/.test(t))) return { type: dir, text: t };
  }

  // 3) 状态胶囊（短文本 ≤ 14）
  if (t.length <= 14) {
    if (
      t === "通过" ||
      t.includes("已入库") ||
      t === "完成" ||
      t === "成功" ||
      t === "已完成" ||
      t === "导入成功" ||
      t === "导入完成" ||
      t.includes("正常")
    )
      return { type: "status-success", text: t };
    if (
      t === "警告" ||
      t === "待处理" ||
      t === "检查中" ||
      t === "未上传" ||
      t === "有警告" ||
      t === "待检查" ||
      t === "运行中" ||
      t.includes("偏低") ||
      t === "待上传"
    )
      return { type: "status-warning", text: t };
    if (
      t === "错误" ||
      t === "失败" ||
      t === "超支" ||
      t === "风险" ||
      t === "异常" ||
      t === "未通过" ||
      t.includes("失败") ||
      t.includes("未通过")
    )
      return { type: "status-danger", text: t };
    if (t === "进行" || t === "当前" || t.includes("视角"))
      return { type: "status-primary", text: t };
    if (t === "提示" || t === "说明" || t === "info")
      return { type: "status-info", text: t };
  }

  return null;
}

/**
 * 根据指标卡或汇总块的 label 语义，给金额主数字左侧加个带图标的小标签（用于 hero-summary-item）
 */
function detectLabelIcon(text: string): { icon: string; variant: "tag-green" | "tag-info" | "tag-purple" | "tag-amber" } | null {
  const t = text.trim();
  if (!t) return null;
  if (t.includes("销售额") || t.includes("销售表现") || t.includes("客单价"))
    return { icon: "💵", variant: "tag-green" };
  if (t.includes("成本") || t.includes("成本额") || t.includes("销售成本"))
    return { icon: "📦", variant: "tag-amber" };
  if (t.includes("费用") || t.includes("支出") || t.includes("费用率"))
    return { icon: "📊", variant: "tag-amber" };
  if (t.includes("利润") || t.includes("毛利") || t.includes("利润率"))
    return { icon: "📈", variant: "tag-purple" };
  if (t.includes("预算")) return { icon: "🎯", variant: "tag-info" };
  if (t.includes("达成率") || t.includes("完成率"))
    return { icon: "🎯", variant: "tag-info" };
  if (t.includes("优先提醒")) return { icon: "🔔", variant: "tag-amber" };
  if (t.includes("件数") || t.includes("销售数量") || t.includes("销量"))
    return { icon: "📦", variant: "tag-green" };
  if (t.includes("订单") || t.includes("平均订单")) return { icon: "💰", variant: "tag-green" };
  return null;
}

/**
 * 判断一个指标/汇总块是否"已经自带原生彩色图标"
 * （hero-summary-item / 老 metric-card 第一个子元素已经是带背景色的 icon wrapper）
 * 如果是，decorateMetricBlock 应该跳过 label 图标 prepend，避免重复
 */
function blockHasNativeIcon(block: HTMLElement): boolean {
  // hero-summary-item 左侧一般有一个带 background 的 div/span 图标容器
  const first = block.firstElementChild as HTMLElement | null;
  if (!first) return false;
  const cls = first.className || "";
  const style = (first as HTMLElement).getAttribute && (first as HTMLElement).getAttribute("style") || "";
  // 命中常见 wrapper 条件：带 icon 类名、或是小尺寸的彩色块
  if (
    /icon|avatar|emoji|badge|tag|summary-icon|hero-icon|metric-icon/i.test(cls) ||
    /width\s*:\s*(1[0-9]|2[0-8])px/.test(style) ||
    /height\s*:\s*(1[0-9]|2[0-8])px/.test(style) ||
    /background(?!-position|-size|-repeat|-image[^(]*url)/.test(style)
  ) {
    return true;
  }
  // 第二个检查：block 自己的 class 含 hero-summary-item -> 老 Dashboard 默认带彩色图标
  if (/hero-summary-item|summary-block|top-summary-card/.test(block.className || "")) return true;
  return false;
}

/**
 * 对单个指标/汇总块做装饰：给标题小标签 + 底部辅助文字
 */
function decorateMetricBlock(block: HTMLElement) {
  if (hasDecorated(block)) return;
  markDecorated(block);

  const skipLabelIcon = blockHasNativeIcon(block);

  // --- 标题行：在标题旁加一个小图标色块（不含label文字，避免重复）
  //     如果 block 已经自带原生彩色图标（hero 里的 💰/📈 🟩 色块等）=> 完全跳过 prepend
  if (!skipLabelIcon) {
    const labelEl =
      block.querySelector<HTMLElement>(":scope > span:first-child, :scope > h4, :scope > p > span, :scope > span, .label, .title, h3, h4");
    if (labelEl && labelEl.textContent) {
      const lbl = labelEl.textContent.trim();
      const iconCfg = detectLabelIcon(lbl);
      if (iconCfg) {
        const chip = createChip("", iconCfg.variant as any, iconCfg.icon);
        const txtSp = chip.querySelector("span:last-child");
        if (txtSp) txtSp.remove();
        chip.style.padding = "1px 6px 1px 5px";
        chip.style.fontSize = "11px";
        chip.style.marginRight = "6px";
        chip.style.verticalAlign = "middle";
        chip.style.display = "inline-flex";
        labelEl.parentElement?.insertBefore(chip, labelEl);
      }
    }
  }

  // --- 底部辅助文字：<small> / <p> / 除标题外的其他 <span>
  const helperSelectors = [
    ":scope > small",
    ":scope > p",
    ":scope > span:nth-of-type(2)",
    ":scope > span:nth-of-type(3)",
    ":scope > span:nth-of-type(4)",
    ":scope > div:nth-of-type(2) span",
    ":scope .hint",
    ":scope .footer",
    ":scope .sub",
  ];
  const seen = new Set<HTMLElement>();
  for (const sel of helperSelectors) {
    const els = Array.from(block.querySelectorAll<HTMLElement>(sel));
    for (const hel of els) {
      if (seen.has(hel)) continue;
      seen.add(hel);
      if (hasDecorated(hel)) continue;
      const htxt = hel.textContent?.trim();
      if (!htxt) continue;
      // 主金额不替换
      if (/^[-¥￥$,，.\d\s万千元%]+$/.test(htxt)) continue;
      // 长整句（带标点） => 不整句替换；只留原文本（最多我们前面已经加了提醒前缀 emoji）
      if (htxt.length > 24 || /[,，.。;；:：]/.test(htxt)) continue;
      const deco = detectDecoration(htxt);
      if (deco?.text) {
        markDecorated(hel);
        const chip = createChip(deco.text, deco.type, deco.icon);
        chip.style.marginTop = "4px";
        chip.style.display = "inline-flex";
        hel.replaceWith(chip);
        break;
      }
    }
  }
}

/**
 * 处理独立的文本节点（状态列、提醒列表）
 * 注意：只替换状态短词；长句只加前缀emoji，不做整句胶囊
 */
function decorateLeaf(leafEl: HTMLElement) {
  if (hasDecorated(leafEl)) return;
  const text = leafEl.textContent?.trim();
  if (!text) return;
  // 状态/td 里面的长句不做整体胶囊
  if (text.length > 18) return;
  if (/[,，.。;；:：！!？?（）()【】\[\]<>《》"“”'‘']/.test(text)) return;

  const ctx = leafEl.closest(
    "td, .badge, .chip, .status, .tag, [class*=status], [class*=Status], [class*=Badge], [class*=Chip], [class*=Tag], .v2-metric-footer, .reminder, .alert, .notice"
  );
  if (!ctx) return;

  const deco = detectDecoration(text);
  if (deco?.text) {
    markDecorated(leafEl);
    const chip = createChip(deco.text, deco.type, deco.icon);
    leafEl.replaceWith(chip);
  }
}

function runDecorate(root: ParentNode = document.body) {
  try {
  if (!(root as any).querySelectorAll) return;

  // --- 0) 章节标题 h2/h3：小图标色块放在标题行左侧（全局点缀入口）---
  const headings = Array.from(
    (root as HTMLElement).querySelectorAll<HTMLElement>("h2, h3, .section-title, .panel-title")
  );
  headings.forEach((h) => {
    if (hasDecorated(h)) return;
    const txt = h.textContent?.trim() || "";
    if (!txt) return;
    let iconCfg: { icon: string; variant: "tag-green" | "tag-info" | "tag-purple" | "tag-amber" } | null = detectLabelIcon(txt);
    if (!iconCfg) {
      if (txt.includes("上传") || txt.includes("入口") || txt.includes("文件")) iconCfg = { icon: "📤", variant: "tag-info" };
      else if (txt.includes("检查") || txt.includes("校验") || txt.includes("明细") && txt.includes("检查")) iconCfg = { icon: "✅", variant: "tag-green" };
      else if (txt.includes("汇总") || txt.includes("处理") || txt.includes("归集")) iconCfg = { icon: "🔄", variant: "tag-amber" };
      else if (txt.includes("导出") || txt.includes("报表")) iconCfg = { icon: "📄", variant: "tag-purple" };
      else if (txt.includes("预算") || txt.includes("编制")) iconCfg = { icon: "🎯", variant: "tag-green" };
      else if (txt.includes("对比") || txt.includes("明细") || txt.includes("按")) iconCfg = { icon: "📊", variant: "tag-info" };
      else if (txt.includes("趋势")) iconCfg = { icon: "📈", variant: "tag-green" };
      else if (txt.includes("排名") || txt.includes("费用") || txt.includes("项目")) iconCfg = { icon: "🏆", variant: "tag-amber" };
      else if (txt.includes("提醒") || txt.includes("洞察") || txt.includes("健康")) iconCfg = { icon: "🔔", variant: "tag-amber" };
      else if (txt.includes("设置") || txt.includes("配置") || txt.includes("版本") || txt.includes("管理")) iconCfg = { icon: "⚙️", variant: "tag-info" };
      else if (txt.includes("筛选")) iconCfg = { icon: "🔍", variant: "tag-info" };
      else if (txt.includes("结果") || txt.includes("输出")) iconCfg = { icon: "📊", variant: "tag-green" };
      else if (txt.includes("逻辑") || txt.includes("说明") || txt.includes("参数")) iconCfg = { icon: "🧠", variant: "tag-purple" };
      else if (txt.includes("定位") || txt.includes("导航")) iconCfg = { icon: "📍", variant: "tag-info" };
      else if (txt.includes("操作") || txt.includes("步骤")) iconCfg = { icon: "⚡", variant: "tag-amber" };
      else if (txt.includes("中心")) iconCfg = { icon: "🎯", variant: "tag-purple" };
    }
    if (iconCfg) {
      markDecorated(h);
      const chip = createChip("", iconCfg.variant as any, iconCfg.icon);
      const txtSp = chip.querySelector("span:last-child");
      if (txtSp) txtSp.remove();
      chip.style.padding = "2px 6px 2px 5px";
      chip.style.fontSize = "12px";
      chip.style.marginRight = "8px";
      chip.style.verticalAlign = "middle";
      chip.style.display = "inline-flex";
      h.prepend(chip);
    } else {
      markDecorated(h);
    }
  });

  // 指标块
  const metricBlocks = Array.from(
    (root as HTMLElement).querySelectorAll<HTMLElement>(
      ".hero-summary-item, .metric-card, .metric-item, .summary-card, .core-metric-card, .summary > div, [class*=Metric], .stat-card, .stat-item, .card.metric"
    )
  );
  metricBlocks.forEach(decorateMetricBlock);

  // 叶子状态文本（badge / td / li）
  const leaves = Array.from(
    (root as HTMLElement).querySelectorAll<HTMLElement>(
      "td > span, td, .badge, .chip, .status, [class*='status-badge'], [class*='StatusBadge'], .tag, .insight-list li, li > span:first-child, .dashboard-hero li, .alert, .notice, .insight-item > span"
    )
  );
  leaves.forEach(decorateLeaf);

  // ---- 特别处理：经营提醒列表（长句，前缀emoji，不wrap整句）----
  const insightLis = Array.from(
    (root as HTMLElement).querySelectorAll<HTMLLIElement>(
      ".insight-item li, .reminders li, .dashboard-hero li, ul.insight-list li, [class*=提醒] li, [role=listitem]"
    )
  );
  insightLis.forEach((li) => {
    if (hasDecorated(li)) return;
    const txt = li.textContent?.trim() || "";
    if (!txt) return;
    markDecorated(li);
    let icon: string | null = null;
    if (txt.includes("节省")) icon = "💡";
    else if (txt.includes("风险") || txt.includes("低于") || txt.includes("未达")) icon = "⚠️";
    else if (txt.includes("增长") || txt.includes("增加") || txt.includes("达成")) icon = "✅";
    else if (txt.includes("使用率") || txt.includes("率")) icon = "📊";
    if (icon) {
      // prepend span 作为前缀
      const s = document.createElement("span");
      s.textContent = icon + " ";
      s.setAttribute(DECORATED_ATTR, "true");
      s.style.marginRight = "2px";
      li.prepend(s);
    }
  });
  } catch (err) {
    (window as any).__v2DecorErr = (window as any).__v2DecorErr || [];
    (window as any).__v2DecorErr.push(err instanceof Error ? err.message : String(err));
  }
}

export function decorateChips_v2(
  scope: HTMLElement | ParentNode = document.body,
  options: { once?: boolean } = {}
): () => void {
  runDecorate(scope);
  if (options.once) return () => undefined;

  let raf = 0;
  const schedule = () => {
    if (raf) return;
    raf = window.requestAnimationFrame(() => {
      raf = 0;
      runDecorate(scope);
    });
  };

  if ((scope as any).getAttribute(OBSERVER_ATTR)) return () => undefined;
  (scope as HTMLElement).setAttribute?.(OBSERVER_ATTR, "true");

  const observer = new MutationObserver(() => schedule());
  observer.observe(scope, { childList: true, subtree: true, characterData: true });

  // 前几秒兜底再刷一次，应对异步渲染
  const timers: number[] = [];
  timers.push(window.setTimeout(schedule, 120));
  timers.push(window.setTimeout(schedule, 500));
  timers.push(window.setTimeout(schedule, 1500));
  timers.push(window.setTimeout(schedule, 3500));
  timers.push(window.setTimeout(schedule, 7000));

  return () => {
    observer.disconnect();
    timers.forEach((id) => window.clearTimeout(id));
    if (raf) cancelAnimationFrame(raf);
    try {
      (scope as HTMLElement).removeAttribute?.(OBSERVER_ATTR);
    } catch {}
  };
}

export default decorateChips_v2;
