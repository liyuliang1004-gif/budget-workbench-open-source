import { useEffect, useMemo, useState } from "react";
import { createVersionBackup, getVersionBackups, getVersionStatus } from "../api/versionApi";
import DataTable from "../components/DataTable";
import EmptyState from "../components/EmptyState";
import StatusBadge from "../components/StatusBadge";
import type { GitVersionStatus, RecentCommit, VersionBackup } from "../types/version";

export default function 版本管理() {
  const [status, setStatus] = useState<GitVersionStatus | null>(null);
  const [backups, setBackups] = useState<VersionBackup[]>([]);
  const [remark, setRemark] = useState("升级前备份");
  const [createdPath, setCreatedPath] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const latestBackup = backups[0];
  const rollbackCommand = useMemo(() => {
    const commit = latestBackup?.current_commit_hash || status?.current_commit_hash || "<commit_hash>";
    return `git reset --hard ${commit}`;
  }, [latestBackup, status]);

  async function refresh() {
    setError("");
    setLoading(true);
    try {
      const [nextStatus, nextBackups] = await Promise.all([getVersionStatus(), getVersionBackups()]);
      setStatus(nextStatus);
      setBackups(nextBackups);
    } catch (err) {
      setError(err instanceof Error ? err.message : "版本信息读取失败，请确认后端服务已启动。");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateBackup() {
    setCreating(true);
    setError("");
    setCreatedPath("");
    try {
      const backup = await createVersionBackup(remark);
      setCreatedPath(backup.backup_path);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建备份失败。");
    } finally {
      setCreating(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  if (loading && !status) {
    return <div className="loading-block">正在读取版本状态...</div>;
  }

  if (error && !status) {
    return <EmptyState title="版本服务暂不可用" description={error} />;
  }

  return (
    <div className="page-stack workbench-page">
      <section className="page-hero">
        <div>
          <h2>版本与备份</h2>
          <p>这里用于升级前留档和查看 Git 状态。页面只展示回滚说明，不直接执行破坏性回滚。</p>
        </div>
        <div className="hero-stat-strip">
          <span><strong>{status?.current_branch || "未知"}</strong>当前分支</span>
          <span><strong>{backups.length}</strong>备份</span>
          <span className={status?.is_dirty ? "danger-text" : ""}><strong>{status?.is_dirty ? "有修改" : "干净"}</strong>工作区</span>
        </div>
      </section>

      {error && <div className="notice warning">{error}</div>}
      {status?.is_dirty && (
        <div className="notice danger">
          当前工作区有未提交修改。升级前先确认这些文件是否需要提交，否则回滚时会增加判断成本。
        </div>
      )}

      <section className="panel version-summary">
        <div>
          <span className="muted">当前分支</span>
          <strong>{status?.current_branch || "未知"}</strong>
        </div>
        <div>
          <span className="muted">Commit（提交编号）</span>
          <strong>{status?.current_commit_hash ? status.current_commit_hash.slice(0, 12) : "未知"}</strong>
        </div>
        <div>
          <span className="muted">Tag（版本标签）</span>
          <strong>{status?.current_tag || "无"}</strong>
        </div>
        <div>
          <span className="muted">工作区</span>
          <StatusBadge value={status?.is_dirty ? "警告：有未提交修改" : "通过：干净"} />
        </div>
      </section>

      <section className="panel">
        <h2>版本状态</h2>
        <div className="version-detail-grid">
          <div>
            <span className="muted">提交说明</span>
            <strong>{status?.current_commit_message || "未知"}</strong>
          </div>
          <div>
            <span className="muted">提交时间</span>
            <strong>{status?.current_commit_time || "未知"}</strong>
          </div>
        </div>
        <h3>未提交文件</h3>
        {status?.uncommitted_files.length ? (
          <ul className="compact-list">
            {status.uncommitted_files.map((item) => <li key={item}>{item}</li>)}
          </ul>
        ) : (
          <p className="muted">当前没有未提交文件。</p>
        )}
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>创建升级前备份</h2>
            <p className="muted">默认不备份 .env、上传文件、输出报表和构建产物。</p>
          </div>
          <button onClick={handleCreateBackup} disabled={creating}>{creating ? "创建中..." : "创建备份"}</button>
        </div>
        <input value={remark} onChange={(event) => setRemark(event.target.value)} aria-label="备份备注" />
        {createdPath && <div className="notice success">备份已创建：{createdPath}</div>}
      </section>

      <section className="panel">
        <h2>备份列表</h2>
        <DataTable<VersionBackup>
          rows={backups}
          columns={[
            { key: "backup_id", title: "备份编号" },
            { key: "created_at", title: "时间" },
            { key: "current_branch", title: "分支" },
            { key: "current_commit_hash", title: "Commit（提交编号）", render: (row) => row.current_commit_hash ? row.current_commit_hash.slice(0, 12) : "未知" },
            { key: "remark", title: "备注" },
            { key: "database_files", title: "数据库", render: (row) => row.database_files?.join(", ") || "无" }
          ]}
        />
      </section>

      <section className="panel">
        <h2>最近提交</h2>
        <DataTable<RecentCommit>
          rows={status?.recent_commits || []}
          columns={[
            { key: "short_hash", title: "Commit（提交编号）" },
            { key: "time", title: "时间" },
            { key: "message", title: "说明" }
          ]}
        />
      </section>

      <section className="panel">
        <h2>回滚说明</h2>
        <p className="muted">页面不执行回滚。需要回滚时先停止后端服务，再由管理员人工确认代码命令和数据库恢复。</p>
        <pre className="command-preview">{rollbackCommand}</pre>
        <p className="muted">数据库恢复使用：scripts/回滚上一版本.py</p>
      </section>
    </div>
  );
}
