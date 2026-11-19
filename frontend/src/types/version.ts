export interface VersionInfo {
  system_name: string;
  version: string;
  stage: string;
  git_branch: string;
  git_commit: string;
}

export interface RecentCommit {
  hash: string;
  short_hash: string;
  time: string;
  message: string;
}

export interface GitVersionStatus {
  is_git_repository: boolean;
  message: string;
  current_branch: string;
  current_commit_hash: string;
  current_commit_message: string;
  current_commit_time: string;
  current_tag: string;
  is_dirty: boolean;
  uncommitted_files: string[];
  recent_commits: RecentCommit[];
}

export interface VersionBackup {
  backup_id: string;
  created_at: string;
  current_branch: string;
  current_commit_hash: string;
  current_commit_message: string;
  current_tag: string;
  is_dirty: boolean;
  database_files: string[];
  config_files: string[];
  rule_files: string[];
  doc_files: string[];
  remark: string;
  backup_path: string;
}
