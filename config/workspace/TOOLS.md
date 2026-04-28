**Note:** Must start with `HOST=0.0.0.0` for LAN access

---

### Ollama (Local LLM)

**Purpose:** GPU-accelerated local inference, intent classification, fast responses

**Classification:**

- Access: Execute
- Scope: Local
- Risk: Safe
- Approval: Auto

**Configuration:**

```yaml
ollama:
  host: 10.0.0.249
  port: 11434
  model: qwen3.5:4b
  gpu: RTX 4070 Ti
```

**Use Cases:**

- Quick intent classification
- Heartbeat checks
- Low-cost routing decisions
- Draft generation

**⚠️ Important:** Ollama plugin config must NOT have `baseUrl` key

---

### Redis

**Purpose:** Event bus, state cache, pub/sub

**Classification:**

- Access: Read/Write
- Scope: Internal
- Risk: Safe
- Approval: Auto

**Configuration:**

```yaml
redis:
  host: 10.0.0.249
  port: 6379
  persistence: appendonly
```

**Streams:**

```
jarvis.commands   → Voice/UI → Control Plane
jarvis.execution  → Control Plane → OpenClaw
jarvis.receipts   → OpenClaw → Control Plane
jarvis.updates    → Control Plane → Voice/UI
```

---

### PostgreSQL

**Purpose:** Durable state storage for Mission Control

**Classification:**

- Access: Read/Write (via Mission Control API)
- Scope: Internal
- Risk: Moderate
- Approval: Via Mission Control

**Configuration:**

```yaml
postgresql:
  host: 10.0.0.249 (Docker)
  port: 5432
  managed_by: Mission Control
```

---

## Tool Families

### File Operations


| Tool                     | Access | Risk     | Approval | Receipt  |
| ------------------------ | ------ | -------- | -------- | -------- |
| `file.read`              | Read   | Safe     | Auto     | Optional |
| `file.write` (workspace) | Write  | Moderate | Ask      | Required |
| `file.write` (system)    | Write  | Critical | Require  | Required |
| `file.delete`            | Write  | High     | Require  | Required |
| `file.trash`             | Write  | Moderate | Ask      | Required |
| `file.copy`              | Write  | Safe     | Auto     | Required |
| `file.move`              | Write  | Moderate | Ask      | Required |


**Policy:** Prefer `trash` over `delete`. Never write outside workspace without explicit approval.

---

### Web Operations


| Tool             | Access | Risk     | Approval | Receipt  |
| ---------------- | ------ | -------- | -------- | -------- |
| `web.search`     | Read   | Safe     | Auto     | Optional |
| `web.fetch`      | Read   | Safe     | Auto     | Optional |
| `web.fetch_auth` | Read   | Moderate | Ask      | Required |
| `web.post`       | Write  | High     | Require  | Required |


**Policy:** Unrestricted public web access. Auth-required URLs need confirmation.

---

### Code Operations


| Tool                     | Access  | Risk     | Approval | Receipt  |
| ------------------------ | ------- | -------- | -------- | -------- |
| `code.generate`          | Execute | Safe     | Auto     | Required |
| `code.execute` (sandbox) | Execute | Moderate | Ask      | Required |
| `code.execute` (system)  | Execute | Critical | Require  | Required |
| `code.commit`            | Write   | High     | Require  | Required |
| `code.push`              | Write   | High     | Require  | Required |


**Policy:** Generated code is safe. Execution requires escalating approval based on scope.

---

### Communication Operations


| Tool          | Access | Risk | Approval | Receipt  |
| ------------- | ------ | ---- | -------- | -------- |
| `email.read`  | Read   | Safe | Auto     | Optional |
| `email.send`  | Write  | High | Require  | Required |
| `email.draft` | Write  | Safe | Auto     | Required |
| `sms.send`    | Write  | High | Require  | Required |
| `slack.read`  | Read   | Safe | Auto     | Optional |
| `slack.post`  | Write  | High | Require  | Required |


**Policy:** Reading is free. Sending requires approval—these are identity-bearing.

---

### Integration Operations


| Tool              | Access | Risk     | Approval | Receipt  |
| ----------------- | ------ | -------- | -------- | -------- |
| `github.read`     | Read   | Safe     | Auto     | Optional |
| `github.issue`    | Write  | Moderate | Ask      | Required |
| `github.commit`   | Write  | High     | Require  | Required |
| `calendar.read`   | Read   | Safe     | Auto     | Optional |
| `calendar.create` | Write  | Moderate | Ask      | Required |
| `notion.read`     | Read   | Safe     | Auto     | Optional |
| `notion.write`    | Write  | Moderate | Ask      | Required |


---

### System Operations


| Tool            | Access  | Risk     | Approval | Receipt  |
| --------------- | ------- | -------- | -------- | -------- |
| `shell.read`    | Execute | Moderate | Ask      | Required |
| `shell.write`   | Execute | High     | Require  | Required |
| `docker.status` | Read    | Safe     | Auto     | Optional |
| `docker.start`  | Execute | Moderate | Ask      | Required |
| `docker.stop`   | Execute | Moderate | Ask      | Required |
| `process.list`  | Read    | Safe     | Auto     | Optional |
| `process.kill`  | Execute | High     | Require  | Required |


---

### Memory Operations


| Tool                   | Access | Risk     | Approval | Receipt  |
| ---------------------- | ------ | -------- | -------- | -------- |
| `memory.read`          | Read   | Safe     | Auto     | None     |
| `memory.write_daily`   | Write  | Safe     | Auto     | Optional |
| `memory.write_durable` | Write  | Moderate | Ask      | Required |
| `memory.delete`        | Write  | High     | Require  | Required |


---

## Integration Status

### Composio-Authenticated Services


| Service         | Status   | Capabilities          | Approval Level   |
| --------------- | -------- | --------------------- | ---------------- |
| **Gmail**       | ✅ Active | Read, Draft, Send     | Send: Require    |
| **GitHub**      | ✅ Active | Read, Issues, Commits | Commits: Require |
| **Supabase**    | ✅ Active | Read, Write           | Write: Ask       |
| **YouTube**     | ✅ Active | Read                  | Auto             |
| **HuggingFace** | ✅ Active | Read, Deploy          | Deploy: Require  |
| **Calendar**    | ✅ Active | Read, Create          | Create: Ask      |
| **Slack**       | ✅ Active | Read, Post            | Post: Require    |
| **Notion**      | ✅ Active | Read, Write           | Write: Ask       |


### Integration Policies

**GitHub:**

- Reading repos/issues: Auto
- Creating issues: Ask
- Committing code: Require
- Force push: Never (blocked)

**Gmail:**

- Reading inbox: Auto
- Drafting: Auto
- Sending: Require
- Forwarding to external: Require

**Calendar:**

- Reading events: Auto
- Creating personal events: Ask
- Creating events with attendees: Require

---

## Environment Reference

### Network Layout

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  Windows Machine (10.0.0.249)                                                                                                                            │
│  ├── OpenClaw Gateway (:18789)                                                                                                                           │
│  ├── Command Center (deprecated — ports 3000/3001 are legacy Mission Control; primary operator UI is Command Center on :5173, control plane API on :8001)│
│  ├── LobsterBoard (:8080)                                                                                                                                │
│  ├── Ollama (:11434)                                                                                                                                     │
│  ├── Redis (:6379)                                                                                                                                       │
│  ├── PostgreSQL (:5432, Docker)                                                                                                                          │
│  ├── Voice Server (:8000)                                                                                                                                │
│  └── Event Coordinator (coordinator.py)                                                                                                                  │
├────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  External Services                                                                                                                                       │
│  ├── DashClaw (jarvis-dashclaw.vercel.app)                                                                                                               │
│  └── Composio (cloud-authenticated)                                                                                                                      │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Port Reference


| Port  | Service                                                                                                                                              | Protocol       |
| ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- |
| 3000  | Command Center (deprecated — ports 3000/3001 are legacy Mission Control; primary operator UI is Command Center on :5173, control plane API on :8001) | HTTP           |
| 3001  | Command Center (deprecated — ports 3000/3001 are legacy Mission Control; primary operator UI is Command Center on :5173, control plane API on :8001) | HTTP           |
| 8000  | Voice Server                                                                                                                                         | HTTP/WebSocket |
| 8080  | LobsterBoard                                                                                                                                         | HTTP           |
| 11434 | Ollama                                                                                                                                               | HTTP           |
| 18789 | OpenClaw Gateway                                                                                                                                     | WebSocket      |
| 5432  | PostgreSQL                                                                                                                                           | TCP            |
| 6379  | Redis                                                                                                                                                | TCP            |


### Startup Sequence

```bash
# Master startup: F:\Jarvis\jarvis.ps1

1. Docker Desktop (PostgreSQL, Redis)
2. OpenClaw Gateway
3. Mission Control
4. LobsterBoard
5. Ollama
6. Event Coordinator
7. Voice Server
8. System Tray
```

---

## Credential Management

### Vault Reference

Credentials are stored in the secure vault, NOT in these files.


| Credential            | Location    | Access Pattern           |
| --------------------- | ----------- | ------------------------ |
| OpenClaw Token        | Vault       | Auto-injected by gateway |
| Mission Control Token | Vault       | Header injection         |
| DashClaw API Key      | Vault       | Header injection         |
| Composio Auth         | Vault       | OAuth managed            |
| OpenAI Key            | Environment | Model calls              |


### Auth Profiles

```
Location: %USERPROFILE%\.openclaw\agents\main\agent\auth-profiles.json
```

---

## Skill Loading

### Progressive Disclosure

```
Level 0: Skill names and descriptions (always loaded)
Level 1: Basic usage instructions (on mention)
Level 2: Full documentation (on explicit use)
Level 3: Error handling and edge cases (on failure)
```

### Skill Directories

```
~/.openclaw/skills/          → User-installed skills
/mnt/skills/public/          → System skills
/mnt/skills/examples/        → Example skills
```

### Skill Security

Before using any community skill:

1. Review source code
2. Check for suspicious network calls
3. Verify no credential exfiltration
4. Test in sandbox first

---

## Tool Usage Rules

### General Principles

1. **Minimum necessary access:** Use the least-privileged tool for the job
2. **Receipt everything:** If it changes state, log it
3. **Ask when uncertain:** Classification doubt → Ask for confirmation
4. **Fail gracefully:** Capture errors with context
5. **Respect timeouts:** Don't hang on slow operations

### Cost Awareness

Track and report:

- Tokens per tool call
- USD cost per mission
- Anomalies (>150% of estimate)

### Rate Limiting


| Service    | Rate Limit      | Behavior        |
| ---------- | --------------- | --------------- |
| OpenAI     | Model-dependent | Backoff + queue |
| GitHub     | 5000/hour       | Cache reads     |
| Gmail      | 250/day (send)  | Queue + warn    |
| Web search | 100/hour        | Cache results   |


---

## Tool Development

### Adding New Tools

New tools require:

1. Classification across all four dimensions
2. Receipt schema definition
3. Approval workflow documentation
4. Integration with DashClaw policy
5. Operator approval before deployment

### Tool Testing

Before production:

1. Sandbox testing
2. Receipt validation
3. Failure mode testing
4. Cost estimation
5. Security review

---

## Version History


| Version | Date       | Changes                            |
| ------- | ---------- | ---------------------------------- |
| 1.0     | 2026-04-10 | Initial production tool policy map |


---

**END OF TOOLS.md**