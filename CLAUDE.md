# CLAUDE.md

Notes for future Claude sessions working on this fork.

## Fork purpose

This fork (`DeveloperMos/maildrop`) adds **multi-domain support** to upstream `haileyydev/maildrop`, so a single container can serve N domains at once instead of one. Driven by a real use case: 7 domains needed to share a single maildrop instance bound to host port 25.

Upstream `DOMAIN` is a single string used in 4 places via `.endswith()` / f-string formatting. We extended it to accept a comma-separated list and rewired those 4 sites.

## Changes

### `config.py`
Added `get_domains()` helper after the `Settings` block:

```python
def get_domains() -> list[str]:
    return [d.strip().lower().lstrip("@") for d in settings.DOMAIN.split(",") if d.strip()]
```

- Keeps `DOMAIN` typed as `str` (no pydantic schema change, no `.env.example` rewrite needed).
- Lowercases + strips whitespace and stray leading `@`, so `"Example.com, @other.com"` works.
- Single-domain configs (`DOMAIN="example.com"`) still work — list of one.

### `src/backend/smtp_server.py`
Recipient check (line ~20):

```python
to_addr = (parsed_email.get('To') or '').lower()
if not any(to_addr.endswith("@" + d) for d in config.get_domains()):
    return '500 Could not process email'
```

- Switched from `endswith(DOMAIN)` to `endswith("@" + d)` — the upstream check let `john@evilfoo.com` through when `DOMAIN=foo.com`. The `@` prefix closes that.
- `parsed_email.get('To')` handles missing/None `To` header instead of KeyError.

### `src/backend/routes/api.py`
Round-robin counter at module top:

```python
import threading
_domain_rr_lock = threading.Lock()
_domain_rr_index = 0

def _next_domain() -> str:
    global _domain_rr_index
    domains = config.get_domains()
    with _domain_rr_lock:
        d = domains[_domain_rr_index % len(domains)]
        _domain_rr_index = (_domain_rr_index + 1) % len(domains)
    return d
```

Used by:
- `/get_random_address` — random local part, rotated domain
- `/get_domain` — rotated domain

`/send_email` `From` validation rewritten to match any configured domain (with `"@" + d` to fix the same suffix-bug as the SMTP path).

**Counter is shared** between both endpoints intentionally — the user wanted a single rotating sequence, not two independent counters.

## Frontend

`src/frontend/static/scripts/api.js` was **not** changed. `getDomain()` still expects a single string and we still return one (just rotated per request), so the UI behavior is unchanged from the user's POV — refreshing rotates which domain shows.

## Usage

Single command, multiple domains:

```bash
docker run -d --restart unless-stopped --name maildrop \
  --ulimit nproc=512:512 --ulimit nofile=2048:2048 \
  --memory="512m" --cpus="1" \
  -p 127.0.0.1:5000:5000 -p 25:25 \
  -e DOMAIN="example.com,example.org,example.net" \
  -e THREADS=1 \
  maildrop-multi:latest
```

Build is `docker build -t maildrop-multi .` from the repo root — uses upstream Dockerfile (Python 3.9-slim, `python ./app.py`).

DNS: each domain in `DOMAIN` needs its own `MX` pointing at the maildrop host. The host still binds a single port 25 — there's no per-domain port routing.

## Things to know before changing

- **Don't reintroduce `config.settings.DOMAIN.endswith` checks anywhere** — always go through `config.get_domains()` so multi-domain stays consistent.
- **`get_domains()` is called per request** (cheap — just splits the env string). If you cache it, invalidate on config reload, otherwise live `.env` edits stop taking effect.
- **Round-robin state is in-process** — if you ever scale to multiple workers/replicas, each will have its own counter and rotation will look uneven. Fine for the current single-container deploy.
- **Upstream is `haileyydev/maildrop`** on `master`. If pulling upstream changes, the 4 patched sites are the conflict surface to watch.

## Commits

- `e42df42` — `support multiple domains via comma-separated DOMAIN`
- `7838394` — `document multi-domain DOMAIN support in README`

Branch: `master`. Remote: `git@github.com:DeveloperMos/maildrop.git`.
