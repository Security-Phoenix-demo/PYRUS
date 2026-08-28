<!-- For minimal context usage, read /DOC_INDEX.md first, then load only the documents relevant to the current task. -->

# PYRUS — System Map

## 1. System Overview

PYRUS (Phoenix YAML Resource Unified Sync) is a YAML-native CMDB automation framework that syncs asset ownership, team structure, vulnerability attribution, and environment configuration into the **Phoenix Security** platform via its REST API. It replaces manual CMDB management with git-driven, CI/CD-integrated configuration.

**Version**: 4.9.2 | **Language**: Python 3.11+ | **Primary API**: Phoenix Security Enterprise v1.22

## 2. Repository Ownership and Boundaries

| Boundary | Owner |
|----------|-------|
| Core engine (`Python script/`) | PYRUS maintainers |
| Utility scripts (`Utils/`) | PYRUS maintainers + client contributors |
| Client configs (`Resources/`) | Per-client (sensitive) |
| Scanner translators (`Utils/Loading_Script_V5_PUB/`) | PYRUS team |
| PowerShell port (`Power Shell script/`) | Legacy, not actively maintained |

## 3. High-Level Architecture

```
YAML Configs → YamlHelper (parse) → Linter (validate) → Phoenix.py (API SDK) → Phoenix Security Platform
                                                          ↑
                                             AutoGroupEngine (tag-based grouping)
```

Two entry points: `run-phx.py` (current, full-featured CLI) and `run.py` (legacy, deprecated).

## 4. Entry Points

| Entry Point | Path | Purpose |
|-------------|------|---------|
| **run-phx.py** | `Python script/run-phx.py` | Main CLI — teams, apps, envs, services, deployments |
| run.py (legacy) | `Python script/run.py` | Deprecated legacy entry |
| run.py (root) | `run.py` | Simplified root-level entry |
| Multi-scanner import | `Utils/Loading_Script_V5_PUB/phoenix_multi_scanner_enhanced.py` | Scanner result imports |
| Report generators | `Utils/report-dashboard/` | Executive PDF/Excel reports |

## 5. Core Runtime Flow Summary

1. **Parse CLI args** — credentials, action flags, API domain, verification mode
2. **Load run-config.yaml** — resolve config file list, GitHub repos, settings
3. **Parse YAML configs** — `YamlHelper.py` loads and merges DeploymentGroups, EnvironmentGroups
4. **Validate** — `Linter.py` checks schema, required fields, types
5. **Authenticate** — OAuth token from Phoenix API
6. **Execute actions** (in order): Teams → Environments → Services → Applications → Components → Deployments
7. **Generate report** — execution summary with per-file breakdown

See: `/docs/architecture/RUNTIME_FLOWS.md`

## 6. High-Risk Areas

| Area | Risk | Details |
|------|------|---------|
| `Phoenix.py` (10,452 lines) | **Critical** | All API calls, caching, rule creation — any change can break sync |
| `YamlHelper.py` (970 lines) | **High** | Config parsing — affects all downstream processing |
| `run-phx.py` (2,966 lines) | **High** | Orchestration logic, report generation |
| YAML schema | **High** | Backwards compatibility required for all client configs |
| `Linter.py` (1,307 lines) | **Medium** | Schema validation — false negatives pass bad data through |
| `AutoGroupEngine.py` (1,056 lines) | **Medium** | Asset grouping at scale (250K+) |

See: `/docs/architecture/CHANGE_BLAST_RADIUS.md`

## 7. Documentation Map

```
/DOC_INDEX.md                          ← Start here (routing)
/CLAUDE.md                             ← This file (system map)
/docs/
  architecture/
    SYSTEM_OVERVIEW.md                 ← Detailed system purpose & capabilities
    REPOSITORY_MAP.md                  ← Module layout & relationships
    RUNTIME_FLOWS.md                   ← Step-by-step execution flows
    DEPENDENCY_GRAPH.md                ← Module dependency chains
    DATA_CONTRACTS.md                  ← YAML schemas, API contracts
    SERVICE_TOPOLOGY.md                ← Internal/external service interactions
    CHANGE_BLAST_RADIUS.md             ← Impact analysis per module
    MODULE_OWNERSHIP.md                ← Responsibility boundaries
  operations/
    RUNBOOK.md                         ← Operating PYRUS
    FAILURE_MODES.md                   ← Common failures & recovery
    DEPLOYMENT.md                      ← CI/CD & deployment
  security/
    SECURITY_MODEL.md                  ← Auth, secrets, trust
    TRUST_BOUNDARIES.md                ← Trust zones
  integrations/
    EXTERNAL_INTEGRATIONS.md           ← Third-party APIs & services
  development/
    LOCAL_DEVELOPMENT.md               ← Setup & run locally
    TESTING_STRATEGY.md                ← Test approach
    SAFE_CHANGE_ZONES.md               ← Safe vs risky modification areas
```

Existing docs preserved: `ARCHITECTURE.md`, `YAML_CONFIGURATION_GUIDE.md`, `YAML_QUICK_REFERENCE.md`, `UTILITIES_CATALOG.md`, `DEVELOPER_QUICK_START.md`, `docs/pyrus-core/DOC-*`

## 8. Documentation Loading Guide

| Task | Load These Documents |
|------|---------------------|
| General understanding | `DOC_INDEX.md` → `CLAUDE.md` → `docs/architecture/SYSTEM_OVERVIEW.md` |
| Architecture tracing | `CLAUDE.md` → `docs/architecture/REPOSITORY_MAP.md` → `RUNTIME_FLOWS.md` → `DEPENDENCY_GRAPH.md` |
| Runtime debugging | `CLAUDE.md` → `docs/architecture/RUNTIME_FLOWS.md` → `docs/operations/FAILURE_MODES.md` |
| Schema/contract changes | `CLAUDE.md` → `docs/architecture/DATA_CONTRACTS.md` → `CHANGE_BLAST_RADIUS.md` |
| Integration changes | `CLAUDE.md` → `docs/integrations/EXTERNAL_INTEGRATIONS.md` → `SERVICE_TOPOLOGY.md` |
| Security review | `CLAUDE.md` → `docs/security/SECURITY_MODEL.md` → `TRUST_BOUNDARIES.md` |
| Production incident | `CLAUDE.md` → `docs/operations/RUNBOOK.md` → `FAILURE_MODES.md` |
| Onboarding | `DOC_INDEX.md` → `CLAUDE.md` → `DEVELOPER_QUICK_START.md` → `docs/development/LOCAL_DEVELOPMENT.md` |

## 9. Rules for Safe Changes

1. **Never modify `Phoenix.py` without understanding the full call chain** — it's the API substrate for everything
2. **YAML schema changes require updating**: `Linter.py`, `YamlHelper.py`, `Phoenix.py`, `YAML_CONFIGURATION_GUIDE.md`, `.cursor/rules/phoenix-yaml-schema.mdc`
3. **Test with `--verification-mode=immediate`** before using deferred mode
4. **Client config files in `Resources/` contain sensitive data** — never commit real credentials
5. **The `run.py` files (root and `Python script/run.py`) are legacy** — all new work goes in `run-phx.py`
6. **Utils/ scripts are largely independent** — safe to modify without affecting core engine

## 10. Known Unknowns

- Exact API rate limits for Phoenix Security API are not documented in this repo
- Production deployment topology (where PYRUS runs in client environments) varies per client
- Some client-specific Resources/ subdirectories contain configs whose full schema is unclear
- The PowerShell port's feature parity with the Python version is uncertain
- `AutoGroupEngine.py` checkpoint file format is not formally specified
- Error recovery behavior when Phoenix API is partially available is not fully tested
