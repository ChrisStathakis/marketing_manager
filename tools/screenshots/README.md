# Screenshot tooling

Regenerates the images used by the documentation site (`docs/assets/*.png`).

This is a **maintenance tool, not part of CI**: it is never installed or run by the CI
workflow, and the images it produces are committed.

## What it does

1. Opens the app in a headless Chromium.
2. Signs in as a demo user.
3. Walks the pages listed in `capture.mjs` and screenshots each one into `docs/assets/`.

Toasts are hidden and animations are frozen, so the output is stable between runs.

## Running it

You need a running app with **demo data**, so the screenshots show something worth looking at.

**1. Install the browser (once).**

```powershell
cd tools\screenshots
npm install
npx playwright install chromium
```

**2. Create a throwaway database and seed it.**

This uses a separate SQLite file so it never touches your development database. From the
repository root:

```powershell
$env:DATABASE_URL="sqlite:///C:/Users/You/AppData/Local/Temp/mm_docs.sqlite3"
.\.venv\Scripts\python.exe backend\manage.py migrate
.\.venv\Scripts\python.exe backend\manage.py seed_demo --owner demo
```

`seed_demo` needs a user to own the campaigns. Create one if you do not have one yet:

```powershell
.\.venv\Scripts\python.exe backend\manage.py createsuperuser
```

**3. Start both servers** (leave each one running in its own terminal), passing the same
`DATABASE_URL` to the backend:

```powershell
# terminal 1
$env:DATABASE_URL="sqlite:///C:/Users/You/AppData/Local/Temp/mm_docs.sqlite3"
.\.venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8000 --noreload

# terminal 2
cd frontend
npm run dev
```

!!! warning "Make sure port 8000 is really yours"
    If a stale `runserver` from an earlier session is still listening, the new one exits and
    the screenshots silently come from the old database. Check with:

    ```powershell
    Get-NetTCPConnection -LocalPort 8000 -State Listen
    ```

**4. Capture.**

```powershell
cd tools\screenshots
node capture.mjs
```

## Options

| Env var | Default | Purpose |
| --- | --- | --- |
| `BASE_URL` | `http://localhost:5173` | Where the frontend is served. |
| `APP_USER` | `demo` | Login username. |
| `APP_PASSWORD` | `demo12345` | Login password. |
| `OUT_DIR` | `../../docs/assets` | Where the PNGs are written. |

## Adding a page

Append to the shot list in `capture.mjs`, then reference the file from a guide page. Keep the
names descriptive (`shop-orders.png`, not `shot-7.png`) and delete any image you stop using —
the docs build fails on a broken image link, which is the point.
