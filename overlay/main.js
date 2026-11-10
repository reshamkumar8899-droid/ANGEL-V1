const { app, BrowserWindow, ipcMain, screen } = require('electron');
const path = require('path');

// Disable GPU compositing issues on some machines
app.commandLine.appendSwitch('disable-gpu-compositing');
app.commandLine.appendSwitch('enable-transparent-visuals');

let win;

function createWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;

  win = new BrowserWindow({
    width: width,
    height: height,
    x: 0,
    y: 0,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    hasShadow: false,
    resizable: false,
    skipTaskbar: false,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Load the Angel HUD with overlay mode flag
  win.loadURL('http://127.0.0.1:7771/?overlay=true');

  // Start with click-through enabled on transparent areas
  win.setIgnoreMouseEvents(true, { forward: true });

  // Remove menu bar
  win.setMenu(null);

  // Prevent the window from being closed accidentally
  win.on('close', (e) => {
    // Allow close
  });

  win.on('closed', () => {
    win = null;
  });
}

// IPC: Toggle click-through based on mouse position over opaque content
ipcMain.on('set-ignore-mouse', (event, ignore) => {
  if (win) {
    if (ignore) {
      win.setIgnoreMouseEvents(true, { forward: true });
    } else {
      win.setIgnoreMouseEvents(false);
    }
  }
});

// IPC: Minimize to tray / restore
ipcMain.on('minimize-overlay', () => {
  if (win) win.minimize();
});

ipcMain.on('close-overlay', () => {
  if (win) win.close();
  app.quit();
});

app.whenReady().then(() => {
  // Small delay for transparent visuals to initialize on Windows
  setTimeout(createWindow, 300);
});

app.on('window-all-closed', () => {
  app.quit();
});
