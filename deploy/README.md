# Deploy: Hetzner VM + Cloudflare R2

The VM hosts the browser tier (73 T2 sites) + long crawls that outlive GitHub
Actions; R2 stores the corpus with free egress. **You create the accounts + tokens;
Claude drives provisioning/deploy via `hcloud` and the repo CLI.**

## 1. Accounts + tokens (you — one time)

**Hetzner Cloud**
1. Sign up at https://console.hetzner.cloud and add a payment method.
2. Create a Project (e.g. `muni-harvest`).
3. Security → API Tokens → **Generate** a token with **Read & Write**. Copy it.
4. Paste it when Claude asks (it goes into `hcloud` context, not the repo).

**Cloudflare R2**
1. Sign up at https://dash.cloudflare.com; go to **R2** and enable it (asks for a
   card even for the free 10 GB tier — $0 until you exceed it).
2. Create a bucket (or let Claude create it): name `muni-harvest`.
3. R2 → **Manage API Tokens** → create an **S3-compatible** token (Object Read &
   Write). Copy: Access Key ID, Secret Access Key, and the S3 endpoint
   `https://<accountid>.r2.cloudflarestorage.com`.

## 2. Provision (Claude drives)

```bash
hcloud context create muni-harvest          # paste the Hetzner token
hcloud ssh-key create --name mh --public-key-from-file ~/.ssh/id_ed25519.pub
hcloud server create --name muni-harvest --type cx22 --image ubuntu-24.04 \
  --location ash --ssh-key mh --user-data-from-file deploy/cloud-init.yaml
```

`cx22` in Ashburn (`ash`) ~ $5/mo. cloud-init installs Python, Chrome, the repo, and
the venv on first boot (watch for `/opt/muni-harvest/READY`).

## 3. Configure secrets on the VM (never in git)

Copy `.env.example` → `.env` on the VM and fill the R2 values:
```
S3_ENDPOINT_URL=https://<accountid>.r2.cloudflarestorage.com
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
S3_BUCKET=muni-harvest
```
Then validate + create the bucket:
```bash
cd /opt/muni-harvest
.venv/bin/muni-harvest store ping
.venv/bin/muni-harvest store ensure
```

## 4. Run the full sweep (on the VM, in tmux so it survives disconnects)

```bash
tmux new -s wayback  '.venv/bin/muni-harvest wayback'      # ~5 min, free deep index
tmux new -s discover '.venv/bin/muni-harvest discover'     # long: live crawl + union
.venv/bin/muni-harvest scorecard
.venv/bin/muni-harvest groundtruth                         # recall vs 942 known PDFs
```

## Re-provision / update an existing box
```bash
ssh root@<ip> 'bash -s' < deploy/setup_vm.sh    # pulls latest main, reinstalls
```
