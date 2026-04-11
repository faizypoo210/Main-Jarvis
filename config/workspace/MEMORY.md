# MEMORY.md — Lightweight context index (not Memory v1)

## Two different “memory” ideas (do not confuse them)

| Layer | What it is |
|-------|------------|
| **This file** | Short, **static** notes the gateway may read for persona/context (operator name, URLs, machine hints). A **human-edited index**, not a database. |
| **Memory v1 (control plane)** | Durable **`memory_items`** rows, operator APIs, promotion from missions/receipts per product rules. **Authoritative** for stored operator memory in Jarvis. |

This repo mirror is **not** an automatic export of `memory_items`. Edit it for **stable** facts you want in the local model context; use Command Center / API for **governed** durable memory.

## Index (edit as needed)

- Operator: Faiz  
- System: Jarvis  
- Command Center: `http://localhost:5173` (dev)  
- Control plane API: `http://localhost:8001`  
- Primary machine: Windows 11 (set user env `JARVIS_LAN_IP` when using LAN URLs from other devices)  

Do **not** paste secrets, tokens, or full mission logs here.
