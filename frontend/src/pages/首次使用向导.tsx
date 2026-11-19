import { useEffect, useState } from "react";
import { chooseDesktopDataDir, isDesktopShell, openDesktopDataDir } from "../api/desktopApi";
import { getGroupsShopsForEdit, getSettings, updateGroupsShops, updateSettings } from "../api/settingsApi";
import DataTable from "../components/DataTable";
import type { OperationGroupOption } from "../types/upload";

export default function 首次使用向导({ onComplete }: { onComplete: () => void }) {
  const [loading, setLoading] = useState(true);
  const [systemName, setSystemName] = useState("经营工作台");
  const [companyName, setCompanyName] = useState("");
  const [defaultYear, setDefaultYear] = useState(String(new Date().getFullYear()));
  const [defaultBudgetVersion, setDefaultBudgetVersion] = useState("1");
  const [dataMode, setDataMode] = useState<"formal" | "demo">("formal");
  const [dataDir, setDataDir] = useState("");
  const [aiMode, setAiMode] = useState("mock");
  const [aiBase, setAiBase] = useState("https://api.deepseek.com");
  const [aiModel, setAiModel] = useState("deepseek-chat");
  const [aiKey, setAiKey] = useState("");
  const [groups, setGroups] = useState<OperationGroupOption[]>([]);
  const [message, setMessage] = useState("");

  useEffect(() => {
    Promise.all([getSettings(), getGroupsShopsForEdit()])
      .then(([settings, registry]) => {
        setSystemName(settings.system_name || "经营工作台");
        setCompanyName(settings.company_name || "");
        setDefaultYear(String(settings.default_year || new Date().getFullYear()));
        setDefaultBudgetVersion(String(settings.default_budget_version || 1));
        setDataMode(settings.data_mode === "demo" ? "demo" : "formal");
        setDataDir(settings.user_data_path || "");
        setAiMode(settings.ai_config?.mode || "mock");
        setAiBase(settings.ai_config?.api_base || "https://api.deepseek.com");
        setAiModel(settings.ai_config?.model || "deepseek-chat");
        setGroups(registry.operation_groups?.length ? registry.operation_groups : [{
          group_code: "G001",
          group_name: "示例运营组",
          status: "active",
          shops: [{ group_code: "G001", shop_code: "S001", shop_name: "示例店铺", status: "active" }],
        }]);
      })
      .catch((error) => setMessage(error.message || "读取初始化配置失败。"))
      .finally(() => setLoading(false));
  }, []);

  function updateGroup(index: number, patch: Partial<OperationGroupOption>) {
    setGroups((prev) => prev.map((group, current) => current === index ? { ...group, ...patch } : group));
  }

  function addGroup() {
    setGroups((prev) => [...prev, { group_code: `G${String(prev.length + 1).padStart(3, "0")}`, group_name: "新运营组", status: "active", shops: [] }]);
  }

  function addShop(groupIndex: number) {
    setGroups((prev) => prev.map((group, current) => current === groupIndex ? {
      ...group,
      shops: [...group.shops, { group_code: group.group_code, shop_code: `S${String(group.shops.length + 1).padStart(3, "0")}`, shop_name: "新店铺", status: "active" }]
    } : group));
  }

  function updateShop(groupIndex: number, shopIndex: number, patch: Record<string, string>) {
    setGroups((prev) => prev.map((group, current) => {
      if (current !== groupIndex) return group;
      return {
        ...group,
        shops: group.shops.map((shop, index) => index === shopIndex ? { ...shop, ...patch, group_code: group.group_code } : shop)
      };
    }));
  }

  async function openDataDir() {
    const result = await openDesktopDataDir();
    setMessage(result.message || (result.success ? "已打开数据目录。" : "无法打开数据目录。"));
  }

  async function changeDataDir() {
    const result = await chooseDesktopDataDir();
    if (result.success) {
      setDataDir(result.data_dir || dataDir);
      setMessage("新的数据目录已保存，重启软件后生效。首次向导可以继续完成。");
      return;
    }
    setMessage(result.message || "未更换数据目录。");
  }

  async function finish() {
    if (!systemName.trim()) {
      setMessage("请填写系统名称。");
      return;
    }
    if (!groups.some((group) => group.group_name.trim() && group.shops.some((shop) => shop.shop_name.trim()))) {
      setMessage("请至少维护一个运营组和一个店铺。");
      return;
    }
    setLoading(true);
    try {
      await updateGroupsShops({ operation_groups: groups });
      await updateSettings({
        system_name: systemName,
        company_name: companyName,
        default_year: Number(defaultYear) || new Date().getFullYear(),
        default_budget_version: Number(defaultBudgetVersion) || 1,
        data_mode: dataMode,
        onboarding_completed: true,
        ai_config: { mode: aiMode, api_base: aiBase, model: aiModel, api_key: aiKey },
      });
      onComplete();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存首次配置失败。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-stack onboarding-wizard">
      <section className="page-hero settings-hero">
        <div>
          <h2>欢迎使用经营工作台</h2>
          <p>先完成基础配置。后续上传、汇总、导出和 AI 分析都会使用这些本地设置。</p>
        </div>
        <div className="hero-stat-strip">
          <span><strong>{dataDir || "待确认"}</strong>数据目录</span>
          <span><strong>{dataMode === "demo" ? "示例" : "正式"}</strong>数据模式</span>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>基础信息</h2>
            <p className="muted">这些内容会显示在系统设置、导出报表和后续初始化配置中。</p>
          </div>
        </div>
        <div className="form-grid">
          <label>系统名称<input value={systemName} onChange={(event) => setSystemName(event.target.value)} /></label>
          <label>公司名称<input value={companyName} placeholder="可先留空" onChange={(event) => setCompanyName(event.target.value)} /></label>
          <label>默认年度<input type="number" value={defaultYear} onChange={(event) => setDefaultYear(event.target.value)} /></label>
          <label>默认预算版本<input type="number" min="1" value={defaultBudgetVersion} onChange={(event) => setDefaultBudgetVersion(event.target.value)} /></label>
          <label>数据模式<select value={dataMode} onChange={(event) => setDataMode(event.target.value === "demo" ? "demo" : "formal")}><option value="formal">正式数据模式</option><option value="demo">示例数据模式</option></select></label>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>数据目录</h2>
            <p className="muted">上传文件、数据库、导出报表、配置和备份都会保存在这里。</p>
          </div>
          <div className="button-row compact-settings-actions">
            <button className="secondary" onClick={openDataDir} disabled={!isDesktopShell()}>打开目录</button>
            <button className="secondary" onClick={changeDataDir} disabled={!isDesktopShell()}>更换目录</button>
          </div>
        </div>
        <div className="notice">{dataDir || "当前未读取到数据目录。"}</div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>AI 接入</h2>
            <p className="muted">AI Key 由用户自己填写；留空可以先使用模拟模式。</p>
          </div>
        </div>
        <div className="form-grid">
          <label>AI 模式<select value={aiMode} onChange={(event) => setAiMode(event.target.value)}><option value="mock">mock（模拟模式）</option><option value="deepseek">DeepSeek（真实模型）</option></select></label>
          <label>AI 接口地址<input value={aiBase} onChange={(event) => setAiBase(event.target.value)} /></label>
          <label>AI 模型<input value={aiModel} onChange={(event) => setAiModel(event.target.value)} /></label>
          <label>AI Key<input type="password" value={aiKey} placeholder="可稍后在系统设置中填写" onChange={(event) => setAiKey(event.target.value)} /></label>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <h2>运营组/店铺</h2>
          <div className="button-row compact-settings-actions">
            <button className="secondary" onClick={addGroup}>新增运营组</button>
          </div>
        </div>
        <div className="page-stack">
          {groups.map((group, groupIndex) => (
            <div className="settings-group-card" key={`${group.group_code}-${groupIndex}`}>
              <div className="form-grid">
                <label>运营组编码<input value={group.group_code} onChange={(event) => updateGroup(groupIndex, { group_code: event.target.value })} /></label>
                <label>运营组名称<input value={group.group_name} onChange={(event) => updateGroup(groupIndex, { group_name: event.target.value })} /></label>
                <label>状态<select value={group.status || "active"} onChange={(event) => updateGroup(groupIndex, { status: event.target.value as "active" | "inactive" })}><option value="active">启用</option><option value="inactive">停用</option></select></label>
              </div>
              <DataTable
                rows={(group.shops || []).map((shop, shopIndex) => ({ ...shop, shopIndex }))}
                columns={[
                  { key: "shop_code", title: "店铺编码", render: (row) => <input value={String(row.shop_code || "")} onChange={(event) => updateShop(groupIndex, Number(row.shopIndex), { shop_code: event.target.value })} /> },
                  { key: "shop_name", title: "店铺名称", render: (row) => <input value={String(row.shop_name || "")} onChange={(event) => updateShop(groupIndex, Number(row.shopIndex), { shop_name: event.target.value })} /> },
                  { key: "status", title: "状态", render: (row) => <select value={String(row.status || "active")} onChange={(event) => updateShop(groupIndex, Number(row.shopIndex), { status: event.target.value })}><option value="active">启用</option><option value="inactive">停用</option></select> }
                ]}
              />
              <div className="button-row compact-settings-actions">
                <button className="secondary" onClick={() => addShop(groupIndex)}>新增店铺</button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="button-row settings-actions">
        <button onClick={finish} disabled={loading}>{loading ? "保存中" : "完成首次配置"}</button>
      </div>
      {message && <div className="notice warning">{message}</div>}
    </div>
  );
}
