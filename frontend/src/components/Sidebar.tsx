import type { PageKey } from "../App";

const items: Array<{ key: PageKey; label: string }> = [
  { key: "home", label: "首页总览" },
  { key: "upload", label: "文件上传中心" },
  { key: "check", label: "上传检查中心" },
  { key: "aggregate", label: "汇总处理中心" },
  { key: "planning", label: "预算编制中心" },
  { key: "export", label: "报表导出中心" }
];

export default function Sidebar({ page, onChange, onAiOpen, onSettingsOpen }: { page: PageKey; onChange: (page: PageKey) => void; onAiOpen: () => void; onSettingsOpen: () => void }) {
  return (
    <aside className="sidebar">
      <div className="brand-row">
        <div className="brand">经营工作台</div>
        <button className="ai-brand-button" onClick={onAiOpen}>AI分析</button>
      </div>
      <nav>
        {items.map((item) => (
          <button key={item.key} className={page === item.key ? "active" : ""} onClick={() => onChange(item.key)}>
            {item.label}
          </button>
        ))}
      </nav>
      <button className="sidebar-settings-button" onClick={onSettingsOpen}>系统设置</button>
    </aside>
  );
}
