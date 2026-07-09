# Composio App-Research — Case Study Page

Single-page deliverable that presents the research agent's output: patterns,
findings on 100 apps, the agent itself, a live trace-viewer proof, and an honest
two-way accuracy check. Read-only consumer of the data files in `public/data/` —
it does not regenerate or re-verify any numbers.

## Stack

Vite + React + TypeScript, no UI framework, no router, no state library. Custom
CSS design system (`src/index.css`). Data is fetched client-side from
`public/data/*.json` via a typed loader (`src/hooks/useResearchData.ts`) that
fails loudly if the schema does not match.

## Run

```bash
npm install
npm run dev        # local dev at http://localhost:5173
npm run build      # type-check + static build → dist/
npm run preview    # serve the built dist/ locally
```

> Node is required. If `node`/`npm` are nvm-wrapped in a non-interactive shell,
> run from an interactive terminal or point PATH at the nvm node bin.

## Before you submit — fill in the repo URL (one place)

Set the real repo URL in `src/lib/config.ts` (`REPO_URL`). The top-bar button,
agent section, and footer all read from there.

## Deploy (static)

`npm run build` emits a static `dist/`. Deploy that directly:

- **Vercel / Netlify:** zero-config (auto-detects Vite). Drag `dist/` in, or
  connect the repo. Works with the default `base: '/'`.
- **GitHub Pages (repo subpath):** set `base: '/<repo-name>/'` in
  `vite.config.ts`, rebuild, then publish `dist/`. All data paths use
  `import.meta.env.BASE_URL`, so they follow the base automatically.

## Structure

```
src/
  types/data.ts              # schema, defined once, imported everywhere
  hooks/useResearchData.ts   # typed client-side loader (fails loud)
  lib/format.ts              # label maps + formatting helpers
  components/
    Headline.tsx      # 1 — header + headline patterns (above the fold)
    AgentSummary.tsx  # 2 — what was built + where a human was needed
    FindingsTable.tsx # 3 — all 100 apps, filter + sort + expand
    ProofViewer.tsx   # 4 — pick an app, load its real trace
    Verification.tsx  # 5 — gold + LLM accuracy, hits and misses honest
    Footer.tsx        # 6 — repo + raw-data links
  App.tsx             # composes the 6 sections in order, nothing else
public/data/          # the 6 JSON files + traces/ (also raw, agent-consumable)
```

## Machine-readability

The JSON in `public/data/` ships as directly-fetchable static assets, so an
agent can consume the full dataset at `/<base>/data/pass2_corrected.json` etc.
with zero JS execution. Those URLs are also linked in the page footer.
