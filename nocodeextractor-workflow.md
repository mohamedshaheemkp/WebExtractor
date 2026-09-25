This gives us a much clearer picture. The important finding is that **NoCodeXport’s Electron layer is surprisingly thin**.

## 1. What `package.json` tells us

NoCodeXport is essentially a **Next.js web application packaged inside Electron**, rather than an Electron app where the extraction engine lives in `main.js`.

The key stack is:

| Layer                | Confirmed technology     |
| -------------------- | ------------------------ |
| Desktop shell        | Electron `39.3.0`        |
| Desktop packaging    | Electron Forge `7.11.1`  |
| UI / renderer        | Next.js `16.0.10`        |
| UI framework         | React `19.2.3`           |
| Styling              | Tailwind CSS 3 + PostCSS |
| Database             | Drizzle ORM + PostgreSQL |
| Authentication       | NextAuth / Auth.js       |
| Image processing     | Sharp `0.34.5`           |
| SVG/raster rendering | `@resvg/resvg-js`        |
| Icons                | Lucide React             |

Most importantly:

```json
"main": "electron/main.js"
```

and:

```json
"dev": "next dev"
```

So the architecture is strongly pointing toward:

```text
                    NoCodeXport
                         │
             ┌───────────┴───────────┐
             │                       │
        Electron shell          Next.js app
             │                       │
       electron/main.js        React UI
             │                       │
       electron/preload.js      likely API routes
             │                       │
             └──────── IPC ──────────┘
```

The `package.json` also confirms that **Next.js is a major application dependency**, not merely something accidentally bundled.

---

# 2. `electron/main.js` is NOT the extraction engine

This is the most important discovery.

`main.js` does **not** contain:

* DOM extraction
* CSS extraction
* website crawling
* browser automation
* asset downloading
* HTML reconstruction
* screenshot analysis
* component inference
* code generation

Instead, it primarily does four things.

### A. Creates the Electron window

```js
mainWindow = new BrowserWindow({
  width: 1200,
  height: 800,
  ...
  webPreferences: {
    nodeIntegration: false,
    contextIsolation: true,
    preload: path.join(__dirname, 'preload.js'),
  }
});
```

This is a fairly standard secure Electron configuration.

Notably:

```text
nodeIntegration: false
contextIsolation: true
```

So the renderer doesn't directly get Node.js access.

---

### B. Loads the web application

This line is extremely revealing:

```js
const APP_URL = isDev
  ? 'http://localhost:3000'
  : 'https://app.nocodexport.app';
```

Then:

```js
mainWindow.loadURL(APP_URL);
```

Therefore the production desktop application is loading:

```text
https://app.nocodexport.app
```

inside Electron.

That means the installed desktop executable isn't necessarily carrying the complete UI/application locally.

Conceptually:

```text
NoCodeXport.exe
      │
      ▼
Electron
      │
      ▼
BrowserWindow
      │
      ▼
https://app.nocodexport.app
```

This is a very significant architectural difference from what we initially might have assumed.

---

# 3. What `preload.js` actually does

`preload.js` exposes a very small bridge:

```js
contextBridge.exposeInMainWorld('electron', {
```

The renderer gets:

```text
window.electron
```

with APIs for:

```text
openExternal()
showItemInFolder()
openPath()

getAppPath()
getPath()

startOAuth()
pollOAuth()
setSessionAndReload()

platform
isElectron
```

There is **no extraction API** exposed here.

For example, there is no:

```text
captureWebsite()
extractDOM()
downloadAssets()
extractCSS()
generateProject()
crawlSite()
exportSite()
```

So again, the actual website-export functionality is almost certainly elsewhere.

---

# 4. The IPC architecture

The IPC channels are:

```text
open-external
show-item-in-folder
open-path
get-app-path
get-path

start-oauth
poll-oauth
set-session-and-reload
```

And they're mainly desktop utility/authentication operations.

For example:

```text
Next.js renderer
      │
      │ window.electron.openExternal()
      ▼
preload.js
      │
      │ ipcRenderer.invoke()
      ▼
main.js
      │
      ▼
Electron shell.openExternal()
```

That's a standard Electron bridge.

---

# 5. OAuth is handled unusually cleanly

Their authentication architecture appears to be:

```text
Electron app
     │
     ▼
start-oauth
     │
     ▼
Generate random token
     │
     ▼
Open external browser
     │
     ▼
app.nocodexport.app/api/auth/electron
     │
     ▼
User authenticates
     │
     ▼
Electron polls token
     │
     ▼
Receives session token
     │
     ▼
Sets NextAuth cookie
     │
     ▼
Reloads Next.js application
```

The random token is generated locally:

```js
crypto.randomBytes(32).toString('hex')
```

That's 256 bits of random data.

Again, though, **this has nothing to do with the website extraction engine itself**.

---

# 6. Where the interesting code probably is

This is where we should go next.

The manifest showed a relatively small Electron directory:

```text
electron/
    electron.d.ts
    main.js
    preload.js
```

That strongly suggests we should **stop digging into Electron** for the extractor.

Instead, we need to locate the Next.js application's actual source.

The interesting files/directories should be things such as:

```text
app/
pages/
components/
lib/
server/
api/
actions/
utils/
```

and potentially:

```text
app/api/...
```

Because the desktop shell points at:

```text
https://app.nocodexport.app
```

there is a good chance the actual extraction workflow is implemented in the Next.js application/backend.

---

# 7. One particularly important clue: `sharp`

They explicitly have:

```json
"sharp": "^0.34.5"
```

and:

```json
"@resvg/resvg-js": "^2.6.2"
```

These are interesting for a website exporter because they can be used for image processing/rendering.

But **we cannot conclude they are used by the extractor merely because they are dependencies**.

We need to find imports such as:

```js
require('sharp')
```

or:

```js
import sharp from 'sharp'
```

and:

```js
require('@resvg/resvg-js')
```

or:

```js
import ... from '@resvg/resvg-js'
```

That will tell us whether they're actually part of the extraction pipeline.

---

# 8. Another major clue: there is NO Playwright/Puppeteer dependency

From the `package.json` you provided, I don't see:

```text
playwright
puppeteer
@playwright/test
```

as direct dependencies.

That doesn't prove they don't use browser automation — it could be:

* remotely hosted
* dynamically installed
* another service
* a dependency of something else
* implemented through browser APIs
* hidden in server infrastructure

But it means we **shouldn't assume NoCodeXport uses Playwright in its packaged application**.

This is especially relevant to your WebExtractor because your architecture currently revolves heavily around browser capture/evidence.

---

# 9. What I think we should investigate next

Don't change your WebExtractor yet.

First, let's map NoCodeXport's actual pipeline.

### Step 1 — Find the application source

From the extracted NoCodeXport directory, run:

```powershell
Get-ChildItem "$out" -Directory
```

Then:

```powershell
Get-ChildItem "$out" -Recurse -Directory |
Where-Object {
    $_.Name -notmatch 'node_modules|\.git|\.next'
} |
Select-Object FullName
```

We're looking for directories such as:

```text
app
pages
components
lib
server
api
src
```

---

### Step 2 — Search for extractor terminology

This is more valuable than blindly reading hundreds of files.

Run:

```powershell
Get-ChildItem "$out" -Recurse -File |
Where-Object {
    $_.FullName -notmatch 'node_modules'
} |
Select-String -Pattern `
"extract|export|crawl|scrape|website|framer|dom|asset|screenshot|html|css|capture|download|generate" `
-CaseSensitive:$false |
Select-Object Path, LineNumber, Line
```

That should expose the application's actual functionality.

---

### Step 3 — Specifically search for browser technology

```powershell
Get-ChildItem "$out" -Recurse -File |
Where-Object {
    $_.FullName -notmatch 'node_modules'
} |
Select-String -Pattern `
"playwright|puppeteer|chromium|BrowserContext|page\.goto|page\.evaluate|webContents|capturePage|CDP|remote-debugging" `
-CaseSensitive:$false |
Select-Object Path, LineNumber, Line
```

This is particularly important for comparing their capture architecture with yours.

---

# 10. What this means for WebExtractor

This is actually a useful discovery for your project.

Your WebExtractor currently has a substantial dedicated extraction/reconstruction architecture:

```text
HAR
 ↓
Asset discovery
 ↓
DOM
 ↓
CSS
 ↓
Design tokens
 ↓
Layout analysis
 ↓
Component inference
 ↓
Behavioral evidence
 ↓
Asset binding
 ↓
Next.js generation
```

NoCodeXport's **Electron layer doesn't appear to compete with this architecture at all**.

Its Electron code is basically:

```text
Desktop wrapper
+
IPC utilities
+
Authentication
```

So the interesting comparison isn't:

```text
WebExtractor vs NoCodeXport Electron
```

It's:

```text
WebExtractor extraction engine
            VS
NoCodeXport's actual Next.js/server extraction implementation
```

**That's the part we haven't reached yet.**

The next thing I would inspect is the extracted application's `app/`, `lib/`, `components/`, `server/`, and API routes. That's where we have the highest chance of finding the actual mechanism NoCodeXport uses to turn a website into an export.
