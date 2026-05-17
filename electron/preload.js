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
  openUploadShortsWindows: () => ipcRenderer.invoke("open-upload-shorts-windows"),
  openYouTubeUploadWindow: () => ipcRenderer.invoke("open-youtube-upload-window"),

  // Reveal a file/folder in Finder/Explorer
  showItemInFolder: (fullPath) => ipcRenderer.invoke("show-item-in-folder", fullPath),

  // File download via native save dialog
  downloadFile: (url, defaultFilename) =>
    ipcRenderer.invoke("download-file", { url, defaultFilename }),

  // Save directly to ~/Downloads/[project] {folderName}/{filename} (no dialog)
  saveToDownloads: (url, folderName, filename) =>
    ipcRenderer.invoke("save-to-downloads", { url, folderName, filename }),

  // Native folder picker
  selectFolder: (title, defaultPath) =>
    ipcRenderer.invoke("select-folder", { title, defaultPath }),
});
