# Resume the document sweep (local run state — not committed)

The GitHub Actions runs are cloud-side and finish on their own even with this
machine off. These follow-up steps are LOCAL (they need the 969MB corpus
data/discover/nodes.jsonl) and resume whenever you restart.

## Run IDs
- docsweep-shard:        30285474662   (artifact: docsweep-merged -> nodes_docsweep.jsonl)
- minutes-recover-shard: 30286362736   (artifact: minutes-recover-merged -> nodes_minutes.jsonl)
- dc-idsweep-shard:      NOT YET LAUNCHED (deferred until docsweep merges, so it only
                          probes truly de-linked gaps instead of ~5-10M ids)

GH="C:\Program Files\GitHub CLI\gh.exe"

## Step 1 — confirm the runs finished
"$GH" run list --limit 6

## Step 2 — download artifacts into data/discover/
cd C:\Users\Owner\documents\muni-harvest
"$GH" run download 30285474662 -n docsweep-merged        --dir data/discover/
"$GH" run download 30286362736 -n minutes-recover-merged --dir data/discover/
# (artifacts land as nodes_docsweep.jsonl / nodes_minutes.jsonl)

## Step 3 — merge into the corpus, dedup by urlkey (lowercased path)
# use the existing merge/dedup approach; nodes_docsweep + nodes_minutes fold into nodes.jsonl

## Step 4 — regenerate manifests (now reflecting docsweep finds) + commit
.venv/Scripts/python.exe -m muni_harvest.cli export-manifests
git add config/dc_known_ids.jsonl.gz config/agenda_only.jsonl.gz
git commit -m "Refresh recover manifests after docsweep merge" && git push

## Step 5 — launch dc-idsweep (now efficient: only de-linked gaps remain)
"$GH" workflow run dc-idsweep-shard.yml -f shards=20

## Step 6 — download dc-idsweep, merge, then re-measure
"$GH" run download <dc-idsweep-run-id> -n dc-idsweep-merged --dir data/discover/
.venv/Scripts/python.exe -m muni_harvest.cli coverage
.venv/Scripts/python.exe -m muni_harvest.cli groundtruth
.venv/Scripts/python.exe scratch/verify_recovery.py     # election recall yardstick
