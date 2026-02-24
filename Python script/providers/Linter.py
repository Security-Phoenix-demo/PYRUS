from cerberus import Validator, schema_registry
import yaml
import re
from collections import Counter

schema_registry.add("ticketing_schema", {
                "TIntegrationName": {
                    "type": "string",
                    "required": True
                },
                "Backlog": {
                    "type": "string",
                    "required": True
                }
                })


schema_registry.add("messaging_schema", {
                "MIntegrationName": {
                    "type": "string",
                    "required": True
                },
                "Channel": {
                    "type": "string",
                    "required": True
                }
                })

schema_registry.add('multi_condition_rule_schema',{
                "RepositoryName": {
                    "type": ["string", "list"],
                    "required": False
                },
                "SearchName": {
                    "type": "string",
                    "required": False
                },
                "AssetType": {
                    "type": "string",
                    "required": False,
                    "allowed": [
                        "REPOSITORY", "SOURCE_CODE", "BUILD", "WEBSITE_API", "CONTAINER", "INFRA", "CLOUD", "WEB", "FOSS", "SAST"
                    ]
                },
                "Tag": {
                    "type": ["string", "list"],
                    "required": False
                },
                "Tags": {
                    "type": "list",
                    "required": False, # todo check this
                    "schema": {
                        "type": "string"
                    }
                },
                "Tag_rule": {
                    "type": ["string", "list"],
                    "required": False
                },
                "Tags_rule": {
                    "type": "list",
                    "required": False,
                    "schema": {
                        "type": "string"
                    }
                },
                "Tag_label": {
                    "type": ["string", "list"],
                    "required": False
                },
                "Tags_label": {
                    "type": "list",
                    "required": False,
                    "schema": {
                        "type": "string"
                    }
                },
                "Cidr": {
                    "type": "string",
                    "required": False
                },
                "Fqdn": {
                    "type": "list",
                    "schema": {
                        "type": "string"
                    },
                    "required": False
                },
                "Netbios": {
                    "type": "list",
                    "schema": {
                        "type": "string"
                    },
                    "required": False
                },
                "OsNames": {
                    "type": "list",
                    "schema": {
                        "type": "string"
                    },
                    "required": False
                },
                "Hostnames": {
                    "type": "list",
                    "schema": {
                        "type": "string"
                    },
                    "required": False
                },
                "AccountId": {
                    "type": "list",
                    "schema": {
                        "type": "string"
                    },
                    "required": False
                },
                "ProviderAccountId": {
                    "type": "list",
                    "schema": {
                        "type": "string"
                    },
                    "required": False
                },
                "ProviderAccountName": {
                    "type": "list",
                    "schema": {
                        "type": "string"
                    },
                    "required": False
                },
                "ResourceGroup": {
                    "type": "list",
                    "schema": {
                        "type": "string"
                    },
                    "required": False
                }
            })

# Validate a component from a config yaml file
def validate_component(component):
    v = Validator({
        "ComponentName": {
            "type": "string",
            "required": True
        },
        "Status": {
            "type": "string",
            "required": False
        },
        "AppID": {
            "type": "integer",
            "required": False
        },
        "Type": {
            "type": "string",
            "required": False
        },
        "TeamNames": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        },
        "Ticketing": {
            "type": "list",
            "schema": {
                "type": "dict",
                "schema": "ticketing_schema"
            },
            "required": False
        },
        "Messaging": {
            "type": "list",
            "schema": {
                "type": "dict",
                "schema": "messaging_schema"
            },
            "required": False
        },
        "RepositoryName": {
            "type": ["string", "list"],
            "required": False
        },
        "SearchName": {
            "type": "string",
            "required": False
        },
        "AssetType": {
            "type": "string",
            "required": False,
            "allowed": [
                "REPOSITORY", "SOURCE_CODE", "BUILD", "WEBSITE_API", "CONTAINER", "INFRA", "CLOUD", "WEB", "FOSS", "SAST"
            ]
        },
        "Tags": {
            "type": "list",
            "required": False,
            "schema": {
                "type": "string"
            }
        },
        "Tag_label": {
            "type": ["string", "list"],
            "required": False
        },
        "Tags_label": {
            "type": "list",
            "required": False,
            "schema": {
                "type": "string"
            }
        },
        "Cidr": {
            "type": "string",
            "required": False
        },
        "Fqdn": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        },
        "Netbios": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        },
        "OsNames": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        },
        "Hostnames": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        },
        "AccountId": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        },
        "ProviderAccountId": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        },
        "ProviderAccountName": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        },
        "ResourceGroup": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        },
        "MultiConditionRule": {
            "type": "dict",
            "schema": "multi_condition_rule_schema",
            "required": False
        },
        "MULTI_MultiConditionRules": {
            "type": "list",
            "schema": {
                "type": "dict",
                "schema": "multi_condition_rule_schema"
            },
            "required": False
        },
        "Tier": {
            "type": "integer",
            "required": False
        },
        "Domain": {
            "type": "string",
            "required": False
        },
        "SubDomain": {
            "type": "string",
            "required": False
        },
        "AutomaticSecurityReview": {
            "type": "boolean",
            "required": False
        },
        "Tag_rule": {
            "type": ["string", "list"],
            "required": False
        },
        "Tags_rule": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        },
        "Deployment_set": {
            "type": "string",
            "required": False
        },
        "Ticketing": {
            "type": "list",
            "schema": {
                "type": "dict",
                "schema": "ticketing_schema"
            },
            "required": False
        },
        "Messaging": {
            "type": "list",
            "schema": {
                "type": "dict",
                "schema": "messaging_schema"
            },
            "required": False
        }
    }, allow_unknown=False)
    
    try:
        # First check required list fields BEFORE schema validation
        # This gives clearer error messages than Cerberus type errors
        list_valid, list_errors = validate_required_list_fields(component, "component")
        if not list_valid:
            return (False, {"required_list_fields": list_errors})
        
        if v.validate(component):
            # Additional custom validation for repository + asset type structure
            structure_valid, structure_errors = validate_repository_asset_structure(component, "component")
            if not structure_valid:
                return (False, {"repository_asset_structure": structure_errors})
            return (True, "")
        return (False, v.errors)
    except Exception as e:
        print(f"Exception occurred while linting component {component}, error: {e}")
        return (False, "Unknown error while linting")


def validate_application(application):
    v = Validator({
        "AppName": {
            "type": "string",
            "required": True
        },
        "AppID": {
            "type": "integer",
            "required": False
        },
        "Status": {
            "type": "string",
            "required": False
        },
        "TeamNames": {
            "type": "list",
            "required": False,
            "schema": {
                "type": "string"
            }
        },
        "BU": {
            "type": ["string", "list"],
            "required": False
        },
        "Domain": {
            "type": "string",
            "required": False
        },
        "SubDomain": {
            "type": "string",
            "required": False
        },
        "ReleaseDefinitions": {
            "type": "list",
            "required": True
        },
        "Responsable": {
            "type": "string",
            "required": True
        },
        "Tier": {
            "type": "integer",
            "required": False
        },
        "Deployment_set": {
            "type": "string",
            "required": False
        },
        "Ticketing": {
            "type": "list",
            "schema": {
                "type": "dict",
                "schema": "ticketing_schema"
            },
            "required": False
        },
        "Messaging": {
            "type": "list",
            "schema": {
                "type": "dict",
                "schema": "messaging_schema"
            },
            "required": False
        },
        "Components": {
            "type": "list",
            "required": False
        },
        "Tag_label": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        },
        "Tags_label": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        }
    }, allow_unknown=False)
    
    try:
        if v.validate(application):
            return (True, "")
        return (False, v.errors)
    except Exception as e:
        print(f"Exception occurred while linting application {application}, error: {e}")
        return (False, "Uknown error while linting")


def validate_environment(environment):
    v = Validator({
        "Name": {
            "type": "string",
            "required": True
        },
        "Type": {
            "type": "string",
            "required": True
        },
        "Tier": {
            "type": "integer",
            "required": True
        },
        "Status": {
            "type": "string",
            "required": True
        },
        "Responsable": {
            "type": "string",
            "required": False  # Made optional since we also accept 'Responsible'
        },
        "Responsible": {
            "type": "string", 
            "required": False  # Alternative field name for 'Responsable'
        },
        "TeamName": {
            "type": "string",
            "required": False
        },
        "Tag_label": {
            "type": "list",
            "required": False
        },
        "Ticketing": {
            "type": "list",
            "schema": {
                "type": "dict",
                "schema": "ticketing_schema"
            },
            "required": False
        },
        "Messaging": {
            "type": "list",
            "schema": {
                "type": "dict",
                "schema": "messaging_schema"
            },
            "required": False
        },
        "Services": {
            "type": "list",
            "required": False
        }
    }, allow_unknown=False)
    
    try:
        # First check required list fields BEFORE schema validation
        # This gives clearer error messages than Cerberus type errors
        list_valid, list_errors = validate_required_list_fields(environment, "environment")
        if not list_valid:
            return (False, {"required_list_fields": list_errors})
        
        if v.validate(environment):
            # Custom validation: ensure either 'Responsable' or 'Responsible' is present
            if not (environment.get('Responsable') or environment.get('Responsible')):
                return (False, {'Responsable_or_Responsible': ['At least one of Responsable or Responsible is required']})
            return (True, "")
        return (False, v.errors)
    except Exception as e:
        print(f"Exception occurred while linting environment {environment}, error: {e}")
        return (False, "Unknown error while linting")


# Validate a service from a config yaml file
def validate_service(service):
    v = Validator({
        "Service": {
            "type": "string",
            "required": True
        },
        "Type": {
            "type": "string",
            "required": True
        },
        "Tier": {
            "type": "integer",
            "required": False
        },
        "TeamName": {
            "type": "string",
            "required": False
        },
        "Ticketing": {
            "type": "list",
            "schema": {
                "type": "dict",
                "schema": "ticketing_schema"
            },
            "required": False
        },
        "Messaging": {
            "type": "list",
            "schema": {
                "type": "dict",
                "schema": "messaging_schema"
            },
            "required": False
        },
        "Deployment_set": {
            "type": "string",
            "required": False
        },
        "Deployment_tag": {
            "type": "string",
            "required": False
        },
        "MultiConditionRule": {
            "type": "dict",
            "schema": "multi_condition_rule_schema",
            "required": False
        },
        "MULTI_MultiConditionRules": {
            "type": "list",
            "schema": {
                "type": "dict",
                "schema": "multi_condition_rule_schema"
            },
            "required": False
        },
        "MultiMultiConditionRules": {
            "type": "list",
            "schema": {
                "type": "dict",
                "schema": "multi_condition_rule_schema"
            },
            "required": False
        },
        "MultiConditionRules": {
            "type": "list",
            "schema": {
                "type": "dict",
                "schema": "multi_condition_rule_schema"
            },
            "required": False
        },
        "RepositoryName": {
            "type": ["string", "list"],
            "required": False
        },
        "SearchName": {
            "type": "string",
            "required": False
        },
        "Tag": {
            "type": ["list", "string"],
            "required": False
        },
        "Tag_rule": {
            "type": ["list", "string"],
            "required": False
        },
        "Tags_rule": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        },
        "Tag_label": {
            "type": ["string", "list"],
            "required": False
        },
        "Tags_label": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        },
        "Cidr": {
            "type": "string",
            "required": False
        },
        "Fqdn": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        },
        "Netbios": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        },
        "OsNames": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        },
        "Hostnames": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        },
        "AccountId": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        },
        "ProviderAccountId": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        },
        "ProviderAccountName": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        },
        "ResourceGroup": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        },
        "AssetType": {
            "type": "string",
            "required": False,
            "allowed": [
                "REPOSITORY", "SOURCE_CODE", "BUILD", "WEBSITE_API", "CONTAINER", "INFRA", "CLOUD", "WEB", "FOSS", "SAST"
            ]
        },
        "Tags": {
            "type": "list",
            "schema": {
                "type": "string"
            },
            "required": False
        }
    }, allow_unknown=False)
    
    try:
        # First check required list fields BEFORE schema validation
        # This gives clearer error messages than Cerberus type errors
        list_valid, list_errors = validate_required_list_fields(service, "service")
        if not list_valid:
            return (False, {"required_list_fields": list_errors})
        
        if v.validate(service):
            # Additional custom validation for repository + asset type structure
            structure_valid, structure_errors = validate_repository_asset_structure(service, "service")
            if not structure_valid:
                return (False, {"repository_asset_structure": structure_errors})
            return (True, "")
        return (False, v.errors)
    except Exception as e:
        print(f"Exception occurred while linting service {service}, error: {e}")
        return (False, "Unknown error while linting")

# Validate a multi-condition rule from a config yaml file
def validate_multi_condition_rule(mcr):
    v = Validator(schema_registry.get('multi_condition_rule_schema'), allow_unknown=False)
    
    try:
        # First check required list fields BEFORE schema validation
        # This gives clearer error messages than Cerberus type errors
        list_valid, list_errors = validate_required_list_fields(mcr, "multi_condition_rule")
        if not list_valid:
            return (False, {"required_list_fields": list_errors})
        
        if v.validate(mcr):
            return (True, "")
        return (False, v.errors)
    except Exception as e:
        print(f"Exception occurred while linting multi-condition rule {mcr}, error: {e}")
        return (False, "Unknown error while linting")


################################################################################
# STRUCTURAL YAML VALIDATION FUNCTIONS
################################################################################

def detect_duplicate_keys_in_yaml(yaml_content):
    """
    Detect duplicate keys in YAML content by parsing the raw text.
    YAML parsers silently overwrite duplicate keys, losing data.
    
    Key Logic:
    - Tracks keys at each indentation level
    - Distinguishes between dictionary keys and list items
    - List items (starting with '-') create new contexts
    - Only flags true duplicate keys within the same dictionary
    
    Args:
        yaml_content: String content of YAML file or file path
        
    Returns:
        tuple: (has_duplicates: bool, duplicate_info: list of dicts)
            Each dict contains: {'line': int, 'key': str, 'level': str, 'suggestion': str}
    """
    # If yaml_content is a file path, read it
    if isinstance(yaml_content, str) and '\n' not in yaml_content and len(yaml_content) < 500:
        try:
            with open(yaml_content, 'r') as f:
                yaml_content = f.read()
        except:
            pass  # Assume it's actual YAML content, not a path
    
    duplicates = []
    lines = yaml_content.split('\n')
    
    # Track keys in current dictionary scope
    # Structure: {(indent_level, section_id): {key: [line_numbers]}}
    # section_id helps differentiate between different list items
    keys_by_scope = {}
    current_scope = {}  # Maps indent level to current section_id
    next_section_id = [0]  # Mutable counter for section IDs
    
    for line_num, line in enumerate(lines, 1):
        # Skip comments and empty lines
        stripped = line.lstrip()
        if not stripped or stripped.startswith('#'):
            continue
        
        # Calculate indentation
        indent = len(line) - len(stripped)
        
        # Check if this is a list item (starts with '- ' after indentation)
        is_list_item = stripped.startswith('- ')
        
        if is_list_item:
            # New list item = new scope at this indentation level
            # Clear current scope at this level and deeper
            current_scope = {k: v for k, v in current_scope.items() if k < indent}
            current_scope[indent] = next_section_id[0]
            next_section_id[0] += 1
            
            # Extract the key from list item: "- key: value" -> "key"
            list_content = stripped[2:].lstrip()  # Remove "- "
            match = re.match(r'^([^:\s][^:]*?):\s*(.*)$', list_content)
            if match:
                key = match.group(1).strip()
                # Don't track list item keys for duplicates - each list item is independent
                continue
        
        # Match YAML key pattern (key: value or key:)
        match = re.match(r'^(\s*)([^:\s][^:]*?):\s*(.*)$', line)
        if not match:
            continue
        
        key = match.group(2).strip()
        
        # Skip list markers that were already processed
        if key.startswith('- '):
            continue
        
        # Get current scope identifier
        # Find the closest parent scope
        parent_scope = None
        for scope_indent in sorted([k for k in current_scope.keys() if k < indent], reverse=True):
            parent_scope = current_scope[scope_indent]
            break
        
        scope_key = (indent, parent_scope)
        
        # Initialize scope if needed
        if scope_key not in keys_by_scope:
            keys_by_scope[scope_key] = {}
        
        # Check for duplicate within this scope
        if key in keys_by_scope[scope_key]:
            # Found a duplicate!
            prev_lines = keys_by_scope[scope_key][key]
            level = "top-level" if indent == 0 else f"indent-{indent}"
            
            suggestion = _generate_duplicate_key_solution(key, indent, line_num, prev_lines[0])
            
            duplicates.append({
                'line': line_num,
                'previous_line': prev_lines[0],
                'key': key,
                'indent_level': indent,
                'level_description': level,
                'suggestion': suggestion
            })
            keys_by_scope[scope_key][key].append(line_num)
        else:
            keys_by_scope[scope_key][key] = [line_num]
    
    return (len(duplicates) > 0, duplicates)


def _generate_duplicate_key_solution(key, indent, current_line, previous_line):
    """
    Generate a helpful solution message for duplicate key errors.
    
    Args:
        key: The duplicate key name
        indent: Indentation level
        current_line: Line number of duplicate
        previous_line: Line number of first occurrence
        
    Returns:
        str: Solution message
    """
    if key in ["DeploymentGroups", "Deployment Groups"] and indent == 0:
        return (
            f"SOLUTION: Merge all applications under a single 'DeploymentGroups:' section. "
            f"Remove the duplicate '{key}' on line {current_line} and move its "
            f"applications (starting with '- AppName:') under the first '{key}' "
            f"on line {previous_line}."
        )
    elif key in ["Environment Groups", "EnvironmentGroups"] and indent == 0:
        return (
            f"SOLUTION: Merge all environments under a single '{key}' section. "
            f"Remove the duplicate '{key}' on line {current_line} and move its "
            f"environments under the first '{key}' on line {previous_line}."
        )
    elif indent == 0:
        return (
            f"SOLUTION: Remove the duplicate top-level key '{key}' on line {current_line}. "
            f"Keep only the first occurrence on line {previous_line}, or merge their contents."
        )
    else:
        return (
            f"SOLUTION: Remove or rename the duplicate key '{key}' on line {current_line}. "
            f"The first occurrence is on line {previous_line}."
        )


def validate_yaml_structure(yaml_file_path):
    """
    Comprehensive YAML structure validation that checks:
    1. Duplicate keys at all levels
    2. Required top-level keys
    3. Empty sections
    4. Data consistency
    
    Args:
        yaml_file_path: Path to YAML configuration file
        
    Returns:
        tuple: (is_valid: bool, errors: dict)
            errors dict structure: {
                'duplicate_keys': [...],
                'missing_keys': [...],
                'empty_sections': [...],
                'structure_errors': [...]
            }
    """
    errors = {
        'duplicate_keys': [],
        'missing_keys': [],
        'empty_sections': [],
        'structure_errors': [],
        'warnings': []
    }
    
    # Check 1: Detect duplicate keys in raw YAML
    try:
        with open(yaml_file_path, 'r') as f:
            yaml_content = f.read()
        
        has_duplicates, duplicate_info = detect_duplicate_keys_in_yaml(yaml_content)
        
        if has_duplicates:
            for dup in duplicate_info:
                errors['duplicate_keys'].append({
                    'error': f"Duplicate key '{dup['key']}' found at {dup['level_description']}",
                    'line': dup['line'],
                    'previous_line': dup['previous_line'],
                    'key': dup['key'],
                    'suggestion': dup['suggestion']
                })
    except Exception as e:
        errors['structure_errors'].append({
            'error': f"Failed to read YAML file: {str(e)}",
            'suggestion': "Ensure the file exists and has read permissions."
        })
        return (False, errors)
    
    # Check 2: Parse YAML and validate structure
    try:
        with open(yaml_file_path, 'r') as f:
            data = yaml.safe_load(f)
        
        if not isinstance(data, dict):
            errors['structure_errors'].append({
                'error': "YAML root must be a dictionary/mapping",
                'suggestion': "Ensure your YAML file starts with key-value pairs, not a list or scalar."
            })
            return (False, errors)
        
        # Check 3: Validate DeploymentGroups section
        # Support both 'DeploymentGroups' and 'Deployment Groups'
        deployment_groups = data.get('DeploymentGroups') or data.get('Deployment Groups')
        if not deployment_groups:
            errors['missing_keys'].append({
                'error': "Missing required top-level key: 'DeploymentGroups' or 'Deployment Groups'",
                'suggestion': "Add 'DeploymentGroups:' section with a list of applications."
            })
        else:
            
            if not isinstance(deployment_groups, list):
                errors['structure_errors'].append({
                    'error': "'DeploymentGroups' must be a list of applications",
                    'suggestion': "Format: 'DeploymentGroups:' followed by '- AppName: YourApp'"
                })
            elif len(deployment_groups) == 0:
                errors['empty_sections'].append({
                    'error': "'DeploymentGroups' section is empty",
                    'suggestion': "Add at least one application with '- AppName: YourApp'"
                })
            else:
                # Validate each application
                app_names = []
                for idx, app in enumerate(deployment_groups):
                    if not isinstance(app, dict):
                        errors['structure_errors'].append({
                            'error': f"Application #{idx+1} in DeploymentGroups is not a dictionary",
                            'suggestion': "Each application must be a dictionary with AppName, Components, etc."
                        })
                        continue
                    
                    app_name = app.get('AppName', f'Application#{idx+1}')
                    app_names.append(app_name)
                    
                    # Check for duplicate application names
                    if app_names.count(app_name) > 1:
                        errors['duplicate_keys'].append({
                            'error': f"Duplicate application name: '{app_name}'",
                            'key': app_name,
                            'suggestion': f"Rename one of the applications with name '{app_name}' to be unique."
                        })
                    
                    # Check for empty or missing Components
                    if 'Components' not in app:
                        errors['warnings'].append({
                            'warning': f"Application '{app_name}' has no 'Components' key",
                            'suggestion': "Add 'Components: []' or a list of components."
                        })
                    elif not app['Components']:
                        errors['warnings'].append({
                            'warning': f"Application '{app_name}' has empty Components list",
                            'suggestion': "Add at least one component or remove the application."
                        })
                    else:
                        # Check for duplicate component names within the application
                        comp_names = [c.get('ComponentName', '') for c in app['Components'] if isinstance(c, dict)]
                        comp_duplicates = [name for name, count in Counter(comp_names).items() if count > 1 and name]
                        for dup_name in comp_duplicates:
                            errors['duplicate_keys'].append({
                                'error': f"Duplicate component name '{dup_name}' in application '{app_name}'",
                                'key': dup_name,
                                'suggestion': f"Rename duplicate components or merge them if they represent the same component."
                            })
        
        # Check 4: Validate Environment Groups section
        # Support both 'Environment Groups' and 'EnvironmentGroups'
        env_groups = data.get('Environment Groups') or data.get('EnvironmentGroups')
        if not env_groups:
            errors['warnings'].append({
                'warning': "Missing 'Environment Groups' or 'EnvironmentGroups' key",
                'suggestion': "Add 'Environment Groups:' section if you have environment configurations."
            })
        else:
            
            if not isinstance(env_groups, list):
                errors['structure_errors'].append({
                    'error': "'Environment Groups' must be a list of environments",
                    'suggestion': "Format: 'Environment Groups:' followed by '- Name: YourEnv'"
                })
            elif len(env_groups) == 0:
                errors['empty_sections'].append({
                    'error': "'Environment Groups' section is empty",
                    'suggestion': "Add at least one environment or remove the section."
                })
            else:
                # Validate each environment
                env_names = []
                for idx, env in enumerate(env_groups):
                    if not isinstance(env, dict):
                        errors['structure_errors'].append({
                            'error': f"Environment #{idx+1} in Environment Groups is not a dictionary",
                            'suggestion': "Each environment must be a dictionary with Name, Services, etc."
                        })
                        continue
                    
                    env_name = env.get('Name', f'Environment#{idx+1}')
                    env_names.append(env_name)
                    
                    # Check for duplicate environment names
                    if env_names.count(env_name) > 1:
                        errors['duplicate_keys'].append({
                            'error': f"Duplicate environment name: '{env_name}'",
                            'key': env_name,
                            'suggestion': f"Rename one of the environments with name '{env_name}' to be unique."
                        })
                    
                    # Check for empty or missing Services
                    if 'Services' in env:
                        if not env['Services']:
                            errors['warnings'].append({
                                'warning': f"Environment '{env_name}' has empty Services list",
                                'suggestion': "Add at least one service or remove the Services key."
                            })
                        else:
                            # Check for duplicate service names within the environment
                            svc_names = [s.get('Service', '') for s in env['Services'] if isinstance(s, dict)]
                            svc_duplicates = [name for name, count in Counter(svc_names).items() if count > 1 and name]
                            for dup_name in svc_duplicates:
                                errors['duplicate_keys'].append({
                                    'error': f"Duplicate service name '{dup_name}' in environment '{env_name}'",
                                    'key': dup_name,
                                    'suggestion': f"Rename duplicate services or merge them if they represent the same service."
                                })
        
        # Check 5: Validate Application/Environment name collisions (Phoenix name resolution issue)
        # Support both key variants
        deployment_groups = data.get('DeploymentGroups') or data.get('Deployment Groups')
        env_groups = data.get('Environment Groups') or data.get('EnvironmentGroups')
        
        if deployment_groups and env_groups:
            
            if isinstance(deployment_groups, list) and isinstance(env_groups, list):
                # Collect application names
                app_names = set()
                for app in deployment_groups:
                    if isinstance(app, dict) and 'AppName' in app:
                        app_names.add(app['AppName'])
                
                # Check for environment names that match application names
                for env in env_groups:
                    if isinstance(env, dict) and 'Name' in env:
                        env_name = env['Name']
                        if env_name in app_names:
                            errors['warnings'].append({
                                'warning': f"⚠️  NAME COLLISION: Environment '{env_name}' has the same name as an Application",
                                'suggestion': (
                                    f"When an Application and Environment share the same name, Phoenix's name-based selector "
                                    f"returns the first match (typically the Application), which can cause 'Wrong asset type' errors. "
                                    f"\n   RECOMMENDED FIX: Rename environment to '{env_name}-ENV' to avoid ambiguity."
                                    f"\n   This ensures rule creation targets the correct entity."
                                    f"\n   Reference: ID-based endpoints (implemented) work around this, but naming convention provides clarity."
                                )
                            })
        
    except yaml.YAMLError as e:
        errors['structure_errors'].append({
            'error': f"YAML parsing error: {str(e)}",
            'suggestion': "Fix YAML syntax errors. Check indentation, colons, and list markers (-)."
        })
        return (False, errors)
    except Exception as e:
        errors['structure_errors'].append({
            'error': f"Unexpected error during validation: {str(e)}",
            'suggestion': "Review the YAML file structure and syntax."
        })
        return (False, errors)
    
    # Determine if validation passed
    has_errors = (
        len(errors['duplicate_keys']) > 0 or
        len(errors['missing_keys']) > 0 or
        len(errors['structure_errors']) > 0
    )
    
    return (not has_errors, errors)


################################################################################
# REQUIRED LIST FIELDS VALIDATION
################################################################################

# Fields that MUST always be lists, even for single values
REQUIRED_LIST_FIELDS = [
    'ProviderAccountId',
    'ProviderAccountName', 
    'ResourceGroup',
    'AccountId',
    'Hostnames',
    'OsNames',
    'Netbios',
    'Fqdn',
    'Tags',
    'Tags_label',
    'Tags_rule',
    'TeamNames',
]

def validate_required_list_fields(item, item_type="component"):
    """
    Validates that fields which must be lists are not provided as strings.
    
    Common Error: Users often provide single values as strings instead of lists:
        ProviderAccountId: "uuid-here"       # ❌ WRONG
        ProviderAccountId:                    # ✅ CORRECT  
          - "uuid-here"
    
    Args:
        item: Component, Service, or multi-condition rule dictionary
        item_type: Type of item being validated ("component", "service", "environment", "rule")
    
    Returns:
        tuple: (is_valid, list of error dicts with field, value, and suggestion)
    """
    errors = []
    
    for field in REQUIRED_LIST_FIELDS:
        if field in item:
            value = item[field]
            
            # Check if the value is a string (incorrect) instead of a list (correct)
            if isinstance(value, str):
                errors.append({
                    'field': field,
                    'value': value,
                    'item_type': item_type,
                    'error': f"'{field}' must be a list, not a string",
                    'suggestion': f"Change from:\n    {field}: \"{value}\"\n  To:\n    {field}:\n      - \"{value}\""
                })
            
            # Also check for None values which could cause issues
            elif value is None:
                errors.append({
                    'field': field,
                    'value': value,
                    'item_type': item_type,
                    'error': f"'{field}' is None/null - should be a list or removed",
                    'suggestion': f"Either remove '{field}' entirely, or provide a list of values."
                })
    
    # Also check nested multi-condition rules
    for mcr_key in ['MultiConditionRule', 'MULTI_MultiConditionRules', 'MultiConditionRules', 'MultiMultiConditionRules']:
        if mcr_key in item:
            mcr_data = item[mcr_key]
            
            # Handle single rule (dict)
            if isinstance(mcr_data, dict):
                rule_valid, rule_errors = validate_required_list_fields(mcr_data, f"{item_type}.{mcr_key}")
                errors.extend(rule_errors)
            
            # Handle multiple rules (list of dicts)
            elif isinstance(mcr_data, list):
                for idx, rule in enumerate(mcr_data):
                    if isinstance(rule, dict):
                        rule_valid, rule_errors = validate_required_list_fields(rule, f"{item_type}.{mcr_key}[{idx}]")
                        errors.extend(rule_errors)
    
    return (len(errors) == 0, errors)


def format_list_field_errors(errors):
    """
    Format list field validation errors into a readable string.
    
    Args:
        errors: List of error dicts from validate_required_list_fields
        
    Returns:
        str: Formatted error message
    """
    if not errors:
        return ""
    
    lines = [
        "❌ REQUIRED LIST FIELD ERRORS:",
        "   The following fields MUST be YAML lists (with - prefix), not strings:",
        ""
    ]
    
    for err in errors:
        lines.append(f"   • {err['field']} in {err['item_type']}:")
        lines.append(f"     Error: {err['error']}")
        lines.append(f"     {err['suggestion']}")
        lines.append("")
    
    return "\n".join(lines)


################################################################################
# EXISTING VALIDATION FUNCTIONS
################################################################################

# Custom validation rule: Check if RepositoryName + AssetType should be in multi-condition rules
def validate_repository_asset_structure(item, item_type="component"):
    """
    Validates that when both RepositoryName and AssetType are present at the top level,
    they should be contained within a multi-condition rule structure.
    
    Args:
        item: Component or Service dictionary
        item_type: Type of item being validated ("component" or "service")
    
    Returns:
        tuple: (is_valid, error_message)
    """
    errors = []
    
    # Check if both RepositoryName and AssetType are present at the top level
    has_repository_name = 'RepositoryName' in item and item['RepositoryName'] is not None
    has_asset_type = 'AssetType' in item and item['AssetType'] is not None
    
    # Check if multi-condition rules are already present
    has_multi_condition_rules = any([
        'MultiConditionRule' in item,
        'MULTI_MultiConditionRules' in item,
        'MultiConditionRules' in item,
        'MultiMultiConditionRules' in item
    ])
    
    if has_repository_name and has_asset_type:
        if not has_multi_condition_rules:
            # Check if there are multiple repositories (list format)
            repo_name = item['RepositoryName']
            is_multiple_repos = isinstance(repo_name, list) and len(repo_name) > 1
            
            if is_multiple_repos:
                errors.append(
                    f"Multiple repositories detected with AssetType. "
                    f"Use 'MULTI_MultiConditionRules' to define separate rules for each repository: {repo_name}"
                )
            else:
                errors.append(
                    f"Both 'RepositoryName' and 'AssetType' are present at {item_type} level. "
                    f"Consider using 'MultiConditionRule' for single repository or 'MULTI_MultiConditionRules' for multiple repositories."
                )
        else:
            # If multi-condition rules exist, warn about potential duplication
            errors.append(
                f"Warning: Both top-level 'RepositoryName'/'AssetType' and multi-condition rules are present. "
                f"Consider consolidating into multi-condition rules only to avoid conflicts."
            )
    
    # Additional check: If multiple repositories in list format, recommend multi-condition rules
    if has_repository_name and not has_asset_type:
        repo_name = item['RepositoryName']
        if isinstance(repo_name, list) and len(repo_name) > 1:
            errors.append(
                f"Multiple repositories detected without AssetType: {repo_name}. "
                f"Consider using 'MULTI_MultiConditionRules' for better organization and to specify AssetType for each."
            )
    
    return (len(errors) == 0, errors)