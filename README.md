# FreezerBags 🧊

A tiny shared inventory for what's in the freezer — built for batch-cooking
ahead of a baby arriving. No login: open it and you're straight at the list.

- Add a food description + number of portions.
- Each item shows total portions and how long ago the oldest batch was frozen
  (badge goes amber at 3 months, red at 6).
- **Eat** and **Add to** open a small dialog to pick the number of portions;
  eating drains the oldest batch first (FIFO), so the age badge always
  reflects what's actually left.
- **Discard** removes an item outright.
- Installable as a PWA (add to home screen) for quick kitchen access.

## Stack

FastAPI + SQLAlchemy + SQLite, server-rendered Jinja templates with
[htmx](https://htmx.org) for the add/eat/add-to/discard actions — no JS
build step, no frontend framework. htmx is vendored in `app/static/` so the
app works fully on the LAN with no internet dependency.

## Run locally

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q                     # run tests
DATA_DIR=./data .venv/bin/uvicorn app.main:app --reload
```

Then open <http://localhost:8000>.

## Run in a container

```bash
docker compose -f docker-compose.dev.yml up --build   # build locally
# or, once an image has been published:
docker compose up -d                                   # ghcr.io/lwilts/freezerbags:latest
```

Data persists in `./data` on the host (mounted at `/data` in the container).

## Deploy to Kubernetes

`k8s/freezerbags.yaml` has a Namespace, PVC, Deployment, Service and an
`HTTPRoute` for `freezer.lab.lkwt.dev` (via `lab-gateway` /
`nginx-gateway`), matching the pattern used by the other apps in the
homelab repo. To deploy via Flux, copy it into
`homelab/flux/apps/home1/freezerbags.yaml` and push.

CI (`.github/workflows/docker-build.yml`) builds and pushes
`ghcr.io/lwilts/freezerbags` on every push to `main` (tagged `latest`) and
on version tags.

## Data model

Each `Item` has one or more `Batch` rows (portions + the date they were
frozen), so topping up an item keeps each addition's own date rather than
losing track of what's oldest. Eating an item consumes the oldest batch(es)
first. An item disappears from the list once its last batch is eaten or it's
discarded — it isn't deleted, just archived, so the underlying data survives
if you ever want a history view later.

## Deliberately left out (for now)

Freezer location/drawer tagging, an eat/discard history with quick re-add of
favourites, and a "this needs eating" nudge for anything past ~6 months. The
items+batches model leaves room for all three later.
