const { contextBridge, ipcRenderer } = require('electron');

// Expose a minimal API to the renderer process via window.electron
contextBridge.exposeInMainWorld('electron', {
  // Open URL in default browser
  openExternal: (url) => ipcRenderer.invoke('open-external', url),

  // Show file in file manager
  showItemInFolder: (path) => ipcRenderer.invoke('show-item-in-folder', path),

  // Open file/folder with default app
  openPath: (path) => ipcRenderer.invoke('open-path', path),

  // Get app paths
  getAppPath: () => ipcRenderer.invoke('get-app-path'),
  getPath: (name) => ipcRenderer.invoke('get-path', name),

  // OAuth - start authentication in external browser (returns token for polling)
  startOAuth: (provider) => ipcRenderer.invoke('start-oauth', provider),

  // OAuth - poll for authentication completion
  pollOAuth: (token) => ipcRenderer.invoke('poll-oauth', token),

  // OAuth - set session cookie and reload app
  setSessionAndReload: (sessionToken) => ipcRenderer.invoke('set-session-and-reload', sessionToken),

  // Platform info
  platform: process.platform,
  isElectron: true,
});
