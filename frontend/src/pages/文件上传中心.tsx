import { useEffect, useState } from "react";
import { checkActualBatch, deleteActualBatch, getActualBatches, importActualBatch, uploadActualFile, type ActualBatch } from "../api/actualApi";
import { importBudgetFile } from "../api/aggregateApi";
import { runFormatCheck, runFullCheck } from "../api/checkApi";
import { deleteUploadedFile, downloadActualBusinessTemplate, downloadShopBudgetTemplate, getGroupsShops, getUploadedFiles, uploadBudgetFile } from "../api/uploadApi";
import DataTable from "../components/DataTable";
import FileUploadBox from "../components/FileUploadBox";
import StatusBadge from "../components/StatusBadge";
import type { OperationGroupOption, UploadedFileRecord } from "../types/upload";

export default function 文件上传中心() {
  const [files, setFiles] = useState<UploadedFileRecord[]>([]);
  const [actualBatches, setActualBatches] = useState<ActualBatch[]>([]);
  const [groups, setGroups] = useState<OperationGroupOption[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [actualFile, setActualFile] = useState<File | null>(null);
  const [actualType, setActualType] = useState<"sales" | "expense">("sales");
  const [actualYear, setActualYear] = useState(new Date().getFullYear());
  const [actualGroupCode, setActualGroupCode] = useState("");
  const [actualShopCode, setActualShopCode] = useState("");
  const [budgetYear, setBudgetYear] = useState(new Date().getFullYear());
  const [budgetVersion, setBudgetVersion] = useState(1);
  const [groupCode, setGroupCode] = useState("");
  const [shopCode, setShopCode] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const refresh = () => {
    getUploadedFiles().then(setFiles).catch((error) => setMessage(error.message));
    getActualBatches().then(setActualBatches).catch(() => undefined);
  };
  useEffect(() => {
    refresh();
    getGroupsShops()
      .then((registry) => {
        const nextGroups = registry.operation_groups || [];
        setGroups(nextGroups);
        const firstGroup = nextGroups[0];
        setGroupCode(firstGroup?.group_code || "");
        setShopCode(firstGroup?.shops?.[0]?.shop_code || "");
        setActualGroupCode(firstGroup?.group_code || "");
        setActualShopCode(firstGroup?.shops?.[0]?.shop_code || "");
      })
      .catch((error) => setMessage(error.message));
  }, []);

  const selectedGroup = groups.find((group) => group.group_code === groupCode);
  const shops = selectedGroup?.shops || [];
  const selectedActualGroup = groups.find((group) => group.group_code === actualGroupCode);
  const actualShops = selectedActualGroup?.shops || [];
  const budgetImportedCount = files.filter((file) => file.import_status === "已入库").length;
  const budgetErrorCount = files.filter((file) => Number(file.error_count || 0) > 0).length;
  const actualImportedCount = actualBatches.filter((batch) => batch.status === "imported").length;

  async function upload() {
    if (!selectedFile) return;
    if (!budgetYear || !groupCode || !shopCode) {
      setMessage("请先选择年度、运营组和店铺，再上传预算表。");
      return;
    }
    setLoading(true);
    setMessage("");
    try {
      await uploadBudgetFile({ file: selectedFile, budgetYear, budgetVersion, groupCode, shopCode });
      setMessage(`${budgetYear} 年第 ${budgetVersion} 版预算上传成功。下一步：在下方列表点击“全流程检查”，无错误后点击“入库”；全部店铺入库后去“汇总处理中心”运行汇总。`);
      setSelectedFile(null);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "上传失败");
    } finally {
      setLoading(false);
    }
  }

  async function uploadActual() {
    if (!actualFile) return;
    if (!actualYear || !actualGroupCode || !actualShopCode) {
      setMessage("请先选择年度、运营组和店铺，再上传实际经营表。");
      return;
    }
    setLoading(true);
    setMessage("");
    try {
      await uploadActualFile(actualFile, actualYear, actualType, actualGroupCode, actualShopCode);
      setMessage(`${actualYear} 年${actualType === "sales" ? "实际销售表" : "实际费用表"}上传成功。下一步：在实际经营文件列表点击“检查”，检查通过后点击“入库”，首页预算 vs 实际会自动纳入该数据。`);
      setActualFile(null);
      refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "实际经营表上传失败");
    } finally {
      setLoading(false);
    }
  }

  function downloadActualTemplate() {
    downloadActualBusinessTemplate();
  }

  async function action(label: string, task: () => Promise<unknown>) {
    try {
      const result = await task() as Record<string, unknown> | undefined;
      const detail = result && ("error_count" in result || "warning_count" in result)
        ? `：错误 ${result.error_count || 0}，提醒 ${result.warning_count || 0}`
        : "";
      setMessage(`${label}完成${detail}`);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : `${label}失败`);
    }
  }

  function canImport(row: Record<string, unknown>) {
    return (row.check_status === "检查通过" || row.check_status === "检查警告" || row.check_status === "有警告") && Number(row.error_count || 0) === 0 && row.import_status !== "已入库";
  }

  return (
    <div className="page-stack workbench-page">
      <section className="page-hero">
        <div>
          <h2>上传入口</h2>
          <p>先绑定年度、预算版本、运营组和店铺，再上传预算表或实际经营表。入库前仍需要人工检查确认。</p>
        </div>
        <div className="hero-stat-strip">
          <span><strong>{files.length}</strong>预算文件</span>
          <span><strong>{budgetImportedCount}</strong>已入库</span>
          <span><strong>{actualBatches.length}</strong>实际文件</span>
          <span><strong>{budgetErrorCount}</strong>待处理错误</span>
        </div>
      </section>

      <section className="panel task-panel">
        <div className="section-heading">
          <div>
            <h2>预算表上传</h2>
            <p className="muted">用于店铺年度预算，第 {budgetVersion} 版会独立入库和汇总。</p>
          </div>
          <button onClick={downloadShopBudgetTemplate}>下载店铺预算模板</button>
        </div>
        <div className="form-grid dense-form">
          <label>年度<input type="number" min={2000} max={2100} value={budgetYear} onChange={(event) => setBudgetYear(Number(event.target.value))} /></label>
          <label>预算版本<select value={budgetVersion} onChange={(event) => setBudgetVersion(Number(event.target.value))}>
            {[1, 2, 3, 4, 5].map((version) => <option key={version} value={version}>第 {version} 版</option>)}
          </select></label>
          <label>运营组<select
            value={groupCode}
            onChange={(event) => {
              const nextGroupCode = event.target.value;
              const nextGroup = groups.find((group) => group.group_code === nextGroupCode);
              setGroupCode(nextGroupCode);
              setShopCode(nextGroup?.shops?.[0]?.shop_code || "");
            }}
          >
            {groups.map((group) => <option key={group.group_code} value={group.group_code}>{group.group_name}</option>)}
          </select></label>
          <label>店铺<select value={shopCode} onChange={(event) => setShopCode(event.target.value)} disabled={!shops.length}>
            {shops.map((shop) => <option key={shop.shop_code} value={shop.shop_code}>{shop.shop_name}</option>)}
          </select></label>
        </div>
        <FileUploadBox
          selectedFile={selectedFile}
          onSelect={setSelectedFile}
          onUpload={upload}
          loading={loading}
          title="选择店铺预算表 .xlsx"
          description="上传后先检查，再由人工确认入库"
          actionLabel="上传预算表"
        />
      </section>

      {!groups.length && <div className="notice danger">未读取到运营组/店铺配置，请先维护本地配置后再上传。</div>}
      {message && <div className="notice">{message}</div>}

      <section className="panel task-panel">
        <div className="section-heading">
          <div>
            <h2>实际经营表上传</h2>
            <p className="muted">用于首页预算 vs 实际对比。模板内含实际销售模板和实际费用模板两个工作表。</p>
          </div>
          <div className="actual-template-actions">
            <button onClick={downloadActualTemplate}>下载实际模板</button>
            <span className="status-badge info">{actualImportedCount} 个批次已入库</span>
          </div>
        </div>
        <div className="form-grid dense-form">
          <label>年度<input type="number" min={2000} max={2100} value={actualYear} onChange={(event) => setActualYear(Number(event.target.value))} /></label>
          <label>表格类型<select value={actualType} onChange={(event) => setActualType(event.target.value as "sales" | "expense")}>
            <option value="sales">实际销售表</option>
            <option value="expense">实际费用表</option>
          </select></label>
          <label>运营组<select
            value={actualGroupCode}
            onChange={(event) => {
              const nextGroupCode = event.target.value;
              const nextGroup = groups.find((group) => group.group_code === nextGroupCode);
              setActualGroupCode(nextGroupCode);
              setActualShopCode(nextGroup?.shops?.[0]?.shop_code || "");
            }}
          >
            {groups.map((group) => <option key={group.group_code} value={group.group_code}>{group.group_name}</option>)}
          </select></label>
          <label>店铺<select value={actualShopCode} onChange={(event) => setActualShopCode(event.target.value)} disabled={!actualShops.length}>
            {actualShops.map((shop) => <option key={shop.shop_code} value={shop.shop_code}>{shop.shop_name}</option>)}
          </select></label>
        </div>
        <FileUploadBox
          selectedFile={actualFile}
          onSelect={setActualFile}
          onUpload={uploadActual}
          loading={loading}
          title={actualType === "sales" ? "选择实际销售表 .xlsx" : "选择实际费用表 .xlsx"}
          description="上传后先检查，通过后再入库到预算实际对比"
          actionLabel="上传实际表"
        />
      </section>

      <section className="panel data-section">
        <div className="section-heading">
          <div>
            <h2>实际经营文件</h2>
            <p className="muted">检查通过后入库，入库数据会影响首页实际与预算对比。</p>
          </div>
        </div>
        <DataTable
          rows={actualBatches as unknown as Record<string, unknown>[]}
          columns={[
            { key: "file_name", title: "实际经营文件" },
            { key: "file_type", title: "类型", render: (row) => row.file_type === "actual_sales" ? "实际销售" : "实际费用" },
            { key: "year", title: "年度" },
            { key: "group_name", title: "运营组", render: (row) => row.group_name || row.group_code || "-" },
            { key: "shop_name", title: "店铺", render: (row) => row.shop_name || row.shop_code || "-" },
            { key: "status", title: "状态", render: (row) => <StatusBadge value={String(row.status_label || row.status)} /> },
            { key: "row_count", title: "有效行" },
            { key: "error_count", title: "错误" },
            { key: "warning_count", title: "提醒" },
            {
              key: "actual_actions",
              title: "操作",
              render: (row) => (
                <div className="button-row compact-actions">
                  <button onClick={() => action("实际表检查", () => checkActualBatch(String(row.batch_id)))}>检查</button>
                  <button onClick={() => action("查看检查结果", () => checkActualBatch(String(row.batch_id)))}>查看结果</button>
                  <button disabled={Number(row.error_count || 0) > 0 || row.status === "imported"} onClick={() => window.confirm("确认将该实际经营表入库？入库后会影响预算实际对比。") && action("实际表入库", () => importActualBatch(String(row.batch_id)))}>入库</button>
                  <button className="danger" onClick={() => window.confirm(row.status === "imported" ? "确认删除该实际经营表及其已入库数据？删除后首页预算实际对比会变化。" : "确认删除该未入库实际经营表？") && action("删除实际表", () => deleteActualBatch(String(row.batch_id)))}>删除</button>
                </div>
              )
            }
          ]}
        />
      </section>

      <section className="panel data-section">
        <div className="section-heading">
          <div>
            <h2>预算文件</h2>
            <p className="muted">预算文件按版本隔离；检查无错误后才能入库。</p>
          </div>
        </div>
        <DataTable
          rows={files as unknown as Record<string, unknown>[]}
          columns={[
            { key: "file_name", title: "文件名" },
            { key: "budget_year", title: "年度" },
            { key: "budget_version", title: "预算版本", render: (row) => `第 ${row.budget_version || 1} 版` },
            { key: "group_name", title: "运营组", render: (row) => row.group_name || row.group_code || "-" },
            { key: "shop_name", title: "店铺", render: (row) => row.shop_name || row.shop_code || "-" },
            { key: "upload_time", title: "上传时间" },
            { key: "check_status", title: "检查状态", render: (row) => <StatusBadge value={String(row.check_status)} /> },
            { key: "import_status", title: "入库状态", render: (row) => <StatusBadge value={String(row.import_status)} /> },
            { key: "error_count", title: "错误" },
            { key: "warning_count", title: "警告" },
            {
              key: "actions",
              title: "操作",
              render: (row) => (
                <div className="button-row compact-actions">
                  <button onClick={() => action("格式检查", () => runFormatCheck(Number(row.id)))}>格式检查</button>
                  <button onClick={() => action("全流程检查", () => runFullCheck(Number(row.id)))}>全流程</button>
                  <button disabled={!canImport(row)} onClick={() => window.confirm("确认将该预算表入库？入库后会影响汇总结果。") && action("入库", () => importBudgetFile(Number(row.id)))}>入库</button>
                  <button className="danger" onClick={() => window.confirm(row.import_status === "已入库" ? "确认删除该文件及其已入库明细，并自动重算汇总？" : "确认删除该上传文件？") && action("删除", () => deleteUploadedFile(Number(row.id)))}>删除</button>
                </div>
              )
            }
          ]}
        />
      </section>
    </div>
  );
}
