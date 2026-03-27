const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("api", {
  request: (method, path, body) =>
    ipcRenderer.invoke("api-request", { method, path, body }),

  // Convenience methods
  get: (path) => ipcRenderer.invoke("api-request", { method: "GET", path }),
  post: (path, body) => ipcRenderer.invoke("api-request", { method: "POST", path, body }),
  put: (path, body) => ipcRenderer.invoke("api-request", { method: "PUT", path, body }),
  delete: (path) => ipcRenderer.invoke("api-request", { method: "DELETE", path }),

  // Shell integration
  openExternal: (url) => ipcRenderer.invoke("open-external", url),
});
