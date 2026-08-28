# Phoenix Security PYRUS - Architecture Overview

**Version**: 4.9.2  
**Last Updated**: February 2026

## Table of Contents

1. [System Overview](#system-overview)
2. [Core Philosophy](#core-philosophy)
3. [Architecture Diagram](#architecture-diagram)
4. [Component Details](#component-details)
5. [Data Flow](#data-flow)
6. [Key Files Reference](#key-files-reference)
7. [Module Dependencies](#module-dependencies)
8. [Extension Points](#extension-points)

---

## System Overview

**PYRUS** (Phoenix YAML Resource Unified Sync) is a YAML-native CMDB automation framework designed to:

- **Unify asset ownership** across cloud-native and DevSecOps environments
- **Automate vulnerability attribution** to the correct teams
- **Synchronize metadata** from CI/CD pipelines, cloud tags, and service catalogs
- **Replace static CMDBs** with dynamic, code-defined configuration

### Key Capabilities

| Capability | Description |
|------------|-------------|
| **Asset Grouping** | Automatically group assets by service, owner, and business unit |
| **Vulnerability Attribution** | Attribute vulnerabilities to the right team instantly |
| **Live Inventory** | Maintain continuously updated inventory aligned with infrastructure |
| **Multi-Source Integration** | Consume metadata from GitHub, GitLab, AWS, Azure, GCP, Backstage, ServiceNow |

---

## Core Philosophy

> **"If you can tag it, PYRUS can sync it."**

### Design Principles

1. **YAML-First**: All configuration defined in YAML files, version-controlled alongside code
2. **Developer Ownership**: Teams define ownership in their repositories
3. **Continuous Sync**: Configuration automatically syncs to Phoenix Security
4. **Plugin Architecture**: Extensible translator system for different data sources
5. **Self-Healing**: Automatic reassignment when ownership, services, or tags change

### CMDB Evolution

| Legacy CMDB | PYRUS Approach |
|-------------|----------------|
| Manual and outdated | Git-driven and always current |
| Lives outside Dev workflow | Lives in your repository |
| Requires ticketing and change boards | CI/CD-native automation |
| No context for risk | Full code-to-cloud visibility |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCES                                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ CI/CD    │  │ Cloud    │  │ Service  │  │ Identity │  │ Security │          │
│  │ Pipelines│  │ Providers│  │ Catalogs │  │ Systems  │  │ Scanners │          │
│  │ (GitHub, │  │ (AWS,    │  │(Backstage│  │ (Okta,   │  │(44+ tools│          │
│  │  GitLab) │  │  Azure)  │  │ ServiceN)│  │  AD)     │  │ supported│          │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘          │
│       │             │             │             │              │                 │
└───────┼─────────────┼─────────────┼─────────────┼──────────────┼─────────────────┘
        │             │             │             │              │
        └─────────────┴─────────────┼─────────────┴──────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         PYRUS CORE ENGINE                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   ┌─────────────────────┐     ┌─────────────────────┐                          │
│   │   YAML Config       │     │   run-config.yaml   │                          │
│   │   (core-structure)  │     │   (runtime config)  │                          │
│   └──────────┬──────────┘     └──────────┬──────────┘                          │
│              │                           │                                      │
│              └───────────┬───────────────┘                                      │
│                          ▼                                                      │
│   ┌──────────────────────────────────────────────────────────────────────┐     │
│   │                     YamlHelper.py                                     │     │
│   │  • Configuration parsing and loading                                  │     │
│   │  • Multi-condition rule processing                                    │     │
│   │  • Subfolder path resolution                                          │     │
│   └──────────────────────────┬───────────────────────────────────────────┘     │
│                              ▼                                                  │
│   ┌──────────────────────────────────────────────────────────────────────┐     │
│   │                       Linter.py                                       │     │
│   │  • Schema validation                                                  │     │
│   │  • Required field checking                                            │     │
│   │  • AssetType enumeration validation                                   │     │
│   │  • List field format enforcement                                      │     │
│   └──────────────────────────┬───────────────────────────────────────────┘     │
│                              ▼                                                  │
│   ┌──────────────────────────────────────────────────────────────────────┐     │
│   │                      Phoenix.py (API SDK)                             │     │
│   │  • Application & Component management                                 │     │
│   │  • Environment & Service management                                   │     │
│   │  • Team & User management                                             │     │
│   │  • Rule creation & batch processing                                   │     │
│   │  • Caching & verification strategies                                  │     │
│   └──────────────────────────┬───────────────────────────────────────────┘     │
│                              │                                                  │
│   ┌──────────────────────────┴───────────────────────────────────────────┐     │
│   │                    AutoGroupEngine.py                                 │     │
│   │  • Intelligent tag-based asset grouping                               │     │
│   │  • 250K+ asset handling                                               │     │
│   │  • Checkpoint & resume system                                         │     │
│   └──────────────────────────────────────────────────────────────────────┘     │
│                                                                                  │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    PHOENIX SECURITY PLATFORM                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                   │
│   │  Applications  │  │  Environments  │  │     Teams      │                   │
│   │  & Components  │  │  & Services    │  │   & Users      │                   │
│   └────────────────┘  └────────────────┘  └────────────────┘                   │
│                                                                                  │
│   ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                   │
│   │  Asset Rules   │  │  Deployments   │  │ Vulnerability  │                   │
│   │  & Matching    │  │  & Linking     │  │  Attribution   │                   │
│   └────────────────┘  └────────────────┘  └────────────────┘                   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. CLI Entry Point (`run-phx.py`)

**Purpose**: Main command-line interface for executing PYRUS operations

**Key Responsibilities**:
- Parse command-line arguments
- Initialize Phoenix API client
- Orchestrate action execution (teams, code, cloud, deployment)
- Generate execution reports
- Handle error recovery and logging

**Key Parameters**:
```bash
--action_teams=true          # Team management
--action_code=true           # Application/component management
--action_cloud=true          # Environment/service management
--action_deployment=true     # Deployment linking
--verification-mode={mode}   # Validation strategy
--silent                     # CI/CD mode
--quick-check N              # Sampling validation
```

### 2. YAML Parser (`YamlHelper.py`)

**Purpose**: Parse and process YAML configuration files

**Key Functions**:
| Function | Purpose |
|----------|---------|
| `load_config()` | Load and merge configuration files |
| `populate_applications_from_config()` | Extract DeploymentGroups |
| `populate_environments_from_env_groups_from_config()` | Extract Environment Groups |
| `load_multi_condition_rule()` | Process MULTI_MultiConditionRules |

**Configuration Resolution**:
1. Load `run-config.yaml` for file list
2. Resolve subfolder paths (`/folder/file.yaml`)
3. Merge multiple YAML files
4. Process inheritance and defaults

### 3. Configuration Linter (`Linter.py`)

**Purpose**: Validate YAML configurations against schema

**Validation Checks**:
- Required fields present (`AppName`, `ReleaseDefinitions`, `Responsable`)
- Field types correct (lists vs strings)
- AssetType values valid (10 enumerated types)
- Email format validation
- Multi-condition rule structure

**Error Codes**:
| Code | Description |
|------|-------------|
| L001 | Required list field as string |
| L002 | Invalid AssetType value |
| L003 | Missing required field |
| L004 | Invalid email format |

### 4. Phoenix API SDK (`Phoenix.py`)

**Purpose**: Interface with Phoenix Security API

**Core Classes/Functions**:

| Area | Functions |
|------|-----------|
| **Applications** | `create_application()`, `update_application()`, `get_applications()` |
| **Components** | `create_custom_component()`, `update_component()`, `create_component_rules()` |
| **Environments** | `create_environment()`, `get_environments()` |
| **Services** | `add_service()`, `add_environment_services()`, `create_service_rules()` |
| **Teams** | `create_team()`, `assign_team_members()`, `get_teams()` |
| **Rules** | `create_multicondition_component_rules()`, `create_multicondition_service_rules()` |
| **Verification** | `ServiceVerificationStrategy`, `EntityValidator`, `BatchVerificationEngine` |

**Caching System**:
- Environment service cache with TTL
- Component cache for batch operations
- Intelligent fallback on cache miss

### 5. Auto-Group Engine (`AutoGroupEngine.py`)

**Purpose**: Intelligent asset grouping based on tags and metadata

**Features**:
- Tag-based grouping with frequency analysis
- Smart fallback strategies for untagged assets
- Checkpoint & resume system (Ctrl+C safe)
- Interactive and batch modes
- 250K+ asset handling capability

**Grouping Strategies**:
1. Application tag grouping
2. Team tag grouping
3. Custom tag grouping
4. Asset-type specific fallbacks (CIDR, hostname, repository, container name)

### 6. Utilities (`Utils.py`)

**Purpose**: Common utility functions

**Categories**:
- String manipulation and path handling
- Date/time formatting
- API response processing
- Logging helpers

---

## Data Flow

### Configuration Processing Flow

```
1. LOAD CONFIGURATION
   ├── Read run-config.yaml
   ├── Resolve ConfigFiles paths
   ├── Load each YAML file
   └── Merge configurations

2. VALIDATE CONFIGURATION
   ├── Schema validation (Linter.py)
   ├── Required field checks
   ├── Type validation
   └── Business rule validation

3. PROCESS ENTITIES (ordered)
   ├── Teams & Users
   ├── Applications
   │   └── Components (with rules)
   ├── Environments
   │   └── Services (with rules)
   └── Deployments

4. CREATE RULES
   ├── Standard asset matching rules
   ├── Multi-condition rules
   └── Tag-based rules

5. VERIFY & REPORT
   ├── Deferred verification (if enabled)
   ├── Success/failure tracking
   └── Execution report generation
```

### API Interaction Pattern

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Check     │────▶│   Create/   │────▶│   Create    │
│   Exists    │     │   Update    │     │   Rules     │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Cache     │     │   Entity    │     │   Rule      │
│   Lookup    │     │   API Call  │     │   API Call  │
└─────────────┘     └─────────────┘     └─────────────┘
```

---

## Key Files Reference

### Core Application Files

| File | Lines | Purpose |
|------|-------|---------|
| `Python script/run-phx.py` | ~1200 | Main CLI entry point |
| `Python script/providers/Phoenix.py` | ~3500 | Phoenix API SDK |
| `Python script/providers/YamlHelper.py` | ~800 | YAML parsing |
| `Python script/providers/Linter.py` | ~600 | Validation |
| `Python script/providers/AutoGroupEngine.py` | ~1500 | Auto-grouping |
| `Python script/providers/Utils.py` | ~300 | Utilities |

### Configuration Files

| File | Purpose |
|------|---------|
| `Python script/Resources/run-config.yaml` | Runtime configuration |
| `Python script/Resources/core-structure.yaml` | Main YAML template |
| `Python script/requirements.txt` | Python dependencies |

### Documentation Files

| File | Purpose |
|------|---------|
| `README.md` | Project overview |
| `YAML_CONFIGURATION_GUIDE.md` | YAML field reference |
| `YAML_QUICK_REFERENCE.md` | Quick lookup |
| `ARCHITECTURE.md` | This document |
| `UTILITIES_CATALOG.md` | Utility scripts catalog |
| `DEVELOPER_QUICK_START.md` | Onboarding guide |

---

## Module Dependencies

```
run-phx.py
    ├── providers/Phoenix.py
    │       ├── providers/Utils.py
    │       └── providers/YamlHelper.py
    │               └── providers/Linter.py
    ├── providers/AutoGroupEngine.py
    │       └── providers/Phoenix.py
    └── providers/autogroup_orchestrator.py
            └── providers/AutoGroupEngine.py
```

### External Dependencies

| Package | Purpose |
|---------|---------|
| `requests` | HTTP client for API calls |
| `pyyaml` | YAML parsing |
| `python-dateutil` | Date handling |
| `urllib3` | HTTP utilities |

---

## Extension Points

### Adding a New Scanner Translator

1. Create `Utils/Loading_Script_V5_PUB/scanner_translators/{scanner}_translator.py`
2. Inherit from `base_translator.py`
3. Implement `translate()` method
4. Register in `__init__.py`
5. Add documentation to `README.md`

### Extending YAML Schema

1. Add field to schema in `Linter.py`
2. Update parsing in `YamlHelper.py`
3. Handle in `Phoenix.py` API calls
4. Update documentation in `YAML_CONFIGURATION_GUIDE.md`
5. Update `.cursor/rules/phoenix-project-master.mdc`

### Adding New Utility Script

1. Create folder in `Utils/` with descriptive name
2. Include `README.md` with usage instructions
3. Add entry to `UTILITIES_CATALOG.md`
4. Follow Python code style guidelines

### Adding New CLI Flag

1. Add argument parsing in `run-phx.py`
2. Pass to appropriate provider function
3. Update CLI documentation in `README.md`
4. Add example to `.cursor/rules/phoenix-project-master.mdc`

---

## Performance Characteristics

### Verification Modes

| Mode | Speed | Validation | Use Case |
|------|-------|------------|----------|
| `immediate` | Baseline | Real-time | Development |
| `deferred` | 10-50x faster | End-only | Large deployments |
| `hybrid` | 5-10x faster | Periodic | Production (default) |
| `disabled` | Maximum | None | Trusted CI/CD |

### Scale Capabilities

- **Assets**: 250K+ with auto-grouping
- **Services**: 1000+ in minutes (deferred mode)
- **API Optimization**: 60-70% reduction with batching
- **Cache Hit Rate**: 98% with intelligent fallback

---

## Related Documentation

- [YAML Configuration Guide](YAML_CONFIGURATION_GUIDE.md) - Complete field reference
- [YAML Quick Reference](YAML_QUICK_REFERENCE.md) - Quick lookup card
- [Utilities Catalog](UTILITIES_CATALOG.md) - All utility scripts
- [Developer Quick Start](DEVELOPER_QUICK_START.md) - Onboarding guide
- [Version History](VERSION_HISTORY.md) - Release notes
