"""
Phoenix Security - Automatic Asset Grouping Engine
Intelligently groups assets by tags and creates Components/Services with checkpoint/resume support

Author: Phoenix Security Team
Date: 2025-11-19
Version: 1.0.0
"""

import os
import json
import yaml
import time
import ipaddress
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional, Set
from collections import defaultdict, Counter
from pathlib import Path
import Levenshtein
import requests

# Import Phoenix API functions
from providers.Phoenix import (
    get_auth_token, construct_api_url, create_application,
    create_custom_component, create_component_rule, get_phoenix_components,
    populate_applications_and_environments
)


class CheckpointManager:
    """Manages checkpoints for resumable execution"""
    
    def __init__(self, checkpoint_folder: str):
        self.checkpoint_folder = Path(checkpoint_folder)
        self.checkpoint_folder.mkdir(parents=True, exist_ok=True)
        
    def save_checkpoint(self, checkpoint_type: str, data: Any, filename: str = None):
        """Save checkpoint data"""
        if filename is None:
            filename = f"checkpoint-{checkpoint_type}-{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        filepath = self.checkpoint_folder / filename
        
        with open(filepath, 'w') as f:
            if isinstance(data, (dict, list)):
                json.dump(data, f, indent=2, default=str)
            else:
                f.write(str(data))
        
        print(f"✅ Checkpoint saved: {filepath}")
        return str(filepath)
    
    def load_checkpoint(self, filename: str) -> Optional[Any]:
        """Load checkpoint data"""
        filepath = self.checkpoint_folder / filename
        
        if not filepath.exists():
            return None
        
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Failed to load checkpoint {filename}: {e}")
            return None
    
    def checkpoint_exists(self, filename: str) -> bool:
        """Check if checkpoint exists"""
        return (self.checkpoint_folder / filename).exists()
    
    def get_checkpoint_age(self, filename: str) -> Optional[timedelta]:
        """Get age of checkpoint file"""
        filepath = self.checkpoint_folder / filename
        
        if not filepath.exists():
            return None
        
        mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
        return datetime.now() - mtime


class TagAnalyzer:
    """Analyzes asset tags to identify optimal grouping strategies"""
    
    def __init__(self, assets: List[Dict]):
        self.assets = assets
        self.total_assets = len(assets)
        self.tag_stats = defaultdict(lambda: {'count': 0, 'values': Counter(), 'coverage': 0.0})
    
    def analyze(self) -> Dict[str, Any]:
        """Perform comprehensive tag analysis"""
        print(f"\n🔍 Analyzing tags across {self.total_assets:,} assets...")
        
        # Count tags
        assets_with_tags = 0
        assets_without_tags = 0
        
        for asset in self.assets:
            tags = asset.get('tags')
            
            if not tags or tags is None:
                assets_without_tags += 1
                continue
            
            assets_with_tags += 1
            
            # Process each tag
            for tag in tags:
                if isinstance(tag, dict):
                    key = tag.get('key', '').strip()
                    value = tag.get('value', '').strip()
                    
                    if key and value:
                        self.tag_stats[key]['count'] += 1
                        self.tag_stats[key]['values'][value] += 1
        
        # Calculate coverage
        for key in self.tag_stats:
            self.tag_stats[key]['coverage'] = (self.tag_stats[key]['count'] / self.total_assets) * 100
            self.tag_stats[key]['unique_values'] = len(self.tag_stats[key]['values'])
            self.tag_stats[key]['most_common'] = dict(self.tag_stats[key]['values'].most_common(5))
        
        # Sort by coverage
        sorted_tags = sorted(
            self.tag_stats.items(),
            key=lambda x: x[1]['coverage'],
            reverse=True
        )
        
        analysis_result = {
            'total_assets': self.total_assets,
            'assets_with_tags': assets_with_tags,
            'assets_without_tags': assets_without_tags,
            'tag_coverage_percent': (assets_with_tags / self.total_assets * 100) if self.total_assets > 0 else 0,
            'total_unique_tag_keys': len(self.tag_stats),
            'tags_by_coverage': [
                {
                    'key': key,
                    'asset_count': stats['count'],
                    'coverage_percent': stats['coverage'],
                    'unique_values': stats['unique_values'],
                    'most_common_values': stats['most_common']
                }
                for key, stats in sorted_tags
            ]
        }
        
        return analysis_result
    
    def print_analysis(self, analysis: Dict):
        """Print human-readable analysis"""
        print("\n" + "="*80)
        print("📊 TAG ANALYSIS RESULTS")
        print("="*80)
        
        print(f"\n📈 Overview:")
        print(f"  Total Assets: {analysis['total_assets']:,}")
        print(f"  Assets with Tags: {analysis['assets_with_tags']:,} ({analysis['tag_coverage_percent']:.1f}%)")
        print(f"  Assets without Tags: {analysis['assets_without_tags']:,}")
        print(f"  Unique Tag Keys: {analysis['total_unique_tag_keys']}")
        
        print(f"\n🏷️  Top Tags by Coverage:")
        print(f"  {'Tag Key':<30} {'Assets':<10} {'Coverage':<10} {'Unique Values':<15}")
        print(f"  {'-'*30} {'-'*10} {'-'*10} {'-'*15}")
        
        for tag_info in analysis['tags_by_coverage'][:20]:  # Show top 20
            print(f"  {tag_info['key']:<30} {tag_info['asset_count']:<10,} "
                  f"{tag_info['coverage_percent']:>8.1f}% {tag_info['unique_values']:>14,}")
        
        print("\n" + "="*80)
    
    def recommend_grouping_tags(self, config: Dict) -> List[str]:
        """Recommend optimal tags for grouping based on configuration"""
        primary_tags = config.get('grouping', {}).get('primary_tags', [])
        secondary_tags = config.get('grouping', {}).get('secondary_tags', [])
        min_frequency = config.get('grouping', {}).get('min_frequency_threshold', 10)
        
        recommended = []
        
        # Check primary tags
        for tag in primary_tags:
            if tag in self.tag_stats and self.tag_stats[tag]['count'] >= min_frequency:
                recommended.append(tag)
        
        # Check secondary tags
        for tag in secondary_tags:
            if tag in self.tag_stats and self.tag_stats[tag]['count'] >= min_frequency:
                if tag not in recommended:
                    recommended.append(tag)
        
        # Add high-frequency tags not in config
        if config.get('grouping', {}).get('use_high_frequency_fallback', True):
            for key, stats in sorted(self.tag_stats.items(), key=lambda x: x[1]['count'], reverse=True):
                if key not in recommended and stats['count'] >= min_frequency:
                    # Exclude metadata tags
                    if key not in ['scanner_name', 'import_date', 'import_type', 'lastScanDateTime']:
                        recommended.append(key)
                        if len(recommended) >= 10:  # Limit recommendations
                            break
        
        return recommended


class AssetGrouper:
    """Groups assets by tags with intelligent fallback strategies"""
    
    def __init__(self, assets: List[Dict], config: Dict, tag_analysis: Dict):
        self.assets = assets
        self.config = config
        self.tag_analysis = tag_analysis
        self.groups = defaultdict(lambda: {'assets': [], 'metadata': {}})
    
    def group_by_tags(self, primary_tag: str, secondary_tag: Optional[str] = None) -> Dict:
        """Group assets by primary and optional secondary tags"""
        print(f"\n🔄 Grouping assets by tags: {primary_tag}" + 
              (f" → {secondary_tag}" if secondary_tag else ""))
        
        tagged_assets = []
        untagged_assets = []
        
        for asset in self.assets:
            tags = asset.get('tags')
            
            if not tags:
                untagged_assets.append(asset)
                continue
            
            # Extract tag values
            tag_dict = {tag.get('key'): tag.get('value') for tag in tags if isinstance(tag, dict)}
            
            primary_value = tag_dict.get(primary_tag)
            
            if not primary_value:
                untagged_assets.append(asset)
                continue
            
            # Create group key
            if secondary_tag:
                secondary_value = tag_dict.get(secondary_tag, 'NoTeam')
                group_key = f"{primary_value}|||{secondary_value}"
            else:
                group_key = primary_value
            
            self.groups[group_key]['assets'].append(asset)
            self.groups[group_key]['metadata'] = {
                'grouping_method': 'tag',
                'grouping_tag_key': primary_tag,
                'grouping_tag_value': primary_value,
                'primary_tag': primary_tag,
                'primary_value': primary_value,
                'secondary_tag': secondary_tag,
                'secondary_value': tag_dict.get(secondary_tag) if secondary_tag else None,
                'asset_type': asset.get('type', 'UNKNOWN'),
                'all_tags': tag_dict
            }
            
            tagged_assets.append(asset)
        
        print(f"  ✅ Grouped {len(tagged_assets):,} tagged assets into {len(self.groups)} groups")
        print(f"  ⚠️  {len(untagged_assets):,} untagged assets will use fallback strategy")
        
        return {
            'tagged_groups': dict(self.groups),
            'untagged_assets': untagged_assets
        }
    
    def group_untagged_by_type(self, untagged_assets: List[Dict]) -> Dict:
        """Group untagged assets by asset type"""
        print(f"\n🔄 Grouping {len(untagged_assets):,} untagged assets by type...")
        
        type_groups = defaultdict(list)
        
        for asset in untagged_assets:
            asset_type = asset.get('type', 'UNKNOWN')
            type_groups[asset_type].append(asset)
        
        for asset_type, assets in type_groups.items():
            print(f"  {asset_type}: {len(assets):,} assets")
        
        return dict(type_groups)
    
    def group_infra_by_network(self, infra_assets: List[Dict]) -> Dict:
        """Group INFRA assets by CIDR or hostname similarity"""
        print(f"\n🔄 Grouping {len(infra_assets):,} INFRA assets by network/hostname...")
        
        config_fallback = self.config.get('fallback', {}).get('infra', {})
        use_cidr = config_fallback.get('cidr_grouping', True)
        hostname_threshold = config_fallback.get('hostname_similarity_threshold', 0.8)
        
        cidr_groups = defaultdict(list)
        hostname_groups = []
        ungrouped = []
        
        for asset in infra_assets:
            # Try CIDR grouping
            if use_cidr:
                ip = asset.get('ip')
                if ip:
                    try:
                        # Group by /24 subnet
                        network = ipaddress.IPv4Network(f"{ip}/24", strict=False)
                        cidr_groups[str(network)].append(asset)
                        continue
                    except:
                        pass
            
            # Try hostname similarity
            hostname = asset.get('hostname') or asset.get('assetName')
            if hostname:
                added = False
                for group in hostname_groups:
                    # Check similarity with first asset in group
                    if group:
                        ref_hostname = group[0].get('hostname') or group[0].get('assetName')
                        if ref_hostname and Levenshtein.ratio(hostname, ref_hostname) >= hostname_threshold:
                            group.append(asset)
                            added = True
                            break
                
                if not added:
                    hostname_groups.append([asset])
            else:
                ungrouped.append(asset)
        
        # Combine results with proper metadata structure
        all_groups = {}
        
        # CIDR-based groups
        for cidr, assets in cidr_groups.items():
            all_groups[f"CIDR-{cidr}"] = {
                'assets': assets,
                'metadata': {
                    'grouping_method': 'cidr',
                    'cidr': cidr,
                    'asset_type': 'INFRA',
                    'group_type': 'network'
                }
            }
        
        # Hostname-based groups
        for idx, group in enumerate(hostname_groups):
            if len(group) >= self.config.get('grouping', {}).get('min_assets_per_component', 2):
                ref_name = group[0].get('hostname') or group[0].get('assetName', 'unknown')
                # Extract common prefix for better grouping
                hostnames = [a.get('hostname') or a.get('assetName', '') for a in group]
                all_groups[f"INFRA-{ref_name[:30]}"] = {
                    'assets': group,
                    'metadata': {
                        'grouping_method': 'hostname',
                        'hostname_pattern': ref_name,
                        'hostnames': hostnames[:10],  # Store up to 10 example hostnames
                        'asset_type': 'INFRA',
                        'group_type': 'hostname'
                    }
                }
        
        # Ungrouped assets
        if ungrouped:
            all_groups["INFRA-Ungrouped"] = {
                'assets': ungrouped,
                'metadata': {
                    'grouping_method': 'type',
                    'asset_type': 'INFRA',
                    'group_type': 'fallback'
                }
            }
        
        print(f"  ✅ Created {len(all_groups)} INFRA groups")
        
        return all_groups
    
    def group_software_by_repository(self, software_assets: List[Dict]) -> Dict:
        """Group SOFTWARE/REPOSITORY assets by repository name"""
        print(f"\n🔄 Grouping {len(software_assets):,} SOFTWARE assets by repository...")
        
        repo_groups = defaultdict(list)
        
        for asset in software_assets:
            repo = asset.get('repository')
            if repo:
                repo_groups[repo].append(asset)
            else:
                # Use asset name as fallback
                name = asset.get('assetName', 'unknown')
                repo_groups[f"CODE-{name}"].append(asset)
        
        # Convert to proper structure with metadata
        result = {}
        for repo_name, assets in repo_groups.items():
            result[repo_name] = {
                'assets': assets,
                'metadata': {
                    'grouping_method': 'repository',
                    'repository_name': repo_name,
                    'asset_type': assets[0].get('type', 'REPOSITORY'),
                    'group_type': 'repository'
                }
            }
        
        print(f"  ✅ Created {len(result)} repository groups")
        
        return result
    
    def group_containers_by_name(self, container_assets: List[Dict]) -> Dict:
        """Group CONTAINER assets by name similarity"""
        print(f"\n🔄 Grouping {len(container_assets):,} CONTAINER assets by name similarity...")
        
        threshold = self.config.get('fallback', {}).get('container', {}).get('name_similarity_threshold', 0.85)
        
        groups = []
        
        for asset in container_assets:
            name = asset.get('imageName') or asset.get('assetName', '')
            
            added = False
            for group in groups:
                ref_name = group[0].get('imageName') or group[0].get('assetName', '')
                if Levenshtein.ratio(name, ref_name) >= threshold:
                    group.append(asset)
                    added = True
                    break
            
            if not added:
                groups.append([asset])
        
        # Convert to dict with proper metadata
        result = {}
        for idx, group in enumerate(groups):
            if len(group) >= self.config.get('grouping', {}).get('min_assets_per_component', 2):
                ref_name = group[0].get('imageName') or group[0].get('assetName', 'unknown')
                image_names = [a.get('imageName') or a.get('assetName', '') for a in group]
                result[f"CONTAINER-{ref_name[:40]}"] = {
                    'assets': group,
                    'metadata': {
                        'grouping_method': 'image_name',
                        'image_name_pattern': ref_name,
                        'image_names': image_names[:10],
                        'asset_type': 'CONTAINER',
                        'group_type': 'container'
                    }
                }
        
        print(f"  ✅ Created {len(result)} container groups")
        
        return result
    
    def group_cloud_by_provider(self, cloud_assets: List[Dict]) -> Dict:
        """Group CLOUD assets by provider and account"""
        print(f"\n🔄 Grouping {len(cloud_assets):,} CLOUD assets by provider/account...")
        
        include_region = self.config.get('fallback', {}).get('cloud', {}).get('include_region', True)
        
        cloud_groups = defaultdict(list)
        
        for asset in cloud_assets:
            provider = asset.get('cloudProvider', 'UNKNOWN')
            account = asset.get('account', 'no-account')
            region = asset.get('region', 'no-region')
            
            if include_region:
                key = f"{provider}-{account}-{region}"
            else:
                key = f"{provider}-{account}"
            
            cloud_groups[key].append(asset)
        
        # Convert to proper structure with metadata
        result = {}
        for key, assets in cloud_groups.items():
            first_asset = assets[0]
            provider = first_asset.get('cloudProvider', 'UNKNOWN')
            account = first_asset.get('account', 'no-account')
            region = first_asset.get('region')
            
            result[key] = {
                'assets': assets,
                'metadata': {
                    'grouping_method': 'cloud_provider',
                    'cloud_provider': provider,
                    'provider_account_id': account,
                    'provider_account_name': account,  # Often same as ID
                    'region': region,
                    'asset_type': 'CLOUD',
                    'group_type': 'cloud'
                }
            }
        
        print(f"  ✅ Created {len(result)} cloud groups")
        
        return result


class ComponentCreator:
    """Creates Components/Services with rules and team assignments"""
    
    def __init__(self, config: Dict, headers: Dict, checkpoint_manager: CheckpointManager):
        self.config = config
        self.headers = headers
        self.checkpoint_manager = checkpoint_manager
        self.created_components = []
        self.created_rules = []
        self.errors = []
    
    def create_component_with_rules(self, 
                                    application_name: str,
                                    component_name: str,
                                    assets: List[Dict],
                                    group_metadata: Dict,
                                    create_rules: bool = True) -> Dict:
        """Create component and associated rules"""
        
        print(f"\n🏗️  Creating component: {component_name}")
        print(f"   Application: {application_name}")
        print(f"   Assets: {len(assets)}")
        
        try:
            # Extract team from metadata
            team_names = self._extract_team_names(assets, group_metadata)
            
            # Build component object
            component = {
                "ComponentName": component_name,
                "TeamNames": team_names,
                "Status": None,
                "Type": None
            }
            
            # Create component via Phoenix API
            create_custom_component(application_name, component, self.headers)
            
            result = {
                'component_name': component_name,
                'application_name': application_name,
                'asset_count': len(assets),
                'team_names': team_names,
                'created_at': datetime.now().isoformat(),
                'status': 'success'
            }
            
            # Create rules if enabled
            if create_rules and self.config.get('rules', {}).get('auto_create', True):
                rules = self._create_rules_for_component(
                    application_name,
                    component_name,
                    assets,
                    group_metadata
                )
                result['rules'] = rules
            
            self.created_components.append(result)
            
            # Checkpoint after each component
            if self.config.get('checkpoint', {}).get('frequency') == 'every_component':
                self._save_execution_checkpoint()
            
            print(f"   ✅ Component created successfully")
            
            return result
            
        except Exception as e:
            error = {
                'component_name': component_name,
                'application_name': application_name,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            self.errors.append(error)
            print(f"   ❌ Failed: {e}")
            
            if not self.config.get('advanced', {}).get('continue_on_error', True):
                raise
            
            return {'status': 'failed', 'error': str(e)}
    
    def _extract_team_names(self, assets: List[Dict], group_metadata: Dict) -> List[str]:
        """Extract team names from assets or metadata"""
        team_tag_keys = self.config.get('team', {}).get('team_tag_keys', ['Team', 'team'])
        
        # Try from group metadata first
        if group_metadata.get('secondary_value'):
            return [group_metadata['secondary_value']]
        
        # Extract from asset tags
        teams = set()
        for asset in assets[:10]:  # Check first 10 assets
            tags = asset.get('tags', [])
            if tags:
                tag_dict = {tag.get('key'): tag.get('value') for tag in tags if isinstance(tag, dict)}
                for key in team_tag_keys:
                    if key in tag_dict:
                        teams.add(tag_dict[key])
        
        return list(teams) if teams else []
    
    def _create_rules_for_component(self, 
                                    application_name: str,
                                    component_name: str,
                                    assets: List[Dict],
                                    group_metadata: Dict) -> List[Dict]:
        """Create asset assignment rules for component"""
        
        print(f"   📋 Creating rules for {component_name}...")
        
        rules_created = []
        strategy = self.config.get('rules', {}).get('strategy', 'separate_rules')
        
        if strategy == 'separate_rules':
            # Create separate rule for each tag
            primary_tag = group_metadata.get('primary_tag')
            primary_value = group_metadata.get('primary_value')
            
            if primary_tag and primary_value:
                rule_name = f"AUTO-RULE-{component_name}-{primary_tag}"
                try:
                    create_component_rule(
                        application_name,
                        component_name,
                        'tags',
                        [{"key": primary_tag, "value": primary_value}],
                        rule_name,
                        self.headers
                    )
                    rules_created.append({
                        'name': rule_name,
                        'type': 'tag',
                        'filter': {primary_tag: primary_value}
                    })
                except Exception as e:
                    print(f"   ⚠️  Rule creation failed: {e}")
            
            # Secondary tag rule
            secondary_tag = group_metadata.get('secondary_tag')
            secondary_value = group_metadata.get('secondary_value')
            
            if secondary_tag and secondary_value and secondary_value != 'NoTeam':
                rule_name = f"AUTO-RULE-{component_name}-{secondary_tag}"
                try:
                    create_component_rule(
                        application_name,
                        component_name,
                        'tags',
                        [{"key": secondary_tag, "value": secondary_value}],
                        rule_name,
                        self.headers
                    )
                    rules_created.append({
                        'name': rule_name,
                        'type': 'tag',
                        'filter': {secondary_tag: secondary_value}
                    })
                except Exception as e:
                    print(f"   ⚠️  Rule creation failed: {e}")
        
        print(f"   ✅ Created {len(rules_created)} rules")
        self.created_rules.extend(rules_created)
        
        return rules_created
    
    def _save_execution_checkpoint(self):
        """Save execution checkpoint"""
        checkpoint_data = {
            'created_components': self.created_components,
            'created_rules': self.created_rules,
            'errors': self.errors,
            'timestamp': datetime.now().isoformat()
        }
        
        self.checkpoint_manager.save_checkpoint(
            'execution',
            checkpoint_data,
            self.config.get('checkpoint', {}).get('execution_log_file', 'checkpoint-03-execution-log.json')
        )


def load_config(config_path: str) -> Dict:
    """Load configuration from YAML file"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def fetch_assets_from_api(client_id: str, client_secret: str, config: Dict) -> List[Dict]:
    """Fetch assets from Phoenix API"""
    print("\n🌐 Fetching assets from Phoenix API...")
    
    # Get auth token
    access_token = get_auth_token(client_id, client_secret)
    headers = {"Authorization": f"Bearer {access_token}"}
    
    page_size = config.get('execution', {}).get('api_fetch_page_size', 1000)
    max_pages = config.get('execution', {}).get('api_fetch_max_pages', 0)
    
    all_assets = []
    page = 0
    
    while True:
        if max_pages > 0 and page >= max_pages:
            break
        
        api_url = construct_api_url(f"/v1/assets?pageNumber={page}&pageSize={page_size}")
        
        # Add filters if specified
        filters = {}
        if config.get('grouping', {}).get('only_unassigned', True):
            filters['onlyUnassigned'] = True
        
        response = requests.post(api_url, headers=headers, json=filters)
        
        if response.status_code != 200:
            print(f"⚠️  API request failed: {response.status_code}")
            break
        
        data = response.json()
        content = data.get('content', [])
        
        if not content:
            break
        
        all_assets.extend(content)
        page += 1
        
        print(f"  Fetched page {page}: {len(content)} assets (Total: {len(all_assets):,})")
        
        if data.get('last', False):
            break
    
    print(f"\n✅ Total assets fetched: {len(all_assets):,}")
    
    return all_assets


def load_assets_from_file(file_path: str) -> List[Dict]:
    """Load assets from JSON file"""
    print(f"\n📄 Loading assets from file: {file_path}")
    
    with open(file_path, 'r') as f:
        assets = json.load(f)
    
    print(f"✅ Loaded {len(assets):,} assets from file")
    
    return assets


def generate_standard_yaml_structure(grouping_plan: Dict, config: Dict) -> Dict:
    """
    Generate standard YAML structure matching core-structure-container.yaml format
    
    This function creates DeploymentGroups (Applications/Components) and 
    EnvironmentGroups (Environments/Services) based on asset types and grouping plan.
    
    Asset Routing Rules (FIXED - no smart routing):
    - DeploymentGroups: WEB, WEBSITE_API, REPOSITORY, SOURCE_CODE, BUILD, FOSS, SAST
    - EnvironmentGroups (INFRA): INFRA
    - EnvironmentGroups (CLOUD): CLOUD, CONTAINER
    
    Args:
        grouping_plan: Dict containing components and services grouping plan
        config: Autogroup configuration dict
    
    Returns:
        Dict in standard YAML structure format
    """
    print("\n" + "="*80)
    print("🏗️  GENERATING STANDARD YAML STRUCTURE")
    print("="*80)
    
    yaml_config = config.get('yaml_generation', {})
    defaults = yaml_config.get('defaults', {})
    routing = yaml_config.get('asset_routing', {})
    
    # Get default values
    default_responsable = defaults.get('responsable', 'admin@company.com')
    default_tier = defaults.get('tier', 5)
    default_status = defaults.get('status', 'Autogenerated-phoenix')
    default_domain = defaults.get('domain', '')
    default_subdomain = defaults.get('subdomain', '')
    include_appid = defaults.get('include_appid', False)
    
    # Asset type routing
    deployment_types = set(routing.get('deployment_group_types', [
        'WEB', 'WEBSITE_API', 'REPOSITORY', 'SOURCE_CODE', 'BUILD', 'FOSS', 'SAST'
    ]))
    environment_types = routing.get('environment_group_types', {})
    
    # Initialize structure
    structure = {}
    
    # Add AllAccessAccounts if specified
    structure['AllAccessAccounts'] = [default_responsable]
    
    # ========================================================================
    # DEPLOYMENT GROUPS (Applications / Components)
    # ========================================================================
    deployment_groups = []
    
    components_by_app = defaultdict(list)
    
    # Extract components from grouping plan
    # Note: grouping_plan has 'groups' dict, not 'components' list
    for group_key, group_data in grouping_plan.get('groups', {}).items():
        # Get asset_type from first asset in the group
        assets = group_data.get('assets', [])
        if not assets:
            continue
        
        asset_type = assets[0].get('type', 'UNKNOWN')
        
        # Check if this asset type belongs in DeploymentGroups
        if asset_type in deployment_types:
            # Determine application name
            app_name = group_data.get('application_name', group_data.get('component_name', 'Ungrouped'))
            
            # Add asset_type and ALL metadata fields to group_data for later use
            group_data['asset_type'] = asset_type
            # Flatten metadata to top level for easy access in rule generation
            metadata = group_data.get('metadata', {})
            for key, value in metadata.items():
                if key not in group_data:  # Don't overwrite existing keys
                    group_data[key] = value
            
            components_by_app[app_name].append(group_data)
    
    # Build DeploymentGroups
    for app_name, components in components_by_app.items():
        app_group = {
            'AppName': app_name,
            'Responsable': default_responsable,
            'Tier': default_tier
        }
        
        # Add optional fields if not empty
        if default_domain:
            app_group['Domain'] = default_domain
        if default_subdomain:
            app_group['SubDomain'] = default_subdomain
        if default_status:
            app_group['Status'] = default_status
        if include_appid:
            app_group['AppID'] = ''  # Leave empty for Phoenix to generate
        
        # Build Components
        app_components = []
        for comp in components:
            component = {
                'ComponentName': comp.get('component_name', 'Unknown'),
                'Status': default_status,
                'Type': comp.get('component_type', 'Release')
            }
            
            # Add team names if available
            if comp.get('team'):
                component['TeamNames'] = [comp['team']]
            
            # Generate MultiConditionRule
            rule = _generate_multi_condition_rule(comp, config)
            if rule:
                component['MultiConditionRule'] = rule
            
            app_components.append(component)
        
        app_group['Components'] = app_components
        deployment_groups.append(app_group)
    
    if deployment_groups and yaml_config.get('include_deployment_groups', True):
        structure['DeploymentGroups'] = deployment_groups
        print(f"✅ Generated {len(deployment_groups)} DeploymentGroups with {sum(len(dg['Components']) for dg in deployment_groups)} Components")
    
    # ========================================================================
    # ENVIRONMENT GROUPS (Environments / Services)
    # ========================================================================
    environment_groups = []
    
    services_by_env = defaultdict(list)
    
    # Extract services from grouping plan
    # Note: grouping_plan has 'groups' dict, not 'services' list
    for group_key, group_data in grouping_plan.get('groups', {}).items():
        # Get asset_type from first asset in the group
        assets = group_data.get('assets', [])
        if not assets:
            continue
        
        asset_type = assets[0].get('type', 'UNKNOWN')
        
        # Check if this asset type belongs in EnvironmentGroups
        if asset_type in environment_types:
            env_config = environment_types[asset_type]
            env_type = env_config.get('environment_type', 'CLOUD')
            env_subtype = env_config.get('environment_subtype', 'CLOUD')
            
            # Determine environment name from group
            env_name = group_data.get('environment', group_data.get('application_name', f"{asset_type}-Environment"))
            
            # Add asset_type and ALL metadata fields to group_data for later use
            group_data['asset_type'] = asset_type
            group_data['_env_type'] = env_type
            group_data['_env_subtype'] = env_subtype
            group_data['service_name'] = group_data.get('component_name', 'Unknown-Service')
            # Flatten metadata to top level for easy access in rule generation
            metadata = group_data.get('metadata', {})
            for key, value in metadata.items():
                if key not in group_data:  # Don't overwrite existing keys
                    group_data[key] = value
            
            # Store service with environment metadata
            services_by_env[env_name].append(group_data)
    
    # Build EnvironmentGroups
    for env_name, services in services_by_env.items():
        # Get environment type from first service
        env_type = services[0].get('_env_type', 'CLOUD')
        
        env_group = {
            'Name': env_name,
            'Type': env_type,
            'Status': default_status,
            'Responsable': default_responsable,
            'Tier': default_tier
        }
        
        # Build Services
        env_services = []
        for svc in services:
            service = {
                'Service': svc.get('service_name', 'Unknown'),
                'Type': svc.get('_env_subtype', 'CLOUD'),
                'Tier': default_tier
            }
            
            # Add team name if available
            if svc.get('team'):
                service['TeamName'] = svc['team']
            
            # Generate MultiConditionRule
            rule = _generate_multi_condition_rule(svc, config)
            if rule:
                service['MultiConditionRule'] = rule
            
            env_services.append(service)
        
        env_group['Services'] = env_services
        environment_groups.append(env_group)
    
    if environment_groups and yaml_config.get('include_environment_groups', True):
        structure['EnvironmentGroups'] = environment_groups
        print(f"✅ Generated {len(environment_groups)} EnvironmentGroups with {sum(len(eg['Services']) for eg in environment_groups)} Services")
    
    print(f"\n📊 Total YAML Structure:")
    print(f"   • DeploymentGroups: {len(deployment_groups)}")
    print(f"   • EnvironmentGroups: {len(environment_groups)}")
    
    return structure


def _generate_multi_condition_rule(component_or_service: Dict, config: Dict) -> Dict:
    """
    Generate MultiConditionRule for a component or service
    
    Generates ONE filter per rule based on grouping method:
    - Tag grouping: Use Tag filter (Tag: "Key: Value")
    - CIDR grouping: Use Cidr filter (Cidr: "10.22.0.0/24")
    - Hostname grouping: Use Hostnames filter
    - Repository grouping: Use RepositoryName filter
    - Cloud provider grouping: Use ProviderAccountId filter
    - Image name grouping: Use SearchName filter
    - Generic type grouping: Use AssetType filter
    
    Args:
        component_or_service: Component or service dict with grouping metadata
        config: Autogroup configuration
    
    Returns:
        Dict with MultiConditionRule fields or empty dict
    """
    rule = {}
    
    grouping_method = component_or_service.get('grouping_method', 'unknown')
    
    # 1. Tag-based grouping
    if grouping_method == 'tag':
        tag_key = component_or_service.get('grouping_tag_key')
        tag_value = component_or_service.get('grouping_tag_value')
        if tag_key and tag_value:
            # Format: "Key: Value" (single tag per rule)
            rule['Tag'] = f"{tag_key}: {tag_value}"
            return rule
    
    # 2. CIDR-based grouping (for INFRA networks)
    elif grouping_method == 'cidr':
        cidr = component_or_service.get('cidr')
        if cidr:
            rule['Cidr'] = cidr
            return rule
    
    # 3. Hostname-based grouping (for INFRA hosts)
    elif grouping_method == 'hostname':
        hostnames = component_or_service.get('hostnames', [])
        if hostnames:
            # Use Hostnames array for matching multiple similar hosts
            rule['Hostnames'] = hostnames[:10]  # Limit to 10 hostnames
            return rule
    
    # 4. Repository-based grouping (for CODE/SAST/BUILD assets)
    elif grouping_method == 'repository':
        repo_name = component_or_service.get('repository_name')
        if repo_name:
            rule['RepositoryName'] = repo_name
            return rule
    
    # 5. Cloud provider grouping (for CLOUD assets)
    elif grouping_method == 'cloud_provider':
        provider_account = component_or_service.get('provider_account_id')
        if provider_account:
            rule['ProviderAccountId'] = [provider_account]
            # Also add provider type
            asset_type = component_or_service.get('asset_type', 'CLOUD')
            rule['AssetType'] = asset_type
            return rule
    
    # 6. Image name grouping (for CONTAINER assets)
    elif grouping_method == 'image_name':
        # For containers, use SearchName with the image pattern
        image_pattern = component_or_service.get('image_name_pattern')
        if image_pattern:
            rule['SearchName'] = image_pattern
            rule['AssetType'] = 'CONTAINER'
            return rule
    
    # 7. Generic type-based fallback
    elif grouping_method == 'type':
        asset_type = component_or_service.get('asset_type')
        if asset_type:
            rule['AssetType'] = asset_type
            return rule
    
    # Fallback: Use SearchName if component/service name available
    name = component_or_service.get('component_name') or component_or_service.get('service_name')
    if name:
        # Strip prefixes like "INFRA-", "CLOUD-", "CIDR-"
        clean_name = name
        for prefix in ['INFRA-', 'CLOUD-', 'CONTAINER-', 'CODE-', 'CIDR-']:
            if clean_name.startswith(prefix):
                clean_name = clean_name[len(prefix):]
                break
        
        rule['SearchName'] = clean_name
    
    return rule


def export_to_yaml(data: Any, output_path: str):
    """Export data to YAML file"""
    with open(output_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    print(f"✅ Exported to: {output_path}")

