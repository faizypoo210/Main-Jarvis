# Jarvis Command Center

Governed executive AI command surface — mission control, not a generic admin panel.

## Run

```bash
cd services/command-center
npm install
npm run dev
```

Opens at [http://localhost:5173](http://localhost:5173).

The UI expects the control plane API at [http://localhost:8001](http://localhost:8001) (see `src/lib/api.ts`).

## Build

```bash
npm run build
npm run preview
```
