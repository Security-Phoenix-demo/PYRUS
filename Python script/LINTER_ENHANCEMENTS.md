# Enhanced Linter - Structural YAML Validation

## Overview

The Linter has been significantly enhanced to catch **structural YAML errors** that cause data loss or unexpected behavior. These errors occur when YAML parsers silently overwrite duplicate keys, leading to missing data without any error messages.

## What's New

### 1. Duplicate Key Detection

The linter now detects duplicate keys at **all levels** of the YAML structure:

- **Top-level keys**: `DeploymentGroups:`, `Environment Groups:`, etc.
- **Dictionary keys**: Duplicate fields within components, services, environments
- **Distinguishes between**:
  - Duplicate keys (ERROR - data loss)
  - List items (OK - multiple entries are valid)

#### Example - Critical Error

```yaml
DeploymentGroups:
  - AppName: Application1
    Components: [...]

# ❌ DUPLICATE KEY - Second DeploymentGroups overwrites first!
DeploymentGroups:
  - AppName: Application2
    Components: [...]
```

**Result**: Only `Application2` is processed. `Application1` is silently lost.

**Linter Detection**:
```
🔴 DUPLICATE KEY: 'DeploymentGroups' found at top-level
Line 8 (first occurrence: line 1)
💡 SOLUTION: Merge all applications under a single 'DeploymentGroups:' section. 
   Remove the duplicate 'DeploymentGroups:' on line 8 and move its applications 
   under the first 'DeploymentGroups:' on line 1.
```

#### Example - Valid YAML (Not a Duplicate)

```yaml
Components:
  - ComponentName: Component1  # ✅ Valid list item
    Status: Active
  - ComponentName: Component2  # ✅ Valid list item
    Status: Active
```

**Result**: Both components are processed correctly.

### 2. Comprehensive Structure Validation

The enhanced linter validates:

✅ **Required sections exist**
- `DeploymentGroups` must be present
- Proper YAML root structure (dictionary, not list)

✅ **Empty sections detection**
- Empty `DeploymentGroups` list
- Empty `Environment Groups` list
- Applications without Components
- Environments without Services

✅ **Duplicate names within scope**
- Duplicate application names
- Duplicate component names within same application
- Duplicate environment names
- Duplicate service names within same environment

✅ **Data type validation**
- `DeploymentGroups` must be a list
- Each application must be a dictionary
- Proper nesting of components/services

### 3. Helpful Error Messages with Solutions

Every error includes:
1. **What** the error is
2. **Where** it occurs (line numbers)
3. **Why** it's a problem
4. **How** to fix it (specific solution)

#### Example Output

```
🔴 DUPLICATE KEY: 'Deployment_set' found at indent-4
Location: Line 165 (first occurrence: line 161)
💡 SOLUTION: Remove or rename the duplicate key 'Deployment_set' on line 165. 
   The first occurrence is on line 161.

🔴 DUPLICATE SERVICE NAME: 'kessel-AuditReport-awsdev' in environment 'Backoffice-Dev'
💡 SOLUTION: Rename duplicate services or merge them if they represent the same service.
```

## New Linter Functions

### `validate_yaml_structure(yaml_file_path)`

Comprehensive structural validation - **Use this first!**

```python
from providers.Linter import validate_yaml_structure

is_valid, errors = validate_yaml_structure('Resources/my-config.yaml')

if not is_valid:
    print("Errors found:")
    for error in errors['duplicate_keys']:
        print(f"  - {error['error']}")
        print(f"    {error['suggestion']}")
```

**Returns**:
- `is_valid`: Boolean indicating if structure is valid
- `errors`: Dictionary with categories:
  - `duplicate_keys`: [] - Duplicate key errors
  - `missing_keys`: [] - Required keys not found
  - `empty_sections`: [] - Empty lists/sections
  - `structure_errors`: [] - Invalid YAML structure
  - `warnings`: [] - Non-critical issues

### `detect_duplicate_keys_in_yaml(yaml_content)`

Focused duplicate key detection only.

```python
from providers.Linter import detect_duplicate_keys_in_yaml

has_duplicates, duplicate_info = detect_duplicate_keys_in_yaml('path/to/file.yaml')

if has_duplicates:
    for dup in duplicate_info:
        print(f"Duplicate '{dup['key']}' at line {dup['line']}")
        print(f"  {dup['suggestion']}")
```

## Integration with Validation Scripts

### `validate_yaml_detailed.py` (Enhanced)

Now includes **structural validation** before component/service validation:

```bash
python3 validate_yaml_detailed.py Resources/my-config.yaml
```

**Workflow**:
1. ✅ **Structure Check** - Validates YAML structure first
   - If errors found → Stop and display fixes needed
   - If valid → Continue to next steps
2. ✅ **Application/Component Validation**
3. ✅ **Environment/Service Validation**
4. ✅ **Comprehensive Report** with success rates

### `test_linter_structure.py` (New)

Standalone structural validation tool:

```bash
python3 test_linter_structure.py Resources/my-config.yaml
```

**Features**:
- Fast structural-only validation
- Colored output with clear error messages
- Detailed suggestions for each error
- Exit codes: 0 (success), 1 (errors found)

## Common Structural Errors & Solutions

### Error 1: Duplicate Top-Level Keys

**Problem**:
```yaml
DeploymentGroups:
  - AppName: App1

DeploymentGroups:  # ❌ Duplicate!
  - AppName: App2
```

**Solution**:
```yaml
DeploymentGroups:
  - AppName: App1
  - AppName: App2  # ✅ Merged under single key
```

### Error 2: Duplicate Field in Component

**Problem**:
```yaml
Components:
  - ComponentName: MyComponent
    Status: Active
    Deployment_set: set1
    Deployment_set: set2  # ❌ Duplicate! Only set2 is used
```

**Solution**:
```yaml
Components:
  - ComponentName: MyComponent
    Status: Active
    Deployment_set: set2  # ✅ Remove duplicate, keep correct value
```

### Error 3: Duplicate Service Names

**Problem**:
```yaml
Services:
  - Service: myservice-dev
    Type: Application
  - Service: myservice-dev  # ❌ Duplicate name!
    Type: Database
```

**Solution** (Option 1 - Different services):
```yaml
Services:
  - Service: myservice-app-dev  # ✅ Renamed to be unique
    Type: Application
  - Service: myservice-db-dev   # ✅ Renamed to be unique
    Type: Database
```

**Solution** (Option 2 - Same service):
```yaml
Services:
  - Service: myservice-dev  # ✅ Merged into one
    Type: Application
    # Include all relevant fields from both duplicates
```

### Error 4: Empty Sections

**Problem**:
```yaml
DeploymentGroups: []  # ❌ Empty list

Environment Groups:
  - Name: Dev
    Services: []  # ⚠️ Warning: No services
```

**Solution**:
```yaml
DeploymentGroups:
  - AppName: MyApp
    Responsable: owner@company.com
    ReleaseDefinitions: []
    Components: [...]

Environment Groups:
  - Name: Dev
    Services:
      - Service: my-service
        Type: Application
```

## Technical Implementation Details

### Key Algorithm Features

1. **Scope-Based Tracking**:
   - Each YAML list item creates a new scope
   - Duplicate detection is scope-aware
   - List items don't trigger false positives

2. **Context Preservation**:
   - Tracks indentation levels
   - Maintains parent-child relationships
   - Properly handles nested structures

3. **Line Number Tracking**:
   - Records first occurrence of each key
   - Tracks all subsequent duplicates
   - Provides accurate line references for fixes

### Code Comments

The code includes detailed comments explaining:
- **What**: What each section does
- **Why**: Why the logic is structured that way
- **How**: How the algorithm works

Example from `detect_duplicate_keys_in_yaml`:
```python
# Track keys in current dictionary scope
# Structure: {(indent_level, section_id): {key: [line_numbers]}}
# section_id helps differentiate between different list items
keys_by_scope = {}

# New list item = new scope at this indentation level
# Clear current scope at this level and deeper
current_scope = {k: v for k, v in current_scope.items() if k < indent}
```

## Best Practices

### 1. Run Structural Validation First

Always validate structure before running the main script:

```bash
# Step 1: Check structure
python3 test_linter_structure.py Resources/my-config.yaml

# Step 2: If valid, run validation
python3 validate_yaml_detailed.py Resources/my-config.yaml

# Step 3: If valid, run main script
python3 run.py Resources/
```

### 2. Fix Duplicates by Merging, Not Deleting

When you find duplicate keys:
- ✅ **DO**: Merge content under the first occurrence
- ❌ **DON'T**: Just delete one - you might lose data

### 3. Use Unique Names

- Application names should be unique across all DeploymentGroups
- Component names should be unique within each Application
- Service names should be unique within each Environment
- Environment names should be unique across all Environment Groups

### 4. Keep Sections Non-Empty

- Don't create empty `DeploymentGroups: []`
- Don't create environments with no services
- Add at least one component per application

## Testing

### Test Files Included

1. **test_linter_structure.py**: Structural validation tester
2. **validate_yaml_detailed.py**: Enhanced with structural checks

### Creating Test Cases

To test duplicate detection:

```yaml
# test_duplicates.yaml
DeploymentGroups:
  - AppName: Test1
    Components: []

DeploymentGroups:  # Intentional duplicate to test
  - AppName: Test2
    Components: []
```

Then run:
```bash
python3 test_linter_structure.py test_duplicates.yaml
```

## Performance

- **Fast**: Parses raw YAML text (no full parsing until structure validated)
- **Efficient**: Single-pass algorithm for duplicate detection
- **Scalable**: Works with large YAML files (tested up to 2600+ lines)

## Questions & Troubleshooting

### Q: Why is my YAML file losing data?

**A**: Likely due to duplicate keys. Run:
```bash
python3 test_linter_structure.py your-file.yaml
```

### Q: How do I know if list items or duplicate keys?

**A**: The linter distinguishes automatically:
- **List items**: `- ComponentName:` (multiple allowed)
- **Dictionary keys**: `Deployment_set:` (duplicates flagged)

### Q: Can I disable structural validation?

**A**: Not recommended, but you can skip by using YamlHelper functions directly. However, this risks data loss from duplicate keys.

### Q: What if I get too many warnings?

**A**: Warnings are non-critical. Focus on errors first (duplicate keys, missing keys, structure errors).

## Summary

The enhanced linter provides:
✅ Early detection of structural errors
✅ Prevents data loss from duplicate keys
✅ Clear, actionable error messages
✅ Solution suggestions for every error
✅ Integration with existing validation workflow
✅ Fast, efficient validation

**Always run structural validation before processing your YAML files!**

