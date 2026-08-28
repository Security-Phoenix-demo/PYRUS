# Phoenix Security PYRUS - Version History

**Current Version**: 4.9.2  
**Last Updated**: February 2026

This document provides a consolidated history of all major releases, features, and changes.

---

## Table of Contents

1. [Version Overview](#version-overview)
2. [Current Release (v4.9.x)](#current-release-v49x)
3. [v4.8.x Series](#v48x-series)
4. [v4.5.x Series](#v45x-series)
5. [CLI Command Evolution](#cli-command-evolution)
6. [Feature Timeline](#feature-timeline)
7. [Breaking Changes](#breaking-changes)

---

## Version Overview

| Version | Release Date | Highlights |
|---------|-------------|------------|
| **v4.9.2** | Jan 2026 | Latest stable release |
| **v4.9.0** | Nov 2025 | Auto-grouping, 250K+ assets, checkpoints |
| **v4.8.9** | Oct 2025 | Rule payload debug save |
| **v4.8.8** | Oct 2025 | Multi-YAML tracking, per-file reporting |
| **v4.8.7** | Sep 2025 | Services & components tracking dashboard |
| **v4.8.6** | Sep 2025 | Multi-deployment strategies |
| **v4.8.5** | Sep 2025 | Enhanced validation, deferred verification |
| **v4.8.4** | Aug 2025 | Quick-check mode, 50x performance |
| **v4.8.3** | Aug 2025 | Tag logic overhaul, repository path shortening |
| **v4.5.2** | Aug 2025 | Execution reporting, application tags |
| **v4.5.1** | Aug 2025 | Subfolder support |
| **v4.5.0** | Jul 2025 | Major tag logic separation |

---

## Current Release (v4.9.x)

### v4.9.2 (January 2026)
**Type**: Maintenance Release

- Documentation updates
- Bug fixes and stability improvements
- Enhanced error messages

### v4.9.0 (November 2025)
**Type**: Major Feature Release

#### Intelligent Auto-Grouping

```bash
# New auto-group feature
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --action_create_components_from_assets=true
```

**Key Features**:
- **Tag-Based Grouping**: Automatically group 250K+ assets by Application, Team, or custom tags
- **Frequency Analysis**: Smart tag frequency detection for optimal grouping
- **Smart Fallback**: Asset-type specific handling for untagged assets
  - CIDR-based for network assets
  - Hostname-based for infrastructure
  - Repository name for code assets
  - Container name for containers

#### Checkpoint & Resume System

- **Interruption-Safe**: Ctrl+C safe execution with zero work lost
- **3-Level Checkpointing**:
  1. Tag analysis checkpoint
  2. Grouping plan checkpoint
  3. Creation progress checkpoint
- **Resume Capability**: Continue from last checkpoint after interruption

#### Operational Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| Interactive | Guided setup with prompts | First-time configuration |
| Batch | Fully automated | CI/CD pipelines |

#### Performance

- Handles 250K+ assets in 4-5 hours
- Production validation included
- 350+ configuration options

---

## v4.8.x Series

### v4.8.9 (October 2025)
**Type**: Enhancement Release

#### Rule Payload Debug Save

**New Features**:
- Automatic payload capture for all rule creation
- Multi-status tracking (request, success, 409 conflicts, 400 errors)
- 19 integration points across components, services, rules
- Persistent JSON storage for offline analysis

```bash
# Enable payload capture
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --debug-save-response \
  --action_cloud=true
```

---

### v4.8.8 (October 2025)
**Type**: Enhancement Release

#### Multi-YAML Configuration Tracking

**New Features**:
- Per-file configuration tracking
- Source YAML filename in every error
- Comprehensive configuration preview before processing
- Per-file breakdown in reports

**Example Output**:
```
Processing File 1/3: core-structure.yaml
  Applications: 15
  Environments: 3
  Services: 45
  Components: 120
```

---

### v4.8.7 (September 2025)
**Type**: Enhancement Release

#### Enhanced Services & Components Tracking

**New Features**:
- Key metrics dashboard with prominent display
- Priority reporting (services and components first)
- Final summary section with quick-reference totals
- Enhanced visibility for created/failed items

**Report Format**:
```
📦 SERVICES CREATED: 45/50 (90% success)
🔧 COMPONENTS CREATED: 120/125 (96% success)
```

---

### v4.8.6 (September 2025)
**Type**: Major Feature Release

#### Multi-Deployment Strategy System

**Three Deployment Strategies**:

| Strategy | Field | Description |
|----------|-------|-------------|
| Service Name | `Deployment_set` | Direct component-to-service matching |
| Deployment Tag | `Deployment_tag` | Tag-based service selector |
| App Inheritance | (automatic) | Inherit from parent application |

**Component-Level Control**:
```yaml
DeploymentGroups:
  - AppName: WebApplication
    Deployment_set: web-app-services    # Application default
    Components:
      - ComponentName: Frontend
        Deployment_set: frontend-services  # Component-specific
      - ComponentName: Backend
        # Inherits web-app-services
```

**Benefits**:
- Granular control at component level
- Flexible matching (direct + tag-based)
- Automatic inheritance reduces complexity
- Batch processing with retry mechanisms

---

### v4.8.5 (September 2025)
**Type**: Major Enhancement Release

#### Enhanced Validation System

**Business Rules Engine**:
- Same service, same environment → Update rules
- Same component, same application → Update rules
- Same service, different environments → Allow with naming
- Same component, different applications → Allow with naming

#### Optional Deferred Verification

**Four Verification Modes**:

| Mode | Speed | Validation | Use Case |
|------|-------|------------|----------|
| `immediate` | Baseline | Real-time | Development |
| `deferred` | 10-50x faster | End-only | Large deployments |
| `hybrid` | 5-10x faster | Periodic | Production (default) |
| `disabled` | Maximum | None | Trusted CI/CD |

```bash
# Use deferred mode for large deployments
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --verification-mode=deferred \
  --action_cloud=true
```

---

### v4.8.4 (August 2025)
**Type**: Performance Breakthrough Release

#### Quick-Check Mode

```bash
# Validate every 20 services
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --quick-check 20 \
  --action_cloud=true
```

**Performance Gains**:
| Configuration | Speed Improvement |
|--------------|-------------------|
| `--quick-check 10` | ~10x faster |
| `--quick-check 20` | ~20x faster |
| `--silent` | ~25x faster |
| `--silent --quick-check 50` | ~50x faster |

#### Silent Mode

```bash
# Perfect for CI/CD
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --silent \
  --action_cloud=true
```

#### Rule Batching

- Batch component rule creation
- 60-70% reduction in API calls
- Smart fallback to individual operations

#### Cache Improvements

- Race condition fix for service detection
- Intelligent fallback on cache miss
- 98% cache hit rate

---

### v4.8.3 (August 2025)
**Type**: Major Overhaul Release

#### Tag Logic Separation

**New Field Purposes**:
| Field | Purpose | Creates |
|-------|---------|---------|
| `Tag_label` / `Tags_label` | Component metadata | Tags on entity |
| `Tag` / `Tags` | Asset matching | Rules to find assets |
| `Tag_rule` / `Tags_rule` | Asset matching | Rules to find assets |

**Migration**:
```yaml
# Before (unclear purpose)
Tags:
  - 'Environment: Production'

# After (explicit - for metadata)
Tags_label:
  - 'Environment: Production'

# After (explicit - for asset matching)
Tags:
  - 'Environment: Production'
```

#### Repository Path Shortening

```yaml
# Before
RepositoryName: gitlab.com/org/development/platform/service

# After (automatic)
RepositoryName: platform/service  # Last 2 segments
```

#### Processing Order Fix

Correct order:
1. Component/Service creation with labels
2. Standard asset matching rules
3. Multi-condition rules

---

## v4.5.x Series

### v4.5.2 (August 2025)
**Type**: Feature Release

#### Comprehensive Execution Reporting

**New Capabilities**:
- Real-time operation tracking
- Component creation tracking
- Visual status indicators (✅ ⚠️ ❌)
- Performance metrics
- Error log integration

**Report Sections**:
- Teams: creation, rules, assignments
- Applications: creation, configuration
- Components: individual tracking
- Environments: creation, updates
- Services: creation, rules
- Cloud assets: rules, third-party

#### Application-Level Tag Support

- Full `Tag_label` processing at application level
- RiskFactor tag support
- Debug logging for tag processing

---

### v4.5.1 (August 2025)
**Type**: Enhancement Release

#### Subfolder Support

```yaml
# run-config.yaml
ConfigFiles:
  - core-structure.yaml                    # Root level
  - /client1/client1-config.yaml          # Subfolder
  - /production/prod-apps.yaml            # Environment-based
```

**Path Syntax**:
- Subfolder: `/folder/file.yaml` (leading slash)
- Root: `file.yaml` (no slash)
- Relative to `Resources/` directory

---

### v4.5.0 (July 2025)
**Type**: Major Release

#### Tag Logic Foundation

- Initial separation of component metadata and asset matching
- Foundation for v4.8.3 improvements
- Schema updates for new tag fields

---

## CLI Command Evolution

### v4.5 Commands

```bash
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --action_teams=true \
  --action_code=true \
  --action_cloud=true
```

### v4.8.4+ Commands (Performance)

```bash
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --action_cloud=true \
  --quick-check 20 \
  --silent
```

### v4.8.5+ Commands (Verification)

```bash
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --action_cloud=true \
  --verification-mode=deferred \
  --verification-batch-size 100
```

### v4.9+ Commands (Auto-Grouping)

```bash
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --action_create_components_from_assets=true
```

---

## Feature Timeline

```
Jul 2025  │ v4.5.0 - Tag logic foundation
          │
Aug 2025  │ v4.5.1 - Subfolder support
          │ v4.5.2 - Execution reporting
          │ v4.8.3 - Tag logic overhaul
          │ v4.8.4 - Performance breakthrough (50x)
          │
Sep 2025  │ v4.8.5 - Deferred verification
          │ v4.8.6 - Multi-deployment strategies
          │ v4.8.7 - Services tracking dashboard
          │
Oct 2025  │ v4.8.8 - Multi-YAML tracking
          │ v4.8.9 - Debug payload capture
          │
Nov 2025  │ v4.9.0 - Auto-grouping (250K+ assets)
          │
Jan 2026  │ v4.9.2 - Current stable release
```

---

## Breaking Changes

### v4.8.3: Tag Field Clarification

**Impact**: Low (backward compatible)

The `Tags` field now explicitly creates asset matching rules (original behavior restored). If you were using `Tags` for component metadata, migrate to `Tags_label`.

### v4.8.5: Verification Mode Default

**Impact**: Low (performance improvement)

Default verification mode changed from `immediate` to `hybrid`. Use `--verification-mode=immediate` for previous behavior.

### v4.5.0: List Field Requirements

**Impact**: Medium (validation enforcement)

The following fields now require list format:
- `ProviderAccountId`
- `TeamNames`
- `Tags`, `Tags_label`, `Tags_rule`
- `Fqdn`, `Hostnames`, `OsNames`, `Netbios`

**Migration**:
```yaml
# Before (may have worked)
ProviderAccountId: "uuid-here"

# After (required)
ProviderAccountId:
  - "uuid-here"
```

---

## Detailed Release Notes

For comprehensive release details, see:

- [`zrelease/RELEASE_NOTES V 4.8.4.md`](zrelease/RELEASE_NOTES%20V%204.8.4.md) - v4.8.3 and v4.8.4
- [`zrelease/RELEASE_V4.8.5.md`](zrelease/RELEASE_V4.8.5.md) - v4.8.5
- Change details in [`zchangelog-details/`](zchangelog-details/) folder

---

## Related Documentation

- [Architecture Overview](ARCHITECTURE.md)
- [YAML Configuration Guide](YAML_CONFIGURATION_GUIDE.md)
- [Developer Quick Start](DEVELOPER_QUICK_START.md)
- [Utilities Catalog](UTILITIES_CATALOG.md)
