import { useEffect, useState } from "react";
import { getActualBatches, getActualCheckResults, type ActualBatch } from "../api/actualApi";
import { getCheckResults } from "../api/checkApi";
import { checkPlanningCostPrices, checkPlanningSalesPrices, type PlanningPriceCheckResponse } from "../api/planningApi";
import { getUploadedFiles } from "../api/uploadApi";
import DataTable from "../components/DataTable";
import ErrorDetailPanel from "../components/ErrorDetailPanel";
import Modal from "../components/Modal";
import StatusBadge from "../components/StatusBadge";
import type { CheckResult } from "../types/check";
import type { UploadedFileRecord } from "../types/upload";
import { translateCheckType, translateSeverity } from "../utils/formatters";

type CheckFileOption = {
  key: string;
  source: "budget" | "actual";
  id: number | string;
  name: string;
  description: string;
};

export default function 上传检查中心() {
  const [files, setFiles] = useState<UploadedFileRecord[]>([]);
  const [actualBatches, setActualBatches] = useState<ActualBatch[]>([]);
  const [fileKey, setFileKey] = useState("");
  const [filters, setFilters] = useState({ check_type: "", severity: "", sheet_name: "", error_code: "" });
  const [results, setResults] = useState<CheckResult[]>([]);
  const [selected, setSelected] = useState<CheckResult | undefined>();
  const [message, setMessage] = useState("");
  const [priceFile, setPriceFile] = useState<File | null>(null);
  const [priceKind, setPriceKind] = useState<"sales" | "cost">("sales");
  const [priceYear, setPriceYear] = useState(new Date().getFullYear() + 1);
  const [checkingPrice, setCheckingPrice] = useState(false);

  useEffect(() => {
    Promise.all([getUploadedFiles(), getActualBatches()])
      .then(([budgetItems, actualItems]) => {
        setFiles(budgetItems);
        setActualBatches(actualItems);
        const firstBudget = budgetItems[0] ? `budget:${budgetItems[0].id}` : "";
        const firstActual = actualItems[0] ? `actual:${actualItems[0].batch_id}` : "";
        setFileKey((prev) => prev || firstBudget || firstActual);
      })
      .catch((error) => setMessage(error.message));
  }, []);

  useEffect(() => {
    if (!fileKey) return;
    setSelected(undefined);
    if (fileKey.startsWith("budget:")) {
      getCheckResults(Number(fileKey.replace("budget:", "")), filters).then(setResults).catch((error) => setMessage(error.message));
      return;
    }
    if (fileKey.startsWith("actual:")) {
      const batchId = fileKey.replace("actual:", "");
      getActualCheckResults(batchId)
        .then((response) => setResults(filterResults(mapExternalIssues(response.issues, { fileId: -1, sourceLabel: "实际经营表" }), filters)))
        .catch((error) => setMessage(error.message));
    }
  }, [fileKey, filters]);

  const options: CheckFileOption[] = [
    ...files.map((file) => ({
      key: `budget:${file.id}`,
      source: "budget" as const,
      id: file.id,
      name: file.file_name,
      description: "预算表",
    })),
    ...actualBatches.map((batch) => ({
      key: `actual:${batch.batch_id}`,
      source: "actual" as const,
      id: batch.batch_id,
      name: batch.file_name,
      description: batch.file_type === "actual_sales" ? "实际销售表" : "实际费用表",
    })),
  ];
  const selectedFile = options.find((file) => file.key === fileKey);
  const errorCount = results.filter((item) => item.severity === "error").length;
  const warningCount = results.filter((item) => item.severity === "warning").length;
  const infoCount = results.filter((item) => item.severity === "info").length;

  async function checkPriceTable() {
    if (!priceFile) {
      setMessage("请先选择要检查的销售价格表或产品成本表。");
      return;
    }
    setCheckingPrice(true);
    setSelected(undefined);
    setMessage("");
    try {
      const response: PlanningPriceCheckResponse = priceKind === "sales"
        ? await checkPlanningSalesPrices(priceFile, priceYear)
        : await checkPlanningCostPrices(priceFile, priceYear);
      setFileKey("");
      setResults(mapExternalIssues(response.issues, { fileId: -2, sourceLabel: response.price_type }));
      setMessage(`${response.price_type}检查完成：有效 ${response.valid_count} 行，错误 ${response.error_count} 个，提醒 ${response.warning_count} 个。`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "价格/成本表检查失败");
    } finally {
      setCheckingPrice(false);
    }
  }

  return (
    <div className="page-stack workbench-page">
      <section className="page-hero">
        <div>
          <h2>检查结果定位</h2>
          <p>{selectedFile ? `当前文件：${selectedFile.description} / ${selectedFile.name}` : "选择一个上传文件，或临时检查销售价格表、产品成本表。"}</p>
        </div>
        <div className="hero-stat-strip">
          <span><strong>{results.length}</strong>检查项</span>
          <span className={errorCount ? "danger-text" : ""}><strong>{errorCount}</strong>错误</span>
          <span><strong>{warningCount}</strong>警告</span>
          <span><strong>{infoCount}</strong>提示</span>
        </div>
      </section>

      <section className="panel task-panel">
        <div className="section-heading">
          <div>
            <h2>筛选条件</h2>
            <p className="muted">点击下方列表中的任意问题，可以查看中文错误明细和建议。</p>
          </div>
        </div>
        <div className="toolbar workbench-toolbar">
          <select value={fileKey} onChange={(event) => setFileKey(event.target.value)}>
            <option value="">请选择文件</option>
            {options.map((file) => <option key={file.key} value={file.key}>{file.description}：{file.name}</option>)}
          </select>
          <select value={filters.check_type} onChange={(event) => setFilters({ ...filters, check_type: event.target.value })}>
            <option value="">全部类型</option>
            <option value="format">格式检查</option>
            <option value="formula">公式检查</option>
            <option value="calculation">计算校验</option>
            <option value="实际销售检查">实际销售检查</option>
            <option value="实际费用检查">实际费用检查</option>
            <option value="销售价格表检查">销售价格表检查</option>
            <option value="产品成本表检查">产品成本表检查</option>
          </select>
          <select value={filters.severity} onChange={(event) => setFilters({ ...filters, severity: event.target.value })}>
            <option value="">全部级别</option><option value="error">错误</option><option value="warning">警告</option><option value="info">提示</option>
          </select>
          <input placeholder="工作表名称" value={filters.sheet_name} onChange={(event) => setFilters({ ...filters, sheet_name: event.target.value })} />
          <input placeholder="错误编码" value={filters.error_code} onChange={(event) => setFilters({ ...filters, error_code: event.target.value })} />
        </div>
      </section>

      <section className="panel task-panel">
        <div className="section-heading">
          <div>
            <h2>价格/成本表临时检查</h2>
            <p className="muted">用于检查明年预算编制中心要导入的销售价格表和产品成本表；检查不会写入数据。</p>
          </div>
        </div>
        <div className="toolbar workbench-toolbar">
          <label>目标年度<input type="number" min={2000} max={2100} value={priceYear} onChange={(event) => setPriceYear(Number(event.target.value))} /></label>
          <label>表格类型<select value={priceKind} onChange={(event) => setPriceKind(event.target.value as "sales" | "cost")}>
            <option value="sales">销售价格表</option>
            <option value="cost">产品成本表</option>
          </select></label>
          <label>选择文件<input type="file" accept=".xlsx,.xls" onChange={(event) => setPriceFile(event.target.files?.[0] || null)} /></label>
          <button onClick={checkPriceTable} disabled={checkingPrice || !priceFile}>{checkingPrice ? "检查中..." : "检查价格/成本表"}</button>
        </div>
      </section>

      {message && <div className="notice">{message}</div>}

      <section className="panel data-section">
        <div className="section-heading">
          <div>
            <h2>检查明细</h2>
            <p className="muted">错误会阻止入库；警告和提示用于人工复核。</p>
          </div>
        </div>
        <DataTable
          rows={results as unknown as Record<string, unknown>[]}
          onRowClick={(row) => setSelected(row as unknown as CheckResult)}
          rowClassName={() => "clickable-row"}
          columns={[
            { key: "severity", title: "级别", render: (row) => <StatusBadge value={String(row.severity)} /> },
            { key: "check_type", title: "类型", render: (row) => translateCheckType(String(row.check_type)) },
            { key: "error_message", title: "问题说明" },
            { key: "error_code", title: "系统码" },
            { key: "sheet_name", title: "工作表" },
            { key: "cell_address", title: "单元格" },
            { key: "suggestion", title: "建议" }
          ]}
        />
      </section>
      {selected && (
        <Modal title={`${translateSeverity(selected.severity)}明细`} onClose={() => setSelected(undefined)}>
          <ErrorDetailPanel result={selected} />
        </Modal>
      )}
    </div>
  );
}

function mapExternalIssues(issues: Array<Partial<CheckResult> & { message?: string }>, context: { fileId: number; sourceLabel: string }): CheckResult[] {
  return issues.map((issue, index) => ({
    id: index + 1,
    file_id: context.fileId,
    check_type: String(issue.check_type || context.sourceLabel),
    severity: String(issue.severity || "info"),
    error_code: issue.error_code || null,
    error_message: String(issue.error_message || issue.message || "检查结果"),
    sheet_name: issue.sheet_name || null,
    cell_address: issue.cell_address || null,
    row_number: issue.row_number || null,
    column_name: issue.column_name || null,
    product_code: issue.product_code || null,
    product_name: issue.product_name || null,
    month: issue.month || null,
    uploaded_value: issue.uploaded_value || null,
    expected_value: issue.expected_value || null,
    diff_value: issue.diff_value || null,
    suggestion: issue.suggestion || null,
  }));
}

function filterResults(results: CheckResult[], filters: { check_type: string; severity: string; sheet_name: string; error_code: string }) {
  return results.filter((result) => {
    if (filters.check_type && result.check_type !== filters.check_type) return false;
    if (filters.severity && result.severity !== filters.severity) return false;
    if (filters.sheet_name && result.sheet_name !== filters.sheet_name) return false;
    if (filters.error_code && result.error_code !== filters.error_code) return false;
    return true;
  });
}
