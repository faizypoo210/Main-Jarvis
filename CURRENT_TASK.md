# CURRENT TASK

## Status: READY

## Task: Build executor worker

## What it does
Reads `jarvis.execution` Redis stream.
Uses Ollama (Qwen 3.5 4B) to classify intent.
Takes action (start with `webbrowser.open`).
Publishes result to `jarvis.receipts` stream.

## Files to touch
- `F:\Jarvis\executor\worker.py` (CREATE NEW)
- `F:\Jarvis\jarvis.ps1` (add executor startup line)

## Files NOT to touch
- Control plane (port 8001) — do not change
- Voice server — do not change
- Command Center — do not change

## Done when
- Worker starts up cleanly
- Reads jarvis.execution stream
- Ollama classifies intent
- webbrowser.open fires for URL intents
- Result published to jarvis.receipts
- Logged in terminal
- jarvis.ps1 starts it

## Next after this
Command Center three-zone layout