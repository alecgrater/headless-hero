const { app, BrowserWindow, ipcMain, shell } = require("electron");
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
    title: "YouTube AI Machine",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (isDev) {
    mainWindow.loadURL("http://localhost:5173");
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "frontend", "dist", "index.html"));
  }
}

// IPC: open external URLs in the default browser
ipcMain.handle("open-external", (_event, url) => shell.openExternal(url));

// IPC: forward API calls from renderer to backend
ipcMain.handle("api-request", async (_event, { method, path, body }) => {
  try {
    const options = {
      method,
      headers: { "Content-Type": "application/json" },
    };
    if (body && method !== "GET") {
      options.body = JSON.stringify(body);
    }
    const response = await fetch(`${BACKEND_URL}${path}`, options);
    const data = await response.json();
    return { ok: response.ok, status: response.status, data };
  } catch (error) {
    return { ok: false, status: 0, data: { error: error.message } };
  }
});

app.whenReady().then(async () => {
  startBackend();
  try {
    await waitForBackend();
    console.log("[main] Backend is ready");
  } catch (e) {
    console.error("[main] Backend failed to start:", e.message);
  }
  createWindow();
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
