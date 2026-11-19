import type { VersionInfo } from "../types/version";

export default function Topbar({ title, version }: { title: string; version?: VersionInfo | null }) {
  return (
    <header className="topbar">
      <div>
        <h1>{title}</h1>
        <p>{version?.system_name || "本地可视化工作台"}</p>
      </div>
    </header>
  );
}
