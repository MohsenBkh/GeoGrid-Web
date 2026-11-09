# GeoGrid Web

A web version of GeoGrid: users upload a shapefile .zip, pay a fixed
fee via ZarinPal, and download the converted DGS (.xlsx) file once
payment is confirmed.

This reuses the exact same conversion engine (`shp2dgs/core/`) as the
desktop GeoGrid.exe product -- same logic, same output format. It does
**not** use the desktop product's machine-bound license system;
payment itself is what gates a conversion here.

## How it works

```
Browser                FastAPI (app/main.py)              ZarinPal
  |                            |                              |
  | 1. upload .zip  ---------->|                              |
  |<----- job_id + price ------|                              |
  |                            |                              |
  | 2. click "Pay" ----------->|                              |
  |                            | 3. request payment --------->|
  |<----------- redirect to ZarinPal's payment page -----------|
  | 4. pays on ZarinPal's site                                 |
  |<----------- redirect back to our /api/payment/callback ----|
  |                            | 5. verify payment ---------->|
  |                            |<---- confirmed --------------|
  |                            | 6. runs Converter() in background
  | 7. polls /status  -------->|
  |<---- status=done, token ---|
  | 8. GET /download?token=... |
  |<----- the .xlsx file ------|
```

## Local setup (testing, no real payment)

```bash
cd geogrid_web
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # ZARINPAL_SANDBOX=true by default -- no real account needed
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 -- you can upload a real shapefile .zip.
With `ZARINPAL_SANDBOX=true` and the placeholder merchant ID, the
actual payment request to ZarinPal's sandbox will fail unless you
register a free sandbox account at https://sandbox.zarinpal.com and
put its merchant ID in `.env` -- real ZarinPal sandbox accounts are
free and instant to create, and let you test the full payment flow
with fake money.

## Deploy on Render (free, no server or domain needed)

Everything Render needs is already in this folder: `Dockerfile` (the app
image) and `render.yaml` (a Blueprint describing the service).

1. Push this folder to a **private** GitHub repository (`git init` in this
   folder, commit, push to `main`).
2. On [render.com](https://render.com): sign up with GitHub → **New** →
   **Blueprint** → pick the repo → **Apply**.
3. Render asks for `ZARINPAL_MERCHANT_ID` (it is marked `sync: false`).
   Leave the placeholder or paste a free
   [sandbox merchant id](https://sandbox.zarinpal.com) — the rest is
   pre-filled by `render.yaml`.
4. Wait for the build (**Logs** tab). When the service is **Live**, open
   `https://<service-name>.onrender.com`.

`SITE_BASE_URL` needs no configuration: the app reads Render's
`RENDER_EXTERNAL_URL`, so the ZarinPal callback stays correct even if
Render renames the service (e.g. `geogrid-web-abc1`). Set `SITE_BASE_URL`
explicitly only if you add a custom domain.

Useful endpoints: `GET /healthz` (Render's health check), `GET /docs`
(FastAPI's API browser).

### Free-tier limits worth knowing before you share the link

- **Sleeping**: the free instance stops after 15 min of inactivity and
  cold-starts on the next request (a few seconds).
- **Ephemeral disk**: persistent disks are paid-only, so `storage/`
  (uploads, converted `.xlsx`, the SQLite job DB) is wiped on every
  deploy/restart/sleep. Fine for a test, **not** acceptable for real paying
  users — for that, upgrade to a paid instance and uncomment the `disk:`
  block at the bottom of `render.yaml` (plus `GEOGRID_STORAGE_DIR=/var/data`).
- **0.1 CPU / 512 MB RAM**: `GEOGRID_MAX_UPLOAD_MB=25` in `render.yaml`
  keeps a single conversion from exhausting memory; raise it only with a
  bigger plan.
- **Sandbox only**: with `ZARINPAL_SANDBOX=true` no real money moves. Real
  payments require a verified merchant account at
  [next.zarinpal.com](https://next.zarinpal.com) and
  `ZARINPAL_SANDBOX=false`.

## Going live on a VPS: step-by-step (starting from nothing)

If you'd rather have a server you control (no sleeping, persistent disk,
custom domain), here's the full path:

### 1. Get a VPS (virtual server)
Pick one and create the cheapest Ubuntu 22.04 instance (1-2 GB RAM is
enough to start):
- Iranian providers (better latency for Iranian users, no sanctions
  friction for Iranian payment/banking integration): ArvanCloud,
  ParsPack, IranServer, Hetzner (EU, also commonly used)
- International: DigitalOcean, Hetzner, Vultr

### 2. Get a domain
Register one from a registrar. For a `.ir` domain, use nic.ir. For
`.com`/others, any registrar (Namecheap, GoDaddy, etc.) works. Point
its DNS **A record** at your VPS's IP address.

### 3. Get a ZarinPal merchant account
Sign up at https://next.zarinpal.com (Iranian business/individual
verification required for a real, non-sandbox merchant ID). This is
the only part Anthropic/I cannot do for you -- it requires your own
identity/business verification with ZarinPal.

### 4. Deploy the app
On the VPS:
```bash
sudo apt update && sudo apt install -y python3-venv python3-pip nginx certbot python3-certbot-nginx
sudo useradd -m -s /bin/bash geogrid
sudo mkdir -p /opt/geogrid_web
sudo chown geogrid:geogrid /opt/geogrid_web
# copy this whole geogrid_web/ folder to /opt/geogrid_web (scp/rsync/git)

sudo -u geogrid bash -c '
  cd /opt/geogrid_web
  python3 -m venv venv
  venv/bin/pip install -r requirements.txt
'
sudo cp /opt/geogrid_web/.env.example /opt/geogrid_web/.env
sudo nano /opt/geogrid_web/.env     # fill in your real ZarinPal merchant ID,
                                     # ZARINPAL_SANDBOX=false, SITE_BASE_URL=https://yourdomain.com

sudo cp deploy/geogrid-web.service /etc/systemd/system/
sudo cp deploy/geogrid-cleanup.service deploy/geogrid-cleanup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now geogrid-web
sudo systemctl enable --now geogrid-cleanup.timer

sudo cp deploy/nginx.conf /etc/nginx/sites-available/geogrid-web
# edit server_name in that file to your actual domain
sudo ln -s /etc/nginx/sites-available/geogrid-web /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

sudo certbot --nginx -d yourdomain.com   # free HTTPS certificate
```

### 5. Test with a real (small) payment
Visit `https://yourdomain.com`, upload a shapefile, and pay a small
real amount to confirm the whole flow before announcing the site.

## Pricing

Set `GEOGRID_PRICE_RIALS` in `.env`. ZarinPal's API takes Rials (not
Toman) -- `500000` Rials = `50000` Toman.

## File retention

Uploaded/converted files are deleted automatically after
`GEOGRID_JOB_RETENTION_HOURS` (default 48h). Two mechanisms exist — the app
runs a cleaner thread every `GEOGRID_CLEANUP_INTERVAL_HOURS` (default 6h,
set `0` to disable), which is what makes retention work on Render/Docker
where no host cron exists; on a VPS you can instead run
`deploy/geogrid-cleanup.timer`. Run it manually any time with
`python -m app.cleanup`.

## Known limitations of this MVP

- **Concurrency**: conversions run in a small in-process thread pool
  (`app/worker.py`, `max_workers=2`). Fine for moderate traffic; if you
  get a lot of simultaneous paid jobs, replace this with a real task
  queue (Celery/RQ + Redis) without changing anything else in
  `main.py`.
- **No user accounts**: each job is anonymous, identified only by a
  random job ID + download token. Add accounts/history later if
  needed.
- **No email receipts/download links**: the user must stay on the
  page (or keep the link `/?job_id=...`) to get their download. Add
  email delivery (e.g. via an SMTP provider) as a follow-up if desired.
