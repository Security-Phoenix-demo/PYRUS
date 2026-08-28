# Phoenix Security PYRUS - Utilities Catalog

**Version**: 4.9.2  
**Last Updated**: February 2026

This document provides a comprehensive catalog of all utility scripts available in the `Utils/` directory, organized by category with usage examples.

---

## Table of Contents

1. [Scanner Import Tools](#1-scanner-import-tools)
2. [Configuration Translators](#2-configuration-translators)
3. [Reporting Tools](#3-reporting-tools)
4. [Asset Counting Scripts](#4-asset-counting-scripts)
5. [CI/CD Integration](#5-cicd-integration)
6. [Migration Tools](#6-migration-tools)
7. [Quick Reference Matrix](#quick-reference-matrix)

---

## 1. Scanner Import Tools

### 1.1 Multi-Scanner Import (Loading_Script_V5_PUB)

**Location**: `Utils/Loading_Script_V5_PUB/`

**Purpose**: Import vulnerability scan results from 44+ security scanners into Phoenix Security.

**Key Files**:
| File | Purpose |
|------|---------|
| `phoenix_multi_scanner_enhanced.py` | Main multi-scanner import script (v3.3.0) |
| `phoenix_multi_scanner_import.py` | Core import functionality |
| `phoenix_import_enhanced.py` | Enhanced API validation |
| `phoenix_import_refactored.py` | Refactored core import |

**Supported Scanners** (44+ translators):

| Category | Scanners |
|----------|----------|
| **Container** | Aqua, Grype, Trivy, Trivy Operator, Sysdig |
| **Cloud** | AWS Inspector, Azure Security Center, MS Defender, Prowler, Scout Suite, Wiz |
| **SAST** | Checkmarx, Fortify, Kiuwan, SonarQube, Veracode SCA |
| **SCA** | Blackduck, CycloneDX, Dependency Check, JFrog Xray, npm audit, ORT, pip audit, Snyk CLI |
| **DAST** | Burp Suite, MicroFocus WebInspect |
| **Secrets** | GitHub Secret Scanning, GitLab Secret Detection, Nosey Parker, TruffleHog |
| **Bug Bounty** | Bugcrowd, HackerOne |
| **Infrastructure** | Qualys, Rapid7 CSV, Tenable |
| **Other** | SARIF (generic), Solar AppScreener, TestSSL |

**Quick Start**:
```bash
cd Utils/Loading_Script_V5_PUB

# Setup credentials
cp config_multi_scanner.ini my_config.ini
# Edit my_config.ini with Phoenix API credentials

# Import Trivy scan
python3 phoenix_multi_scanner_enhanced.py \
  --file trivy-results.json \
  --config my_config.ini \
  --assessment "Container-Scan-Q4"

# Import with custom asset name
python3 phoenix_multi_scanner_enhanced.py \
  --file scan.json \
  --config my_config.ini \
  --assessment "My-Scan" \
  --asset-name "production-cluster"
```

**Documentation**:
- `README.md` - Main documentation
- `PHOENIX_SCANNER_QUICK_START.md` - Quick start guide
- `QUICK_START_ALL_SCANNERS.md` - Scanner-specific examples
- `REFERENCE_DOCUMENTATION/` - Detailed architecture guides

---

### 1.2 Scanner Service (phoenix-scanner-service)

**Location**: `Utils/Loading_Script_V5_PUB/phoenix-scanner-service/`

**Purpose**: REST API service for programmatic scanner imports (Docker-ready).

**Key Features**:
- FastAPI-based REST API
- Docker Compose deployment
- Queue-based processing
- Multi-worker support

**Quick Start**:
```bash
cd Utils/Loading_Script_V5_PUB/phoenix-scanner-service

# Using Docker
docker-compose up -d

# Manual start
pip install -r requirements.txt
./start.sh
```

**API Endpoints**:
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/scan` | POST | Submit scan file |
| `/api/v1/status/{id}` | GET | Check import status |
| `/api/v1/health` | GET | Health check |

---

### 1.3 Legacy Import Scripts

**Location**: `Utils/Loading_Script_V3/`, `Utils/Loading_Script_V4/`

**Purpose**: Previous versions maintained for backward compatibility.

| Version | Features |
|---------|----------|
| V3 | Basic batch import, simple file processing |
| V4 | Enhanced field mapping, data anonymization |
| V5 | Multi-scanner, batching, 44+ translators (current) |

---

## 2. Configuration Translators

### 2.1 CSV Translator

**Location**: `Utils/csv_translator/`

**Purpose**: Convert CSV/JSON vulnerability exports to Phoenix format and optionally upload.

**Key Files**:
| File | Purpose |
|------|---------|
| `csv_converter.py` | Main conversion script |
| `csv_convert_and_upload.py` | Convert + upload in one step |
| `csv_uploader.py` | Batch folder upload |
| `convert.sh` | Bash wrapper script |

**Supported Formats**:
- Infrastructure vulnerabilities (infra)
- Cloud vulnerabilities (cloud)
- Web vulnerabilities (web)
- Software vulnerabilities (software)
- Prowler OCSF JSON

**Quick Start**:
```bash
cd Utils/csv_translator

# Convert only
./convert.sh --format infra --source source/vuln_report.csv

# Convert and upload
python csv_convert_and_upload.py \
  --source vuln_export.csv \
  --format infra \
  --assessment "Q4-Scan" \
  --config config.ini

# Batch upload folder
python csv_uploader.py \
  --folder results/scans \
  --format infra \
  --assessment "Network-Scan" \
  --config config.ini
```

**Documentation**:
- `README.md` - Main documentation
- `README_UPLOAD.md` - Upload guide
- `CSV_UPLOAD_GUIDE.md` - Detailed upload docs
- `CREDENTIALS_QUICK_REFERENCE.md` - Credential setup

---

### 2.2 Backstage Translator

**Location**: `Utils/Backstage Translator/`

**Purpose**: Convert Backstage/ServiceNow service catalog data to Phoenix YAML format.

**Key Files**:
| File | Purpose |
|------|---------|
| `backstage_translator.py` | Main translator |
| `catalog_parser.py` | Backstage catalog parsing |

**Quick Start**:
```bash
cd "Utils/Backstage Translator"

python backstage_translator.py \
  --input catalog-info.yaml \
  --output core-structure.yaml
```

---

### 2.3 Q2 Banking Translator

**Location**: `Utils/client scripts/Translator-service-q2/`

**Purpose**: Client-specific translators for Q2 Banking configurations.

**Sub-tools**:
| Tool | Purpose |
|------|---------|
| `CSV-JSON-REPO/` | CSV to Phoenix YAML converter |
| `okta-translator/` | Okta team/user integration |
| `q2-yaml-new-translator/` | Enhanced YAML translator |

**Documentation**:
- `CSV-JSON-REPO/QUICK_REFERENCE.md` - Quick reference
- `okta-translator/README_OKTA_TRANSLATOR.md` - Okta integration guide

---

## 3. Reporting Tools

### 3.1 Executive Dashboard Reports

**Location**: `Utils/report-dashboard/`

**Purpose**: Generate executive PDF/Excel reports from Phoenix dashboard data.

**Key Features**:
- Professional PDF reports with Phoenix branding
- Excel workbooks with multi-sheet data
- Risk gauges, pie charts, bar charts, heatmaps
- Main, Application, and Environment dashboard support

**Key Files**:
| File | Purpose |
|------|---------|
| `executive_pdf_report_generator.py` | Main PDF generator |
| `executive_json_to_spreadsheet_converter.py` | Spreadsheet generator |
| `fresh_data_pdf_generator.py` | Live data processing |
| `report_script_main_dashboard/` | Main dashboard scripts |
| `report_script_env_dashboard/` | Environment dashboard scripts |

**Visualizations**:
1. Risk Level Gauge (0-1000)
2. Vulnerability Distribution by Severity
3. Top Applications by Risk
4. Top Services by Risk
5. SLA Compliance Status
6. Vulnerability Trends & Forecasting
7. Business Unit Heatmap
8. Vulnerability Classification Analysis
9. Findings Prioritization Funnel

**Quick Start**:
```bash
cd Utils/report-dashboard

# Generate executive report
python executive_pdf_report_generator.py \
  --input "main dashbaord/data/" \
  --output results/

# Fresh data processing
python fresh_data_pdf_generator.py \
  --source "main dashbaord/data-cb/" \
  --output results/
```

---

### 3.2 Vulnerability Reports

**Location**: `Utils/report-vulnerability_report/`

**Purpose**: Detailed vulnerability analysis reports.

**Key Features**:
- Page-by-page vulnerability details
- Executive summary reports
- Comprehensive analysis reports

**Documentation**:
- `report-vulnerability_page_report/README_EXECUTIVE_REPORT.md`
- `report-vulnerability_page_report/README_COMPREHENSIVE.md`

---

### 3.3 Asset & Vulnerability Reports

**Location**: `Utils/report-asset_and_vulnerability_report/`

**Purpose**: Combined asset-centric vulnerability reporting.

**Key Files**:
| File | Purpose |
|------|---------|
| `asset_vulnerability_report.py` | Main report generator |
| Various PDF templates | Report formatting |

**Documentation**: `README.md`, `README_VULNERABILITY_REPORTS.md`

---

### 3.4 Team Dashboard Reports

**Location**: `Utils/report-Team_dashboard_report/`

**Purpose**: Team-specific dashboard reporting.

---

## 4. Asset Counting Scripts

### 4.1 Cloud Asset Counters

**Location**: `Utils/asset-count-scripts/cloud/`

**Purpose**: Count and inventory cloud assets across providers.

**Scripts**:
| Script | Provider |
|--------|----------|
| `aws-asset-counter.py` | AWS resources |
| `azure-asset-counter.py` | Azure resources |
| `gcp-asset-counter.py` | GCP resources |

**Quick Start**:
```bash
cd Utils/asset-count-scripts/cloud

# AWS assets
python aws-asset-counter.py --profile default --output aws_inventory.json

# Azure assets
python azure-asset-counter.py --subscription SUB_ID --output azure_inventory.json

# GCP assets
python gcp-asset-counter.py --project PROJECT_ID --output gcp_inventory.json
```

**Documentation**: `README.md`, `QUICK_START.md`

---

### 4.2 Git Repository Counter

**Location**: `Utils/asset-count-scripts/git/`

**Purpose**: Count and inventory Git repositories.

**Documentation**: `README.md`, `QUICK_START.md`

---

### 4.3 Wiz Asset Counter

**Location**: `Utils/asset-count-scripts/wiz/`

**Purpose**: Count and inventory Wiz cloud security assets.

**Key Files**:
| File | Purpose |
|------|---------|
| `wiz_assets_count_light.py` | Lightweight asset counter |
| `asset-count-wiz.py` | Full asset counter |

**Documentation**: `README.md`

---

## 5. CI/CD Integration

### 5.1 Gating

**Location**: `Utils/Gating/`

**Purpose**: Security gating for CI/CD pipelines.

**Key Features**:
- Pass/fail gates based on vulnerability thresholds
- Integration with CI/CD systems
- Policy-based enforcement

**Documentation**: `README.md`

---

### 5.2 Jenkins Integration

**Location**: `Utils/Jenkins Integration/`

**Purpose**: Jenkins pipeline integration for Phoenix Security.

**Key Files**:
| File | Purpose |
|------|---------|
| `Jenkinsfile.groovy` | Pipeline script |
| Pipeline templates | Jenkins job templates |

**Documentation**: `README.md`

---

## 6. Migration Tools

### 6.1 Nucleus to Phoenix

**Location**: `Utils/Nucleustophoenix/`

**Purpose**: Migrate vulnerability data from Nucleus to Phoenix Security.

**Key Files**:
| File | Purpose |
|------|---------|
| `nucleus_to_phoenix.py` | Main migration script |
| Various converters | Format conversion |

**Documentation**: `README_NUCLEUS_TO_PHOENIX.md`, `QUICK_START.md`

---

### 6.2 Pentest Import

**Location**: `Utils/pentest-import/`

**Purpose**: Import penetration test results into Phoenix Security.

**Quick Start**:
```bash
cd Utils/pentest-import

# Setup
cp config.ini.example config.ini
# Edit config.ini

# Import pentest results
python pentest_import.py --input results.csv --assessment "Pentest-Q4"
```

**Documentation**: `README.md`

---

### 6.3 Container Third-Party

**Location**: `Utils/container3rp/`

**Purpose**: Third-party container integration utilities.

**Documentation**: `README.md`

---

### 6.4 Technology Determination

**Location**: `Utils/technology-determination/`

**Purpose**: Automated technology stack detection from NVD and other sources.

**Components**:
- Go-based NVD tools
- Technology classification logic
- CPE matching utilities

**Documentation**: `README.md`

---

## Quick Reference Matrix

### By Task

| Task | Tool | Location |
|------|------|----------|
| Import Trivy scan | Multi-Scanner | `Loading_Script_V5_PUB/` |
| Import AWS Inspector | Multi-Scanner | `Loading_Script_V5_PUB/` |
| Import Qualys results | Multi-Scanner | `Loading_Script_V5_PUB/` |
| Convert CSV vulnerabilities | CSV Translator | `csv_translator/` |
| Generate executive report | Report Dashboard | `report-dashboard/` |
| Count AWS assets | Asset Counter | `asset-count-scripts/cloud/` |
| Migrate from Nucleus | Migration | `Nucleustophoenix/` |
| Import pentest results | Pentest Import | `pentest-import/` |
| Jenkins integration | CI/CD | `Jenkins Integration/` |
| Security gating | CI/CD | `Gating/` |
| Backstage integration | Translator | `Backstage Translator/` |

### By Scanner Type

| Scanner | Translator File |
|---------|-----------------|
| Aqua | `aqua_translator.py` |
| AWS Inspector | `aws_inspector_translator.py` |
| Azure Security Center | `azure_security_center_translator.py` |
| Blackduck | `blackduck_translator.py` |
| Bugcrowd | `bugcrowd_translator.py` |
| Burp Suite | `burp_translator.py` |
| Checkmarx | `checkmarx_translator.py` |
| Contrast | `contrast_translator.py` |
| CycloneDX | `cyclonedx_translator.py` |
| Dependency Check | `dependency_check_translator.py` |
| Fortify | `fortify_translator.py` |
| GitHub Secret Scanning | `github_secret_scanning_translator.py` |
| GitLab Secret Detection | `gitlab_secret_detection_translator.py` |
| Grype | `grype_translator.py` |
| HackerOne | `hackerone_translator.py` |
| JFrog Xray | `jfrog_xray_translator.py` |
| Kiuwan | `kiuwan_translator.py` |
| KubeAudit | `kubeaudit_translator.py` |
| MS Defender | `msdefender_translator.py` |
| Nosey Parker | `noseyparker_translator.py` |
| npm audit | `npm_audit_translator.py` |
| ORT | `ort_translator.py` |
| Phoenix CSV | `phoenix_csv_translator.py` |
| pip audit | `pip_audit_translator.py` |
| Prowler | `prowler_translator.py` |
| Qualys | `qualys_translator.py` |
| Rapid7 CSV | `rapid7_csv_translator.py` |
| SARIF | `sarif_translator.py` |
| Scout Suite | `scout_suite_translator.py` |
| Snyk CLI | `snyk_cli_translator.py` |
| SonarQube | `sonarqube_translator.py` |
| Sysdig | `sysdig_translator.py` |
| Tenable | `tenable_translator.py` |
| TestSSL | `testssl_translator.py` |
| Trivy | `trivy_translator.py` |
| Trivy Operator | `trivy_operator_translator.py` |
| TruffleHog | `trufflehog_translator.py` |
| Veracode SCA | `veracode_sca_translator.py` |
| Wiz | `wiz_translator.py` |

---

## Adding New Utilities

When adding a new utility script:

1. **Create folder** in `Utils/` with descriptive name
2. **Include README.md** with:
   - Purpose and features
   - Installation/setup
   - Usage examples
   - Configuration options
3. **Update this catalog** with new entry
4. **Follow code style** from `.cursor/rules/phoenix-project-master.mdc`
5. **Add tests** if applicable

---

## Related Documentation

- [Architecture Overview](ARCHITECTURE.md) - System architecture
- [YAML Configuration Guide](YAML_CONFIGURATION_GUIDE.md) - YAML reference
- [Developer Quick Start](DEVELOPER_QUICK_START.md) - Getting started
- [Version History](VERSION_HISTORY.md) - Release notes
