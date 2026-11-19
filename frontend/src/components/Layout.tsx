import type { ReactNode } from "react";
import type { PageKey } from "../App";
import type { VersionInfo } from "../types/version";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

export default function Layout({ page, title, version, onPageChange, onSettingsOpen, onAiOpen, children }: { page: PageKey; title: string; theme: string; version?: VersionInfo | null; onPageChange: (page: PageKey) => void; onSettingsOpen: () => void; onAiOpen: () => void; children: ReactNode }) {
  return (
    <div className="app-shell">
      <Sidebar page={page} onChange={onPageChange} onAiOpen={onAiOpen} onSettingsOpen={onSettingsOpen} />
      <main className="content">
        <Topbar title={title} version={version} />
        {children}
      </main>
    </div>
  );
}
