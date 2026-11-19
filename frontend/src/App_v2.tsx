import { useEffect, useMemo, useState } from "react";
import { getSettings } from "./api/settingsApi";
import { getVersion } from "./api/versionApi";
import Layout_v2 from "./components_v2/Layout_v2";
import Modal from "./components/Modal";
import AI经营分析 from "./pages/AI经营分析";
import 上传检查中心 from "./pages/上传检查中心";
import 报表导出中心 from "./pages/报表导出中心";
import 文件上传中心 from "./pages/文件上传中心";
import 汇总处理中心 from "./pages/汇总处理中心";
import 版本管理 from "./pages/版本管理";
import 系统设置 from "./pages/系统设置";
import AI提示词设置 from "./pages/AI提示词设置";
import 首页总览 from "./pages/首页总览_v2";
import 预算编制中心 from "./pages/预算编制中心";
import 首次使用向导 from "./pages/首次使用向导";
import type { VersionInfo } from "./types/version";

export type PageKey = "home" | "upload" | "check" | "aggregate" | "export" | "planning";

const titles: Record<PageKey, string> = {
  home: "首页总览",
  upload: "文件上传",
  check: "上传检查",
  aggregate: "汇总处理",
  export: "报表导出",
  planning: "预算编制"
};

function pageFromHash(): PageKey {
  const key = window.location.hash.replace("#/", "") || "home";
  return (Object.keys(titles).includes(key) ? key : "home") as PageKey;
}

export default function App_v2() {
  const [page, setPage] = useState<PageKey>(pageFromHash());
  const [theme, setTheme] = useState(localStorage.getItem("budget-theme") || "light");
  const [version, setVersion] = useState<VersionInfo | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsTab, setSettingsTab] = useState<"system" | "aiPrompts" | "version" | "appearance">("system");
  const [aiOpen, setAiOpen] = useState(false);
  const [onboardingRequired, setOnboardingRequired] = useState(false);
  const [headerYear, setHeaderYear] = useState<string>("2026");
  const [headerBudgetVersion, setHeaderBudgetVersion] = useState<string>("1");
  // 回调引用：顶栏修改year/V时，反向同步到首页组件内部filters
  const homepageRef = useState<{ setFiltersFromHeader?: (next: Partial<{ year: string; budget_version: string }>) => void }>({})[0];

  useEffect(() => {
    document.documentElement.dataset.ui = "v2";
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("budget-theme", theme);
    return () => {
      delete document.documentElement.dataset.ui;
    };
  }, [theme]);

  useEffect(() => {
    getVersion().then(setVersion).catch(() => setVersion(null));
    getSettings().then((settings) => setOnboardingRequired(settings.onboarding_completed === false)).catch(() => setOnboardingRequired(false));
    const onHashChange = () => setPage(pageFromHash());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const content = useMemo(() => {
    switch (page) {
      case "upload": return <文件上传中心 />;
      case "check": return <上传检查中心 />;
      case "aggregate": return <汇总处理中心 />;
      case "export": return <报表导出中心 />;
      case "planning": return <预算编制中心 />;
      default:
        return (
          <首页总览
            onAiOpen={() => setAiOpen(true)}
            onHeaderFiltersChange={(year, budgetVersion) => {
              setHeaderYear(year);
              setHeaderBudgetVersion(budgetVersion);
            }}
            refCapture={(setter) => { homepageRef.setFiltersFromHeader = setter; }}
            key={page}
          />
        );
    }
  }, [page, homepageRef]);

  function changePage(next: PageKey) {
    window.location.hash = `/${next}`;
    setPage(next);
  }

  const toggleTheme = () => setTheme(theme === "dark" ? "light" : "dark");

  const handleYearChange = (year: string) => {
    setHeaderYear(year);
    if (homepageRef.setFiltersFromHeader) {
      homepageRef.setFiltersFromHeader({ year });
    }
  };

  const handleBudgetVersionChange = (budgetVersion: string) => {
    setHeaderBudgetVersion(budgetVersion);
    if (homepageRef.setFiltersFromHeader) {
      homepageRef.setFiltersFromHeader({ budget_version: budgetVersion });
    }
  };

  return (
    <Layout_v2
      page={page}
      title={titles[page]}
      theme={theme}
      onThemeToggle={toggleTheme}
      version={version}
      onPageChange={changePage}
      onSettingsOpen={() => setSettingsOpen(true)}
      onAiOpen={() => setAiOpen(true)}
      year={page === "home" ? headerYear : undefined}
      budgetVersion={page === "home" ? headerBudgetVersion : undefined}
      onYearChange={handleYearChange}
      onBudgetVersionChange={handleBudgetVersionChange}
    >
      {content}
      {settingsOpen && (
        <Modal title="系统设置" onClose={() => setSettingsOpen(false)}>
          <div className="settings-tabs">
            <button className={settingsTab === "system" ? "active" : ""} onClick={() => setSettingsTab("system")}>系统设置</button>
            <button className={settingsTab === "aiPrompts" ? "active" : ""} onClick={() => setSettingsTab("aiPrompts")}>AI 提示词</button>
            <button className={settingsTab === "version" ? "active" : ""} onClick={() => setSettingsTab("version")}>版本管理</button>
            <button className={settingsTab === "appearance" ? "active" : ""} onClick={() => setSettingsTab("appearance")}>外观设置</button>
          </div>
          {settingsTab === "system" && <系统设置 theme={theme} onThemeChange={() => setTheme(theme === "dark" ? "light" : "dark")} />}
          {settingsTab === "aiPrompts" && <AI提示词设置 />}
          {settingsTab === "version" && <版本管理 />}
          {settingsTab === "appearance" && (
            <section className="panel">
              <h2>深浅色模式</h2>
              <p className="muted">当前主题：{theme === "dark" ? "深色金色主题" : "浅色主题"}</p>
              <div className="button-row compact-settings-actions">
                <button onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? "切换浅色模式" : "切换深色模式"}</button>
              </div>
            </section>
          )}
        </Modal>
      )}
      {aiOpen && (
        <Modal title="AI分析" onClose={() => setAiOpen(false)} resizable>
          <AI经营分析 />
        </Modal>
      )}
      {onboardingRequired && (
        <Modal title="首次使用向导" onClose={() => undefined} showClose={false}>
          <首次使用向导 onComplete={() => setOnboardingRequired(false)} />
        </Modal>
      )}
    </Layout_v2>
  );
}
