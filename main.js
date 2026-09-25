const { app, BrowserWindow, shell, ipcMain, session } = require('electron');
const path = require('path');
const crypto = require('crypto');

let mainWindow = null;

const isDev = process.env.NODE_ENV === 'development';
const APP_URL = isDev ? 'http://localhost:3000' : 'https://app.nocodexport.app';

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
    // Use default native title bar for proper cross-platform support
    // This ensures window controls (close/minimize/maximize) are in the OS title bar
    // and not overlapping with app content
    backgroundColor: '#F5F5F7',
    icon: path.join(__dirname, '..', 'public', 'icon.png'),
    title: 'NoCodeXport',
  });

  // Load the Next.js app
  mainWindow.loadURL(APP_URL);

  // Open DevTools in development
  if (isDev) {
    mainWindow.webContents.openDevTools();
  }

  // Open external links in default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// App lifecycle
app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// IPC handlers for window.electron API
ipcMain.handle('open-external', async (_, url) => {
  await shell.openExternal(url);
});

ipcMain.handle('show-item-in-folder', async (_, filePath) => {
  shell.showItemInFolder(filePath);
});

ipcMain.handle('open-path', async (_, filePath) => {
  return await shell.openPath(filePath);
});

ipcMain.handle('get-app-path', () => {
  return app.getAppPath();
});

ipcMain.handle('get-path', (_, name) => {
  return app.getPath(name);
});

// OAuth: Start authentication in external browser with polling
ipcMain.handle('start-oauth', async (_, provider) => {
  // Generate secure random token (UUID-like)
  const token = crypto.randomBytes(32).toString('hex');

  // Build OAuth URL
  const authUrl = `${APP_URL}/api/auth/electron?provider=${encodeURIComponent(provider)}&token=${encodeURIComponent(token)}`;

  // Open in external browser
  await shell.openExternal(authUrl);

  return { token };
});

// OAuth: Poll for authentication completion
ipcMain.handle('poll-oauth', async (_, token) => {
  try {
    const response = await fetch(`${APP_URL}/api/auth/electron`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    });

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('OAuth poll error:', error);
    return { status: 'error', message: error.message };
  }
});

// OAuth: Set session cookie and reload app
ipcMain.handle('set-session-and-reload', async (_, sessionToken) => {
  if (!mainWindow) return;

  try {
    // Parse the APP_URL to get the domain
    const url = new URL(APP_URL);
    const domain = url.hostname;

    // Set the NextAuth session cookie in Electron's session
    const cookieName = isDev ? 'next-auth.session-token' : '__Secure-next-auth.session-token';

    await session.defaultSession.cookies.set({
      url: APP_URL,
      name: cookieName,
      value: sessionToken,
      path: '/',
      httpOnly: true,
      secure: !isDev,
      sameSite: 'lax',
    });

    console.log('Session cookie set, reloading app...');

    // Reload the app to pick up the session
    mainWindow.loadURL(APP_URL);

    return { success: true };
  } catch (error) {
    console.error('Failed to set session cookie:', error);
    return { success: false, error: error.message };
  }
});
