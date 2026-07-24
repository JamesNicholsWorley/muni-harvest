"""Discovery layer — union four sources into a per-site navigation tree.

Sources: Wayback (historical) + sitemaps (seed) + polite live crawl (structure) +
CMS listing endpoints. Everything is deduped into a manifest of `Node`s keyed by
urlkey (and later sha256), which is also the second-pass skip mechanism. This layer
INDEXES only — it records resolvable download URLs (incl. Google Drive / S3) but
does not fetch document bytes; that is a separate gated stage.
"""
