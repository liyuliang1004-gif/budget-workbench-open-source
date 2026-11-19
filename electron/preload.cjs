const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("budgetDesktop", {
  getDataDir: () => ipcRenderer.invoke("data-dir:get"),
  openDataDir: () => ipcRenderer.invoke("data-dir:open"),
  chooseDataDir: () => ipcRenderer.invoke("data-dir:choose"),
  getUiVersion: () => ipcRenderer.invoke("ui-version:get"),
  setUiVersion: (v) => ipcRenderer.invoke("ui-version:set", v),
});
