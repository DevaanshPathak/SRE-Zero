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

The model baseline panel reads selectable model names from the root `.env` `OPENAI_MODEL` value and local `notes/available_models.md`. Running a comparison calls the configured OpenAI-compatible `/chat/completions` endpoint server-side for exactly the two selected models.

No real infrastructure control is exposed.
