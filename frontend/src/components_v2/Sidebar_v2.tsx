import type { PageKey } from "../App";

const items: Array<{ key: PageKey; label: string; icon: string }> = [
  { key: "home", label: "首页总览", icon: "📊" },
  { key: "upload", label: "文件上传", icon: "📤" },
  { key: "check", label: "上传检查", icon: "✅" },
  { key: "aggregate", label: "汇总处理", icon: "🔄" },
  { key: "planning", label: "预算编制", icon: "🎯" },
  { key: "export", label: "报表导出", icon: "📄" },
  { key: "settings", label: "系统设置", icon: "⚙️" },
];

export default function Sidebar_v2({
  page,
  onChange,
  onSettingsOpen,
  versionText = "v0.1.0",
}: {
  page: PageKey;
  onChange: (page: PageKey) => void;
  onSettingsOpen?: () => void;
  versionText?: string;
  onAiOpen?: () => void;
}) {
  const handleClick = (key: PageKey) => {
    if (key === "settings" && onSettingsOpen) {
      onSettingsOpen();
    } else {
      onChange(key);
    }
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <h1>预算管理系统</h1>
        <p>Budget Management System</p>
      </div>
      <nav className="sidebar-nav">
        {items.map((item) => (
          <a
            key={item.key}
            className={`nav-item ${page === item.key ? "active" : ""}`}
            onClick={(e) => {
              e.preventDefault();
              handleClick(item.key);
            }}
            href="#"
          >
            <span className="nav-icon">{item.icon}</span>
            <span>{item.label}</span>
          </a>
        ))}
      </nav>
      <div className="sidebar-footer">{versionText}</div>
    </aside>
  );
}
