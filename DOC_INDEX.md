<!-- This file is the compressed documentation router. Read this first to decide which documents to load. -->

# PYRUS Documentation Index

**System**: PYRUS (Phoenix YAML Resource Unified Sync) v4.9.2
**Purpose**: YAML-native CMDB automation for Phoenix Security — asset ownership, vulnerability attribution, metadata sync

## Documentation Domains

| Domain | Authoritative Document | When to Load |
|--------|----------------------|--------------|
| System overview | `/CLAUDE.md` | Always — start here |
| Architecture deep-dive | `/docs/architecture/SYSTEM_OVERVIEW.md` | Understanding system design |
| Repository layout | `/docs/architecture/REPOSITORY_MAP.md` | Finding code, onboarding |
| Runtime execution | `/docs/architecture/RUNTIME_FLOWS.md` | Debugging, tracing flows |
| Dependencies | `/docs/architecture/DEPENDENCY_GRAPH.md` | Impact analysis |
| Data contracts | `/docs/architecture/DATA_CONTRACTS.md` | Schema/API changes |
| Service topology | `/docs/architecture/SERVICE_TOPOLOGY.md` | Integration changes |
| Change risk | `/docs/architecture/CHANGE_BLAST_RADIUS.md` | Before modifying code |
| Operations | `/docs/operations/RUNBOOK.md` | Running/maintaining PYRUS |
| Failure modes | `/docs/operations/FAILURE_MODES.md` | Incident response |
| Security | `/docs/security/SECURITY_MODEL.md` | Security review |
| Integrations | `/docs/integrations/EXTERNAL_INTEGRATIONS.md` | External API changes |
| Local dev | `/docs/development/LOCAL_DEVELOPMENT.md` | Getting started |
| Testing | `/docs/development/TESTING_STRATEGY.md` | Writing/running tests |
| Utilities | `/UTILITIES_CATALOG.md` | Using utility scripts |
| YAML schema | `/YAML_CONFIGURATION_GUIDE.md` | Writing YAML configs |

## Task-Based Routing

- **"How does PYRUS work?"** → `CLAUDE.md` → `docs/architecture/SYSTEM_OVERVIEW.md`
- **"I need to modify Phoenix.py"** → `docs/architecture/CHANGE_BLAST_RADIUS.md` → `docs/architecture/RUNTIME_FLOWS.md`
- **"Something is failing"** → `docs/operations/FAILURE_MODES.md` → `docs/operations/RUNBOOK.md`
- **"Adding a new YAML field"** → `YAML_CONFIGURATION_GUIDE.md` → `docs/architecture/DATA_CONTRACTS.md`
- **"Security review"** → `docs/security/SECURITY_MODEL.md` → `docs/security/TRUST_BOUNDARIES.md`
- **"Import scanner results"** → `UTILITIES_CATALOG.md` (section 1)
- **"Generate reports"** → `UTILITIES_CATALOG.md` (section 3)
- **"Publish sanitized Utils to the public Phoenix Utils repository"** → `Utils/UTILS_PUBLISH_TO_PUBLIC.md` (`Utils/publish_utils_to_public_repo.py`)

## High-Risk Areas (Load Docs Before Changing)

- `Python script/providers/Phoenix.py` — 10K+ line API SDK, highest blast radius
- `Python script/providers/YamlHelper.py` — Config parsing, affects all downstream
- `Python script/run-phx.py` — Main orchestrator, 3K lines
- `Python script/Resources/core-structure.yaml` — Client config data
- YAML schema fields — backwards compatibility required
