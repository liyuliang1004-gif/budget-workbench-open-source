import { useMemo, useState } from "react";
import Modal from "./Modal";
import type { DashboardChartType, DashboardCustomConfig, DashboardLayoutConfig, DashboardWidgetCatalog, DashboardWidgetConfig } from "../types/dashboard";

interface Props {
  catalog: DashboardWidgetCatalog;
  layout: DashboardLayoutConfig;
  onClose: () => void;
  onSave: (layout: DashboardLayoutConfig) => Promise<void>;
  onReset: () => Promise<void>;
}

const customChartTypes: DashboardChartType[] = ["bar_table", "bar", "horizontal_bar", "table", "line", "smooth_line", "area", "step_line", "scatter"];

function resequence(widgets: DashboardWidgetConfig[]) {
  return widgets.map((widget, index) => ({ ...widget, order: (index + 1) * 10 }));
}

function customTitle(catalog: DashboardWidgetCatalog, config: DashboardCustomConfig) {
  const dimension = catalog.dimensions.find((item) => item.id === config.dimension)?.label || "维度";
  const metric = catalog.metrics.find((item) => item.id === config.metric)?.label || "指标";
  return `按${dimension}的${metric} TOP${config.top_n}`;
}

function isForbidden(catalog: DashboardWidgetCatalog, config: DashboardCustomConfig) {
  return catalog.forbidden_combinations.find((item) => item.dimension === config.dimension && item.metrics.includes(config.metric));
}

export default function DashboardConfigModal({ catalog, layout, onClose, onSave, onReset }: Props) {
  const [draft, setDraft] = useState<DashboardLayoutConfig>(() => ({ ...layout, widgets: [...layout.widgets].sort((a, b) => a.order - b.order) }));
  const [tab, setTab] = useState<"modules" | "layout" | "custom">("modules");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [customConfig, setCustomConfig] = useState<DashboardCustomConfig>({ metric: "sales_amount", dimension: "product", data_view: "actual", sort_by: "actual", top_n: 10 });

  const standardById = useMemo(() => Object.fromEntries(catalog.standard_widgets.map((item) => [item.id, item])), [catalog]);

  function updateWidget(id: string, patch: Partial<DashboardWidgetConfig>) {
    setDraft((current) => ({ ...current, widgets: current.widgets.map((item) => item.id === id ? { ...item, ...patch } : item) }));
  }

  function moveWidget(id: string, direction: -1 | 1) {
    setDraft((current) => {
      const widgets = [...current.widgets].sort((a, b) => a.order - b.order);
      const index = widgets.findIndex((item) => item.id === id);
      const target = index + direction;
      if (index < 0 || target < 0 || target >= widgets.length) return current;
      const [item] = widgets.splice(index, 1);
      widgets.splice(target, 0, item);
      return { ...current, widgets: resequence(widgets) };
    });
  }

  function addCustomWidget() {
    const forbidden = isForbidden(catalog, customConfig);
    if (forbidden) {
      setMessage(forbidden.reason);
      return;
    }
    const title = customTitle(catalog, customConfig);
    const next: DashboardWidgetConfig = {
      id: `custom_${Date.now()}`,
      module_id: "custom",
      kind: "custom",
      title,
      visible: true,
      order: (draft.widgets.length + 1) * 10,
      width: "half",
      chart_type: "bar_table",
      expanded: false,
      custom_config: customConfig,
    };
    setDraft((current) => ({ ...current, widgets: resequence([...current.widgets, next]) }));
    setMessage(`已添加：${title}`);
    setTab("layout");
  }

  async function save() {
    setSaving(true);
    setMessage("");
    try {
      await onSave({ ...draft, widgets: resequence([...draft.widgets].sort((a, b) => a.order - b.order)) });
      onClose();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存首页配置失败");
    } finally {
      setSaving(false);
    }
  }

  async function reset() {
    if (!window.confirm("确认恢复默认首页布局？当前自定义配置会被覆盖。")) return;
    setSaving(true);
    try {
      await onReset();
      onClose();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "恢复默认首页失败");
    } finally {
      setSaving(false);
    }
  }

  const sortedWidgets = [...draft.widgets].sort((a, b) => a.order - b.order);

  return (
    <Modal title="配置首页" onClose={onClose} resizable>
      <div className="settings-tabs">
        <button className={tab === "modules" ? "active" : ""} onClick={() => setTab("modules")}>模块库</button>
        <button className={tab === "layout" ? "active" : ""} onClick={() => setTab("layout")}>布局设置</button>
        <button className={tab === "custom" ? "active" : ""} onClick={() => setTab("custom")}>自定义图表</button>
      </div>
      {message && <div className="notice warning">{message}</div>}

      {tab === "modules" && (
        <div className="dashboard-config-list">
          {sortedWidgets.map((widget) => (
            <label className="dashboard-config-row" key={widget.id}>
              <input type="checkbox" checked={widget.visible} onChange={(event) => updateWidget(widget.id, { visible: event.target.checked })} />
              <span>
                <strong>{widget.title}</strong>
                <small>{widget.kind === "custom" ? "自定义图表" : standardById[widget.module_id || widget.id]?.category || "标准模块"}</small>
              </span>
            </label>
          ))}
        </div>
      )}

      {tab === "layout" && (
        <div className="dashboard-config-list">
          {sortedWidgets.map((widget, index) => {
            const standard = widget.kind === "standard" ? standardById[widget.module_id || widget.id] : null;
            const chartTypes = widget.kind === "custom" ? customChartTypes : standard?.allowed_chart_types || [widget.chart_type];
            return (
              <div className="dashboard-layout-row" key={widget.id}>
                <div>
                  <strong>{widget.title}</strong>
                  <small>{widget.visible ? "显示" : "隐藏"} · {widget.width === "full" ? "全宽" : "半宽"}</small>
                </div>
                <div className="dashboard-layout-controls">
                  <button className="secondary compact-button" disabled={index === 0} onClick={() => moveWidget(widget.id, -1)}>上移</button>
                  <button className="secondary compact-button" disabled={index === sortedWidgets.length - 1} onClick={() => moveWidget(widget.id, 1)}>下移</button>
                  <select value={widget.width} onChange={(event) => updateWidget(widget.id, { width: event.target.value as "half" | "full" })}>
                    <option value="half">半宽</option>
                    <option value="full">全宽</option>
                  </select>
                  <select value={widget.chart_type} onChange={(event) => updateWidget(widget.id, { chart_type: event.target.value as DashboardChartType })}>
                    {chartTypes.map((type) => <option key={type} value={type}>{catalog.chart_types.find((item) => item.id === type)?.label || type}</option>)}
                  </select>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {tab === "custom" && (
        <div className="panel dashboard-custom-builder">
          <div className="form-grid">
            <label>指标
              <select value={customConfig.metric} onChange={(event) => setCustomConfig({ ...customConfig, metric: event.target.value as DashboardCustomConfig["metric"] })}>
                {catalog.metrics.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
              </select>
            </label>
            <label>维度
              <select value={customConfig.dimension} onChange={(event) => setCustomConfig({ ...customConfig, dimension: event.target.value as DashboardCustomConfig["dimension"] })}>
                {catalog.dimensions.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
              </select>
            </label>
            <label>数据视图
              <select value={customConfig.data_view} onChange={(event) => setCustomConfig({ ...customConfig, data_view: event.target.value as DashboardCustomConfig["data_view"] })}>
                {catalog.data_views.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
              </select>
            </label>
            <label>排序
              <select value={customConfig.sort_by} onChange={(event) => setCustomConfig({ ...customConfig, sort_by: event.target.value as DashboardCustomConfig["sort_by"] })}>
                {catalog.sort_options.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
              </select>
            </label>
            <label>TOP N
              <select value={customConfig.top_n} onChange={(event) => setCustomConfig({ ...customConfig, top_n: Number(event.target.value) as DashboardCustomConfig["top_n"] })}>
                {catalog.top_n_options.map((item) => <option key={item} value={item}>前 {item}</option>)}
              </select>
            </label>
          </div>
          <p className="muted">{isForbidden(catalog, customConfig)?.reason || "当前组合可用，保存后会在首页展示。"}</p>
          <button onClick={addCustomWidget}>添加自定义图表</button>
        </div>
      )}

      <div className="dashboard-config-footer">
        <button className="secondary" onClick={reset} disabled={saving}>恢复默认首页</button>
        <div>
          <button className="secondary" onClick={onClose} disabled={saving}>取消</button>
          <button onClick={save} disabled={saving}>{saving ? "保存中..." : "保存配置"}</button>
        </div>
      </div>
    </Modal>
  );
}
