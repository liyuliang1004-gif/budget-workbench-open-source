export interface DesktopDataDirResult {
  success?: boolean;
  data_dir?: string;
  restart_required?: boolean;
  message?: string;
}

export function isDesktopShell() {
  return typeof window !== "undefined" && Boolean(window.budgetDesktop);
}

export async function getDesktopDataDir() {
  return window.budgetDesktop?.getDataDir?.() ?? null;
}

export async function openDesktopDataDir() {
  if (!window.budgetDesktop?.openDataDir) {
    return { success: false, message: "当前浏览器模式不支持直接打开数据目录，请在桌面端使用。" };
  }
  try {
    return await window.budgetDesktop.openDataDir();
  } catch (error) {
    return { success: false, message: error instanceof Error ? error.message : "打开数据目录失败。" };
  }
}

export async function chooseDesktopDataDir() {
  if (!window.budgetDesktop?.chooseDataDir) {
    return { success: false, message: "当前浏览器模式不支持更换数据目录，请在桌面端使用。" };
  }
  try {
    return await window.budgetDesktop.chooseDataDir();
  } catch (error) {
    return { success: false, message: error instanceof Error ? error.message : "更换数据目录失败。" };
  }
}
