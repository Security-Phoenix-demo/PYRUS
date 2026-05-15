import os
import yaml
from pathlib import Path
from providers.Utils import calculate_criticality
from email_validator import validate_email, EmailNotValidError

# Handle imports with fallback for both relative and absolute imports
try:
    # Try relative imports first (when run as part of a package)
    from .Linter import validate_component, validate_application, validate_environment, validate_service
    from .Phoenix import extract_last_two_path_parts
except (ImportError, ValueError):
    try:
        # Fall back to absolute imports (when run standalone or from different context)
        from Linter import validate_component, validate_application, validate_environment, validate_service
        from Phoenix import extract_last_two_path_parts
    except ImportError:
        # Final fallback - try with full module path
        import sys
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, current_dir)
        from Linter import validate_component, validate_application, validate_environment, validate_service
        from Phoenix import extract_last_two_path_parts

# Check if PyYAML module exists
try:
    import yaml
    print("Module exists")
except ImportError:
    print("Module does not exist. Installing...")
    os.system('pip install pyyaml')

# Debug setting
DEBUG = True


def get_key_with_variants(data, *variants):
    """
    Helper function to support multiple key variants (with/without spaces)
    Returns the value for the first matching key variant found, or None
    
    Args:
        data: The dictionary to search in
        *variants: Variable number of key variants to try
    
    Returns:
        The value for the first matching key, or None if not found
    """
    for variant in variants:
        if variant in data:
            return data[variant]
    return None


# Function to populate repositories
def populate_repositories(resource_folder):
    if not resource_folder:
        print("Please supply path for the resources")
        return []

    core_structure = os.path.join(resource_folder, "core-structure.yaml")

    return populate_repositories_from_config(core_structure) 


def populate_repositories_from_config(core_structure):
    repos = []
    with open(core_structure, 'r') as stream:
        repos_yaml = yaml.safe_load(stream)

    # Support both 'DeploymentGroups' and 'Deployment Groups'
    deployment_groups = get_key_with_variants(repos_yaml, 'DeploymentGroups', 'Deployment Groups')
    if not deployment_groups:
        print(f"DeploymentGroups not found in {core_structure}, unable to populate repositories")
        return repos

    for deployment_group in deployment_groups:
        if 'BuildDefinitions' not in deployment_group:
            continue
        
        for row in deployment_group['BuildDefinitions']:
            repositoryNames = row.get('RepositoryName', [])
            
            # Check if repositoryNames is a string, if so convert to list
            if isinstance(repositoryNames, str):
                repositoryNames = [repositoryNames]
            
            # Ensure repositoryNames is iterable
            if not isinstance(repositoryNames, list):
                print(f"Warning: RepositoryName is not in an expected format for row: {row}")
                continue

            for repositoryName in repositoryNames:
                # Extract last 2 parts of repository path for cleaner names
                shortened_repo_name = extract_last_two_path_parts(repositoryName)
                print(f'Created repository {shortened_repo_name} (original: {repositoryName})')
                item = {
                    'RepositoryName': shortened_repo_name,
                    'Domain': row['Domain'],
                    'Tier': row.get('Tier', 5),
                    'Subdomain': row['SubDomain'],
                    'Team': row['TeamName'],
                    'BuildDefinitionName': row['BuildDefinitionName']
                }
                repos.append(item)

    return repos


# Function to populate environments
def populate_environments_from_env_groups(resource_folder):
    if not resource_folder:
        print("Please supply path for the resources")
        return []

    banking_core = os.path.join(resource_folder, "core-structure.yaml")
    return populate_environments_from_env_groups_from_config(banking_core)


def populate_environments_from_env_groups_from_config(config_file_path):
    envs = []
    
    with open(config_file_path, 'r') as stream:
        repos_yaml = yaml.safe_load(stream)

    # Support both 'Environment Groups' and 'EnvironmentGroups'
    environment_groups = get_key_with_variants(repos_yaml, 'Environment Groups', 'EnvironmentGroups')
    if not environment_groups:
        print(f"Environment Groups key not found in {config_file_path}, unable to populate envs from config")
        return envs

    for row in environment_groups:
        print_linter_result(row.get('Name', 'N/A'), validate_environment(row))
        
        # Handle both 'Responsable' and 'Responsible' field names
        responsable = row.get('Responsable') or row.get('Responsible', '')
        if responsable:
            responsable = responsable.lower()
        
        # Define the environment item
        item = {
            'Name': row['Name'],
            'Type': row['Type'],
            'Criticality': calculate_criticality(row['Tier']),
            'CloudAccounts': [""],  # Add CloudAccounts if applicable
            'Status': row['Status'],
            'Responsable': responsable,
            'BU': row.get('BU', None),
            'TeamName': row.get('TeamName', None),  # Add TeamName from the environment or set as None
            'Ticketing': load_ticketing(row),
            'Messaging': load_messaging(row),
            'Services': []  # To populate services later
        }

        # Now process the services under the "Team" or "Services" key
        if 'Services' in row:
            for service in row['Services']:
                print_linter_result(service.get('Service', 'N/A'), validate_service(service))
                repository_names = service.get('RepositoryName', [])
                if isinstance(repository_names, str):
                    repository_names = [repository_names]
                # Build the service entry with association details
                service_entry = {
                    'Service': service['Service'],
                    'Type': service['Type'],
                    'Tier': service.get('Tier', 5),  # Default tier to 5 if not specified
                    'TeamName': service.get('TeamName', item['TeamName']),  # Default to environment's TeamName if missing
                    'Ticketing': load_ticketing(service),
                    'Messaging': load_messaging(service),
                    'Deployment_set': service.get('Deployment_set', None),
                    'Deployment_tag': service.get('Deployment_tag', None),
                    'MultiConditionRule': list(x for x in [load_multi_condition_rule(service.get('MultiConditionRule', None))] if x is not None),
                    'MultiConditionRules': load_multi_condition_rules(service),
                    'RepositoryName': repository_names,  # Properly handle missing 'RepositoryName'
                    'SearchName': service.get('SearchName', None),
                    "Tag": service.get("Tag", None),
                    "Tag_rule": service.get("Tag_rule", None),
                    "Tags_rule": service.get("Tags_rule", None),
                    "Tag_label": service.get("Tag_label", None),
                    "Tags_label": service.get("Tags_label", None),
                    "Cidr": service.get("Cidr", None),
                    "Fqdn": service.get("Fqdn", None),
                    "Netbios": service.get("Netbios", None),
                    "OsNames": service.get("OsNames", None),
                    "Hostnames": service.get("Hostnames", None),
                    "ProviderAccountId": service.get("ProviderAccountId", None),
                    "ProviderAccountName": service.get("ProviderAccountName", None),
                    "ResourceGroup": service.get("ResourceGroup", None),
                    "AssetType": service.get("AssetType", None)
                }
                item['Services'].append(service_entry)

        # Append the environment entry to the list of environments
        envs.append(item)

    return envs

# Function to populate subdomain owners
def populate_subdomain_owners(repos):
    subdomains = {}

    for repo in repos:
        print(repo['RepositoryName'])

        if repo['Subdomain'] not in subdomains:
            subdomains[repo['Subdomain']] = []

        if repo['Team'] not in subdomains[repo['Subdomain']]:
            subdomains[repo['Subdomain']].append(repo['Team'])

    return subdomains


# Function to populate teams

# Example of populating repositories - already in place, no changes needed unless additional processing is required

# Function to populate teams
def populate_teams(resource_folder, config_file_name='run-config.yaml'):
    teams = []

    if not resource_folder:
        print("Please supply path for the resources")
        return teams

    # Load teams folder from configuration
    teams_folder = load_teams_folder(resource_folder, config_file_name)
    teams_file_path = os.path.join(resource_folder, teams_folder)

    if not os.path.exists(teams_file_path):
        print(f"Path does not exist: {teams_file_path}")
        print(f"TeamsFolder configured in {config_file_name}: {teams_folder}")
        exit(1)

    for team_file in Path(teams_file_path).glob("*.yaml"):
        with open(team_file, 'r') as stream:
            team = yaml.safe_load(stream)

        found = False
        for t in teams:
            if t['TeamName'] == team['TeamName']:
                found = True
                break

        if not found:
            teams.append(team)

    return teams


# Function to populate hives
def populate_hives(resource_folder, config_file_name='run-config.yaml'):
    hives = []

    if not resource_folder:
        print("Please supply path for the resources")
        return hives

    # Load hives file path from configuration
    enable_hives, hives_file = load_hives_config(resource_folder, config_file_name)
    
    if not enable_hives:
        print(f"Hives are disabled in {config_file_name}")
        return hives
    
    yaml_file = os.path.join(resource_folder, hives_file)

    if not os.path.exists(yaml_file):
        print(f"File not found or invalid path: {yaml_file}")
        print(f"HivesFile configured in {config_file_name}: {hives_file}")
        return hives

    with open(yaml_file, 'r') as stream:
        yaml_content = yaml.safe_load(stream)

    is_custom_email = yaml_content.get('CustomEmail', False)
    company_email_domain = yaml_content.get('CompanyEmailDomain', None)
    if not is_custom_email and not company_email_domain:
        company_email_domain = input('Please enter company email domain (without @ symbol):')

    for hive in yaml_content['Hives']:
        for team in hive['Teams']:
            products = []
            if team.get('Product'):
                products = [conditionally_replace_first_last_name_with_email(is_custom_email, company_email_domain, p)
                            for p in team['Product'].split(' and ')]

            hive_object = {
                'Lead': conditionally_replace_first_last_name_with_email(is_custom_email, company_email_domain, team['Lead']),
                'Product': products,
                'Team': team['Name']
            }

            hives.append(hive_object)

    return hives

# If is_custom_email=True, only validate the emails and don't replace anything
def conditionally_replace_first_last_name_with_email(is_custom_email, company_email_domain, first_last_name_or_email):
    if (is_custom_email):
        try:
            result = validate_email(first_last_name_or_email)
            return
        except EmailNotValidError as e:
            print(str(e))
            exit(1)

    
    return first_last_name_or_email.strip().lower().replace(" ", ".") + "@" + company_email_domain


def populate_all_access_emails(resource_folder):
    if not resource_folder:
        print("Please supply path for the resources")
        return []

    core_structure = os.path.join(resource_folder, "core-structure.yaml")

    return populate_all_access_emails_from_config(core_structure)


def populate_all_access_emails_from_config(config_file_path):
    with open(config_file_path, 'r') as stream:
        repos_yaml = yaml.safe_load(stream)

    if 'AllAccessAccounts' not in repos_yaml:
        print(f"AllAccessAccounts not found in {config_file_path}, unable to populate all access account list")
        return []
    return repos_yaml['AllAccessAccounts']

# Populate applications

# Populate applications
def populate_applications(resource_folder):
    if not resource_folder:
        print("Please supply path for the resources")
        return []

    core_structure = os.path.join(resource_folder, "core-structure.yaml")

    return populate_applications_from_config(core_structure)


def populate_applications_from_config(config_file_path):
    apps = []
    with open(config_file_path, 'r') as stream:
        apps_yaml = yaml.safe_load(stream)

    # Support both 'DeploymentGroups' and 'Deployment Groups'
    deployment_groups = get_key_with_variants(apps_yaml, 'DeploymentGroups', 'Deployment Groups')
    if not deployment_groups:
        print(f"DeploymentGroups key not found in {config_file_path}, unable to populate apps from config")
        return apps
        

    for row in deployment_groups:
        print_linter_result(row.get("AppName", "N/A"), validate_application(row))
        app = {
            'AppName': row['AppName'],
            'BU': row.get('BU', None),
            'Status': row.get('Status', None),
            'TeamNames': row.get('TeamNames', []),
            'ReleaseDefinitions': row['ReleaseDefinitions'],
            'Responsable': row['Responsable'].lower(),
            'Criticality': calculate_criticality(row.get('Tier', 5)),
            'Deployment_set': row.get('Deployment_set', None),
            'Ticketing': load_ticketing(row),
            'Messaging': load_messaging(row),
            'Tag_label': row.get('Tag_label', None),
            'Tags_label': row.get('Tags_label', None),
            'Components': []
        }

        if not 'Components' in row:
            continue

        for component in row['Components']:
            # Handle RepositoryName properly
            print_linter_result(component.get("ComponentName", "N/A"), validate_component(component))
            repository_names = component.get('RepositoryName', [])
            if isinstance(repository_names, str):
                repository_names = [repository_names]

            # Get ticketing and messaging configurations
            ticketing = load_ticketing(component) or app.get('Ticketing')  # Inherit from app if not specified
            messaging = load_messaging(component) or app.get('Messaging')  # Inherit from app if not specified

            comp = {
                'ComponentName': component['ComponentName'],
                'Status': component.get('Status', None),
                'Type': component.get('Type', None),
                'Ticketing': ticketing,
                'Messaging': messaging,
                'TeamNames': component.get('TeamNames', app['TeamNames']),
                'Deployment_set': component.get('Deployment_set', None),
                'RepositoryName': repository_names,
                'SearchName': component.get('SearchName', None),
                'Tags': component.get('Tags', None),
                'Tag_label': component.get('Tag_label', None),
                'Tags_label': component.get('Tags_label', None),
                'Cidr': component.get('Cidr', None),
                'Fqdn': component.get('Fqdn', None),
                'Netbios': component.get('Netbios', None),
                'OsNames': component.get('OsNames', None),
                'Hostnames': component.get('Hostnames', None),
                'ProviderAccountId': component.get('ProviderAccountId', None),
                'ProviderAccountName': component.get('ProviderAccountName', None),
                'ResourceGroup': component.get('ResourceGroup', None),
                'AssetType': component.get('AssetType', None),
                'MultiConditionRule': load_multi_condition_rule(component.get('MultiConditionRule', None)),
                'MultiConditionRules': load_multi_condition_rules(component),
                'Criticality': calculate_criticality(component.get('Tier', 5)),
                'Domain': component.get('Domain', None),
                'SubDomain': component.get('SubDomain', None),
                'AutomaticSecurityReview': component.get('AutomaticSecurityReview', None)
            }

            if DEBUG:
                print(f"\nProcessing component {comp['ComponentName']}:")
                if ticketing:
                    print(f"└─ Ticketing configuration:")
                    for ticket_config in ticketing:
                        print(f"   └─ TIntegrationName: {ticket_config.get('TIntegrationName')}")
                        print(f"   └─ Backlog: {ticket_config.get('Backlog')}")
                if messaging:
                    print(f"└─ Messaging configuration:")
                    for message_config in messaging:
                        print(f"   └─ MIntegrationName: {message_config.get('MIntegrationName')}")
                        print(f"   └─ Channel: {message_config.get('Channel')}")

            app['Components'].append(comp)
        apps.append(app)

    return apps


def load_multi_condition_rule(mcr):
    if not mcr:
        return None
    
    # Validate the multi-condition rule format
    from providers.Linter import validate_multi_condition_rule
    is_valid, error_msg = validate_multi_condition_rule(mcr)
    if not is_valid:
        print(f'Multi-condition rule validation failed: {error_msg}')
        print(f'Skipping invalid multi-condition rule: {mcr}')
        return None
    
    # Map AccountId to ProviderAccountId for backward compatibility
    provider_account_id = mcr.get("ProviderAccountId") or mcr.get("AccountId")
    
    rule = {
        "RepositoryName": mcr.get("RepositoryName", None),
        "SearchName": mcr.get("SearchName", None),
        "Tags": mcr.get("Tags", None),
        "Tag": mcr.get("Tag", None),
        "Tag_rule": mcr.get("Tag_rule", None),
        "Tags_rule": mcr.get("Tags_rule", None),
        "Tag_label": mcr.get("Tag_label", None),
        "Tags_label": mcr.get("Tags_label", None),
        "Cidr": mcr.get("Cidr", None),
        "Fqdn": mcr.get("Fqdn", None),
        "Netbios": mcr.get("Netbios", None),
        "OsNames": mcr.get("OsNames", None),
        "Hostnames": mcr.get("Hostnames", None),
        "ProviderAccountId": provider_account_id,  # Support both AccountId and ProviderAccountId
        "ProviderAccountName": mcr.get("ProviderAccountName", None),
        "ResourceGroup": mcr.get("ResourceGroup", None),
        "AssetType": mcr.get("AssetType", None)
    }

    if all(value is None for value in rule.values()):
        print(f'Multicondition rule is missing values, skipping multicondition rule. Received MultiConditionRule: {mcr}')
        return None
    return rule


def load_multi_condition_rules(component):
    rules = []
    
    # Check all possible variations of multicondition rule keys
    rule_keys = [
        'MULTI_MultiConditionRules',
        'MultiMultiConditionRules',
        'MultiConditionRules',
        'MultiConditionRule'
    ]
    
    for key in rule_keys:
        if key in component and component[key]:
            # If it's a single rule, wrap it in a list
            rules_list = component[key] if isinstance(component[key], list) else [component[key]]
            for mcr in rules_list:
                rule = load_multi_condition_rule(mcr)
                if rule:
                    rules.append(rule)
    
    return rules if rules else None


def load_flag_for_create_users(resource_folder):
    core_structure = os.path.join(resource_folder, "core-structure.yaml")
    return load_flag_for_create_users_from_config(core_structure)


def load_flag_for_create_users_from_config(config_file_path):
    with open(config_file_path, 'r') as stream:
        repos_yaml = yaml.safe_load(stream)

    # Handle both dictionary and list structures
    if isinstance(repos_yaml, dict):
        # Dictionary structure - check for CreateUsersForApplications flag
        if True == repos_yaml.get('CreateUsersForApplications', "False"):
            return True
    elif isinstance(repos_yaml, list):
        # List structure - no CreateUsersForApplications flag, return False
        return False
    
    return False


def load_ticketing(element):
    """
    Load ticketing configuration from element.
    Only accepts list format:
    Ticketing:
      - TIntegrationName: Jira-testphx
        Backlog: demoteam2
    """
    if 'Ticketing' not in element:
        return None
    
    ticketing = element.get('Ticketing')
    
    # Only accept list format
    if not isinstance(ticketing, list):
        print(f'Ticketing must be in list format. Current format: {type(ticketing)}')
        print('Example format:\nTicketing:\n  - TIntegrationName: Jira-testphx\n    Backlog: demoteam2')
        return None
    
    if not ticketing:  # Empty list
        return None
    
    # Get the first item from the list
    ticketing_config = ticketing[0]
    if not isinstance(ticketing_config, dict):
        print(f'Invalid ticketing configuration format: {ticketing_config}')
        return None
    
    # Support both old and new integration name fields
    integration_name = ticketing_config.get('TIntegrationName') or ticketing_config.get('IntegrationName')
    backlog = ticketing_config.get('Backlog')
    
    # Check for required fields
    if not backlog:
        print(f'Ticketing missing mandatory Backlog field: {ticketing_config}')
        return None
    
    if not integration_name:
        print(f'Ticketing missing integration name (TIntegrationName or IntegrationName): {ticketing_config}')
        return None
    
    if ticketing_config.get('IntegrationName') and not ticketing_config.get('TIntegrationName'):
        print(f'Warning: Using deprecated "IntegrationName" field in Ticketing. Please update to "TIntegrationName"')
    
    return ticketing


def load_messaging(element):
    """
    Load messaging configuration from element.
    Only accepts list format:
    Messaging:
      - MIntegrationName: Slack-phx
        Channel: int-tests
    """
    if 'Messaging' not in element:
        return None
    
    messaging = element.get('Messaging')
    
    # Only accept list format
    if not isinstance(messaging, list):
        print(f'Messaging must be in list format. Current format: {type(messaging)}')
        print('Example format:\nMessaging:\n  - MIntegrationName: Slack-phx\n    Channel: int-tests')
        return None
    
    if not messaging:  # Empty list
        return None
    
    # Get the first item from the list
    messaging_config = messaging[0]
    if not isinstance(messaging_config, dict):
        print(f'Invalid messaging configuration format: {messaging_config}')
        return None
    
    # Support both old and new integration name fields
    integration_name = messaging_config.get('MIntegrationName') or messaging_config.get('IntegrationName')
    channel = messaging_config.get('Channel')
    
    # Check for required fields
    if not channel:
        print(f'Messaging missing mandatory Channel field: {messaging_config}')
        return None
    
    if not integration_name:
        print(f'Messaging missing integration name (MIntegrationName or IntegrationName): {messaging_config}')
        return None
    
    if messaging_config.get('IntegrationName') and not messaging_config.get('MIntegrationName'):
        print(f'Warning: Using deprecated "IntegrationName" field in Messaging. Please update to "MIntegrationName"')
    
    return messaging


def load_run_config(resource_folder, config_file_name='run-config.yaml'):
    default_config_files = ["core-structure.yaml"]
    config_file = os.path.join(resource_folder, config_file_name)
    if not resource_folder or not os.path.exists(config_file):
        config = {
            "ConfigFiles": default_config_files
        }
        print(f" ! Run config not provided via {config_file_name}, using default values: {config}")
        return config

    with open(config_file, 'r') as stream:
        config = yaml.safe_load(stream)

    if not 'ConfigFiles' in config:
        print(f" ! ConfigFiles not found in {config_file_name}, using default value: {default_config_files}")
        config['ConfigFiles'] = default_config_files
    
    return config


def print_linter_result(name, linter_result):
    print("****************************************")
    print("* Linter results")
    print("*")
    print(f"* {name} Is Valid: {linter_result[0]}")
    if linter_result[1]:
        print("*")
        print(f"* Linter errors: {linter_result[1]}")
    print("****************************************")


def load_remote_configuration_locations(resource_folder, config_file_name='run-config.yaml'):
    if not resource_folder:
        print("Please supply path for the resources")
        return []

    repos_file = os.path.join(resource_folder, config_file_name)

    with open(repos_file, 'r') as stream:
        repos_yaml = yaml.safe_load(stream)

    if not 'GitHubRepositories' in repos_yaml:
        print(f"{config_file_name} configuration is missing 'GitHubRepositories' property, will not load GitHub configurations")
        return []

    return repos_yaml['GitHubRepositories']


def load_github_repo_folder(resource_folder, config_file_name='run-config.yaml'):
    if not resource_folder:
        print("Please supply path for the resources")
        return None

    repos_file = os.path.join(resource_folder, config_file_name)

    with open(repos_file, 'r') as stream:
        repos_yaml = yaml.safe_load(stream)

    if not 'GitHubRepoFolder' in repos_yaml:
        raise Exception(f"{config_file_name} configuration is missing 'GitHubRepoFolder' property")

    return repos_yaml['GitHubRepoFolder']


def load_github_config_file_name(resource_folder, config_file_name='run-config.yaml'):
    if not resource_folder:
        print("Please supply path for the resources")
        return None

    repos_file = os.path.join(resource_folder, config_file_name)

    with open(repos_file, 'r') as stream:
        repos_yaml = yaml.safe_load(stream)

    if not 'ConfigFileName' in repos_yaml:
        raise Exception(f"{config_file_name} configuration is missing 'ConfigFileName' property")

    return repos_yaml['ConfigFileName']


def load_enable_github_autodetect_config(resource_folder, config_file_name='run-config.yaml'):
    if not resource_folder:
        print("Please supply path for the resources")
        return None

    repos_file = os.path.join(resource_folder, config_file_name)

    with open(repos_file, 'r') as stream:
        repos_yaml = yaml.safe_load(stream)

    if not 'EnableGitHubAutoDetectConfig' in repos_yaml:
        print(f"EnableGitHubAutoDetectConfig not found in {config_file_name}, disabling GitHub autodetection of config files")
        return False

    return repos_yaml['EnableGitHubAutoDetectConfig']


def load_teams_folder(resource_folder, config_file_name='run-config.yaml'):
    """Load the teams folder path from run-config.yaml"""
    if not resource_folder:
        print("Please supply path for the resources")
        return "Teams"  # Default fallback

    config_file = os.path.join(resource_folder, config_file_name)
    
    if not os.path.exists(config_file):
        print(f"{config_file_name} not found, using default Teams folder")
        return "Teams"

    with open(config_file, 'r') as stream:
        config = yaml.safe_load(stream)

    if not 'TeamsFolder' in config:
        print(f"TeamsFolder not found in {config_file_name}, using default: Teams")
        return "Teams"

    teams_folder = config['TeamsFolder']
    # Strip leading slash to ensure it's treated as a relative path
    if teams_folder.startswith('/'):
        teams_folder = teams_folder[1:]
    
    return teams_folder


def load_hives_config(resource_folder, config_file_name='run-config.yaml'):
    """Load hives configuration from run-config.yaml"""
    if not resource_folder:
        print("Please supply path for the resources")
        return True, "hives.yaml"  # Default fallback

    config_file = os.path.join(resource_folder, config_file_name)
    
    if not os.path.exists(config_file):
        print(f"{config_file_name} not found, using default hives configuration")
        return True, "hives.yaml"

    with open(config_file, 'r') as stream:
        config = yaml.safe_load(stream)

    enable_hives = config.get('EnableHives', True)
    hives_file = config.get('HivesFile', 'hives.yaml')
    
    return enable_hives, hives_file

def extract_config_file_summary(config_file_path):
    """
    Extract a comprehensive summary of what's in a YAML config file (v4.8.8)
    Parses YAML to count and list all entities for preview before processing
    
    Returns:
        dict: {
            'applications': [list of app names],
            'environments': [list of env names],
            'services': [list of service names with env],
            'components': [list of component names with app],
            'repositories': [list of repo names],
            'teams': [list of team names],
            'counts': {total counts for each entity type}
        }
    """
    summary = {
        'applications': [],
        'environments': [],
        'services': [],
        'components': [],
        'repositories': [],
        'teams': [],
        'counts': {
            'total_applications': 0,
            'total_environments': 0,
            'total_services': 0,
            'total_components': 0,
            'total_repositories': 0,
            'total_teams': 0
        }
    }
    
    try:
        with open(config_file_path, 'r') as stream:
            config_data = yaml.safe_load(stream)
        
        if not config_data:
            return summary
        
        # Extract Applications and Components
        # Support both 'DeploymentGroups' and 'Deployment Groups'
        deployment_groups = get_key_with_variants(config_data, 'DeploymentGroups', 'Deployment Groups')
        if deployment_groups:
            for app in deployment_groups:
                app_name = app.get('AppName', 'Unnamed Application')
                summary['applications'].append(app_name)
                summary['counts']['total_applications'] += 1
                
                # Extract components
                if 'Components' in app:
                    for component in app['Components']:
                        comp_name = component.get('ComponentName', 'Unnamed Component')
                        summary['components'].append(f"{app_name} -> {comp_name}")
                        summary['counts']['total_components'] += 1
        
        # Extract Environments and Services
        # Support both 'Environment Groups' and 'EnvironmentGroups'
        environment_groups = get_key_with_variants(config_data, 'Environment Groups', 'EnvironmentGroups')
        if environment_groups:
            for env_group in environment_groups:
                # Handle both single environment and list of environments
                environments = env_group.get('Environments', [])
                if not isinstance(environments, list):
                    environments = [environments]
                
                for env in environments:
                    env_name = env.get('Name', 'Unnamed Environment')
                    summary['environments'].append(env_name)
                    summary['counts']['total_environments'] += 1
                    
                    # Extract services from this environment
                    services = env.get('Services', [])
                    for service in services:
                        service_name = service.get('ServiceName', 'Unnamed Service')
                        summary['services'].append(f"{service_name} ({env_name})")
                        summary['counts']['total_services'] += 1
        
        # Extract Repositories
        if 'Repositories' in config_data:
            repos = config_data['Repositories']
            if isinstance(repos, list):
                for repo in repos:
                    repo_name = repo.get('RepositoryName', repo.get('Name', 'Unnamed Repository'))
                    summary['repositories'].append(repo_name)
                    summary['counts']['total_repositories'] += 1
        
        # Extract Teams
        if 'Teams' in config_data:
            teams = config_data['Teams']
            if isinstance(teams, list):
                for team in teams:
                    team_name = team.get('TeamName', team.get('Name', 'Unnamed Team'))
                    summary['teams'].append(team_name)
                    summary['counts']['total_teams'] += 1
        
    except Exception as e:
        print(f"⚠️ Warning: Could not fully extract config summary from {config_file_path}: {e}")
    
    return summary

def print_config_file_summary(config_file_path, file_index, total_files, api_domain, source_type='local'):
    """
    Print a comprehensive summary of a config file before processing (v4.8.8)
    Shows what will be created/updated with hierarchical relationships
    
    Args:
        config_file_path: Path to the YAML config file
        file_index: Current file number (1-based)
        total_files: Total number of files to process
        api_domain: API endpoint being used
        source_type: Type of source ('local' or 'github')
    """
    # Determine source label and emoji
    source_emoji = "📁" if source_type == 'local' else "🌐"
    source_label = "LOCAL FILE" if source_type == 'local' else "GITHUB REPOSITORY"
    
    print("\n" + "=" * 80)
    print(f"{source_emoji} PROCESSING FILE {file_index}/{total_files} - {source_label}")
    print("=" * 80)
    print(f"FILE: {os.path.basename(config_file_path)}")
    print(f"PATH: {config_file_path}")
    print(f"SOURCE: {source_label}")
    print(f"API ENDPOINT: {api_domain}")
    print("=" * 80)
    
    summary = extract_config_file_summary(config_file_path)
    
    print(f"\n📊 CONFIGURATION OVERVIEW")
    print("-" * 80)
    print(f"  Applications: {summary['counts']['total_applications']}")
    print(f"  Environments: {summary['counts']['total_environments']}")
    print(f"  Services: {summary['counts']['total_services']}")
    print(f"  Components: {summary['counts']['total_components']}")
    print(f"  Repositories: {summary['counts']['total_repositories']}")
    print(f"  Teams: {summary['counts']['total_teams']}")
    
    # Print Applications and their Components
    if summary['applications']:
        print(f"\n📱 APPLICATIONS ({summary['counts']['total_applications']}):")
        print("-" * 80)
        for app_name in summary['applications']:
            print(f"  • {app_name}")
            # Print components for this app
            app_components = [c for c in summary['components'] if c.startswith(f"{app_name} ->")]
            if app_components:
                for comp in app_components[:5]:  # Show first 5
                    comp_name = comp.split(" -> ")[1]
                    print(f"    └─ {comp_name}")
                if len(app_components) > 5:
                    print(f"    └─ ... and {len(app_components) - 5} more components")
    
    # Print Environments and their Services
    if summary['environments']:
        print(f"\n🌍 ENVIRONMENTS ({summary['counts']['total_environments']}):")
        print("-" * 80)
        for env_name in summary['environments']:
            print(f"  • {env_name}")
            # Print services for this environment
            env_services = [s for s in summary['services'] if f"({env_name})" in s]
            if env_services:
                for service in env_services[:5]:  # Show first 5
                    service_name = service.split(" (")[0]
                    print(f"    └─ {service_name}")
                if len(env_services) > 5:
                    print(f"    └─ ... and {len(env_services) - 5} more services")
    
    # Print all Components summary
    if summary['components']:
        print(f"\n🔧 COMPONENTS ({summary['counts']['total_components']}):")
        print("-" * 80)
        for comp in summary['components'][:10]:  # Show first 10
            print(f"  • {comp}")
        if len(summary['components']) > 10:
            print(f"  • ... and {len(summary['components']) - 10} more components")
    
    # Print Repositories
    if summary['repositories']:
        print(f"\n📦 REPOSITORIES ({summary['counts']['total_repositories']}):")
        print("-" * 80)
        for repo in summary['repositories'][:10]:  # Show first 10
            print(f"  • {repo}")
        if len(summary['repositories']) > 10:
            print(f"  • ... and {len(summary['repositories']) - 10} more repositories")
    
    # Print Teams
    if summary['teams']:
        print(f"\n👥 TEAMS ({summary['counts']['total_teams']}):")
        print("-" * 80)
        for team in summary['teams']:
            print(f"  • {team}")
    
    print("\n" + "=" * 80)
    print(f"🚀 STARTING PROCESSING...")
    print("=" * 80 + "\n")
    
    return summary
