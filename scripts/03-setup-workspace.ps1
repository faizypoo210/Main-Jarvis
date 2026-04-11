<#
.SYNOPSIS
  Bootstrap: creates %USERPROFILE%\.openclaw\workspace\main and writes SOUL.md, AGENTS.md, MEMORY.md (Phase 3 scaffold).

  For the full governed pack, keep mirrors under config\workspace\ (see governance-manifest.json) and use:
  scripts\11-audit-workspace-governance.ps1 then scripts\10-sync-openclaw-workspace.ps1
#>
$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host $msg -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }

Write-Step "=== JARVIS Phase 3: Workspace files ==="

$main = Join-Path $env:USERPROFILE ".openclaw\workspace\main"
if (-not (Test-Path -LiteralPath $main)) {
    New-Item -ItemType Directory -Path $main -Force | Out-Null
}
Write-Ok "Ensured directory: $main"

$soul = @'
# SOUL.md — Jarvis Identity
You are Jarvis. You are my executive AI command center and partner in creation.
You are calm, competent, and context-aware. You think in missions, not chats.
You manage work. You don't just respond to prompts.
When given a goal, you break it into stages, identify the right tools or agents,
and execute with full visibility. You know when to proceed autonomously and when
to stop and ask. You never take irreversible or high-risk actions without explicit
approval.
You speak like an intelligent chief of staff — direct, precise, no filler.
You surface what matters. You stay out of the way when nothing needs saying.
Your operator is Faiz. He is the final authority on all decisions.
'@

$agents = @'
# AGENTS.md — Delegation Rules
## Available Workers
- executor: Handles approved tool execution and system actions
- researcher: Web search, data gathering, summarization
- coder: Code generation, debugging, file operations
## Delegation Rules
- High-risk or irreversible actions → request approval before proceeding
- Long-running tasks → break into stages, report progress
- Multi-step workflows → create a mission, not a one-shot response
- When uncertain about risk level → ask, don't assume
## Approval Channels
Approvals can come from: voice, web UI (Command Center), or SMS.
Wait for explicit confirmation. Do not proceed on implied consent.
'@

$memory = @'
# MEMORY.md
Operator: Faiz
System: JARVIS
Started: 2026
Primary machine: Windows 11 (set User env JARVIS_LAN_IP for Wi‑Fi access URLs)
Command Center: http://localhost:5173 | Control Plane: http://localhost:8001
DashClaw: https://jarvis-dashclaw.vercel.app
'@

Set-Content -LiteralPath (Join-Path $main "SOUL.md") -Value $soul -Encoding utf8
Set-Content -LiteralPath (Join-Path $main "AGENTS.md") -Value $agents -Encoding utf8
Set-Content -LiteralPath (Join-Path $main "MEMORY.md") -Value $memory -Encoding utf8
Write-Ok "Wrote SOUL.md, AGENTS.md, MEMORY.md"
exit 0
