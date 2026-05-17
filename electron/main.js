const { app, BrowserWindow, ipcMain, shell, dialog } = require("electron");
const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

let mainWindow;
let backendProcess;

const isDev = !app.isPackaged;
const BACKEND_PORT = 8420;
const BACKEND_URL = `http://localhost:${BACKEND_PORT}`;

function startBackend() {
  const backendDir = isDev
    ? path.join(__dirname, "..", "backend")
    : path.join(process.resourcesPath, "backend");

  backendProcess = spawn(
    "uv",
    ["run", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", String(BACKEND_PORT)],
    {
      cwd: backendDir,
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env },
    }
  );

  backendProcess.stdout.on("data", (data) => {
    console.log(`[backend] ${data}`);
  });

  backendProcess.stderr.on("data", (data) => {
    console.error(`[backend] ${data}`);
  });

  backendProcess.on("close", (code) => {
    console.log(`[backend] exited with code ${code}`);
  });
}

async function waitForBackend(retries = 30, delay = 500) {
  for (let i = 0; i < retries; i++) {
    try {
      const response = await fetch(`${BACKEND_URL}/api/health`);
      if (response.ok) return true;
    } catch {
      // Backend not ready yet
    }
    await new Promise((r) => setTimeout(r, delay));
  }
  throw new Error("Backend failed to start");
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    title: "Headless Hero",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (isDev) {
    mainWindow.loadURL("http://localhost:5173");
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "frontend", "dist", "index.html"));
  }
}

// IPC: open external URLs in the default browser
ipcMain.handle("open-external", (_event, url) => shell.openExternal(url));

// IPC: reveal a file or folder in Finder / Explorer
ipcMain.handle("show-item-in-folder", (_event, fullPath) => shell.showItemInFolder(fullPath));

// IPC: open a native folder picker and return the selected path
ipcMain.handle("select-folder", async (_event, { title, defaultPath }) => {
  const { canceled, filePaths } = await dialog.showOpenDialog(mainWindow, {
    title: title || "Select Folder",
    defaultPath: defaultPath || undefined,
    properties: ["openDirectory", "createDirectory"],
  });
  if (canceled || !filePaths.length) return { canceled: true };
  return { canceled: false, path: filePaths[0] };
});

// IPC: download a file from the backend via native save dialog
ipcMain.handle("download-file", async (_event, { url, defaultFilename }) => {
  const { canceled, filePath } = await dialog.showSaveDialog(mainWindow, {
    defaultPath: defaultFilename || "download",
  });
  if (canceled || !filePath) return { canceled: true };
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Download failed: ${response.status}`);
  const buffer = Buffer.from(await response.arrayBuffer());
  fs.writeFileSync(filePath, buffer);
  return { canceled: false, filePath };
});

// IPC: save a file directly to ~/Downloads/[project] {folderName}/{filename} (no dialog)
// If filename already exists, append an incrementing number: thumbnail.png → thumbnail2.png → thumbnail3.png
ipcMain.handle("save-to-downloads", async (_event, { url, folderName, filename }) => {
  const downloadsDir = app.getPath("downloads");
  const safeProjectName = folderName.replace(/[/\\?%*:|"<>]/g, "").trim() || "Untitled";
  const safeFolderName = `[project] ${safeProjectName}`;
  const safeFilename = path.basename(filename);
  const folder = path.join(downloadsDir, safeFolderName);
  fs.mkdirSync(folder, { recursive: true });
  const ext = path.extname(safeFilename);
  const stem = ext ? safeFilename.slice(0, -ext.length) : safeFilename;
  const initialDest = path.join(folder, safeFilename);
  let destPath = initialDest;
  let counter = 2;
  while (fs.existsSync(destPath)) {
    destPath = path.join(folder, `${stem}${counter}${ext}`);
    counter += 1;
  }
  console.log(`[save-to-downloads] requested=${safeFilename} initial=${initialDest} final=${destPath} collided=${destPath !== initialDest}`);
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Download failed: ${response.status}`);
  const buffer = Buffer.from(await response.arrayBuffer());
  fs.writeFileSync(destPath, buffer);
  return { filePath: destPath };
});

// IPC: forward API calls from renderer to backend
ipcMain.handle("api-request", async (_event, { method, path, body }) => {
  try {
    const options = {
      method,
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(20 * 60 * 1000), // 20 minutes — segmented script gen can take 7+min
    };
    if (body && method !== "GET") {
      options.body = JSON.stringify(body);
    }
    const response = await fetch(`${BACKEND_URL}${path}`, options);
    const text = await response.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text || `HTTP ${response.status}` };
    }
    return { ok: response.ok, status: response.status, data };
  } catch (error) {
    return { ok: false, status: 0, data: { error: `${error.name}: ${error.message}` } };
  }
});

app.whenReady().then(async () => {
  // Check if backend is already running (e.g. from npm run dev:backend)
  let alreadyRunning = false;
  try {
    const res = await fetch(`${BACKEND_URL}/api/health`);
    if (res.ok) alreadyRunning = true;
  } catch {
    // not running yet
  }

  if (alreadyRunning) {
    console.log("[main] Backend already running, skipping spawn");
  } else {
    startBackend();
    try {
      await waitForBackend();
      console.log("[main] Backend is ready");
    } catch (e) {
      console.error("[main] Backend failed to start:", e.message);
    }
  }
  createWindow();

  // Prevent the main window from navigating away from the app (e.g. cross-origin download links)
  mainWindow.webContents.on("will-navigate", (event, url) => {
    const appOrigins = ["http://localhost:5173", "http://localhost:8420"];
    if (!appOrigins.some((origin) => url.startsWith(origin + "/"))) {
      event.preventDefault();
    }
  });
});

app.on("window-all-closed", () => {
  if (backendProcess) {
    backendProcess.kill();
  }
  app.quit();
});

app.on("before-quit", () => {
  if (backendProcess) {
    backendProcess.kill();
  }
});
