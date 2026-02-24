# YAML Validation Guide

## 🔍 Overview

This guide explains how to validate Phoenix Security YAML configuration files with detailed success rate reporting for **Components** (under Applications) and **Services** (under Environment Groups).

---

## 📋 Available Validation Scripts

### 1. **validate_yaml_detailed.py** (Recommended)
**Purpose**: Comprehensive validation with separate success rates for Components and Services

**Features**:
- ✅ Validates DeploymentGroups (Applications)
- ✅ Validates Components under each Application
- ✅ Validates Environment Groups
- ✅ Validates Services under each Environment Group
- ✅ Shows **separate success rates** for Components vs Services
- ✅ Detailed error reporting with line-by-line breakdown
- ✅ Color-coded output (✅ success, ⚠️ warnings, ❌ errors)

**Usage**:
```bash
cd "Python script"

# Validate default file (core-structure-backoffice-with-env-demo.yaml)
python3 validate_yaml_detailed.py

# Validate specific file
python3 validate_yaml_detailed.py Resources/q2/core-structure-backoffice-with-env-demo.yaml

# Validate any YAML file
python3 validate_yaml_detailed.py path/to/your/config.yaml
```

**Output Example**:
```
================================================================================
🔍 PHOENIX SECURITY YAML VALIDATION REPORT
================================================================================
📄 File: Resources/q2/core-structure-backoffice-with-env-demo.yaml

📦 VALIDATING DEPLOYMENT GROUPS & COMPONENTS
--------------------------------------------------------------------------------
✅ DeploymentGroup: BackOffice
   BU: BackOffice
   Status: Production
   Components: 23
   ✅ Component: backofficeapi
      Deployment_set: backoffice-api
      Status: Production
   ✅ Component: console-ui
      Deployment_set: console-ui
      Status: Production
   ...

🌍 VALIDATING ENVIRONMENT GROUPS & SERVICES
--------------------------------------------------------------------------------
✅ Environment Group: Backoffice-Prod
   Type: CLOUD
   Status: Production
   Services: 15
   ✅ Service: q2_backoffice-api-awsprd
      Deployment_set: backoffice-api
      Type: Cloud
   ✅ Service: q2_console-ui-awsprd
      Deployment_set: console-ui
      Type: Cloud
   ...

================================================================================
📊 VALIDATION SUMMARY
================================================================================

✅ DEPLOYMENT GROUPS (Applications):
   Total:      1
   Valid:      1
   Invalid:    0
   Success Rate: 100.0%

✅ COMPONENTS (under Applications):
   Total:      23
   Valid:      23
   Invalid:    0
   Success Rate: 100.0%

✅ ENVIRONMENT GROUPS:
   Total:      5
   Valid:      5
   Invalid:    0
   Success Rate: 100.0%

✅ SERVICES (under Environment Groups):
   Total:      45
   Valid:      45
   Invalid:    0
   Success Rate: 100.0%

✅ OVERALL VALIDATION:
   Total Items:  74
   Valid:        74
   Invalid:      0
   Success Rate: 100.0%

================================================================================
```

---

### 2. **run-phx.py** (Full Execution with Reporting)
**Purpose**: Execute Phoenix Security configuration with comprehensive reporting

**Features**:
- ✅ Full execution of Phoenix Security configuration
- ✅ Tracks all operations (teams, users, apps, components, services, etc.)
- ✅ Generates detailed execution report
- ✅ Shows success rates for all operations

**Usage**:
```bash
cd "Python script"
python3 run-phx.py
```

---

### 3. **Quick YAML Syntax Check**
**Purpose**: Fast syntax validation only (no schema validation)

**Usage**:
```bash
cd "Python script"
python3 -c "import yaml; yaml.safe_load(open('Resources/q2/core-structure-backoffice-with-env-demo.yaml')); print('✅ YAML syntax is VALID!')"
```

---

## 📊 Understanding Success Rates

### **Components Success Rate**
- **What it measures**: Validation of Components defined under DeploymentGroups (Applications)
- **Key validations**:
  - ComponentName is present and valid
  - Deployment_set is properly formatted (not a list item)
  - Status is valid (Production, Staging, Dev, etc.)
  - Required fields are present (Tier, Domain, TeamNames, etc.)
  - MULTI_MultiConditionRules are properly structured

### **Services Success Rate**
- **What it measures**: Validation of Services defined under Environment Groups
- **Key validations**:
  - Service name is present and valid
  - Deployment_set is properly formatted (not a list item)
  - Type is valid (Cloud, Code, etc.)
  - MULTI_MultiConditionRules are properly structured
  - Tags are properly formatted (if present)

---

## 🔧 Common Validation Issues

### Issue 1: Malformed Deployment_set
**Problem**: `DeploymentSet` formatted as list item instead of dictionary key
```yaml
# ❌ WRONG
Components:
  - ComponentName: mycomponent
    - DeploymentSet: myapp

# ✅ CORRECT
Components:
  - ComponentName: mycomponent
    Deployment_set: myapp
```

### Issue 2: Inconsistent Deployment_set Values
**Problem**: Same service has different deployment_set values across environments
```yaml
# ❌ INCONSISTENT
# Production
Deployment_set: backofficeapi

# Staging
Deployment_set: backoffice-api

# ✅ CONSISTENT (use hyphenated format everywhere)
Deployment_set: backoffice-api
```

### Issue 3: Missing BU Field
**Problem**: Business Unit not specified
```yaml
# ❌ MISSING BU
DeploymentGroups:
  - AppName: MyApp
    Status: Production

# ✅ WITH BU
DeploymentGroups:
  - AppName: MyApp
    BU: BackOffice
    Status: Production
```

### Issue 4: Malformed Tags
**Problem**: Tags have extra text concatenated
```yaml
# ❌ WRONG
Tags:
  - 'Backend'extra_text_here

# ✅ CORRECT
Tags:
  - 'Backend'
```

---

## 🎯 Validation Workflow

### Step 1: Quick Syntax Check
```bash
cd "Python script"
python3 -c "import yaml; yaml.safe_load(open('Resources/q2/core-structure-backoffice-with-env-demo.yaml')); print('✅ YAML syntax is VALID!')"
```

### Step 2: Detailed Schema Validation
```bash
python3 validate_yaml_detailed.py Resources/q2/core-structure-backoffice-with-env-demo.yaml
```

### Step 3: Review Success Rates
- Check **Components Success Rate** (should be 100%)
- Check **Services Success Rate** (should be 100%)
- Review any error details

### Step 4: Fix Issues
- Use error details to locate problems
- Apply corrections
- Re-run validation

### Step 5: Full Execution (Optional)
```bash
python3 run-phx.py
```

---

## 📈 Success Rate Interpretation

| Success Rate | Status | Action Required |
|--------------|--------|-----------------|
| **100%** | ✅ Excellent | Ready for production |
| **80-99%** | ⚠️ Good | Review and fix minor issues |
| **50-79%** | ⚠️ Fair | Significant issues, fix before deployment |
| **< 50%** | ❌ Poor | Major issues, requires immediate attention |

---

## 🚀 Quick Commands Reference

```bash
# Navigate to Python script directory
cd "Python script"

# Validate default Q2 BackOffice file
python3 validate_yaml_detailed.py

# Validate specific file
python3 validate_yaml_detailed.py Resources/q2/core-structure-backoffice-with-env-demo.yaml

# Validate with output to file
python3 validate_yaml_detailed.py Resources/q2/core-structure-backoffice-with-env-demo.yaml > validation_report.txt

# Quick syntax check only
python3 -c "import yaml; yaml.safe_load(open('Resources/q2/core-structure-backoffice-with-env-demo.yaml')); print('✅ YAML syntax is VALID!')"

# Full execution with reporting
python3 run-phx.py
```

---

## 📝 Exit Codes

- **0**: All validations passed (100% success rate)
- **1**: One or more validations failed (< 100% success rate)

Use exit codes in CI/CD pipelines:
```bash
python3 validate_yaml_detailed.py Resources/q2/core-structure.yaml
if [ $? -eq 0 ]; then
    echo "✅ Validation passed, proceeding with deployment"
else
    echo "❌ Validation failed, stopping deployment"
    exit 1
fi
```

---

## 🆘 Troubleshooting

### Script Not Found
```bash
# Ensure you're in the correct directory
cd "Python script"
ls -la validate_yaml_detailed.py
```

### Import Errors
```bash
# Ensure providers are available
ls -la providers/Linter.py
ls -la providers/YamlHelper.py
```

### File Not Found
```bash
# Check file path
ls -la Resources/q2/core-structure-backoffice-with-env-demo.yaml
```

---

## 📚 Related Documentation

- **YAML Configuration Guide**: `/YAML_CONFIGURATION_GUIDE.md`
- **YAML Quick Reference**: `/YAML_QUICK_REFERENCE.md`
- **Linter Schema**: `Python script/providers/Linter.py`
- **YAML Helper**: `Python script/providers/YamlHelper.py`
- **Q2 Translator Docs**: `Utils/Translator-service-q2/CSV-JSON-REPO/DOCUMENTATION_SUMMARY.md`

---

## ✅ Best Practices

1. **Always validate before deployment**: Run `validate_yaml_detailed.py` before pushing to production
2. **Monitor success rates**: Aim for 100% success rate on both Components and Services
3. **Fix issues immediately**: Don't let validation errors accumulate
4. **Use consistent naming**: Follow deployment_set naming conventions
5. **Document BU**: Always specify Business Unit for applications
6. **Test in stages**: Validate → Fix → Re-validate → Deploy

---

**Last Updated**: 2025-10-29  
**Version**: 1.0  
**Maintainer**: Phoenix Security AutoConfig Team

