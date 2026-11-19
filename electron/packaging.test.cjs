const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const rootDir = path.resolve(__dirname, "..");
const packageJson = require(path.join(rootDir, "package.json"));

test("package scripts include a Windows installer build that uses a CI-safe backend bundle", () => {
  assert.match(packageJson.scripts["backend:bundle:ci"], /^python -m PyInstaller /);
  assert.match(packageJson.scripts["desktop:win"], /backend:bundle:ci/);
  assert.match(packageJson.scripts["desktop:win"], /electron-builder --win nsis/);
  assert.doesNotMatch(packageJson.scripts["desktop:win"], /portable/);
  assert.match(packageJson.scripts["desktop:win"], /--publish never/);
});

test("macOS DMG build uses the local Electron runtime to avoid network download stalls", () => {
  assert.match(packageJson.scripts["desktop:dmg"], /^install-electron &&/);
  assert.match(packageJson.scripts["desktop:dmg"], /--publish never/);
  assert.match(packageJson.scripts["desktop:dmg"], /-c\.electronDist=node_modules\/electron\/dist/);
});

test("electron-builder has one Windows installer target", () => {
  assert.deepEqual(packageJson.build.win.target, ["nsis"]);
  assert.equal(packageJson.build.win.artifactName, "BusinessWorkbench-${version}-windows-${arch}.${ext}");
  assert.equal(packageJson.build.nsis.oneClick, false);
  assert.equal(packageJson.build.electronDist, undefined);
});

test("desktop package uses the product name and supplied app icons", () => {
  assert.equal(packageJson.build.productName, "经营工作台");
  assert.equal(packageJson.build.nsis.shortcutName, "经营工作台");
  assert.equal(packageJson.build.mac.icon, "electron/assets/icons/icon.icns");
  assert.equal(packageJson.build.win.icon, "electron/assets/icons/icon.ico");
  assert.ok(packageJson.build.files.includes("electron/assets/icons/**/*"));
  assert.ok(fs.existsSync(path.join(rootDir, "electron", "assets", "icons", "icon.icns")));
  assert.ok(fs.existsSync(path.join(rootDir, "electron", "assets", "icons", "icon.ico")));
});

test("GitHub Actions Windows workflow builds and uploads installer artifacts", () => {
  const workflowPath = path.join(rootDir, ".github", "workflows", "build-windows.yml");
  const workflow = fs.readFileSync(workflowPath, "utf8");

  assert.match(workflow, /runs-on: windows-latest/);
  assert.match(workflow, /npm run desktop:win/);
  assert.match(workflow, /actions\/upload-artifact@/);
  assert.match(workflow, /path: release\/\*\.exe/);
});

test("desktop app prevents duplicate windows and exposes a real quit path", () => {
  const mainPath = path.join(rootDir, "electron", "main.cjs");
  const main = fs.readFileSync(mainPath, "utf8");

  assert.match(main, /requestSingleInstanceLock\(\)/);
  assert.match(main, /app\.on\("second-instance"/);
  assert.match(main, /process\.platform === "win32"/);
  assert.match(main, /退出系统/);
});

test("settings modal has no activation tab in either UI", () => {
  for (const entry of ["App.tsx", "App_v2.tsx"]) {
    const app = fs.readFileSync(path.join(rootDir, "frontend", "src", entry), "utf8");
    assert.doesNotMatch(app, /授权激活|settingsTab === "license"/);
  }
});
