const { app, BrowserWindow, ipcMain, shell, dialog, screen } = require("electron");
const fs = require("fs");
const path = require("path");
const { execFile, spawn } = require("child_process");

let mainWindow;
let backendProcess;

const isDev = !app.isPackaged;
const DEBUG = !!process.env.HH_DEBUG;
const debug = (...args) => {
  if (DEBUG) console.log(...args);
};
const BACKEND_PORT = 8420;
const FRONTEND_PORT = 5173;
const BACKEND_URL = `http://localhost:${BACKEND_PORT}`;
const CHROME_APP_NAME = "Google Chrome";
const UPLOAD_SHORTS_URLS = [
  "https://www.instagram.com/watchunranked/",
  "https://www.tiktok.com/tiktokstudio",
  "https://studio.youtube.com/channel/UCBLhENZIlxFAQ59owrMSauw/videos/upload?d=ud&filter=%5B%5D&sort=%7B%22columnType%22%3A%22date%22%2C%22sortOrder%22%3A%22DESCENDING%22%7D",
];
const YOUTUBE_LONGFORM_UPLOAD_URL = "https://studio.youtube.com/channel/UCBLhENZIlxFAQ59owrMSauw/videos/upload?d=ud&filter=%5B%5D&sort=%7B%22columnType%22%3A%22date%22%2C%22sortOrder%22%3A%22DESCENDING%22%7D";
const UPLOAD_SHORTS_WINDOW_SIZE = { width: 684, height: 1203 };

function isAppUrl(url) {
  const appOrigins = ["http://localhost:5173", "http://localhost:8420"];
  return appOrigins.some((origin) => url.startsWith(origin + "/"));
}

function openExternalUrl(url) {
  if (process.platform !== "darwin") {
    return shell.openExternal(url);
  }

  return new Promise((resolve, reject) => {
    let settled = false;
    const settle = (fn) => {
      if (settled) return;
      settled = true;
      fn();
    };
    const child = spawn("open", ["-a", CHROME_APP_NAME, url], { stdio: "ignore" });
    child.once("error", (error) => settle(() => reject(error)));
    child.once("exit", (code) => {
      settle(
        code === 0
          ? resolve
          : () => reject(new Error(`Failed to open ${url} in ${CHROME_APP_NAME}`)),
      );
    });
  });
}

function openExternalUrlFromEvent(url) {
  openExternalUrl(url).catch((error) => {
    console.error(`[main] Failed to open external URL in ${CHROME_APP_NAME}:`, error);
  });
}

function appleScriptString(value) {
  return `"${String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
}

function runProcess(command, args) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const settle = (fn) => {
      if (settled) return;
      settled = true;
      fn();
    };
    const child = spawn(command, args, { stdio: "ignore" });
    child.once("error", (error) => settle(() => reject(error)));
    child.once("exit", (code) => {
      settle(
        code === 0
          ? resolve
          : () => reject(new Error(`${command} exited with code ${code}`)),
      );
    });
  });
}

function getUploadShortsWindowBounds() {
  const displays = screen.getAllDisplays().sort((a, b) => {
    if (a.bounds.x !== b.bounds.x) return a.bounds.x - b.bounds.x;
    return a.bounds.y - b.bounds.y;
  });
  const leftDisplay = displays[0] ?? screen.getPrimaryDisplay();
  const middleDisplay = displays[1] ?? leftDisplay;
  const { width, height } = UPLOAD_SHORTS_WINDOW_SIZE;

  const clampHeight = (display) => Math.min(height, display.workArea.height);
  const top = (display) => display.workArea.y;

  return [
    {
      x: leftDisplay.workArea.x,
      y: top(leftDisplay),
      width,
      height: clampHeight(leftDisplay),
    },
    {
      x: leftDisplay.workArea.x + Math.max(leftDisplay.workArea.width - width, 0),
      y: top(leftDisplay),
      width,
      height: clampHeight(leftDisplay),
    },
    {
      x: middleDisplay.workArea.x,
      y: top(middleDisplay),
      width,
      height: clampHeight(middleDisplay),
    },
  ];
}

function openUploadShortsWindows() {
  if (process.platform !== "darwin") {
    return Promise.all(UPLOAD_SHORTS_URLS.map((url) => shell.openExternal(url))).then(() => undefined);
  }

  const bounds = getUploadShortsWindowBounds();

  return UPLOAD_SHORTS_URLS.reduce((chain, url, index) => {
    return chain.then(async () => {
      const { x, y, width, height } = bounds[index];
      await runProcess("osascript", [
        "-e",
        [
          `tell application ${appleScriptString(CHROME_APP_NAME)}`,
          "activate",
          "set uploadWindow to make new window",
          `set URL of active tab of uploadWindow to ${appleScriptString(url)}`,
          `set bounds of uploadWindow to {${x}, ${y}, ${x + width}, ${y + height}}`,
          "end tell",
        ].join("\n"),
      ]);
    });
  }, Promise.resolve());
}

function openUploadWindow(url) {
  if (process.platform !== "darwin") {
    return shell.openExternal(url);
  }

  const [bounds] = getUploadShortsWindowBounds();
  const { x, y, width, height } = bounds;
  return runProcess("osascript", [
    "-e",
    [
      `tell application ${appleScriptString(CHROME_APP_NAME)}`,
      "activate",
      "set uploadWindow to make new window",
      `set URL of active tab of uploadWindow to ${appleScriptString(url)}`,
      `set bounds of uploadWindow to {${x}, ${y}, ${x + width}, ${y + height}}`,
      "end tell",
    ].join("\n"),
  ]);
}

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
    debug(`[backend] ${data}`);
  });

  backendProcess.stderr.on("data", (data) => {
    console.error(`[backend] ${data}`);
  });

  backendProcess.on("close", (code) => {
    if (code && code !== 0) {
      console.error(`[backend] exited with code ${code}`);
    } else {
      debug(`[backend] exited with code ${code}`);
    }
  });
}

function execFileLines(command, args) {
  return new Promise((resolve) => {
    execFile(command, args, (error, stdout) => {
      if (error) {
        resolve([]);
        return;
      }
      resolve(stdout.split(/\r?\n/).map((line) => line.trim()).filter(Boolean));
    });
  });
}

function parsePid(value) {
  const pid = Number.parseInt(value, 10);
  return Number.isInteger(pid) && pid > 0 && pid !== process.pid ? pid : null;
}

async function listListeningPids(port) {
  if (process.platform === "win32") return [];
  const lines = await execFileLines("lsof", ["-ti", `tcp:${port}`]);
  return [...new Set(lines.map(parsePid).filter(Boolean))];
}

async function getProcessInfo(pid) {
  const lines = await execFileLines("ps", ["-o", "ppid=", "-o", "command=", "-p", String(pid)]);
  const [line] = lines;
  if (!line) return null;
  const match = line.match(/^(\d+)\s+(.+)$/);
  if (!match) return null;
  const ppid = parsePid(match[1]);
  return { pid, ppid, command: match[2] };
}

async function listChildPids(pid) {
  if (process.platform === "win32") return [];
  const lines = await execFileLines("pgrep", ["-P", String(pid)]);
  return lines.map(parsePid).filter(Boolean);
}

function isYoloDevServerCommand(command) {
  return (
    command.includes("npm run dev:backend") ||
    command.includes("npm run dev:frontend") ||
    command.includes("uv run uvicorn api.main:app") ||
    command.includes("uvicorn api.main:app") ||
    command.includes("vite --host") ||
    /(^|\s)vite(\s|$)/.test(command)
  );
}

async function collectDescendantPids(pid, collected = new Set()) {
  for (const childPid of await listChildPids(pid)) {
    if (collected.has(childPid)) continue;
    collected.add(childPid);
    await collectDescendantPids(childPid, collected);
  }
  return collected;
}

async function collectYoloProcessPids(seedPids) {
  const pids = new Set(seedPids);

  for (const pid of seedPids) {
    for (const childPid of await collectDescendantPids(pid)) {
      pids.add(childPid);
    }

    let currentPid = pid;
    while (currentPid) {
      const info = await getProcessInfo(currentPid);
      if (!info?.ppid) break;

      const parentInfo = await getProcessInfo(info.ppid);
      if (!parentInfo || !isYoloDevServerCommand(parentInfo.command)) break;

      pids.add(parentInfo.pid);
      for (const childPid of await collectDescendantPids(parentInfo.pid)) {
        pids.add(childPid);
      }
      currentPid = parentInfo.pid;
    }
  }

  return [...pids].filter((pid) => pid !== process.pid);
}

function terminatePids(pids) {
  for (const pid of pids) {
    try {
      process.kill(pid, "SIGTERM");
    } catch {
      // Process already exited.
    }
  }
  setTimeout(() => {
    for (const pid of pids) {
      try {
        process.kill(pid, "SIGKILL");
      } catch {
        // Process exited after SIGTERM.
      }
    }
  }, 1500).unref();
}

async function stopYoloProcesses() {
  try {
    await fetch(`${BACKEND_URL}/dev/api/kill-all`, {
      method: "POST",
      signal: AbortSignal.timeout(3000),
    });
  } catch (error) {
    console.warn("[main] Backend kill-all request failed:", error.message);
  }

  const listeningPids = isDev
    ? await Promise.all([listListeningPids(FRONTEND_PORT), listListeningPids(BACKEND_PORT)])
    : [[]];
  const pids = await collectYoloProcessPids([...new Set(listeningPids.flat())]);
  terminatePids(pids);

  if (backendProcess) {
    backendProcess.kill();
    backendProcess = null;
  }

  setTimeout(() => app.quit(), 100).unref();
  return { stopped: true, processes: pids.length };
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

const WINDOW_MIN_SIZE = { width: 1000, height: 700 };

// Persisted window bounds live next to the app's other user data so the window
// reopens at whatever size/position it was last left at (see createWindow).
function getWindowStateFile() {
  return path.join(app.getPath("userData"), "window-state.json");
}

function loadWindowState() {
  try {
    const state = JSON.parse(fs.readFileSync(getWindowStateFile(), "utf8"));
    if (
      state &&
      ["x", "y", "width", "height"].every((key) => typeof state[key] === "number")
    ) {
      return state;
    }
  } catch {
    // No saved state yet (first launch) or unreadable — caller falls back.
  }
  return null;
}

// Guard against restoring onto a display that no longer exists (e.g. an external
// monitor was unplugged), which would open the window off-screen.
function boundsVisibleOnSomeDisplay(bounds) {
  return screen.getAllDisplays().some((display) => {
    const area = display.workArea;
    const interWidth =
      Math.min(bounds.x + bounds.width, area.x + area.width) - Math.max(bounds.x, area.x);
    const interHeight =
      Math.min(bounds.y + bounds.height, area.y + area.height) - Math.max(bounds.y, area.y);
    return interWidth > 200 && interHeight > 100;
  });
}

// First-launch default: fill the primary display's work area (large, like a
// maximized window, but still a normal resizable/movable window).
function getDefaultWindowBounds() {
  const { workArea } = screen.getPrimaryDisplay();
  return { x: workArea.x, y: workArea.y, width: workArea.width, height: workArea.height };
}

function saveWindowState(win) {
  if (!win || win.isDestroyed()) return;
  try {
    // getNormalBounds() returns the un-maximized size so a maximized window
    // still restores to a sensible size when later un-maximized.
    const bounds = win.getNormalBounds();
    fs.writeFileSync(
      getWindowStateFile(),
      JSON.stringify({ ...bounds, isMaximized: win.isMaximized() }),
    );
  } catch (err) {
    debug("Failed to save window state", err);
  }
}

function persistWindowState(win) {
  let timer = null;
  const scheduleSave = () => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => saveWindowState(win), 400);
  };
  win.on("resize", scheduleSave);
  win.on("move", scheduleSave);
  win.on("maximize", scheduleSave);
  win.on("unmaximize", scheduleSave);
  win.on("close", () => {
    if (timer) clearTimeout(timer);
    saveWindowState(win);
  });
}

function createWindow() {
  const saved = loadWindowState();
  const useSaved = saved && boundsVisibleOnSomeDisplay(saved);
  const bounds = useSaved
    ? { x: saved.x, y: saved.y, width: saved.width, height: saved.height }
    : getDefaultWindowBounds();

  mainWindow = new BrowserWindow({
    ...bounds,
    minWidth: WINDOW_MIN_SIZE.width,
    minHeight: WINDOW_MIN_SIZE.height,
    title: "Headless Hero",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (useSaved && saved.isMaximized) {
    mainWindow.maximize();
  }

  persistWindowState(mainWindow);

  if (isDev) {
    mainWindow.loadURL("http://localhost:5173");
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "frontend", "dist", "index.html"));
  }
}

// IPC: open external URLs in Chrome, regardless of the system default browser.
ipcMain.handle("open-external", (_event, url) => openExternalUrl(url));

// IPC: open the short-form upload destinations in positioned Chrome windows.
ipcMain.handle("open-upload-shorts-windows", () => openUploadShortsWindows());

// IPC: open the long-form upload destination in a positioned Chrome window.
ipcMain.handle("open-youtube-upload-window", () => openUploadWindow(YOUTUBE_LONGFORM_UPLOAD_URL));

// IPC: emergency stop for YOLO mode. Cancels backend jobs, kills dev servers, and quits Electron.
ipcMain.handle("stop-yolo-processes", () => stopYoloProcesses());

// IPC: reveal a file or folder in Finder / Explorer
ipcMain.handle("show-item-in-folder", (_event, fullPath) => shell.showItemInFolder(fullPath));

// IPC: open a file or folder with the operating system default app
ipcMain.handle("open-path", async (_event, fullPath) => {
  const error = await shell.openPath(fullPath);
  if (error) throw new Error(error);
});

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
  debug(`[save-to-downloads] requested=${safeFilename} initial=${initialDest} final=${destPath} collided=${destPath !== initialDest}`);
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
    debug("[main] Backend already running, skipping spawn");
  } else {
    startBackend();
    try {
      await waitForBackend();
      debug("[main] Backend is ready");
    } catch (e) {
      console.error("[main] Backend failed to start:", e.message);
    }
  }
  createWindow();

  // Prevent the main window from navigating away from the app (e.g. cross-origin download links)
  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (!isAppUrl(url)) {
      event.preventDefault();
      openExternalUrlFromEvent(url);
    }
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (!isAppUrl(url)) {
      openExternalUrlFromEvent(url);
    }
    return { action: "deny" };
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
