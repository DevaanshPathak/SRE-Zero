# SRE-Zero Frontend

Next.js console for interacting with the SRE-Zero simulator.

## Run

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Build

```bash
npm run typecheck
npm run build
```

## Design

The frontend uses local Next API routes to run an in-memory simulator session over the repository's deterministic JSON task configs. Hidden task fields stay server-side; the browser receives observations, action results, rewards, and metrics.

No real infrastructure control is exposed.

