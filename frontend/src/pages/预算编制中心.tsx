import { useEffect, useMemo, useState } from "react";
import {
  exportPlanningWorkbook,
  getPlanningFiles,
  getPlanningOptions,
  openPlanningLocation,
  uploadPlanningCostPrices,
  uploadPlanningSalesPrices,
  type PlanningExportFile,
  type PlanningShopOption
} from "../api/planningApi";
import FileUploadBox from "../components/FileUploadBox";

const currentYear = new Date().getFullYear();

export default function 预算编制中心() {
  const [referenceYear, setReferenceYear] = useState(currentYear);
  const [targetYear, setTargetYear] = useState(currentYear + 1);
  const [budgetVersion, setBudgetVersion] = useState(1);
  const [groupName, setGroupName] = useState("");
  const [shopName, setShopName] = useState("");
  const [targetSalesWan, setTargetSalesWan] = useState("");
  const [growthRate, setGrowthRate] = useState("10");
  const [salesPriceRate, setSalesPriceRate] = useState("0");
  const [costPriceRate, setCostPriceRate] = useState("0");
  const [salesPriceSource, setSalesPriceSource] = useState<"actual" | "budget" | "uploaded">("actual");
  const [costPriceSource, setCostPriceSource] = useState<"actual" | "budget" | "uploaded">("actual");
  const [salesPriceFile, setSalesPriceFile] = useState<File | null>(null);
  const [costPriceFile, setCostPriceFile] = useState<File | null>(null);
  const [referenceSpringMonth, setReferenceSpringMonth] = useState(2);
  const [targetSpringMonth, setTargetSpringMonth] = useState(2);
  const [groups, setGroups] = useState<Array<{ group_name: string; group_code?: string }>>([]);
  const [shops, setShops] = useState<PlanningShopOption[]>([]);
  const [files, setFiles] = useState<PlanningExportFile[]>([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getPlanningOptions(referenceYear)
      .then((options) => {
        setGroups(options.groups || []);
        setShops(options.shops || []);
        const firstGroup = options.groups?.[0]?.group_name || "";
        const firstShop = options.shops?.find((item) => !firstGroup || item.group_name === firstGroup)?.shop_name || options.shops?.[0]?.shop_name || "";
        setGroupName((prev) => prev || firstGroup);
        setShopName((prev) => prev || firstShop);
      })
      .catch((error) => setMessage(error.message || "读取预算编制选项失败"));
  }, [referenceYear]);

  useEffect(() => {
    refreshGeneratedFiles();
    window.addEventListener("focus", refreshGeneratedFiles);
    return () => window.removeEventListener("focus", refreshGeneratedFiles);
  }, []);

  const visibleShops = useMemo(() => {
    if (!groupName) return shops;
    return shops.filter((item) => item.group_name === groupName || !item.group_name);
  }, [groupName, shops]);

  function changeGroup(nextGroupName: string) {
    const nextShops = shops.filter((item) => item.group_name === nextGroupName || !item.group_name);
    setGroupName(nextGroupName);
    setShopName(nextShops[0]?.shop_name || "");
  }

  async function refreshGeneratedFiles() {
    try {
      const response = await getPlanningFiles();
      setFiles(response.files || []);
    } catch {
      // 保留当前页面状态；历史记录读取失败不影响编制参数填写。
    }
  }

  async function generateWorkbook() {
    if (!shopName) {
      setMessage("请先选择店铺。若这里没有店铺，请先导入今年实际数据或维护运营组/店铺。");
      return;
    }
    setLoading(true);
    setMessage("");
    try {
      const response = await exportPlanningWorkbook({
        reference_year: referenceYear,
        target_year: targetYear,
        budget_version: budgetVersion,
        group_name: groupName || undefined,
        shop_name: shopName,
        target_sales_amount: targetSalesWan ? Number(targetSalesWan) * 10000 : undefined,
        target_growth_rate: Number(growthRate || 0),
        sales_price_adjustment_rate: Number(salesPriceRate || 0),
        cost_price_adjustment_rate: Number(costPriceRate || 0),
        sales_price_source: salesPriceSource,
        cost_price_source: costPriceSource,
        reference_spring_month: referenceSpringMonth,
        target_spring_month: targetSpringMonth
      });
      await refreshGeneratedFiles();
      if (!response.files?.length) {
        setFiles([]);
      }
      setMessage("明年预算编制表已生成。打开文件后，可在“产品预算调整”和“费用预算调整”中修改占比、价格、成本和费用率，主表会跟随公式重算。");
    } catch (error) {
      const nextMessage = error instanceof Error ? error.message : "生成预算编制表失败";
      setMessage(nextMessage);
      if (nextMessage.includes("未上传") || nextMessage.includes("导入")) {
        window.alert(nextMessage);
      }
    } finally {
      setLoading(false);
    }
  }

  async function openGeneratedFile(file: PlanningExportFile) {
    try {
      await openPlanningLocation(file.name);
      setMessage(`已打开 ${file.name} 所在目录。`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "打开文件所在目录失败");
    }
  }

  async function uploadPriceFile(kind: "sales" | "cost") {
    const file = kind === "sales" ? salesPriceFile : costPriceFile;
    if (!file) return;
    setLoading(true);
    setMessage("");
    try {
      const response = kind === "sales"
        ? await uploadPlanningSalesPrices(file, targetYear)
        : await uploadPlanningCostPrices(file, targetYear);
      if (kind === "sales") {
        setSalesPriceFile(null);
      } else {
        setCostPriceFile(null);
      }
      setMessage(`${response.price_type}导入完成：${response.imported_count} 个产品。导入后不会自动套用，请在“销售价来源/成本价来源”里选择“使用导入表”。`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "价格表导入失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-stack workbench-page planning-page">
      <section className="page-hero">
        <div>
          <h2>明年预算编制中心</h2>
          <p>按店铺生成下一年度预算基准表：先定全年销售目标，再按参考年实际节奏、同月产品结构、价格成本和费用小项费用率自动拆解。</p>
        </div>
        <div className="hero-stat-strip">
          <span><strong>{referenceYear}</strong>参考年度</span>
          <span><strong>{targetYear}</strong>目标年度</span>
          <span><strong>{shopName || "未选择"}</strong>当前店铺</span>
          <span><strong>{files.length}</strong>生成文件</span>
        </div>
      </section>

      <section className="planning-grid">
        <div className="panel task-panel">
          <div className="section-heading">
            <div>
              <h2>编制参数</h2>
              <p className="muted">目标销售额为最终口径；增长率只在没有填写目标销售额时用于推算。</p>
            </div>
          </div>
          <div className="form-grid dense-form">
            <label>参考年度<input type="number" value={referenceYear} onChange={(event) => setReferenceYear(Number(event.target.value))} /></label>
            <label>目标年度<input type="number" value={targetYear} onChange={(event) => setTargetYear(Number(event.target.value))} /></label>
            <label>预算版本<select value={budgetVersion} onChange={(event) => setBudgetVersion(Number(event.target.value))}>
              {[1, 2, 3, 4, 5].map((version) => <option key={version} value={version}>第 {version} 版</option>)}
            </select></label>
            <label>运营组<select value={groupName} onChange={(event) => changeGroup(event.target.value)}>
              <option value="">全部运营组</option>
              {groups.map((group) => <option key={group.group_name} value={group.group_name}>{group.group_name}</option>)}
            </select></label>
            <label>店铺<select value={shopName} onChange={(event) => setShopName(event.target.value)}>
              <option value="">请选择店铺</option>
              {visibleShops.map((shop) => <option key={`${shop.group_name || "all"}-${shop.shop_name}`} value={shop.shop_name}>{shop.shop_name}</option>)}
            </select></label>
            <label>全年销售目标（万元）<input type="number" min={0} value={targetSalesWan} onChange={(event) => setTargetSalesWan(event.target.value)} placeholder="例如 6000" /></label>
            <label>目标增长率（%）<input type="number" value={growthRate} onChange={(event) => setGrowthRate(event.target.value)} /></label>
            <label>销售价调整（%）<input type="number" value={salesPriceRate} onChange={(event) => setSalesPriceRate(event.target.value)} /></label>
            <label>成本价调整（%）<input type="number" value={costPriceRate} onChange={(event) => setCostPriceRate(event.target.value)} /></label>
            <label>销售价来源<select value={salesPriceSource} onChange={(event) => setSalesPriceSource(event.target.value as "actual" | "budget" | "uploaded")}>
              <option value="actual">参考今年实际</option>
              <option value="budget">参考今年预算</option>
              <option value="uploaded">使用导入价</option>
            </select></label>
            <label>成本价来源<select value={costPriceSource} onChange={(event) => setCostPriceSource(event.target.value as "actual" | "budget" | "uploaded")}>
              <option value="actual">参考今年实际</option>
              <option value="budget">参考今年预算</option>
              <option value="uploaded">使用导入价</option>
            </select></label>
            <label>参考年春节月份<select value={referenceSpringMonth} onChange={(event) => setReferenceSpringMonth(Number(event.target.value))}>
              {Array.from({ length: 12 }, (_, index) => index + 1).map((month) => <option key={month} value={month}>{month}月</option>)}
            </select></label>
            <label>目标年春节月份<select value={targetSpringMonth} onChange={(event) => setTargetSpringMonth(Number(event.target.value))}>
              {Array.from({ length: 12 }, (_, index) => index + 1).map((month) => <option key={month} value={month}>{month}月</option>)}
            </select></label>
          </div>
          <div className="button-row">
            <button onClick={generateWorkbook} disabled={loading}>{loading ? "生成中..." : "生成明年预算表"}</button>
          </div>
          <div className="planning-upload-grid">
            <FileUploadBox
              selectedFile={salesPriceFile}
              onSelect={setSalesPriceFile}
              onUpload={() => uploadPriceFile("sales")}
              loading={loading}
              title="选择销售价格表 .xlsx"
              description={`导入到 ${targetYear} 年；是否使用由“销售价来源”决定`}
              actionLabel="导入销售价表"
            />
            <FileUploadBox
              selectedFile={costPriceFile}
              onSelect={setCostPriceFile}
              onUpload={() => uploadPriceFile("cost")}
              loading={loading}
              title="选择产品成本表 .xlsx"
              description={`导入到 ${targetYear} 年；是否使用由“成本价来源”决定`}
              actionLabel="导入成本价表"
            />
          </div>
        </div>

        <div className="panel planning-logic-card">
          <h2>生成逻辑</h2>
          <ol>
            <li>先按店铺确定明年全年销售目标。</li>
            <li>用参考年实际销售节奏拆到 12 个月，并按春节月份迁移节奏。</li>
            <li>每个月按参考年同月产品销售占比分摊到产品。</li>
            <li>销售额除以销售价得到数量，数量乘以成本价得到成本。</li>
            <li>费用按小项读取参考年同月费用率，再乘以明年月度销售目标。</li>
            <li>导出后可在辅助表里手工改产品占比、价格、成本和费用率。</li>
          </ol>
          <div className="notice warning">
            销售价表和成本价表导入后只是成为可选数据源；只有在编制参数里选择“使用导入表”，生成预算时才会采用。
          </div>
        </div>
      </section>

      {message && <div className="notice">{message}</div>}

      <section className="panel data-section">
        <div className="section-heading">
          <div>
            <h2>生成结果</h2>
            <p className="muted">文件保存在系统输出目录。点击表格行可直接打开文件所在位置。</p>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>文件名</th>
                <th>表格说明</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {files.length ? files.map((file) => (
                <tr key={file.name} className="clickable-row" onClick={() => openGeneratedFile(file)}>
                  <td>{file.name}</td>
                  <td>{file.description}</td>
                  <td>打开所在目录</td>
                </tr>
              )) : (
                <tr><td colSpan={3} className="table-empty-cell">还没有生成预算编制表</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
