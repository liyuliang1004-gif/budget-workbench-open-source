const assert = require("node:assert/strict");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  buildBackendArgs,
  buildBackendLaunch,
  buildRuntimeEnv,
  defaultDataDir,
  defaultLauncherConfigPath,
  defaultSuggestedDataDir,
  frontendUrl,
  packagedBackendPath,
  readSavedDataDir,
  resolvePythonExecutable,
  writeSavedDataDir,
} = require("./helpers.cjs");

test("defaultDataDir uses macOS Application Support", () => {
  const result = defaultDataDir({ platform: "darwin", homeDir: "/Users/demo" });

  assert.equal(result, path.join("/Users/demo", "Library", "Application Support", "经营工作台"));
});

test("defaultSuggestedDataDir uses Documents workbench data folder", () => {
  const result = defaultSuggestedDataDir({ documentsDir: "/Users/demo/Documents" });

  assert.equal(result, path.join("/Users/demo/Documents", "工作台数据"));
});

test("defaultLauncherConfigPath stores only launcher config under Application Support", () => {
  const result = defaultLauncherConfigPath({ platform: "darwin", homeDir: "/Users/demo" });

  assert.equal(result, path.join("/Users/demo", "Library", "Application Support", "经营工作台", "launcher.json"));
});

test("saved data dir is used only when the target directory still exists", () => {
  const configPath = path.join(os.tmpdir(), "budget-workbench-launcher.json");
  const savedDir = path.join(os.tmpdir(), "budget-workbench-data");
  const readFileSync = () => JSON.stringify({ data_dir: savedDir });
  const existsSync = (candidate) => candidate === configPath || candidate === savedDir;

  assert.equal(readSavedDataDir({ configPath, existsSync, readFileSync }), savedDir);
  assert.equal(readSavedDataDir({ configPath, existsSync: (candidate) => candidate === configPath, readFileSync }), null);
});

test("writeSavedDataDir persists the selected data directory", () => {
  const writes = [];
  const dirs = [];
  const configPath = path.join("/tmp", "经营工作台", "launcher.json");

  writeSavedDataDir({
    configPath,
    dataDir: "/Users/demo/Documents/工作台数据",
    mkdirSync: (dir) => dirs.push(dir),
    writeFileSync: (file, content) => writes.push({ file, content }),
  });

  assert.deepEqual(dirs, [path.dirname(configPath)]);
  assert.equal(writes[0].file, configPath);
  assert.deepEqual(JSON.parse(writes[0].content), { data_dir: "/Users/demo/Documents/工作台数据" });
});

test("buildRuntimeEnv binds the selected data dir", () => {
  const env = buildRuntimeEnv({
    baseEnv: { PATH: "/bin" },
    dataDir: "/tmp/budget-data",
    backendPort: 8123,
    frontendDistDir: "/Applications/经营工作台.app/Contents/Resources/app/frontend/dist",
  });

  assert.equal(env.BUDGET_WORKBENCH_DATA_DIR, "/tmp/budget-data");
  assert.equal(env.BUDGET_WORKBENCH_BACKEND_PORT, "8123");
  assert.equal(env.BUDGET_WORKBENCH_FRONTEND_DIST_DIR, "/Applications/经营工作台.app/Contents/Resources/app/frontend/dist");
  assert.equal(env.PATH, "/bin");
});

test("buildBackendArgs starts uvicorn on the selected host and port", () => {
  const args = buildBackendArgs({ host: "127.0.0.1", port: 8123 });

  assert.deepEqual(args, [
    "-m",
    "uvicorn",
    "backend.main:app",
    "--host",
    "127.0.0.1",
    "--port",
    "8123",
  ]);
});

test("frontendUrl points Electron at the backend-served desktop page", () => {
  assert.equal(frontendUrl({ host: "127.0.0.1", port: 8123 }), "http://127.0.0.1:8123/");
});

test("resolvePythonExecutable prefers project venv when present", () => {
  const rootDir = "/tmp/budget-workbench-test";
  const expected = "/tmp/budget-workbench-test/.venv/bin/python";
  const result = resolvePythonExecutable({
    rootDir,
    existsSync: (candidate) => candidate === expected,
    fallback: "/usr/bin/python3",
    platform: "darwin",
  });

  assert.equal(result, expected);
});

test("resolvePythonExecutable uses Windows venv layout on Windows", () => {
  const rootDir = "C:\\Users\\demo\\budget-workbench";
  const expected = "C:\\Users\\demo\\budget-workbench\\.venv\\Scripts\\python.exe";
  const result = resolvePythonExecutable({
    rootDir,
    existsSync: (candidate) => candidate === expected,
    fallback: "python",
    platform: "win32",
  });

  assert.equal(result, expected);
});

test("packagedBackendPath points to app resources backend executable on macOS", () => {
  const result = packagedBackendPath({
    resourcesPath: "/Applications/经营工作台.app/Contents/Resources",
    platform: "darwin",
  });

  assert.equal(result, "/Applications/经营工作台.app/Contents/Resources/backend-runtime/budget-workbench-backend/budget-workbench-backend");
});

test("packagedBackendPath points to app resources backend executable on Windows", () => {
  const result = packagedBackendPath({
    resourcesPath: "C:\\Program Files\\经营工作台\\resources",
    platform: "win32",
  });

  assert.equal(result, "C:\\Program Files\\经营工作台\\resources\\backend-runtime\\budget-workbench-backend\\budget-workbench-backend.exe");
});

test("buildBackendLaunch uses packaged backend executable when available", () => {
  const packaged = "/Applications/经营工作台.app/Contents/Resources/backend-runtime/budget-workbench-backend/budget-workbench-backend";
  const launch = buildBackendLaunch({
    rootDir: "/project",
    host: "127.0.0.1",
    port: 8123,
    resourcesPath: "/Applications/经营工作台.app/Contents/Resources",
    platform: "darwin",
    existsSync: (candidate) => candidate === packaged,
  });

  assert.equal(launch.command, packaged);
  assert.deepEqual(launch.args, ["--host", "127.0.0.1", "--port", "8123"]);
  assert.equal(launch.cwd, path.dirname(packaged));
  assert.equal(launch.usesPackagedBackend, true);
});

test("buildBackendLaunch uses packaged backend executable on Windows when available", () => {
  const packaged = "C:\\Program Files\\经营工作台\\resources\\backend-runtime\\budget-workbench-backend\\budget-workbench-backend.exe";
  const launch = buildBackendLaunch({
    rootDir: "C:\\project",
    host: "127.0.0.1",
    port: 8123,
    resourcesPath: "C:\\Program Files\\经营工作台\\resources",
    platform: "win32",
    existsSync: (candidate) => candidate === packaged,
  });

  assert.equal(launch.command, packaged);
  assert.deepEqual(launch.args, ["--host", "127.0.0.1", "--port", "8123"]);
  assert.equal(launch.cwd, "C:\\Program Files\\经营工作台\\resources\\backend-runtime\\budget-workbench-backend");
  assert.equal(launch.usesPackagedBackend, true);
});

test("buildBackendLaunch falls back to project python during development", () => {
  const launch = buildBackendLaunch({
    rootDir: "/project",
    host: "127.0.0.1",
    port: 8123,
    resourcesPath: "/Applications/经营工作台.app/Contents/Resources",
    platform: "darwin",
    existsSync: () => false,
    pythonFallback: "/usr/bin/python3",
  });

  assert.equal(launch.command, "/usr/bin/python3");
  assert.deepEqual(launch.args, ["-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8123"]);
  assert.equal(launch.cwd, "/project");
  assert.equal(launch.usesPackagedBackend, false);
});
