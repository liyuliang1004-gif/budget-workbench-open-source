import type { DesktopDataDirResult } from "../api/desktopApi";

declare global {
  interface Window {
    budgetDesktop?: {
      getDataDir: () => Promise<DesktopDataDirResult>;
      openDataDir: () => Promise<DesktopDataDirResult>;
      chooseDataDir: () => Promise<DesktopDataDirResult>;
    };
  }
}

export {};
