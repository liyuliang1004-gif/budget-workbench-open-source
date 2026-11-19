import { useEffect, useState } from "react";
import { getDashboardOverview } from "../api/dashboardApi";
import { exportCustomReport, exportDashboardView, exportExcel, exportStaticDashboard, getExportFiles, openExportLocation } from "../api/exportApi";
import { getGroupsShops } from "../api/uploadApi";
import DataTable from "../components/DataTable";
import type { ExportFile, ExportFilesResponse } from "../types/export";
import type { OperationGroupOption } from "../types/upload";

export default function 报表导出中心() {
  const [year, setYear] = useState("2026");
  const [budgetVersion, setBudgetVersion] = useState(1);
  const [month, setMonth] = useState("");
  const [dataView, setDataView] = useState("comparison");
  const [groupCode, setGroupCode] = useState("");
  const [shopCode, setShopCode] = useState("");
  const [productName, setProductName] = useState("");
  const [groups, setGroups] = useState<OperationGroupOption[]>([]);
  const [productOptions, setProductOptions] = useState<Array<{ product_key?: string; product_code?: string | null; product_name: string }>>([]);
  const [files, setFiles] = useState<ExportFilesResponse>({ reports: [], dashboards: [] });
  const [activeTab, setActiveTab] = useState<"quick" | "custom" | "history">("quick");
  const [activeType, setActiveType] = useState("全部");
  const [customTemplate, setCustomTemplate] = useState("budget_actual_detail");
  const [latestName, setLatestName] = useState("");
  const [message, setMessage] = useState("");

  const refresh = () => getExportFiles().then(setFiles).catch((error) => setMessage(error.message));
  useEffect(() => {
    const latest = readLatestExportMarker();
    if (latest?.name) {
      setLatestName(latest.name);
      setActiveTab("history");
      setActiveType(latest.kind === "dashboard" ? "当前视角" : "全部");
      setMessage(`已显示最近从首页导出的记录：${latest.name}。点击历史列表条目即可在电脑中定位文件目录。`);
    }
    refresh();
  }, [budgetVersion]);
  useEffect(() => { getGroupsShops().then((registry) => setGroups(registry.operation_groups || [])).catch(() => setGroups([])); }, []);

  const selectedGroup = groups.find((group) => group.group_code === groupCode);
  const shops = selectedGroup?.shops || groups.flatMap((group) => group.shops || []);
  const viewContext = {
    year: Number(year) || undefined,
    budget_version: budgetVersion,
    month: month ? Number(month) : undefined,
    group_code: groupCode || undefined,
    shop_code: shopCode || undefined,
    product_name: productName || undefined,
    data_view: dataView,
    top_n: 20,
  };

  useEffect(() => {
    getDashboardOverview(viewContext)
      .then((overview) => setProductOptions(overview.filter_options?.products || []))
      .catch(() => setProductOptions([]));
  }, [year, budgetVersion, month, groupCode, shopCode, dataView]);

  async function run(label: string, type: string, task: () => Promise<unknown>) {
    try {
      setActiveType(type);
      const result = await task() as { files?: ExportFile[]; dashboard_path?: string };
      setLatestName(result.files?.[0]?.name || result.dashboard_path?.split("/").slice(-2, -1)[0] || "");
      setMessage(`${label}成功${result.files?.[0]?.name ? `：${result.files[0].name}` : ""}`);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : `${label}失败`);
    }
  }

  function inferType(name: string) {
    if (name.includes("当前视角")) return "当前视角";
    if (name.includes("自定义")) return "自定义导出";
    if (name.includes("看板")) return "静态看板";
    if (name.includes("部门预算")) return "部门";
    if (name.includes("运营组")) return "运营组";
    if (name.includes("店铺")) return "店铺";
    if (name.includes("产品品类")) return "产品品类";
    if (name.includes("费用")) return "费用";
    if (name.includes("错误")) return "错误报告";
    return "其他";
  }

  const rows = [
    ...files.reports.map((item) => ({ ...item, kind: "report", type: inferType(item.name) })),
    ...files.dashboards.map((item) => ({ ...item, kind: "dashboard", type: inferType(item.name) }))
  ].sort((a, b) => String(b.exported_at || "").localeCompare(String(a.exported_at || "")));
  const allExportCount = files.reports.length + files.dashboards.length;

  async function openRow(row: Record<string, unknown>) {
    try {
      await openExportLocation(String(row.name), row.kind === "dashboard" ? "dashboard" : "report");
      setMessage(`已定位到文件目录：${row.name}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "打开目录失败");
    }
  }

  return (
    <div className="page-stack workbench-page">
      <section className="page-hero">
        <div>
          <h2>报表导出</h2>
          <p>按当前筛选条件生成 Excel/WPS 报表或静态看板。点击历史列表条目可定位到文件目录。</p>
        </div>
        <div className="hero-stat-strip">
          <span><strong>第 {budgetVersion} 版</strong>预算版本</span>
          <span><strong>{allExportCount}</strong>历史导出</span>
          <span><strong>{rows.length}</strong>当前列表</span>
        </div>
      </section>

      <section className="panel task-panel">
        <div className="section-heading">
          <div>
            <h2>导出筛选</h2>
            <p className="muted">筛选条件会用于“当前首页视角”和自定义导出。</p>
          </div>
        </div>
        <div className="toolbar export-filter workbench-toolbar">
          <input value={year} onChange={(event) => setYear(event.target.value)} placeholder="年份" />
          <select value={budgetVersion} onChange={(event) => setBudgetVersion(Number(event.target.value))}>{[1, 2, 3, 4, 5].map((version) => <option key={version} value={version}>第 {version} 版</option>)}</select>
          <select value={month} onChange={(event) => setMonth(event.target.value)}><option value="">全年</option>{Array.from({ length: 12 }, (_, index) => index + 1).map((item) => <option key={item} value={item}>{item}月</option>)}</select>
          <select value={groupCode} onChange={(event) => { const next = event.target.value; const group = groups.find((item) => item.group_code === next); setGroupCode(next); setShopCode(group?.shops?.[0]?.shop_code || ""); }}><option value="">全部运营组</option>{groups.map((group) => <option key={group.group_code} value={group.group_code}>{group.group_name}</option>)}</select>
          <select value={shopCode} onChange={(event) => setShopCode(event.target.value)}><option value="">全部店铺</option>{shops.map((shop) => <option key={shop.shop_code} value={shop.shop_code}>{shop.shop_name}</option>)}</select>
          <input list="export-product-options" value={productName} onChange={(event) => setProductName(event.target.value)} placeholder="搜索或选择产品" />
          <datalist id="export-product-options">
            {productOptions.map((item, index) => <option key={item.product_key || `${item.product_code || "name"}-${item.product_name}-${index}`} value={item.product_name} />)}
          </datalist>
          <select value={dataView} onChange={(event) => setDataView(event.target.value)}><option value="comparison">预算 vs 实际</option><option value="budget">预算</option><option value="actual">实际</option></select>
        </div>
      </section>

      <div className="settings-tabs segmented-tabs">
        <button className={activeTab === "quick" ? "active" : ""} onClick={() => setActiveTab("quick")}>快速导出</button>
        <button className={activeTab === "custom" ? "active" : ""} onClick={() => setActiveTab("custom")}>自定义导出</button>
        <button className={activeTab === "history" ? "active" : ""} onClick={() => setActiveTab("history")}>导出历史</button>
      </div>
      {activeTab === "quick" && (
        <section className="panel task-panel">
          <div className="section-heading">
            <div>
              <h2>快速导出</h2>
              <p className="muted">常用报表一键生成，生成后会在下方历史列表高亮。</p>
            </div>
          </div>
          <div className="button-grid export-action-grid">
          <button onClick={() => run("导出当前首页视角", "当前视角", () => exportDashboardView(viewContext))}>导出当前首页视角</button>
          {[
            ["department", "部门预算实际汇总", "部门"],
            ["group", "运营组预算实际汇总", "运营组"],
            ["shop", "店铺预算实际汇总", "店铺"],
            ["product", "产品销售排行榜", "产品品类"],
            ["expense", "费用超支明细", "费用"],
            ["error", "错误定位表", "错误报告"],
            ["all", "全部 Excel/WPS 报表", "全部 Excel/WPS"],
          ].map(([type, label, exportType]) => <button key={type} className={activeType === exportType ? "active-action" : ""} onClick={() => run(label, exportType, () => exportExcel(type, Number(year) || undefined, budgetVersion))}>{label}</button>)}
          <button onClick={() => run("部门静态看板", "静态看板", () => exportStaticDashboard("department", Number(year) || undefined, undefined, budgetVersion))}>部门静态看板</button>
          <button onClick={() => run("运营组静态看板", "静态看板", () => exportStaticDashboard("group", Number(year) || undefined, groupCode || undefined, budgetVersion))}>运营组静态看板</button>
          </div>
        </section>
      )}
      {activeTab === "custom" && (
        <section className="panel task-panel">
          <div className="section-heading">
            <div>
              <h2>自定义导出</h2>
              <p className="muted">第一版自定义导出使用固定模板，筛选条件来自上方控制台。</p>
            </div>
          </div>
          <div className="toolbar workbench-toolbar">
            <select value={customTemplate} onChange={(event) => setCustomTemplate(event.target.value)}>
              <option value="budget_actual_detail">预算实际对比明细</option>
              <option value="product_sales_rank">产品销售排行榜</option>
              <option value="shop_product_detail">店铺产品销售明细</option>
              <option value="group_shop_summary">运营组店铺汇总</option>
              <option value="expense_detail">费用结构明细</option>
              <option value="error_detail">错误定位明细</option>
            </select>
            <button onClick={() => run("自定义导出", "自定义导出", () => exportCustomReport({ ...viewContext, template: customTemplate }))}>生成自定义导出</button>
          </div>
        </section>
      )}
      {message && <div className="notice">{message}</div>}
      <section className="panel data-section">
        <div className="section-heading">
          <div>
            <h2>导出历史</h2>
            <p className="muted">显示全部历史导出，包含 Excel/WPS 报表和 HTML 静态看板。点击条目可在电脑中定位文件目录。</p>
          </div>
          <button className="secondary compact-button" onClick={refresh}>刷新历史</button>
        </div>
        <DataTable rows={rows as unknown as Record<string, unknown>[]} onRowClick={openRow} rowClassName={(row) => (row as ExportFile).name === latestName ? "latest-row clickable-row" : "clickable-row"} columns={[
          { key: "type", title: "报表类型" },
          { key: "budget_version", title: "预算版本", render: (row) => row.budget_version ? `第 ${row.budget_version} 版` : "未标注" },
          { key: "exported_at", title: "导出时间" },
          { key: "name", title: "文件名" },
          { key: "description", title: "表格说明" }
        ]} />
      </section>
    </div>
  );
}

function readLatestExportMarker(): { name: string; kind?: string } | null {
  try {
    const raw = localStorage.getItem("budget-latest-export");
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { name?: string; kind?: string };
    return parsed.name ? { name: parsed.name, kind: parsed.kind } : null;
  } catch {
    return null;
  }
}
