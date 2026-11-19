import StatusBadge_v2 from "./StatusBadge_v2";

export interface DataTableColumn {
  key: string;
  title: string;
  render?: (row: Record<string, unknown>) => React.ReactNode;
  width?: number | string;
}

type CellDecor = "percent" | "money" | "count" | "status" | "none";

/**
 * DataTable_v2 —— 纯数据表格，参考"年度销售数据统计分析表"的报表风格
 * 原则：
 *   1) 数据可读性优先，不做花哨装饰（去掉 rate bar / v2-cell-inner 胶囊 / 空态 emoji 渐变）
 *   2) 保留功能性装饰（StatusBadge_v2 / trend chip / v2-tag-box 等原本就有的语义标签）
 *   3) 仅给 td 挂 col-first / col-last / col-money / col-count / col-percent 这几个语义类，
 *      让 CSS 层统一控制对齐、字重、颜色，完全不影响数据和逻辑
 */
export default function DataTable_v2({
  rows,
  columns,
  emptyText = "暂无数据",
}: {
  rows: Record<string, unknown>[];
  columns: DataTableColumn[];
  emptyText?: string;
}) {
  function columnDecorationType(col: DataTableColumn): CellDecor {
    const title = String(col.title || col.key);
    if (/状态|检查|上传|入库|处理|审核/.test(title)) return "status";
    if (
      /完成率|达成率|使用率|费用率|利润率|增长率|增长率|完成占比|占比|渗透率|转化率|率|%|百分比/.test(title)
    )
      return "percent";
    if (
      /金额|销售额|成本|利润|费用|支出|收入|毛利|售价|均价|单价|实际\s*[（(]?\s*万元|预算\s*[（(]?\s*万元|差异\s*[（(]?\s*万元|[（(]\s*万元\s*[)）]|万元$|额$|差异$|实际$|预算$/.test(
        title
      )
    )
      return "money";
    if (/件数|数量|销量|订单数|单数|笔数|人数|人次|次数|个数|个$|件$|台$/.test(title)) return "count";
    return "none";
  }

  function maybeDecorateCell(cellValue: unknown, type: CellDecor): React.ReactNode {
    if (typeof cellValue !== "string") {
      if (typeof cellValue === "number") return maybeDecorateCell(String(cellValue), type);
      return cellValue as React.ReactNode;
    }
    const s = cellValue;
    if (type === "status") return <StatusBadge_v2 value={s} />;
    if (s.includes("偏低"))
      return (
        <span className="cell-warn" data-prefix="⚠️">
          {s}
        </span>
      );
    if (type === "percent" || /\d+(\.\d+)?%/.test(s)) {
      let dir: "up" | "down" | "warn" | "neutral" = "neutral";
      if (s.includes("↑") || s.includes("增长") || s.includes("增加")) dir = "up";
      if (s.includes("↓") || s.includes("低于") || s.includes("下降") || s.includes("节省")) dir = "down";
      if (s.includes("偏低") || s.includes("未达") || s.includes("警告")) dir = "warn";
      const clean = s.replace(/[↑↓]/g, "").trim();
      const dirName = dir !== "neutral" ? dir : "";
      return (
        <span className={`cell-percent ${dirName}`} data-dir={dir}>
          {dir === "up" && <span className="p-arrow">↑</span>}
          {dir === "down" && <span className="p-arrow">↓</span>}
          {clean}
        </span>
      );
    }
    if (type === "money") {
      let variant: "pos" | "neg" | "neu" = "neu";
      if (s.includes("超支") || s.includes("-")) variant = "neg";
      if (s.includes("节省") || s.includes("+")) variant = "pos";
      return <span className={`cell-money cell-${variant}`}>{s}</span>;
    }
    if (type === "count") {
      return <span className="cell-count">{s}</span>;
    }
    return cellValue;
  }

  function tdClasses(index: number, type: CellDecor): string {
    const c: string[] = [];
    if (index === 0) c.push("col-first");
    if (index === columns.length - 1) c.push("col-last");
    if (type === "money") c.push("col-money");
    if (type === "count") c.push("col-count");
    if (type === "percent") c.push("col-percent");
    return c.join(" ");
  }

  function thClasses(index: number, col: DataTableColumn): string {
    const c: string[] = [];
    if (index === 0) c.push("col-first");
    if (index === columns.length - 1) c.push("col-last");
    const type = columnDecorationType(col);
    if (type === "money") c.push("col-money");
    if (type === "count") c.push("col-count");
    if (type === "percent") c.push("col-percent");
    return c.join(" ");
  }

  if (!rows || !rows.length) {
    return (
      <div className="v2-table-wrap">
        <table className="v2-table">
          <thead>
            <tr>
              {columns.map((col, i) => (
                <th
                  key={col.key}
                  className={thClasses(i, col)}
                  style={col.width ? { width: col.width } : undefined}
                >
                  {col.title}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="v2-table-empty" colSpan={columns.length}>
                {emptyText}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="v2-table-wrap">
      <table className="v2-table">
        <thead>
          <tr>
            {columns.map((col, i) => (
              <th
                key={col.key}
                className={thClasses(i, col)}
                style={col.width ? { width: col.width } : undefined}
              >
                {col.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr
              key={rowIndex}
              className={`row-${rowIndex % 2 === 0 ? "odd" : "even"} ${row.onClick ? "row-clickable" : ""}`}
              style={{ cursor: row.onClick ? "pointer" : "default" }}
              onClick={row.onClick as unknown as React.MouseEventHandler<HTMLTableRowElement>["onClick"]}
            >
              {columns.map((col, colIndex) => {
                const rawContent: unknown = col.render
                  ? col.render(row)
                  : (row[col.key] as unknown);
                const cellType = columnDecorationType(col);
                const isCustomRender = Boolean(col.render);
                let content: React.ReactNode;
                if (isCustomRender) {
                  content = rawContent as React.ReactNode;
                } else {
                  content = maybeDecorateCell(rawContent, cellType);
                }
                if (
                  !col.render &&
                  typeof rawContent === "string" &&
                  (col.key.includes("status") || col.key.includes("状态"))
                ) {
                  content = <StatusBadge_v2 value={rawContent} />;
                }
                const cls = tdClasses(colIndex, cellType);
                return (
                  <td key={col.key} className={cls}>
                    {content}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
