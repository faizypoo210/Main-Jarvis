# JARVIS Week 2: Cursor 3.0 Deployment Guide

**Perfect approach:** Use Cursor's **Composer** + **Terminal** + **Agent mode** to execute the entire deployment with minimal manual work.

> **Security:** Embedded prompts below use placeholders such as `<OPENCLAW_GATEWAY_TOKEN_SET_VIA_ENV>` and `<YOUR_LAN_IP>`. Never paste real tokens or keys into this file. If any value ever appeared in git history, **rotate** it (see `docs/SECRET_ROTATION.md`).

---

## Setup: Prepare Cursor Workspace

### Step 1: Create JARVIS Project Folder

**In PowerShell (outside Cursor):**
```powershell
# Create project root
mkdir C:\jarvis-project
cd C:\jarvis-project

# Create structure
mkdir config
mkdir scripts
mkdir docs

# Open in Cursor
cursor .
```

### Step 2: Create Deployment Tracker

**In Cursor, create `DEPLOYMENT_STATUS.md`:**

```markdown
# JARVIS Week 2 Deployment Status

## Day 1: Docker + Databases
- [ ] Docker Desktop installed
- [ ] PostgreSQL container running
- [ ] Redis container running
- [ ] Connections verified

## Day 2: Mission Control
- [ ] Repository cloned
- [ ] Configuration files created
- [ ] Docker Compose deployed
- [ ] Web UI accessible

## Day 3: OpenClaw Gateway
- [ ] OpenClaw installed
- [ ] Workspace configured
- [ ] Gateway running
- [ ] Health check passing

## Day 4: LobsterBoard
- [ ] Repository cloned
- [ ] Configuration created
- [ ] Server running
- [ ] Dashboard accessible

## Day 5: Ollama + GPU
- [ ] Ollama installed
- [ ] qwen3:4b downloaded
- [ ] GPU acceleration verified
- [ ] OpenClaw integration tested

## Day 6: Voice Integration
- [ ] Voice option selected
- [ ] Configuration applied
- [ ] Voice commands working

## Day 7: Composio Integrations
- [ ] Composio installed
- [ ] Services connected
- [ ] OpenClaw integration tested

## Final Testing
- [ ] Full stack health check
- [ ] Voice → execution flow
- [ ] Approval flow
- [ ] Phone access working
```

---

## Deployment Strategy: Cursor Workflow

### Phase-Based Execution

Each phase = **One Cursor Composer session** with specific instructions.

**Workflow:**
1. Copy the Cursor prompt below
2. Open Cursor Composer (`Cmd/Ctrl + I`)
3. Paste the prompt
4. Let Cursor create files and generate commands
5. Execute commands in Cursor's integrated terminal
6. Verify results before moving to next phase

---

## Phase 1: Docker + Database Setup

### Cursor Prompt (Composer):

```
I'm deploying JARVIS on Windows. Create all configuration files and PowerShell scripts for Phase 1:

TASK: Set up Docker Desktop, PostgreSQL, and Redis

REQUIREMENTS:
1. Create a PowerShell script `scripts/01-install-docker-databases.ps1` that:
   - Checks if Docker Desktop is installed
   - Provides installation instructions if not
   - Creates data directories at C:\jarvis-data\postgres and C:\jarvis-data\redis
   - Starts PostgreSQL container (name: jarvis-postgres, port: 5432, user: jarvis, password: jarvis_secure_password_2026, db: jarvis_missions)
   - Starts Redis container (name: jarvis-redis, port: 6379, with persistence)
   - Verifies both containers are running
   - Tests connections

2. Create `config/database-config.json` with:
   - PostgreSQL connection string
   - Redis connection string
   - Container configuration details

3. Create `scripts/01-verify-databases.ps1` that:
   - Checks PostgreSQL is accessible
   - Checks Redis responds to PING
   - Shows container status
   - Displays resource usage

CREDENTIALS (use these exact values):
- PostgreSQL user: jarvis
- PostgreSQL password: jarvis_secure_password_2026
- PostgreSQL database: jarvis_missions

Generate all files now. Make scripts idempotent (safe to re-run).
```

**After Cursor generates files:**

**Execute in Cursor Terminal (PowerShell):**
```powershell
# Run installation script
.\scripts\01-install-docker-databases.ps1

# If Docker Desktop not installed, follow instructions, then re-run

# Verify
.\scripts\01-verify-databases.ps1
```

**Expected Output:**
```
✓ PostgreSQL running on port 5432
✓ Redis running on port 6379
✓ Database connection successful
✓ Redis PING successful
```

**Mark complete in `DEPLOYMENT_STATUS.md`** ✅

---

## Phase 2: Mission Control Deployment

**Historical / deprecated:** The primary Jarvis stack is Command Center + Control Plane + workers. Legacy Mission Control scripts and compose live under **`deprecated/mission-control/`** (not `scripts/`). Do not extend this path for new features.

### Cursor Prompt (Composer):

```
Phase 2: Deploy OpenClaw Mission Control

TASK: Clone repo, create configs, deploy with Docker Compose

REQUIREMENTS:
1. Create `scripts/02-setup-mission-control.ps1` that:
   - Clones https://github.com/abhi1693/openclaw-mission-control to C:\projects\openclaw-mission-control
   - Creates .env file in root with these exact values:
     DATABASE_URL=postgresql://jarvis:jarvis_secure_password_2026@host.docker.internal:5432/jarvis_missions
     REDIS_URL=redis://host.docker.internal:6379
     OPENCLAW_GATEWAY_URL=http://host.docker.internal:18789
     OPENCLAW_GATEWAY_TOKEN=<OPENCLAW_GATEWAY_TOKEN_SET_VIA_ENV>
     AUTH_TOKEN=(set in Mission Control .env — never commit real tokens)
     DASHCLAW_BASE_URL=https://jarvis-dashclaw.vercel.app
     DASHCLAW_API_KEY=<DASHCLAW_API_KEY_SET_VIA_ENV>
     ENABLE_DASHCLAW=true
     ENABLE_COST_TRACKING=true
     NODE_ENV=production
     PORT=3000
   
   - Creates identical backend/.env file
   - Modifies docker-compose.yml to:
     * Remove postgres and redis services (we use host containers)
     * Add extra_hosts: host.docker.internal:host-gateway to backend and webhook-worker
     * Keep only: frontend, backend, webhook-worker services
   
   - Runs docker-compose build
   - Runs docker-compose up -d
   - Waits for services to be healthy
   - Opens http://localhost:3000 in browser

2. Create `scripts/02-verify-mission-control.ps1` that:
   - Checks all containers are running
   - Tests API endpoint http://localhost:3001/api/health
   - Shows logs for any errors
   - Verifies database migrations ran

IMPORTANT: Use host.docker.internal for all host service connections from Docker containers.

Generate all files now.
```

**Execute in Cursor Terminal (legacy only):**
```powershell
# Run setup
.\deprecated\mission-control\02-setup-mission-control.ps1

# Verify
.\deprecated\mission-control\02-verify-mission-control.ps1

# Open Mission Control
start http://localhost:3000
```

**Mark complete in `DEPLOYMENT_STATUS.md`** ✅

---

## Phase 3: OpenClaw Gateway

### Cursor Prompt (Composer):

```
Phase 3: Install and configure OpenClaw Gateway

TASK: Install OpenClaw, create workspace, configure gateway

REQUIREMENTS:
1. Create `scripts/03-install-openclaw.ps1` that:
   - Downloads OpenClaw installer for Windows
   - Provides installation command: Invoke-WebRequest -Uri https://openclaw.ai/install.ps1 -OutFile install-openclaw.ps1; .\install-openclaw.ps1
   - Waits for user to complete installation
   - Verifies openclaw command is available

2. Create `config/openclaw-config.json` with this exact structure:
   {
     "gateway": {
       "port": 18789,
       "host": "0.0.0.0",
       "token": "<OPENCLAW_GATEWAY_TOKEN_SET_VIA_ENV>"
     },
     "agents": {
       "main": {
         "workspace": "C:\\Users\\<REPLACE_USERNAME>\\.openclaw\\workspace\\main",
         "model": "claude-sonnet-4-20250514",
         "temperature": 0.2,
         "provider": "anthropic"
       },
       "local": {
         "model": "qwen3:4b",
         "provider": "ollama",
         "baseUrl": "http://localhost:11434",
         "temperature": 0.3
       }
     },
     "api": {
       "anthropic": {
         "apiKey": "YOUR_ANTHROPIC_API_KEY_HERE"
       }
     },
     "tools": {
       "exec": {
         "security": "allowlist",
         "ask": "on-miss"
       }
     }
   }

3. Create `config/workspace/SOUL.md` with Jarvis personality:
   - Executive AI command center inspired by Iron Man
   - Calm, competent, context-aware
   - Think in missions, not chats
   - Request approval for risky actions
   - Professional chief-of-staff communication style

4. Create `config/workspace/AGENTS.md` with delegation strategy:
   - executor: approved actions, tools
   - researcher: web search, analysis
   - coder: code generation, debugging
   - Delegation rules for approval, sub-missions, stages

5. Create `scripts/03-configure-openclaw.ps1` that:
   - Copies config to C:\Users\<USERNAME>\.openclaw\config.json (replacing <REPLACE_USERNAME>)
   - Creates workspace directory structure
   - Copies SOUL.md and AGENTS.md to workspace
   - Prompts for Anthropic API key and updates config
   - Starts gateway: openclaw gateway start
   - Verifies gateway is running: curl http://localhost:18789/health

6. Create `scripts/03-verify-openclaw.ps1` that:
   - Checks gateway status
   - Tests WebSocket connection
   - Verifies workspace files exist
   - Shows gateway logs

Generate all files now.
```

**Execute in Cursor Terminal:**
```powershell
# Install OpenClaw (if not already)
.\scripts\03-install-openclaw.ps1

# Configure
.\scripts\03-configure-openclaw.ps1
# When prompted, enter your Anthropic API key

# Verify
.\scripts\03-verify-openclaw.ps1
```

**Mark complete in `DEPLOYMENT_STATUS.md`** ✅

---

## Phase 4: LobsterBoard Dashboard

### Cursor Prompt (Composer):

```
Phase 4: Deploy LobsterBoard dashboard

TASK: Clone, configure, and start LobsterBoard

REQUIREMENTS:
1. Create `scripts/04-setup-lobsterboard.ps1` that:
   - Clones https://github.com/Curbob/LobsterBoard to C:\projects\LobsterBoard
   - Runs npm install
   - Creates config.json with:
     * port: 8080
     * host: 0.0.0.0
     * theme: dark
     * OpenClaw gateway URL: http://localhost:18789
     * Gateway token: <OPENCLAW_GATEWAY_TOKEN_SET_VIA_ENV>
     * Mission Control base URL: http://localhost:3000
     * Mission Control auth token: (set in `.env` — not in repo)
     * DashClaw base URL: https://jarvis-dashclaw.vercel.app
     * DashClaw API key: <DASHCLAW_API_KEY_SET_VIA_ENV>
   
   - Starts server: node server.cjs
   - Opens http://localhost:8080 in browser

2. Create `scripts/04-start-lobsterboard.ps1` (startup script):
   - Changes to LobsterBoard directory
   - Starts node server.cjs
   - Can be used for automatic startup

3. Create `scripts/04-verify-lobsterboard.ps1` that:
   - Checks server is running on port 8080
   - Tests dashboard accessibility
   - Shows process status

4. Create `config/lobsterboard-widgets.json` with recommended widget layout:
   - OpenClaw Auth Status widget
   - Active Missions widget (from Mission Control)
   - Docker Containers widget
   - System Resources widget
   - Pending Approvals widget (from DashClaw)

Generate all files now.
```

**Execute in Cursor Terminal:**
```powershell
# Setup LobsterBoard
.\scripts\04-setup-lobsterboard.ps1

# In a new terminal tab/window (keep server running)
# Verify
.\scripts\04-verify-lobsterboard.ps1

# Open dashboard
start http://localhost:8080
```

**In Browser:**
- Press `Ctrl+E` to enter edit mode
- Add widgets from `config/lobsterboard-widgets.json`
- Save layout

**Mark complete in `DEPLOYMENT_STATUS.md`** ✅

---

## Phase 5: Ollama + GPU Acceleration

### Cursor Prompt (Composer):

```
Phase 5: Install Ollama with GPU acceleration

TASK: Install Ollama, download qwen3:4b, verify GPU

REQUIREMENTS:
1. Create `scripts/05-install-ollama.ps1` that:
   - Downloads Ollama installer: Invoke-WebRequest -Uri https://ollama.ai/download/OllamaSetup.exe -OutFile OllamaSetup.exe
   - Runs installer
   - Waits for installation to complete
   - Verifies ollama command is available

2. Create `scripts/05-pull-model.ps1` that:
   - Checks NVIDIA GPU with nvidia-smi
   - Verifies CUDA is detected
   - Pulls qwen3:4b model: ollama pull qwen3:4b
   - Lists installed models: ollama list
   - Tests model: ollama run qwen3:4b "Hello, I'm Jarvis"
   - Verifies GPU is being used (check for CUDA in output)

3. Create `scripts/05-integrate-ollama-openclaw.ps1` that:
   - Updates OpenClaw config to include local agent with qwen3:4b
   - Tests local agent: openclaw chat --agent local "What can you do?"
   - Compares response time vs cloud model

4. Create `scripts/05-verify-ollama.ps1` that:
   - Checks Ollama service status
   - Verifies GPU acceleration
   - Shows loaded models
   - Tests inference speed

Generate all files now.
```

**Execute in Cursor Terminal:**
```powershell
# Install Ollama
.\scripts\05-install-ollama.ps1

# Setup qwen3:4b
.\scripts\05-pull-model.ps1

# Integrate with OpenClaw
.\scripts\05-integrate-ollama-openclaw.ps1

# Verify
.\scripts\05-verify-ollama.ps1
```

**Mark complete in `DEPLOYMENT_STATUS.md`** ✅

---

## Phase 6: Composio Integrations

### Cursor Prompt (Composer):

```
Phase 6: Setup Composio integrations

TASK: Install Composio, connect services, integrate with OpenClaw

REQUIREMENTS:
1. Create `scripts/06-install-composio.ps1` that:
   - Installs Composio CLI: npm install -g composio-core
   - Verifies installation: composio --version
   - Runs composio login (opens browser for auth)

2. Create `scripts/06-connect-services.ps1` that:
   - Connects Gmail: composio add gmail
   - Connects Google Calendar: composio add googlecalendar
   - Connects Slack: composio add slack
   - Connects Notion: composio add notion
   - Connects GitHub: composio add github
   - Lists connected apps: composio apps
   - Shows connection status

3. Create `scripts/06-integrate-openclaw.ps1` that:
   - Installs OpenClaw plugin: npm install @composio/openclaw-plugin
   - Adds to OpenClaw skills: openclaw skills add composio
   - Creates test missions for each integration

4. Create `config/composio-test-missions.json` with test commands:
   - Gmail: "Check my Gmail for unread messages from today"
   - Calendar: "Create a Google Calendar event for tomorrow at 2pm called 'JARVIS Testing'"
   - Slack: "Send a message to #general saying 'JARVIS is online'"
   - Notion: "List my Notion pages"
   - GitHub: "Show my GitHub repositories"

5. Create `scripts/06-verify-composio.ps1` that:
   - Tests each integration
   - Verifies actions are available in OpenClaw
   - Shows connection status

Generate all files now.
```

**Execute in Cursor Terminal:**
```powershell
# Install Composio
.\scripts\06-install-composio.ps1
# Browser will open - complete authentication

# Connect services
.\scripts\06-connect-services.ps1
# Each service will open browser for OAuth - approve all

# Integrate with OpenClaw
.\scripts\06-integrate-openclaw.ps1

# Verify
.\scripts\06-verify-composio.ps1
```

**Mark complete in `DEPLOYMENT_STATUS.md`** ✅

---

## Phase 7: Phone Access + Firewall

### Cursor Prompt (Composer):

```
Phase 7: Enable phone access to JARVIS

TASK: Configure Windows Firewall, create startup scripts

REQUIREMENTS:
1. Create `scripts/07-configure-firewall.ps1` that:
   - Creates firewall rule for Mission Control (port 3000)
   - Creates firewall rule for LobsterBoard (port 8080)
   - Creates firewall rule for OpenClaw Gateway (port 18789)
   - Creates firewall rule for Ollama (port 11434)
   - Verifies rules are active
   - Shows Windows IP address (<YOUR_LAN_IP>)

2. Create `scripts/07-test-phone-access.ps1` that:
   - Displays URLs for phone access:
     * Mission Control: http://<YOUR_LAN_IP>:3000
     * LobsterBoard: http://<YOUR_LAN_IP>:8080
     * Gateway API: http://<YOUR_LAN_IP>:18789
   - Tests each endpoint is accessible
   - Provides QR codes for easy phone scanning (if possible)

3. Create `scripts/start-jarvis.ps1` (master startup script) that:
   - Starts Docker containers (PostgreSQL, Redis)
   - Starts Mission Control (docker-compose)
   - Starts OpenClaw Gateway
   - Starts LobsterBoard
   - Starts Ollama (if not running as service)
   - Waits for all services to be healthy
   - Displays status dashboard with all URLs
   - Shows startup time

4. Create `scripts/stop-jarvis.ps1` that:
   - Gracefully stops all services
   - Shows shutdown confirmation

5. Create `scripts/restart-jarvis.ps1` that:
   - Stops all services
   - Waits 5 seconds
   - Starts all services
   - Verifies health

6. Create `scripts/status-jarvis.ps1` that:
   - Shows status of all services
   - Tests all endpoints
   - Shows resource usage
   - Displays logs for any failed services

Generate all files now.
```

**Execute in Cursor Terminal:**
```powershell
# Configure firewall (requires admin)
# Right-click PowerShell → Run as Administrator
.\scripts\07-configure-firewall.ps1

# Test phone access
.\scripts\07-test-phone-access.ps1

# Test master startup script
.\scripts\start-jarvis.ps1

# Check status
.\scripts\status-jarvis.ps1
```

**On your phone:**
- Connect to same WiFi
- Open browser
- Visit `http://<YOUR_LAN_IP>:3000` (Mission Control)
- Visit `http://<YOUR_LAN_IP>:8080` (LobsterBoard)

**Mark complete in `DEPLOYMENT_STATUS.md`** ✅

---

## Phase 8: End-to-End Testing

### Cursor Prompt (Composer):

```
Phase 8: Create comprehensive testing suite

TASK: Build automated tests for full JARVIS stack

REQUIREMENTS:
1. Create `scripts/08-test-health.ps1` that:
   - Tests PostgreSQL connection
   - Tests Redis connection
   - Tests Mission Control API
   - Tests OpenClaw Gateway
   - Tests LobsterBoard
   - Tests Ollama
   - Tests Composio connections
   - Shows pass/fail for each service

2. Create `scripts/08-test-voice-flow.ps1` that:
   - Sends test command via OpenClaw API: "Search for AI agent frameworks on GitHub"
   - Waits for mission creation in Mission Control
   - Checks DashClaw decision log
   - Verifies execution
   - Checks receipt recording
   - Shows full flow timeline

3. Create `scripts/08-test-approval-flow.ps1` that:
   - Sends risky command: "Delete test file"
   - Verifies DashClaw intercepts with approval requirement
   - Shows approval request in LobsterBoard
   - Provides manual approval step
   - Verifies execution after approval
   - Checks receipt

4. Create `scripts/08-test-composio.ps1` that:
   - Tests each Composio integration
   - Verifies data retrieval
   - Tests action execution
   - Shows results

5. Create `config/test-results.md` template for recording test outcomes

6. Create `scripts/08-benchmark.ps1` that:
   - Measures response latency for each layer
   - Tests concurrent mission handling
   - Measures GPU vs CPU inference speed
   - Shows performance metrics

Generate all files now.
```

**Execute in Cursor Terminal:**
```powershell
# Run health check
.\scripts\08-test-health.ps1

# Test voice → execution flow
.\scripts\08-test-voice-flow.ps1

# Test approval flow
.\scripts\08-test-approval-flow.ps1

# Test Composio integrations
.\scripts\08-test-composio.ps1

# Run benchmarks
.\scripts\08-benchmark.ps1
```

**Mark complete in `DEPLOYMENT_STATUS.md`** ✅

---

## Master Control Scripts

### Final Cursor Prompt (Composer):

```
Final Phase: Create master control and documentation

TASK: Build comprehensive control scripts and docs

REQUIREMENTS:
1. Create `scripts/jarvis.ps1` (master CLI) with subcommands:
   - jarvis start    → starts all services
   - jarvis stop     → stops all services
   - jarvis restart  → restarts all services
   - jarvis status   → shows health of all services
   - jarvis logs <service> → shows logs for specific service
   - jarvis test     → runs full test suite
   - jarvis backup   → creates backup of databases and configs
   - jarvis restore  → restores from backup
   - jarvis update   → pulls latest versions of all components

2. Create `QUICKSTART.md` with:
   - 5-minute getting started guide
   - Common commands
   - Troubleshooting checklist
   - Phone access instructions

3. Create `ARCHITECTURE.md` with:
   - System diagram
   - Service descriptions
   - Port map
   - Data flow diagrams
   - Integration points

4. Create `TROUBLESHOOTING.md` with:
   - Common issues and solutions
   - Debug commands
   - Log locations
   - Service restart procedures

5. Create `scripts/install-scheduled-tasks.ps1` that:
   - Creates Windows scheduled task to run jarvis.ps1 start on boot
   - Sets up daily backup task
   - Configures log rotation

Generate all files now.
```

**Execute in Cursor Terminal:**
```powershell
# Install scheduled tasks (requires admin)
.\scripts\install-scheduled-tasks.ps1

# Test master CLI
.\scripts\jarvis.ps1 status
.\scripts\jarvis.ps1 test
```

---

## Quick Reference: Daily Usage

**After Week 2 deployment complete:**

```powershell
# Start JARVIS
.\scripts\jarvis.ps1 start

# Check status
.\scripts\jarvis.ps1 status

# View logs
.\scripts\jarvis.ps1 logs mission-control

# Restart a service
.\scripts\jarvis.ps1 restart openclaw

# Run tests
.\scripts\jarvis.ps1 test

# Create backup
.\scripts\jarvis.ps1 backup

# Stop JARVIS
.\scripts\jarvis.ps1 stop
```

**Access points:**
- Mission Control: `http://localhost:3000`
- LobsterBoard: `http://localhost:8080`
- Phone (same WiFi): `http://<YOUR_LAN_IP>:3000`

---

## Why This Cursor Workflow Works

**Advantages:**
1. **All configs in version control** - Track every change
2. **Idempotent scripts** - Safe to re-run
3. **Automated verification** - Catch issues early
4. **Clear checkpoints** - Know exactly where you are
5. **Cursor Composer** - Generates correct PowerShell syntax
6. **Integrated terminal** - Execute without leaving Cursor
7. **Documentation as code** - Everything in one place

**Cursor Features Used:**
- **Composer** (`Cmd/Ctrl + I`): Generate all files at once
- **Terminal**: Execute scripts directly
- **File tree**: See all generated configs
- **Chat**: Troubleshoot specific issues
- **Multi-file edit**: Update configs across files

---

Ready to start? **Copy the Phase 1 Cursor prompt into Composer and begin!** 

Each phase takes 5-15 minutes. After all 8 phases, you'll have a complete JARVIS deployment with scripts to manage it all from Cursor.