# Phoenix Security PYRUS - Developer Quick Start Guide

**Version**: 4.9.2  
**Last Updated**: February 2026

This guide provides everything a developer needs to get started with the Phoenix Security PYRUS project.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Initial Setup](#2-initial-setup)
3. [Configuration Basics](#3-configuration-basics)
4. [Running the Script](#4-running-the-script)
5. [Validation & Linting](#5-validation--linting)
6. [Common Development Tasks](#6-common-development-tasks)
7. [Debugging](#7-debugging)
8. [Code Style Guidelines](#8-code-style-guidelines)
9. [Testing](#9-testing)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.8+ (3.10+ recommended) | Runtime environment |
| pip | Latest | Package management |
| Git | 2.x+ | Version control |

### Required Access

- Phoenix Security API credentials (Client ID & Client Secret)
- Access to Phoenix Security tenant

### Optional Tools

| Tool | Purpose |
|------|---------|
| VS Code / Cursor | Recommended IDE with YAML support |
| Docker | For scanner service deployment |

---

## 2. Initial Setup

### Clone the Repository

```bash
git clone <repository-url>
cd autoconfig-priv-latest
```

### Install Dependencies

```bash
cd "Python script"
pip install -r requirements.txt
```

### Configure Credentials

**Option 1: Environment Variables (Recommended)**
```bash
export PHOENIX_CLIENT_ID="your-client-id"
export PHOENIX_CLIENT_SECRET="your-client-secret"
```

**Option 2: config.ini File**
```bash
cp Resources/config.ini.example Resources/config.ini
# Edit Resources/config.ini with your credentials
```

### Verify Installation

```bash
# Test import of core modules
python3 -c "from providers.Phoenix import *; print('Phoenix SDK loaded')"
python3 -c "from providers.YamlHelper import *; print('YamlHelper loaded')"
python3 -c "from providers.Linter import *; print('Linter loaded')"
```

---

## 3. Configuration Basics

### Project Structure

```
autoconfig-priv-latest/
├── Python script/
│   ├── run-phx.py              # Main CLI entry point
│   ├── providers/              # Core modules
│   │   ├── Phoenix.py          # Phoenix API SDK
│   │   ├── YamlHelper.py       # YAML parser
│   │   ├── Linter.py           # Validation
│   │   └── Utils.py            # Utilities
│   └── Resources/
│       ├── run-config.yaml     # Runtime configuration
│       └── core-structure.yaml # YAML template
├── Utils/                      # Utility scripts
└── Documentation/              # API docs
```

### Key Configuration Files

#### run-config.yaml

```yaml
# Configuration files to load
ConfigFiles:
  - core-structure.yaml           # Root level file
  - /subfolder/client-config.yaml # Subfolder path

# Optional settings
CreateUsersForApplications: true  # Auto-create users
TeamsFolder: /teams               # Teams folder
EnableHives: false                # Hives feature
```

#### core-structure.yaml

```yaml
DeploymentGroups:
  - AppName: MyApplication
    Status: Production
    TeamNames:
      - DevTeam
    ReleaseDefinitions: []
    Responsable: user@example.com
    Tier: 2
    Components:
      - ComponentName: backend-service
        RepositoryName: org/backend
        AssetType: REPOSITORY
        Tags:
          - "service:backend"

Environment Groups:
  - Name: Production
    Type: CLOUD
    Status: Production
    Responsable: user@example.com
    Tier: 1
    Services:
      - Service: web-cluster
        Type: Cloud
        AssetType: CLOUD
        ProviderAccountId:
          - "account-uuid"
```

---

## 4. Running the Script

### Basic Commands

```bash
cd "Python script"

# Full setup (teams, apps, cloud)
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --action_teams=true \
  --action_code=true \
  --action_cloud=true

# Teams only
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --action_teams=true

# Applications only
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --action_code=true

# Cloud/Services only
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --action_cloud=true
```

### Performance Modes

```bash
# Development (full validation)
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --verification-mode=immediate \
  --action_cloud=true

# Production (balanced)
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --verification-mode=hybrid \
  --action_cloud=true

# CI/CD (maximum speed)
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --verification-mode=disabled \
  --silent \
  --action_cloud=true
```

### Common Flag Combinations

| Use Case | Command |
|----------|---------|
| Initial setup | `--action_teams=true --action_code=true --action_cloud=true` |
| Update apps | `--action_code=true` |
| Update services | `--action_cloud=true` |
| CI/CD pipeline | `--silent --verification-mode=disabled` |
| Debugging | `--verbose --debug-save-response` |

---

## 5. Validation & Linting

### Quick Validation

```bash
cd "Python script"
python3 -c "
from providers.Linter import *
import yaml

with open('Resources/core-structure.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Validate applications
for app in config.get('DeploymentGroups', []):
    valid, errors = validate_application(app)
    status = '✅' if valid else '❌'
    print(f'{status} {app.get(\"AppName\")}: {errors if not valid else \"OK\"}')

# Validate environments
for env in config.get('Environment Groups', []):
    valid, errors = validate_environment(env)
    status = '✅' if valid else '❌'
    print(f'{status} {env.get(\"Name\")}: {errors if not valid else \"OK\"}')
"
```

### Full Validation Script

```bash
# Create a validation script
python3 validate_yaml_detailed.py Resources/core-structure.yaml
```

### Common Validation Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `L001: Required list field as string` | `ProviderAccountId: "uuid"` | Change to list: `ProviderAccountId: ["uuid"]` |
| `L002: Invalid AssetType` | Using unsupported type | Use: REPOSITORY, CONTAINER, CLOUD, etc. |
| `L003: Missing required field` | Missing `AppName`, etc. | Add required field |
| `L004: Invalid email format` | Bad email in Responsable | Fix email format |

### Required List Fields (Always Lists)

```yaml
# CORRECT
ProviderAccountId:
  - "uuid-1"
TeamNames:
  - "Team1"
Tags:
  - "tag1"
Fqdn:
  - "api.example.com"

# INCORRECT
ProviderAccountId: "uuid-1"    # Must be list!
TeamNames: "Team1"             # Must be list!
Tags: "tag1"                   # Must be list!
```

---

## 6. Common Development Tasks

### Adding a New Scanner Translator

1. **Create translator file**:
```bash
cd Utils/Loading_Script_V5_PUB/scanner_translators/
cp base_translator.py new_scanner_translator.py
```

2. **Implement translate method**:
```python
# new_scanner_translator.py
from .base_translator import BaseTranslator

class NewScannerTranslator(BaseTranslator):
    def translate(self, raw_data: dict) -> dict:
        # Transform scanner output to Phoenix format
        return {
            "assets": [...],
            "vulnerabilities": [...]
        }
```

3. **Register in `__init__.py`**:
```python
from .new_scanner_translator import NewScannerTranslator
```

4. **Add documentation** to README.md

### Extending YAML Schema

1. **Update Linter.py** with new field:
```python
# In component_schema dict
"NewField": {"type": "string", "required": False}
```

2. **Update YamlHelper.py** to parse field:
```python
# In populate_applications_from_config()
new_field = component.get('NewField')
```

3. **Update Phoenix.py** to use field:
```python
# In create_custom_component()
if 'NewField' in component:
    payload['newField'] = component['NewField']
```

4. **Update documentation**:
   - `YAML_CONFIGURATION_GUIDE.md`
   - `.cursor/rules/phoenix-project-master.mdc`

### Adding a New CLI Flag

1. **Add argument in run-phx.py**:
```python
parser.add_argument(
    '--new-feature',
    type=str,
    default='default-value',
    help='Description of new feature'
)
```

2. **Pass to function**:
```python
result = phoenix.some_function(
    new_feature=args.new_feature
)
```

3. **Update README.md** with flag documentation

---

## 7. Debugging

### Enable Verbose Output

```bash
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --verbose \
  --action_cloud=true
```

### Save API Responses

```bash
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --debug-save-response \
  --json-to-save 10 \
  --action_cloud=true
```

Debug files saved to: `Python script/debug/`

### Check Error Logs

```bash
# View error log
cat "Python script/errors.log"

# View run log
cat "Python script/run-log.log"
```

### Debug YAML Loading

```python
# Test YAML loading
from providers.YamlHelper import *
import yaml

with open('Resources/core-structure.yaml', 'r') as f:
    config = yaml.safe_load(f)

print(f"Applications: {len(config.get('DeploymentGroups', []))}")
print(f"Environments: {len(config.get('Environment Groups', []))}")
```

### Common Debug Scenarios

| Issue | Debug Command |
|-------|--------------|
| API errors | `--debug-save-response` |
| YAML parsing | Python YAML load test |
| Validation errors | Run linter directly |
| Service not created | Check `--verbose` output |

---

## 8. Code Style Guidelines

### Python Style

```python
def process_entity(entity: dict) -> dict:
    """
    Process a single entity.
    
    Args:
        entity: Entity dictionary with required fields
        
    Returns:
        Result dictionary with success status
    """
    # Guard clauses at top
    if not entity:
        logger.error("Entity is None")
        return {"success": False, "error": "Empty entity"}
    
    if "name" not in entity:
        logger.error(f"Missing 'name' in entity: {entity}")
        return {"success": False, "error": "Missing name"}
    
    # Happy path last
    try:
        result = api_call(entity)
        logger.info(f"Processed: {entity['name']}")
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Failed: {entity['name']}, error: {e}")
        return {"success": False, "error": str(e)}
```

### Documentation Requirements

Every code change must include:

1. **Inline comment** (1-2 lines) with `#`
2. **README.md update** if user-facing
3. **CHANGELOG entry** or release note
4. **Name of change** in documentation

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Variables | snake_case with verbs | `is_valid`, `has_errors` |
| Functions | snake_case | `create_component()` |
| Classes | PascalCase | `EntityValidator` |
| Constants | UPPER_SNAKE | `MAX_BATCH_SIZE` |
| Files | lowercase with underscores | `yaml_helper.py` |

---

## 9. Testing

### Unit Tests

```bash
cd "Python script"
python3 -m pytest tests/
```

### Sample Test Files

Test files in `Python script/tests/Sample files/`:
- `core-structure.yaml` - Valid configuration
- `axelot.yaml` - Client example
- `hives.yaml` - Hives configuration

### Validation Testing

```bash
# Validate sample file
python3 -c "
from providers.Linter import validate_application
import yaml

with open('tests/Sample files/core-structure.yaml', 'r') as f:
    config = yaml.safe_load(f)

for app in config.get('DeploymentGroups', []):
    valid, errors = validate_application(app)
    print(f'{app.get(\"AppName\")}: {valid}')
"
```

### Integration Testing

```bash
# Dry run (validate only, no API calls)
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --validate-only \
  --action_cloud=true
```

---

## 10. Troubleshooting

### Common Issues

#### "Required list field as string" Error

**Problem**: Field like `ProviderAccountId` defined as string instead of list.

**Fix**:
```yaml
# Wrong
ProviderAccountId: "uuid-here"

# Correct
ProviderAccountId:
  - "uuid-here"
```

#### "Invalid AssetType" Error

**Problem**: Using unsupported AssetType value.

**Fix**: Use one of the 10 valid types:
- `REPOSITORY`, `SOURCE_CODE`, `BUILD`, `WEBSITE_API`
- `CONTAINER`, `INFRA`, `CLOUD`
- `WEB`, `FOSS`, `SAST`

#### Script Hanging

**Problem**: Script hangs during API calls.

**Solutions**:
1. Check network connectivity
2. Verify API credentials
3. Use `--verification-mode=disabled` for faster execution
4. Check `errors.log` for details

#### YAML Parse Error

**Problem**: YAML syntax error causing parse failure.

**Debug**:
```python
import yaml
try:
    with open('file.yaml', 'r') as f:
        yaml.safe_load(f)
    print("Valid YAML")
except yaml.YAMLError as e:
    print(f"Error: {e}")
```

**Common causes**:
- Mixed tabs and spaces
- Incorrect indentation
- Missing colons
- Unquoted special characters

#### API 409 Conflict Error

**Problem**: Entity already exists.

**Solutions**:
- Script will automatically update existing entities
- Check if duplicate names in different scopes
- Use `--verbose` to see conflict details

### Getting Help

1. Check documentation:
   - `YAML_CONFIGURATION_GUIDE.md`
   - `YAML_QUICK_REFERENCE.md`
   - `ARCHITECTURE.md`

2. Review error logs:
   - `Python script/errors.log`
   - `Python script/run-log.log`

3. Check release notes for recent changes:
   - `zrelease/` folder
   - `zchangelog-details/` folder

---

## Quick Reference Card

### Essential Commands

```bash
# Navigate to script directory
cd "Python script"

# Full execution
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --action_teams=true \
  --action_code=true \
  --action_cloud=true

# Validate only
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --validate-only

# Debug mode
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --verbose \
  --debug-save-response

# Fast CI/CD mode
python3 run-phx.py CLIENT_ID CLIENT_SECRET \
  --silent \
  --verification-mode=disabled
```

### Required List Fields

Always use YAML list format for:
- `ProviderAccountId`
- `ProviderAccountName`
- `ResourceGroup`
- `TeamNames`
- `Tags`, `Tags_label`, `Tags_rule`
- `Fqdn`, `Hostnames`, `OsNames`, `Netbios`

### Valid AssetTypes

| Software | Infrastructure |
|----------|---------------|
| REPOSITORY | CONTAINER |
| SOURCE_CODE | INFRA |
| BUILD | CLOUD |
| WEBSITE_API | |
| WEB | |
| FOSS | |
| SAST | |

---

## Related Documentation

- [Architecture Overview](ARCHITECTURE.md)
- [YAML Configuration Guide](YAML_CONFIGURATION_GUIDE.md)
- [YAML Quick Reference](YAML_QUICK_REFERENCE.md)
- [Utilities Catalog](UTILITIES_CATALOG.md)
- [Version History](VERSION_HISTORY.md)
