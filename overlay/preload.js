const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('angelOverlay', {
  setIgnoreMouse: (ignore) => ipcRenderer.send('set-ignore-mouse', ignore),
  minimize: () => ipcRenderer.send('minimize-overlay'),
  close: () => ipcRenderer.send('close-overlay'),
});
