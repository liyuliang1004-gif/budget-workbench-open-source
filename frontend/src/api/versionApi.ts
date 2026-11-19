import { apiGet, apiPost } from "./client";
import type { GitVersionStatus, VersionBackup, VersionInfo } from "../types/version";

export function getVersion() {
  return apiGet<VersionInfo>("/api/version");
}

export function getVersionStatus() {
  return apiGet<GitVersionStatus>("/api/version/status");
}

export function createVersionBackup(remark: string) {
  return apiPost<VersionBackup>("/api/version/create-backup", { remark });
}

export function getVersionBackups() {
  return apiGet<VersionBackup[]>("/api/version/backups");
}

export function getVersionBackup(backupId: string) {
  return apiGet<VersionBackup>(`/api/version/backups/${backupId}`);
}
