import type { ReactNode } from "react";
import type { PageKey } from "../App";
import type { VersionInfo } from "../types/version";
import Sidebar_v2 from "./Sidebar_v2";
import Topbar_v2 from "./Topbar_v2";

export default function Layout_v2({
  page,
  title,
  subtitle,
  version,
  theme,
  onThemeToggle,
  rightActions,
  onPageChange,
  onSettingsOpen,
  onAiOpen,
  year,
  budgetVersion,
  onYearChange,
  onBudgetVersionChange,
  children,
}: {
  page: PageKey;
  title: string;
  subtitle?: string;
  version?: VersionInfo | null;
  theme: string;
  onThemeToggle?: () => void;
  rightActions?: ReactNode;
  onPageChange: (page: PageKey) => void;
  onSettingsOpen: () => void;
  onAiOpen: () => void;
  year?: string;
  budgetVersion?: string;
  onYearChange?: (year: string) => void;
  onBudgetVersionChange?: (version: string) => void;
  children: ReactNode;
}) {
  return (
    <div className="app-shell">
      <Sidebar_v2
        page={page}
        onChange={onPageChange}
        onAiOpen={onAiOpen}
        onSettingsOpen={onSettingsOpen}
        versionText={version?.version ? `v${version.version}` : "v1.0.0"}
      />
      <main className="main">
        <Topbar_v2
          title={title}
          subtitle={subtitle}
          version={version}
          theme={theme}
          onThemeToggle={onThemeToggle}
          rightActions={rightActions}
          year={year}
          budgetVersion={budgetVersion}
          onYearChange={onYearChange}
          onBudgetVersionChange={onBudgetVersionChange}
          onAiOpen={onAiOpen}
        />
        <div className="content">
          <div className="page-stack">{children}</div>
        </div>
      </main>
    </div>
  );
}
