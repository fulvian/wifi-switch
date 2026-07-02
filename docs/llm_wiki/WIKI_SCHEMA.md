---
title: "wifi-switch LLM Wiki — Schema & Conventions"
kind: schema
status: active
created: 2026-07-02
last_updated: 2026-07-02
tags: [schema, conventions, wiki-ops]
confidence: high
cross_refs:
  - "[[index]]"
  - "[[log]]"
---

# wifi-switch LLM Wiki — Schema & Conventions

Compiled architectural knowledge for LLM sessions (Karpathy paradigm): pages capture *why* and *how*, not what `grep` already shows. Canonical, fuller schema lives at `/home/fulvio/coding/aria/docs/llm_wiki/WIKI_SCHEMA.md`; this file records only the deltas for this small project.

## Core rules (subset)

1. **Compiled, not transcribed.** If a fact is derivable from `wifi_switch.py`, do not write it here — document the *rationale* and *non-obvious runtime behavior* instead.
2. **Frontmatter mandatory** on every page except `log.md`: `title, kind, status, created, last_updated, sources, tags, confidence`.
3. **`sources:`** each entry = `path (read YYYY-MM-DD)`.
4. **Status lifecycle**: `draft → active → stale → superseded → historical`.
5. **Cross-links** with `[[page-slug]]`.
6. **Pages short** (≤300 lines). Current state at top; history goes to `log.md`.

## Layout

```
docs/llm_wiki/
├── WIKI_SCHEMA.md          # this file
└── wiki/
    ├── index.md            # navigation hub
    ├── log.md              # append-only ledger
    └── *.md                # architecture / policy pages
```

## log.md entry format

```
## YYYY-MM-DD — [UPDATE|INGEST|INCIDENT] short description
Detail: path, commit, what changed, why. Pages: [[slug]]
```
