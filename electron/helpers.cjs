const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const APP_NAME = "经营工作台";
const DEFAULT_HOST = "127.0.0.1";
const DEFAULT_BACKEND_PORT = 8000;

function defaultDataDir({ platform = process.platform, homeDir = os.homedir(), appName = APP_NAME } = {}) {
  if (platform === "darwin") {
    return path.join(homeDir, "Library", "Application Support", appName);
  }
  if (platform === "win32") {
    return path.join(process.env.APPDATA || path.join(homeDir, "AppData", "Roaming"), appName);
  }
  return path.join(homeDir, ".local", "share", appName);
}

function defaultSuggestedDataDir({ documentsDir = path.join(os.homedir(), "Documents") } = {}) {
  return path.join(documentsDir, "工作台数据");
}

function defaultLauncherConfigPath({ platform = process.platform, homeDir = os.homedir(), appName = APP_NAME, userDataDir } = {}) {
  return path.join(userDataDir || defaultDataDir({ platform, homeDir, appName }), "launcher.json");
}

function readSavedDataDir({
  configPath = defaultLauncherConfigPath(),
  existsSync = fs.existsSync,
  readFileSync = fs.readFileSync,
} = {}) {
  if (!existsSync(configPath)) return null;
  try {
    const raw = JSON.parse(readFileSync(configPath, "utf8"));
    const saved = typeof raw.data_dir === "string" ? raw.data_dir : "";
    if (!saved || !existsSync(saved)) return null;
    return saved;
  } catch {
    return null;
  }
}

function writeSavedDataDir({
  configPath = defaultLauncherConfigPath(),
  dataDir,
  mkdirSync = fs.mkdirSync,
  writeFileSync = fs.writeFileSync,
} = {}) {
  if (!dataDir) {
    throw new Error("缺少数据保存位置。");
  }
  mkdirSync(path.dirname(configPath), { recursive: true });
  writeFileSync(configPath, JSON.stringify({ data_dir: dataDir }, null, 2));
}

function pathApiForPlatform(platform = process.platform) {
  return platform === "win32" ? path.win32 : path.posix;
}

function resolvePythonExecutable({
  rootDir,
  existsSync = fs.existsSync,
  fallback = process.env.PYTHON || "python3",
  platform = process.platform,
}) {
  const pathApi = pathApiForPlatform(platform);
  const venvPython = platform === "win32"
    ? pathApi.join(rootDir, ".venv", "Scripts", "python.exe")
    : pathApi.join(rootDir, ".venv", "bin", "python");
  return existsSync(venvPython) ? venvPython : fallback;
}

function packagedBackendPath({ resourcesPath = process.resourcesPath, platform = process.platform } = {}) {
  const pathApi = pathApiForPlatform(platform);
  const executableName = platform === "win32" ? "budget-workbench-backend.exe" : "budget-workbench-backend";
  return pathApi.join(resourcesPath, "backend-runtime", "budget-workbench-backend", executableName);
}

function buildBackendArgs({ host = DEFAULT_HOST, port = DEFAULT_BACKEND_PORT }) {
  return ["-m", "uvicorn", "backend.main:app", "--host", host, "--port", String(port)];
}

function buildPackagedBackendArgs({ host = DEFAULT_HOST, port = DEFAULT_BACKEND_PORT }) {
  return ["--host", host, "--port", String(port)];
}

function buildBackendLaunch({
  rootDir,
  host = DEFAULT_HOST,
  port = DEFAULT_BACKEND_PORT,
  resourcesPath = process.resourcesPath,
  platform = process.platform,
  existsSync = fs.existsSync,
  pythonFallback = process.env.PYTHON || "python3",
}) {
  const packaged = packagedBackendPath({ resourcesPath, platform });
  if (existsSync(packaged)) {
    const pathApi = pathApiForPlatform(platform);
    return {
      command: packaged,
      args: buildPackagedBackendArgs({ host, port }),
      cwd: pathApi.dirname(packaged),
      usesPackagedBackend: true,
    };
  }
  return {
    command: resolvePythonExecutable({ rootDir, existsSync, fallback: pythonFallback, platform }),
    args: buildBackendArgs({ host, port }),
    cwd: rootDir,
    usesPackagedBackend: false,
  };
}

function buildRuntimeEnv({ baseEnv = process.env, dataDir, backendPort, frontendDistDir }) {
  const env = {
    ...baseEnv,
    BUDGET_WORKBENCH_DATA_DIR: dataDir,
    BUDGET_WORKBENCH_BACKEND_PORT: String(backendPort),
  };
  if (frontendDistDir) {
    env.BUDGET_WORKBENCH_FRONTEND_DIST_DIR = frontendDistDir;
  }
  return env;
}

function frontendUrl({ host = DEFAULT_HOST, port = DEFAULT_BACKEND_PORT }) {
  return `http://${host}:${port}/`;
}

function readSavedUiVersion({
  configPath = defaultLauncherConfigPath(),
  existsSync = fs.existsSync,
  readFileSync = fs.readFileSync,
} = {}) {
  if (!existsSync(configPath)) return "v1";
  try {
    const raw = JSON.parse(readFileSync(configPath, "utf8"));
    return raw.ui_version === "v2" ? "v2" : "v1";
  } catch {
    return "v1";
  }
}

function writeSavedUiVersion({
  configPath = defaultLauncherConfigPath(),
  uiVersion,
  mkdirSync = fs.mkdirSync,
  existsSync = fs.existsSync,
  readFileSync = fs.readFileSync,
  writeFileSync = fs.writeFileSync,
} = {}) {
  let saved = {};
  if (existsSync(configPath)) {
    try {
      const parsed = JSON.parse(readFileSync(configPath, "utf8"));
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        saved = parsed;
      }
    } catch {
      saved = {};
    }
  }
  saved.ui_version = uiVersion === "v2" ? "v2" : "v1";
  mkdirSync(path.dirname(configPath), { recursive: true });
  writeFileSync(configPath, JSON.stringify(saved, null, 2));
}

function frontendUrlForUi({ host = DEFAULT_HOST, port = DEFAULT_BACKEND_PORT, uiVersion } = {}) {
  return uiVersion === "v2"
    ? `http://${host}:${port}/index_v2.html`
    : `http://${host}:${port}/index.html`;
}

module.exports = {
  APP_NAME,
  DEFAULT_BACKEND_PORT,
  DEFAULT_HOST,
  buildBackendArgs,
  buildBackendLaunch,
  buildRuntimeEnv,
  defaultDataDir,
  defaultLauncherConfigPath,
  defaultSuggestedDataDir,
  frontendUrl,
  pathApiForPlatform,
  packagedBackendPath,
  readSavedDataDir,
  resolvePythonExecutable,
  writeSavedDataDir,
  readSavedUiVersion,
  writeSavedUiVersion,
  frontendUrlForUi,
};
