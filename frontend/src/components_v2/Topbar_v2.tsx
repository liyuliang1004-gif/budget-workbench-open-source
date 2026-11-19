import type { VersionInfo } from "../types/version";

export default function Topbar_v2({
  title,
  theme,
  onThemeToggle,
  rightActions,
  year,
  budgetVersion,
  onYearChange,
  onBudgetVersionChange,
  onAiOpen,
}: {
  title: string;
  subtitle?: string;
  version?: VersionInfo | null;
  theme?: string;
  onThemeToggle?: () => void;
  rightActions?: React.ReactNode;
  year?: string;
  budgetVersion?: string;
  onYearChange?: (year: string) => void;
  onBudgetVersionChange?: (version: string) => void;
  onAiOpen?: () => void;
}) {
  const isDark = theme === "dark";

  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="topbar-title">{title}</div>
      </div>
      <div className="topbar-right">
        {onAiOpen ? (
          <button type="button" className="ai-btn" onClick={onAiOpen}>
            🤖 AI助手
          </button>
        ) : null}

        {year !== undefined && onYearChange ? (
          <select
            className="topbar-select"
            value={year}
            onChange={(e) => onYearChange(e.target.value)}
          >
            {[2026, 2027, 2028].map((y) => (
              <option key={y} value={String(y)}>
                {y}年
              </option>
            ))}
          </select>
        ) : null}

        {budgetVersion !== undefined && onBudgetVersionChange ? (
          <select
            className="topbar-select"
            value={budgetVersion}
            onChange={(e) => onBudgetVersionChange(e.target.value)}
          >
            {[1, 2, 3, 4, 5].map((v) => (
              <option key={v} value={String(v)}>
                V{v}初稿
              </option>
            ))}
          </select>
        ) : null}

        {onThemeToggle ? (
          <button
            type="button"
            className="theme-toggle"
            onClick={onThemeToggle}
            title={isDark ? "切换浅色模式" : "切换深色模式"}
          >
            {isDark ? "☀️" : "🌙"}
          </button>
        ) : null}

        {rightActions}
      </div>
    </header>
  );
}
