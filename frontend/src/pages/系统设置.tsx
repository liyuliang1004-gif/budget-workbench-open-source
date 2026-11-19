import { useEffect, useState } from "react";
import { chooseDesktopDataDir, isDesktopShell, openDesktopDataDir } from "../api/desktopApi";
import { getGroupsShopsForEdit, getSettings, updateGroupsShops, updateSettings, type SettingsInfo } from "../api/settingsApi";
import DataTable from "../components/DataTable";
import type { OperationGroupOption } from "../types/upload";

export default function 系统设置({ theme, onThemeChange }: { theme: string; onThemeChange: () => void }) {
  const [settings, setSettings] = useState<SettingsInfo | null>(null);
  const [systemName, setSystemName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [defaultYear, setDefaultYear] = useState(String(new Date().getFullYear()));
  const [defaultBudgetVersion, setDefaultBudgetVersion] = useState("1");
  const [dataMode, setDataMode] = useState<"formal" | "demo">("formal");
  const [aiMode, setAiMode] = useState("mock");
  const [aiBase, setAiBase] = useState("https://api.deepseek.com");
  const [aiModel, setAiModel] = useState("deepseek-chat");
  const [aiKey, setAiKey] = useState("");
  const [groups, setGroups] = useState<OperationGroupOption[]>([]);
  const [message, setMessage] = useState("");

  useEffect(() => {
    getSettings().then((value) => {
      setSettings(value);
      setSystemName(value.system_name || "经营工作台");
      setCompanyName(value.company_name || "");
      setDefaultYear(String(value.default_year || new Date().getFullYear()));
      setDefaultBudgetVersion(String(value.default_budget_version || 1));
      setDataMode(value.data_mode === "demo" ? "demo" : "formal");
      setAiMode(value.ai_config?.mode || "mock");
      setAiBase(value.ai_config?.api_base || "https://api.deepseek.com");
      setAiModel(value.ai_config?.model || "deepseek-chat");
    }).catch(() => setSettings(null));
    getGroupsShopsForEdit().then((value) => setGroups(value.operation_groups || [])).catch((error) => setMessage(error.message));
  }, []);

  async function save() {
    const next = await updateSettings({
      system_name: systemName,
      company_name: companyName,
      default_year: Number(defaultYear) || new Date().getFullYear(),
      default_budget_version: Number(defaultBudgetVersion) || 1,
      data_mode: dataMode,
      theme,
      ai_config: { mode: aiMode, api_base: aiBase, model: aiModel, api_key: aiKey }
    });
    setSettings(next);
    setAiKey("");
    setMessage("设置已保存到本地配置，不会提交到 Git。");
  }

  async function openDataDir() {
    const result = await openDesktopDataDir();
    setMessage(result.message || (result.success ? "已打开数据目录。" : "无法打开数据目录。"));
  }

  async function changeDataDir() {
    const result = await chooseDesktopDataDir();
    if (result.success) {
      setMessage(`新的数据目录已保存：${result.data_dir || ""}。请退出并重新打开软件后生效。`);
      return;
    }
    setMessage(result.message || "未更换数据目录。");
  }

  async function saveGroups() {
    const saved = await updateGroupsShops({ operation_groups: groups });
    setGroups(saved.operation_groups || []);
    setMessage("运营组/店铺配置已保存，刷新上传中心后生效。");
  }

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

  const rows = settings ? Object.entries({
    "当前工作区路径": settings.workspace,
    "当前数据目录": settings.user_data_path || "",
    "上传目录": settings.upload_path,
    "输出目录": settings.output_path,
    "数据库路径": settings.database_path,
    "模板版本": settings.template_version || "V1.0",
    "默认年度": settings.default_year || "",
    "默认预算版本": settings.default_budget_version ? `第 ${settings.default_budget_version} 版` : "",
    "数据模式": settings.data_mode === "demo" ? "示例数据模式" : "正式数据模式",
    "首次配置": settings.onboarding_completed ? "已完成" : "未完成",
    "金额误差阈值": settings.amount_tolerance ?? "0.01",
    "AI Key 状态": settings.ai_config?.api_key_configured ? `已配置：${settings.ai_config.api_key_masked}` : "未配置",
    "主题设置": theme === "dark" ? "深色金色主题" : "浅色主题"
  }).map(([name, value]) => ({ name, value: String(value) })) : [];
  const shopCount = groups.reduce((sum, group) => sum + (group.shops?.length || 0), 0);
  const activeGroupCount = groups.filter((group) => (group.status || "active") === "active").length;

  return (
    <div className="page-stack workbench-page">
      <section className="page-hero settings-hero">
        <div>
          <h2>系统配置</h2>
          <p>系统名称、AI 接入和运营组/店铺主数据都保存在本地配置文件中，不写入 Git。</p>
        </div>
        <div className="hero-stat-strip">
          <span><strong>{activeGroupCount}</strong>启用运营组</span>
          <span><strong>{shopCount}</strong>店铺</span>
          <span><strong>{settings?.ai_config?.api_key_configured ? "已配置" : "未配置"}</strong>AI Key</span>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>可修改设置</h2>
            <p className="muted">AI 默认只回答问题，不执行上传、删除、入库、导出或清理数据。</p>
          </div>
        </div>
        <div className="form-grid">
          <label>系统名称<input value={systemName} onChange={(event) => setSystemName(event.target.value)} /></label>
          <label>公司名称<input value={companyName} placeholder="例如：某某食品有限公司" onChange={(event) => setCompanyName(event.target.value)} /></label>
          <label>默认年度<input type="number" value={defaultYear} onChange={(event) => setDefaultYear(event.target.value)} /></label>
          <label>默认预算版本<input type="number" min="1" value={defaultBudgetVersion} onChange={(event) => setDefaultBudgetVersion(event.target.value)} /></label>
          <label>数据模式<select value={dataMode} onChange={(event) => setDataMode(event.target.value === "demo" ? "demo" : "formal")}><option value="formal">正式数据模式</option><option value="demo">示例数据模式</option></select></label>
          <label>AI 模式<select value={aiMode} onChange={(event) => setAiMode(event.target.value)}><option value="mock">mock（模拟模式）</option><option value="deepseek">DeepSeek（真实模型）</option></select></label>
          <label>AI 接口地址<input value={aiBase} onChange={(event) => setAiBase(event.target.value)} /></label>
          <label>AI 模型<input value={aiModel} onChange={(event) => setAiModel(event.target.value)} /></label>
          <label>AI Key<input type="password" value={aiKey} placeholder="留空则保留已有配置" onChange={(event) => setAiKey(event.target.value)} /></label>
        </div>
        <div className="button-row settings-actions">
          <button onClick={save}>保存设置</button>
          <button className="secondary" onClick={onThemeChange}>{theme === "dark" ? "切换浅色模式" : "切换深色模式"}</button>
        </div>
        {message && <div className="notice success">{message}</div>}
      </section>
      <section className="panel data-section">
        <div className="section-heading">
          <div>
            <h2>当前环境</h2>
            <p className="muted">这些路径和阈值用于排查上传、导出和本地配置问题。</p>
          </div>
          <div className="button-row compact-settings-actions">
            <button className="secondary" onClick={openDataDir} disabled={!isDesktopShell()}>打开数据目录</button>
            <button className="secondary" onClick={changeDataDir} disabled={!isDesktopShell()}>更换数据目录</button>
          </div>
        </div>
        {!isDesktopShell() && <div className="notice warning">当前是浏览器模式，打开和更换数据目录请在桌面端使用。</div>}
        <DataTable rows={rows} columns={[{ key: "name", title: "设置项" }, { key: "value", title: "当前值" }]} />
      </section>
      <section className="panel">
        <div className="section-heading">
          <h2>运营组/店铺维护</h2>
          <div className="button-row compact-settings-actions">
            <button onClick={addGroup}>新增运营组</button>
            <button onClick={saveGroups}>保存运营组/店铺</button>
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
    </div>
  );
}
