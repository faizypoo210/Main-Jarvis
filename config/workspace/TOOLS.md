# TOOLS.md — Capability policy (OpenClaw / Composio)

## Connected surfaces (example integrations)

When Composio or similar is configured, typical surfaces may include:

- Gmail: read, send, search  
- Google Calendar: read/create events, availability  
- Slack: channels, messages  
- Notion: pages and databases  
- GitHub: repos, issues, PRs  

**Actual** tool availability depends on OpenClaw configuration, auth profiles, and Composio setup on the machine. This list is **policy intent**, not a guarantee every action works in every environment.

## Rules

- Confirm before **sending** email/messages or **creating** calendar events on the operator’s behalf.  
- **Writes** to Notion/GitHub repos often need explicit approval; **reads** and search are lower risk.  
- **Destructive** or identity-bearing operations follow operator rules in `USERS.md` and real approvals in the **control plane**.

## Receipts and mission truth

Execution outcomes that matter for governance should show up as **receipts and mission events** via the executor/control plane. This markdown does **not** replace posted receipts or API state.
