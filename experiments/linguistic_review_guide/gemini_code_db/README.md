# AWN4 Gemini CLI Autonomous Linguistic Review Pipeline

Automated pipeline for reviewing all **84,956 noun synsets** in the Arabic WordNet v4 (AWN4).
Each synset is reviewed by a Gemini CLI agent that validates lemmas, checks definitions,
evaluates hypernymy relations, and enriches the synset with Arabic root information and
usage examples — all grounded in a 300 MB+ Arabic dictionary database queried via `sqlite3`.

## Architecture Overview

```
                         campaign.yaml (wave definitions)
                              │
                    wave_controller.py (orchestrator)
                       │         │         │
                    prepare    execute    status/sync
                       │         │
            extract_synset_info.py    docker/run_batch.sh
            (generates prepared/)          │
                                    batch_runner.py (concurrency)
                                           │
                                    run_review.sh (per-synset)
                                           │
                                    gemini -p (Gemini CLI)
                                           │
                                    *.review.yaml (output)
```

### Component Roles

| Component | Role |
|---|---|
| `wave_controller.py` | Campaign lifecycle: partition synsets into waves, track progress, orchestrate |
| `campaign.yaml` | Wave definitions (depth ranges, worker counts, sub-wave sizes) |
| `campaign.db` | SQLite progress database (waves, sub_waves, synset_waves) |
| `generate_bfs_batch.py` | BFS traversal of AWN4 noun hierarchy, outputs batch files |
| `extract_synset_info.py` | Prepares synset metadata + pre-fetched DB evidence |
| `batch_runner.py` | Async concurrent executor with AIMD, model fallback, retry |
| `batch_status.py` | SQLite status DB for per-run tracking (`batch_runs`, `synset_status`, `attempt_log`) |
| `run_review.sh` | Per-synset Gemini CLI invocation with isolated `GEMINI_CLI_HOME` |
| `docker/run_batch.sh` | Docker launcher with egress firewall and volume mounts |
| `review_instructions.md` | System prompt for the Gemini reviewer agent |
| `db_reference.md` | SQL schema reference the agent uses for DB queries |

## Quick Start

### Prerequisites

1. **Python 3.11+** with `wn`, `pyyaml` installed
2. **AWN4** loaded in the `wn` database: `wn download awn:4`
3. **Arabic dictionary DB** at `~/Desktop/MLProjects/wn-project/arabic-dictionaries/db/arabic_dict.db`
4. **Docker** installed (for containerized execution)
5. **Gemini CLI** authenticated via OAuth or API key

### First-Time Setup

```bash
cd experiments/linguistic_review_guide/gemini_code_db

# 1. Initialize the campaign: generates wave batch files and creates campaign.db
python3 wave_controller.py init

# 2. Sync existing reviews (if any) into campaign.db
python3 wave_controller.py sync

# 3. Check campaign status
python3 wave_controller.py status
```

### Typical Workflow

```bash
# Step 1: Prepare a wave (extract synset metadata + evidence from DB)
python3 wave_controller.py prepare W2

# Step 2: Execute the wave (runs reviews inside Docker)
python3 wave_controller.py execute W2

# Step 3: Sync results back to campaign.db
python3 wave_controller.py sync

# Step 4: Check progress
python3 wave_controller.py status
```

---

## Detailed Component Documentation

### 1. `wave_controller.py` — Campaign Lifecycle Manager

The top-level orchestrator that partitions the 84,956 synset review into manageable
BFS-depth waves and tracks progress across sessions.

#### Subcommands

##### `init` — Initialize Campaign

Creates `campaign.db`, generates wave batch files (via `generate_bfs_batch.py`),
and populates the `synset_waves` table.

```bash
python3 wave_controller.py init
python3 wave_controller.py init --force   # Regenerate batch files even if they exist
```

**What it does:**
1. Reads `campaign.yaml` for wave definitions
2. For each wave, calls `generate_bfs_batch.py --min-depth N --max-depth M -o waves/WX.txt`
3. Creates/updates `campaign.db` with wave metadata and per-synset wave assignments

**Output:** `waves/W0.txt` through `waves/W6.txt`, `campaign.db`

##### `status` — Campaign Dashboard

Displays per-wave progress, cost, throughput, and estimated time remaining.

```bash
python3 wave_controller.py status
```

**Sample output:**
```
  AWN4 Noun Review: 188/84,956 (0.2%)
  Prepared: 280  |  Failed: 0  |  Cost: $0.14

  Wave   Status     Progress         Depth    Prepared   Failed
  ---------------------------------------------------------------
  W0     done       31/31            L0-L2    31         0
  W1     partial    157/249          L3       249        0
  W2     pending    0/2212           L4       0          0
  ...

  Throughput: ~188 synsets/day
  Remaining: ~84,768 synsets (~451 days at current rate)
```

##### `sync` — Scan Disk & Update Progress

Scans the output directory for `.review.yaml` files and the `prepared/` directory,
then updates `campaign.db` with actual counts. Also pulls cost and failure data
from `.batch_status.db`.

```bash
python3 wave_controller.py sync
```

**What it does:**
1. Counts `*.review.yaml` files in `output/reviews_gemini_db/`
2. Counts `prepared/*/` directories
3. Updates `synset_waves.reviewed` and `synset_waves.prepared` flags
4. Aggregates per-wave counts into the `waves` table
5. Pulls per-synset costs from `.batch_status.db` and distributes to waves
6. Auto-detects wave status: `done` (all reviewed), `partial` (some reviewed), `pending` (none)

##### `prepare <wave_id>` — Prepare Synset Metadata

Runs `extract_synset_info.py --batch waves/WX.txt` to generate `prepared/{synset_id}/`
directories for each synset in the wave.

```bash
python3 wave_controller.py prepare W2
python3 wave_controller.py prepare W2 --force   # Overwrite existing prepared dirs
```

**What it creates per synset:**
- `prepared/{synset_id}/synset_info.yaml` — Full synset metadata (lemmas, definition, relations, examples)
- `prepared/{synset_id}/synset_info_masked.yaml` — Lemmas removed (for blind lemma generation step)
- `prepared/{synset_id}/evidence.json` — Pre-fetched dictionary evidence (saves 3 DB queries at review time)

##### `execute <wave_id>` — Run Reviews

Launches `docker/run_batch.sh` for the wave. Large waves are automatically split
into sub-waves per the `sub_wave_size` in `campaign.yaml`.

```bash
python3 wave_controller.py execute W2
python3 wave_controller.py execute W2 --workers 4          # Override worker count
python3 wave_controller.py execute W2 --resume             # Resume interrupted run
python3 wave_controller.py execute W4 --continue-on-error  # Don't stop on sub-wave failure
```

**Sub-wave splitting:** When `synset_count > sub_wave_size`, the wave is split into
chunks (e.g., W4 with 48,494 synsets → 17 sub-waves of ~3,000). Sub-waves are executed
sequentially and tracked in the `sub_waves` table.

#### Global Options

```bash
python3 wave_controller.py --config /path/to/campaign.yaml --db /path/to/campaign.db <command>
```

#### Database Schema (`campaign.db`)

```sql
-- Wave-level tracking
CREATE TABLE waves (
    wave_id        TEXT PRIMARY KEY,   -- "W0", "W1", ...
    depth_min      INTEGER NOT NULL,   -- BFS depth range start
    depth_max      INTEGER NOT NULL,   -- BFS depth range end
    synset_count   INTEGER DEFAULT 0,  -- Total synsets in this wave
    batch_file     TEXT,               -- Path to waves/WX.txt
    status         TEXT DEFAULT 'pending',  -- pending|preparing|prepared|executing|partial|done
    prepared_count INTEGER DEFAULT 0,
    reviewed_count INTEGER DEFAULT 0,
    failed_count   INTEGER DEFAULT 0,
    total_cost_usd REAL DEFAULT 0.0,
    started_at     TEXT,
    finished_at    TEXT
);

-- Sub-wave tracking (for large waves that get split)
CREATE TABLE sub_waves (
    sub_wave_id  TEXT PRIMARY KEY,   -- "W4_sub0", "W4_sub1", ...
    wave_id      TEXT NOT NULL,      -- Parent wave
    batch_file   TEXT,
    run_id       TEXT,               -- Links to .batch_status.db
    synset_count INTEGER DEFAULT 0,
    status       TEXT DEFAULT 'pending',
    reviewed     INTEGER DEFAULT 0,
    failed       INTEGER DEFAULT 0,
    cost_usd     REAL DEFAULT 0.0,
    started_at   TEXT,
    finished_at  TEXT
);

-- Per-synset wave assignment
CREATE TABLE synset_waves (
    synset_id   TEXT PRIMARY KEY,  -- "awn4-00001740-n"
    wave_id     TEXT NOT NULL,
    sub_wave_id TEXT,
    bfs_depth   INTEGER,
    prepared    INTEGER DEFAULT 0, -- 1 if prepared/ dir exists
    reviewed    INTEGER DEFAULT 0  -- 1 if .review.yaml exists
);
```

---

### 2. `campaign.yaml` — Wave Definitions

Defines the BFS-depth partitioning and execution parameters for the full campaign.

```yaml
campaign:
  name: "awn4-nouns-full"
  tree_size: 84956                    # Total noun synsets
  output_dir: "../output/reviews_gemini_db"  # Relative to gemini_code_db/
  prepared_dir: "prepared"            # Relative to gemini_code_db/

waves:
  - id: W0
    depth: [0, 2]       # BFS depths L0-L2 (entity, physical/abstract, ...)
    status: done         # Manual override (init uses this as initial status)
    workers: 2

  - id: W1
    depth: [3, 3]        # L3 only
    status: partial
    workers: 2

  - id: W2
    depth: [4, 4]        # L4 only
    workers: 2

  - id: W3
    depth: [5, 6]        # L5-L6
    workers: 2

  - id: W4
    depth: [7, 9]        # L7-L9 (largest wave: 48,494 synsets)
    sub_wave_size: 3000  # Auto-split into ~3000-synset chunks
    workers: 2

  - id: W5
    depth: [10, 13]      # L10-L13
    sub_wave_size: 3000
    workers: 2

  - id: W6
    depth: [14, 99]      # L14+ (leaf nodes)
    workers: 2
```

**Actual synset distribution (from BFS traversal):**

| Wave | Depth | Synsets | % of Tree |
|---|---|---:|---:|
| W0 | L0-L2 | 31 | 0.04% |
| W1 | L3 | 249 | 0.29% |
| W2 | L4 | 2,212 | 2.60% |
| W3 | L5-L6 | 20,745 | 24.42% |
| W4 | L7-L9 | 48,494 | 57.08% |
| W5 | L10-L13 | 12,565 | 14.79% |
| W6 | L14-L16 | 660 | 0.78% |

---

### 3. `generate_bfs_batch.py` — BFS Batch File Generator

Traverses the AWN4 noun hierarchy breadth-first and outputs synset IDs.

```bash
# Full tree
python3 generate_bfs_batch.py -o batches/noun_all.txt

# Specific depth range
python3 generate_bfs_batch.py --min-depth 5 --max-depth 6 -o waves/W3.txt

# Preview stats without writing
python3 generate_bfs_batch.py --dry-run

# Single depth level
python3 generate_bfs_batch.py --min-depth 4 --max-depth 4 -o waves/W2.txt

# Only synsets that have pre-existing evidence
python3 generate_bfs_batch.py --require-evidence -o batch.txt
```

**Output format** (e.g., `waves/W0.txt`):
```
# BFS Noun Batch: L0-L2
# Generated: 2026-03-14T12:22:06Z
# Depth: 0-2 | Total: 31 | Tree: 84956
#
# L0:1 L1:3 L2:27
awn4-00001740-n
awn4-00001930-n
awn4-00002137-n
...
```

The header metadata (Tree size, per-depth counts) is consumed by `batch_runner.py`
for progress percentage display.

---

### 4. `extract_synset_info.py` — Synset Preparation

Generates `prepared/{synset_id}/` directories with metadata and pre-fetched
dictionary evidence for each synset.

```bash
# Single synset
python3 extract_synset_info.py awn4-02592253-n

# Multiple synsets
python3 extract_synset_info.py awn4-02592253-n awn4-03070134-n

# From batch file
python3 extract_synset_info.py --batch waves/W2.txt

# All AWN4 synsets (nouns only)
python3 extract_synset_info.py --all --pos n

# Custom DB path
python3 extract_synset_info.py --batch list.txt --db /path/to/arabic_dict.db

# Force overwrite existing
python3 extract_synset_info.py --batch list.txt --force
```

**Output per synset (`prepared/awn4-XXXXXXXX-n/`):**

| File | Content |
|---|---|
| `synset_info.yaml` | Full synset metadata: lemmas, definition, POS, relations, examples |
| `synset_info_masked.yaml` | Same but with lemmas removed (for blind lemma generation in Step 0.5) |
| `evidence.json` | Pre-fetched dictionary evidence: headword matches, enrichment terms, English bridge translations |

The evidence pre-fetch replaces 3 of the 5 DB queries the reviewer agent would
run at review time, saving ~3 tool-call round-trips per synset.

---

### 5. `batch_runner.py` — Concurrent Batch Executor

Async Python executor that manages parallel Gemini CLI review processes with
adaptive concurrency, model fallback, and automatic retry.

```bash
# Single synset
python3 batch_runner.py awn4-02592253-n --workers 1

# All prepared synsets
python3 batch_runner.py --all --workers 8

# From batch file
python3 batch_runner.py --batch waves/W2.txt --workers 10

# With adaptive AIMD concurrency
python3 batch_runner.py --batch waves/W2.txt --workers 10 --adaptive

# Resume interrupted run (latest)
python3 batch_runner.py --resume --workers 4

# Resume specific run
python3 batch_runner.py --resume --run-id abc12345 --workers 4

# Preview without running
python3 batch_runner.py --batch waves/W2.txt --dry-run

# Custom model
python3 batch_runner.py --all --workers 4 --model pro
```

**Key features:**

- **Adaptive concurrency (AIMD):** Additive increase (+1 worker after 5 consecutive successes), multiplicative decrease (halve on rate limit). Enabled with `--adaptive`.
- **Model fallback chain:** `gemini-3-flash-preview` → `gemini-3.1-pro-preview`. When the primary model is rate-limited, automatically switches to the next. When all models are exhausted and cooldown > 5 minutes, the batch stops gracefully.
- **Exponential backoff:** Retries at 10s, 30s, 90s delays.
- **Rate limit detection:** Parses both trajectory JSONL errors and stderr text for quota/rate limit signals (429, RESOURCE_EXHAUSTED, etc.).
- **Graceful shutdown:** SIGINT/SIGTERM stops launching new reviews, waits for in-flight to complete.
- **Skip-if-exists:** Automatically skips synsets that already have a `.review.yaml` file.
- **Progress reporting:** Every 30s logs batch %, tree %, throughput, ETA, active workers, model status.

**CLI options:**

| Flag | Default | Description |
|---|---|---|
| `--workers N` | 4 | Max concurrent workers (max: 50) |
| `--max-retries N` | 2 | Max retries per synset |
| `--timeout N` | 30 | Per-synset timeout in minutes |
| `--resume` | — | Resume most recent interrupted run |
| `--run-id ID` | — | Resume a specific run by ID |
| `--model NAME` | `gemini-3-flash-preview` | Model override (aliases: `flash`, `pro`) |
| `--adaptive` | — | Enable AIMD adaptive concurrency |
| `--tree-size N` | auto | Total tree size for progress % |
| `--batch FILE` | — | Read synset IDs from file |
| `--all` | — | Process all prepared synsets |
| `--dry-run` | — | List synsets without processing |

---

### 6. `batch_status.py` — Per-Run Status Database

SQLite WAL-mode database for tracking individual review status across concurrent
workers and runs. Used by `batch_runner.py`; also read by `wave_controller.py sync`.

```python
from batch_status import BatchStatusDB
from pathlib import Path

db = BatchStatusDB(Path("output/.batch_status.db"))

# Create a new run
db.create_run("abc123", total_synsets=50, workers=4, model="gemini-3-flash-preview")
db.init_synsets("abc123", ["awn4-001-n", "awn4-002-n"])

# Update status
db.mark_running("awn4-001-n", "abc123", attempt=0)
db.mark_success("awn4-001-n", "abc123", cost_usd=0.0012, duration_s=85.0)
db.mark_failed("awn4-002-n", "abc123", exit_code=1, error="timeout", duration_s=1800.0)

# Query
stats = db.get_stats("abc123")
# {'pending': 0, 'running': 0, 'success': 1, 'failed': 1, 'skipped': 0, 'total_cost': 0.0012}

resumable = db.get_resumable_synsets("abc123")
# [('awn4-002-n', 0)]

db.finish_run("abc123", "completed")
```

**Schema (`.batch_status.db`):**

| Table | Purpose |
|---|---|
| `batch_runs` | Per-run metadata: run_id, timestamps, model, cost, status |
| `synset_status` | Per-synset status within a run: pending → running → success/failed/skipped |
| `attempt_log` | Forensic log of every attempt (survives retry overwrites) |

---

### 7. `run_review.sh` — Per-Synset Gemini CLI Invocation

Shell script that invokes the Gemini CLI once for a single synset review.
Called by `batch_runner.py` as a subprocess.

```bash
# Single synset (direct use, requires Gemini auth)
./run_review.sh awn4-02592253-n

# All prepared synsets (sequential, no concurrency)
./run_review.sh --all

# Environment variable overrides
MODEL=gemini-3.1-pro-preview MAX_TURNS=80 ./run_review.sh awn4-02592253-n
```

**Environment variables:**

| Variable | Default | Description |
|---|---|---|
| `MODEL` | `gemini-3-flash-preview` | Gemini model to use |
| `MAX_TURNS` | `80` | Max agent turns per review |
| `ARABIC_DICT_DB` | Hard-coded path | Path to Arabic dictionary SQLite DB |
| `PREPARED_DIR` | `./prepared` | Input directory with synset metadata |
| `OUTPUT_DIR` | `../output/reviews_gemini_db` | Output directory for review YAML |

**Per-synset isolation:** Each invocation creates a temporary `GEMINI_CLI_HOME`
directory with fresh settings.json, preventing session state from leaking between reviews.
The temporary directory is cleaned up after each review completes.

---

### 8. `docker/run_batch.sh` — Docker Launcher

Runs the full batch pipeline inside a Docker container with security hardening.

```bash
# All synsets, 4 workers (default)
./docker/run_batch.sh

# Custom workers
./docker/run_batch.sh --workers 8

# From batch file
./docker/run_batch.sh --batch /path/to/batch.txt --workers 10 --adaptive

# Resume interrupted run
./docker/run_batch.sh --resume --workers 4

# Single synset
./docker/run_batch.sh --workers 2 awn4-02592253-n

# Custom model
MODEL=gemini-3.1-pro-preview ./docker/run_batch.sh --workers 10
```

**Docker container features:**
- **Egress firewall:** Default-deny whitelist (only Gemini API endpoints allowed)
- **Read-only inputs:** `prepared/`, `spec/`, `review_instructions.md`, `db_reference.md`, `arabic_dict.db`
- **Writable output:** `/output` volume mount for review YAML and status DB
- **Auth passthrough:** Mounts `~/.gemini/oauth_creds.json` read-only, or passes `GEMINI_API_KEY`
- **OOM protection:** `NODE_OPTIONS=--max-old-space-size=4096`
- **NET_ADMIN/NET_RAW caps:** Required for iptables firewall setup inside container

---

## Output Format

### Review Files (`*.review.yaml`)

Each synset produces a YAML file with a 6-step review schema:

```yaml
step0_evidence:           # Dictionary evidence (confirm/contradict/expand)
  per_lemma:
    - lemma: "طين"
      confirm: [...]
      contradicts: [...]
      expands: [...]

step05_lemma_generation:  # Blind lemma candidates (evidence + knowledge-based)
  evidence_candidates: [...]
  knowledge_candidates: [...]

step1_lemma_validation:   # Per-lemma decision (confirmed/rejected/modified)
  per_lemma:
    - lemma: "طين"
      decision: "confirmed"
      actions: [...]      # create_entry, add_sense, remove_sense

step3_definition:         # Definition review (retain/revise)
  current_definition: "..."
  assessment:
    decision: "retain"
  authored_definitions: [...]

step4_relations:          # Hypernymy/antonymy validation
  hypernymy:
    current_hypernym: "..."
    test_result: "correct"
  actions: [...]          # add/remove synset relations

step5_enrichment:         # Root, examples, cultural fit, POS check
  per_lemma:
    - lemma: "طين"
      enrichment:
        root: "ط-ي-ن"
      examples: [...]
  cultural_fit:
    assessment: "native"
  actions: [...]          # add_synset_example
```

### Trajectory Files (`*.trajectory.jsonl`)

Gemini CLI stream-json output. Each line is a JSON event:

```jsonl
{"type":"turn_start","turn":1}
{"type":"tool_call","name":"read_file","args":{"path":"..."}}
{"type":"tool_result","name":"read_file","result":"..."}
{"type":"text","content":"Reviewing synset..."}
{"type":"result","status":"success","stats":{"input_tokens":45000,"output_tokens":8000}}
```

### Log Files (`*.stderr.log`)

Gemini CLI stderr output. Contains auth status, errors, and quota messages.

---

## Wave Batch Files (`waves/`)

Generated by `wave_controller.py init`. Each file lists synset IDs for a depth range:

```
# BFS Noun Batch: L0-L2
# Generated: 2026-03-14T12:22:06Z
# Depth: 0-2 | Total: 31 | Tree: 84956
#
# L0:1 L1:3 L2:27
awn4-00001740-n
awn4-00001930-n
...
```

The header is parsed by `batch_runner.py` for the `Tree:` size (used in progress %).

---

## Common Operations

### Check overall progress
```bash
python3 wave_controller.py sync && python3 wave_controller.py status
```

### Resume after quota reset
```bash
# batch_runner skips synsets with existing .review.yaml files,
# so just re-execute the wave — no --resume needed
python3 wave_controller.py execute W1
```

### Inspect a specific review
```bash
cat output/reviews_gemini_db/awn4-02592253-n.review.yaml
```

### Count completed reviews
```bash
ls output/reviews_gemini_db/*.review.yaml | wc -l
```

### Check for failures in current run
```bash
sqlite3 output/reviews_gemini_db/.batch_status.db \
  "SELECT synset_id, error_message FROM synset_status WHERE status='failed' ORDER BY synset_id"
```

### Query batch run history
```bash
sqlite3 output/reviews_gemini_db/.batch_status.db \
  "SELECT run_id, started_at, status, total_synsets, total_cost_usd FROM batch_runs ORDER BY started_at"
```

### Check token usage per model
```bash
sqlite3 output/reviews_gemini_db/.batch_status.db \
  "SELECT model, COUNT(*), SUM(total_cost_usd) FROM batch_runs GROUP BY model"
```

---

## Troubleshooting

### Quota exhaustion (`TerminalQuotaError`)
The OAuth free tier allows ~150 synsets/day. When exhausted, `batch_runner.py`
automatically falls back from `gemini-3-flash-preview` to `gemini-3.1-pro-preview`.
If both are exhausted, the batch stops. Wait for quota reset (~24h) and re-execute.

### `--resume` picks wrong run
`batch_runner.py --resume` grabs the latest run by `started_at`. If test runs happened
after your main batch, `--resume` may resume the wrong run. Use `--run-id <ID>` instead,
or simply re-execute without `--resume` (skip-if-exists handles dedup).

### YAML parse errors in reviews
Gemini occasionally outputs non-standard YAML keys (e.g., Arabic-keyed fields with
incorrect indentation). These are cosmetic issues in optional notes sections and don't
affect the actionable data (lemma decisions, definition updates, relation changes).

### Docker build fails
Ensure Docker Desktop is running. The image includes `node:20`, Gemini CLI, Python 3,
sqlite3, and iptables. First build takes ~2 minutes.

```bash
cd docker && docker build -t gemini-reviewer-db .
```
