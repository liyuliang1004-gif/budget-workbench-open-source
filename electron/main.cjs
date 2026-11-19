const { app, BrowserWindow, Menu, clipboard, dialog, ipcMain, shell } = require("electron");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const net = require("node:net");
const path = require("node:path");

const {
  APP_NAME,
  DEFAULT_BACKEND_PORT,
  DEFAULT_HOST,
  buildBackendLaunch,
  buildRuntimeEnv,
  defaultLauncherConfigPath,
  defaultSuggestedDataDir,
  frontendUrl,
  frontendUrlForUi,
  readSavedDataDir,
  readSavedUiVersion,
  writeSavedDataDir,
  writeSavedUiVersion,
} = require("./helpers.cjs");

app.commandLine.appendSwitch("lang", "zh-CN");

const rootDir = path.resolve(__dirname, "..");
const frontendDistDir = path.join(rootDir, "frontend", "dist");
let dataDir = null;
let uiVersion = "v1";
let backendPort = null;
let backendProcess = null;
let mainWindow = null;
let isQuitting = false;

const singleInstanceLock = app.requestSingleInstanceLock();
if (!singleInstanceLock) {
  app.quit();
}

function portIsFree(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.once("listening", () => {
      server.close(() => resolve(true));
    });
    server.listen(port, DEFAULT_HOST);
  });
}

async function findFreePort(startPort) {
  for (let port = startPort; port < startPort + 100; port += 1) {
    if (await portIsFree(port)) return port;
  }
  throw new Error(`未找到可用端口：${startPort}-${startPort + 99}`);
}

function waitForBackend(url, timeoutMs = 20000) {
  const healthUrl = `${url.replace(/\/$/, "")}/api/health`;
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    async function check() {
      try {
        const response = await fetch(healthUrl);
        if (response.ok) {
          resolve();
          return;
        }
      } catch {
        // Backend is still starting.
      }
      if (Date.now() > deadline) {
        reject(new Error("后端服务启动超时。"));
        return;
      }
      setTimeout(check, 300);
    }
    check();
  });
}

function ensureFrontendBuilt() {
  const indexPath = path.join(frontendDistDir, "index.html");
  if (!fs.existsSync(indexPath)) {
    throw new Error("前端页面尚未构建，请先运行 npm run build。");
  }
}

async function promptForDataDir({ reason } = {}) {
  if (reason) {
    await dialog.showMessageBox({
      type: "warning",
      title: "选择数据保存位置",
      message: reason,
      buttons: ["重新选择"],
      defaultId: 0,
    });
  }
  const result = await dialog.showOpenDialog({
    title: "选择数据保存位置",
    message: "请选择经营工作台的数据保存位置。上传文件、数据库、导出报表、配置和备份都会保存在这里。",
    buttonLabel: "使用此文件夹",
    defaultPath: defaultSuggestedDataDir({ documentsDir: app.getPath("documents") }),
    properties: ["openDirectory", "createDirectory"],
  });
  if (result.canceled || result.filePaths.length === 0) {
    throw new Error("未选择数据保存位置，经营工作台已退出。");
  }
  return result.filePaths[0];
}

async function resolveDataDirAtStartup() {
  if (process.env.BUDGET_WORKBENCH_DATA_DIR) {
    return process.env.BUDGET_WORKBENCH_DATA_DIR;
  }
  const configPath = defaultLauncherConfigPath({ userDataDir: app.getPath("userData") });
  const saved = readSavedDataDir({ configPath });
  if (saved) return saved;
  const configExists = fs.existsSync(configPath);
  const selected = await promptForDataDir({
    reason: configExists ? "上次选择的数据目录不存在或无法访问，请重新选择数据保存位置。" : undefined,
  });
  fs.mkdirSync(selected, { recursive: true });
  writeSavedDataDir({ configPath, dataDir: selected });
  return selected;
}

async function startBackend() {
  ensureFrontendBuilt();
  if (!dataDir) {
    throw new Error("未选择数据保存位置。");
  }
  fs.mkdirSync(dataDir, { recursive: true });
  backendPort = await findFreePort(Number(process.env.BUDGET_WORKBENCH_BACKEND_PORT || DEFAULT_BACKEND_PORT));
  const env = buildRuntimeEnv({ baseEnv: process.env, dataDir, backendPort, frontendDistDir });
  const launch = buildBackendLaunch({ rootDir, host: DEFAULT_HOST, port: backendPort });
  backendProcess = spawn(launch.command, launch.args, {
    cwd: launch.cwd,
    env,
    stdio: "ignore",
  });
  backendProcess.once("exit", (code) => {
    if (code !== 0 && mainWindow) {
      dialog.showErrorBox(APP_NAME, "后台服务已退出，请重新打开软件。");
    }
  });
  const url = frontendUrl({ host: DEFAULT_HOST, port: backendPort });
  await waitForBackend(url);
  createMenu();
  return url;
}

function createMenu() {
  const template = [
    {
      label: APP_NAME,
      submenu: [
        { label: "打开数据目录", click: () => shell.openPath(dataDir) },
        {
          label: "界面样式",
          submenu: [
            {
              label: "经典版 UI（V1）",
              type: "radio",
              checked: uiVersion === "v1",
              click: () => switchUiVersion("v1").catch((error) => {
                dialog.showErrorBox(APP_NAME, error instanceof Error ? error.message : "界面切换失败。");
              }),
            },
            {
              label: "新版 UI（V2 · 清新表格）",
              type: "radio",
              checked: uiVersion === "v2",
              click: () => switchUiVersion("v2").catch((error) => {
                dialog.showErrorBox(APP_NAME, error instanceof Error ? error.message : "界面切换失败。");
              }),
            },
          ],
        },
        {
          label: "只读数据接口",
          submenu: [
            {
              label: "打开 API 文档",
              enabled: backendPort !== null,
              click: () => shell.openExternal(`http://${DEFAULT_HOST}:${backendPort}/docs`),
            },
            {
              label: "复制 API 地址",
              enabled: backendPort !== null,
              click: () => clipboard.writeText(`http://${DEFAULT_HOST}:${backendPort}/api/read-only`),
            },
            {
              label: "复制 MCP 地址",
              enabled: backendPort !== null,
              click: () => clipboard.writeText(`http://${DEFAULT_HOST}:${backendPort}/mcp`),
            },
          ],
        },
        { type: "separator" },
        { role: "reload", label: "刷新页面" },
        { role: "togglefullscreen", label: "切换全屏" },
        { type: "separator" },
        { role: "quit", label: "退出系统" },
      ],
    },
    {
      label: "编辑",
      submenu: [
        { role: "cut", label: "剪切" },
        { role: "copy", label: "复制" },
        { role: "paste", label: "粘贴" },
        { type: "separator" },
        { role: "selectAll", label: "全选" },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

async function switchUiVersion(version) {
  const nextUiVersion = version === "v2" ? "v2" : "v1";
  writeSavedUiVersion({
    configPath: defaultLauncherConfigPath({ userDataDir: app.getPath("userData") }),
    uiVersion: nextUiVersion,
  });
  uiVersion = nextUiVersion;
  createMenu();
  if (mainWindow && backendPort !== null) {
    await mainWindow.loadURL(frontendUrlForUi({
      host: DEFAULT_HOST,
      port: backendPort,
      uiVersion,
    }));
  }
  return { success: true, ui_version: uiVersion };
}

function showMainWindow() {
  if (!mainWindow) return;
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show();
  mainWindow.focus();
}

function registerDesktopIpc() {
  ipcMain.handle("data-dir:get", () => ({ data_dir: dataDir }));
  ipcMain.handle("data-dir:open", async () => {
    if (!dataDir) return { success: false, message: "未选择数据目录。" };
    fs.mkdirSync(dataDir, { recursive: true });
    const error = await shell.openPath(dataDir);
    return { success: !error, message: error || "已打开数据目录。", data_dir: dataDir };
  });
  ipcMain.handle("data-dir:choose", async () => {
    const selected = await promptForDataDir();
    fs.mkdirSync(selected, { recursive: true });
    writeSavedDataDir({ configPath: defaultLauncherConfigPath({ userDataDir: app.getPath("userData") }), dataDir: selected });
    return {
      success: true,
      data_dir: selected,
      restart_required: true,
      message: "新的数据目录已保存，重启软件后生效。",
    };
  });
  ipcMain.handle("ui-version:get", () => ({ ui_version: uiVersion }));
  ipcMain.handle("ui-version:set", (_event, version) => switchUiVersion(version));
}

async function createWindow() {
  await startBackend();
  mainWindow = new BrowserWindow({
    title: APP_NAME,
    width: 1440,
    height: 920,
    minWidth: 1180,
    minHeight: 760,
    backgroundColor: "#f3f7fc",
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: path.join(__dirname, "preload.cjs"),
    },
  });
  mainWindow.once("ready-to-show", () => mainWindow.show());
  mainWindow.on("close", (event) => {
    if (isQuitting) return;
    if (process.platform === "win32") {
      isQuitting = true;
      return;
    }
    event.preventDefault();
    mainWindow.minimize();
  });
  await mainWindow.webContents.session.clearCache();
  await mainWindow.loadURL(frontendUrlForUi({
    host: DEFAULT_HOST,
    port: backendPort,
    uiVersion,
  }));
}

function stopBackend() {
  if (!backendProcess || backendProcess.killed) return;
  backendProcess.kill();
  backendProcess = null;
}

app.whenReady().then(async () => {
  app.setName(APP_NAME);
  try {
    dataDir = await resolveDataDirAtStartup();
    uiVersion = readSavedUiVersion({
      configPath: defaultLauncherConfigPath({ userDataDir: app.getPath("userData") }),
    });
    registerDesktopIpc();
    createMenu();
    await createWindow();
  } catch (error) {
    dialog.showErrorBox(APP_NAME, error instanceof Error ? error.message : "桌面端启动失败。");
    app.quit();
  }
});

app.on("window-all-closed", () => {
  if (isQuitting) app.quit();
});

app.on("second-instance", () => {
  showMainWindow();
});

app.on("before-quit", () => {
  isQuitting = true;
  stopBackend();
});

app.on("activate", () => {
  if (mainWindow) {
    showMainWindow();
    return;
  }
  createWindow().catch((error) => {
    dialog.showErrorBox(APP_NAME, error instanceof Error ? error.message : "桌面端启动失败。");
  });
});
