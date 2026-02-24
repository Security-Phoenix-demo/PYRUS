"""
Phoenix Security - Autogroup Orchestrator
Main entry point for automatic asset grouping and component creation

Usage:
    from providers.autogroup_orchestrator import run_autogroup
    run_autogroup(client_id, client_secret, config_path, mode='batch')
"""

import os
import sys
import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from providers.AutoGroupEngine import (
    CheckpointManager, TagAnalyzer, AssetGrouper, ComponentCreator,
    load_config, fetch_assets_from_api, load_assets_from_file, export_to_yaml,
    generate_standard_yaml_structure
)
from providers.Phoenix import get_auth_token, populate_applications_and_environments
from providers.YamlHelper import (
    populate_applications_from_config, populate_environments_from_env_groups_from_config,
    populate_repositories_from_config, populate_teams
)


def run_autogroup(client_id: str, 
                  client_secret: str,
                  config_path: str,
                  mode: str = 'batch',
                  asset_source: str = None,
                  asset_file: str = None,
                  action_teams: bool = False,
                  action_code: bool = False,
                  action_cloud: bool = False) -> Dict:
    """
    Main orchestration function for automatic asset grouping
    
    TWO-MODE OPERATION:
    - Mode A (Generate Only): When all action flags are False
      → Generates YAML configuration file only
      → User can review and manually implement later
    
    - Mode B (Generate + Implement): When any action flag is True
      → Generates YAML configuration file
      → Automatically implements based on action flags
    
    Args:
        client_id: Phoenix API client ID
        client_secret: Phoenix API client secret
        config_path: Path to autogroup-config.yaml
        mode: 'interactive' or 'batch' (default: 'batch')
        asset_source: 'api' or 'file' (overrides config)
        asset_file: Path to asset JSON file (if asset_source='file')
        action_teams: Create/assign teams (default: False)
        action_code: Implement CODE-related components (default: False)
        action_cloud: Implement CLOUD-related components (default: False)
    
    Returns:
        Dict with execution results and statistics
    """
    
    print("\n" + "="*80)
    print("🚀 PHOENIX SECURITY - AUTOMATIC ASSET GROUPING")
    print("="*80)
    print(f"Mode: {mode.upper()}")
    print(f"Config: {config_path}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n🎯 Action Flags:")
    print(f"   • Teams: {'✅ Enabled' if action_teams else '❌ Disabled'}")
    print(f"   • Code: {'✅ Enabled' if action_code else '❌ Disabled'}")
    print(f"   • Cloud: {'✅ Enabled' if action_cloud else '❌ Disabled'}")
    
    # Determine operation mode
    implementation_enabled = action_teams or action_code or action_cloud
    if not implementation_enabled:
        print(f"\n📝 OPERATION MODE: Generate YAML Only (no implementation)")
    else:
        print(f"\n🚀 OPERATION MODE: Generate YAML + Implement")
    
    print("="*80)
    
    # ========================================================================
    # PHASE 0: INITIALIZATION
    # ========================================================================
    
    # Load configuration
    config = load_config(config_path)
    
    # Override mode if specified
    if mode:
        config['execution']['mode'] = mode
    
    # Override asset source if specified
    if asset_source:
        config['execution']['asset_source'] = asset_source
    if asset_file:
        config['execution']['asset_file'] = asset_file
    
    # Setup checkpoint manager
    config_dir = Path(config_path).parent
    checkpoint_folder = config_dir / config.get('checkpoint', {}).get('folder', 'checkpoints')
    checkpoint_manager = CheckpointManager(str(checkpoint_folder))
    
    # Initialize results tracking
    results = {
        'started_at': datetime.now().isoformat(),
        'config_path': config_path,
        'mode': config['execution']['mode'],
        'phases': {},
        'statistics': {},
        'errors': []
    }
    
    # Get auth token and headers
    access_token = get_auth_token(client_id, client_secret)
    headers = {"Authorization": f"Bearer {access_token}"}
    
    print("\n✅ Initialization complete")
    
    # ========================================================================
    # PHASE 1: ASSET LOADING
    # ========================================================================
    
    print("\n" + "="*80)
    print("PHASE 1: ASSET LOADING")
    print("="*80)
    
    phase_start = datetime.now()
    
    # Check for checkpoint
    checkpoint_file = config.get('checkpoint', {}).get('tag_analysis_file', 'checkpoint-01-tag-analysis.json')
    can_resume = config.get('checkpoint', {}).get('enabled', True) and config.get('execution', {}).get('resume_from_checkpoint', True)
    
    if can_resume and checkpoint_manager.checkpoint_exists(checkpoint_file):
        age = checkpoint_manager.get_checkpoint_age(checkpoint_file)
        max_age_hours = config.get('checkpoint', {}).get('max_checkpoint_age_hours', 168)
        
        if age and age.total_seconds() / 3600 < max_age_hours:
            print(f"📌 Found recent checkpoint (age: {age})")
            
            if mode == 'batch' or _confirm("Resume from checkpoint?"):
                checkpoint_data = checkpoint_manager.load_checkpoint(checkpoint_file)
                if checkpoint_data:
                    assets = checkpoint_data.get('assets', [])
                    tag_analysis = checkpoint_data.get('tag_analysis', {})
                    print(f"✅ Resumed from checkpoint: {len(assets):,} assets loaded")
                    results['phases']['asset_loading'] = {
                        'status': 'resumed_from_checkpoint',
                        'asset_count': len(assets),
                        'duration_seconds': (datetime.now() - phase_start).total_seconds()
                    }
                    goto_phase_2 = True
                else:
                    goto_phase_2 = False
            else:
                goto_phase_2 = False
        else:
            print(f"⚠️  Checkpoint too old (age: {age}), fetching fresh data")
            goto_phase_2 = False
    else:
        goto_phase_2 = False
    
    if not goto_phase_2:
        # Fetch fresh assets
        asset_source = config['execution'].get('asset_source', 'api')
        
        if asset_source == 'file':
            asset_file_path = config['execution'].get('asset_file', 'example-data/assets.json')
            # Make path relative to Python script folder
            script_dir = Path(__file__).parent.parent
            asset_file_full = script_dir / asset_file_path
            assets = load_assets_from_file(str(asset_file_full))
        else:
            assets = fetch_assets_from_api(client_id, client_secret, config)
        
        results['phases']['asset_loading'] = {
            'status': 'success',
            'asset_count': len(assets),
            'source': asset_source,
            'duration_seconds': (datetime.now() - phase_start).total_seconds()
        }
        
        # Perform tag analysis
        print("\n" + "="*80)
        print("PHASE 1B: TAG ANALYSIS")
        print("="*80)
        
        analyzer = TagAnalyzer(assets)
        tag_analysis = analyzer.analyze()
        analyzer.print_analysis(tag_analysis)
        
        # Save checkpoint
        if config.get('checkpoint', {}).get('enabled', True):
            checkpoint_data = {
                'assets': assets,
                'tag_analysis': tag_analysis,
                'timestamp': datetime.now().isoformat()
            }
            checkpoint_manager.save_checkpoint('tag_analysis', checkpoint_data, checkpoint_file)
        
        # Export tag analysis if configured
        if config.get('output', {}).get('export_tag_analysis', True):
            output_path = config_dir / config['output']['tag_analysis_path'].replace(
                '{timestamp}', datetime.now().strftime('%Y%m%d_%H%M%S')
            )
            with open(output_path, 'w') as f:
                json.dump(tag_analysis, f, indent=2)
            print(f"\n✅ Tag analysis exported to: {output_path}")
    
    # ========================================================================
    # PHASE 2: GROUPING STRATEGY
    # ========================================================================
    
    print("\n" + "="*80)
    print("PHASE 2: GROUPING STRATEGY")
    print("="*80)
    
    phase_start = datetime.now()
    
    # Determine grouping tags
    analyzer = TagAnalyzer(assets)
    
    # If tag_analysis was loaded from checkpoint, reconstruct tag_stats
    if tag_analysis and 'tags_by_coverage' in tag_analysis:
        # Reconstruct tag_stats from tags_by_coverage
        for tag_info in tag_analysis['tags_by_coverage']:
            tag_key = tag_info['key']
            analyzer.tag_stats[tag_key] = {
                'count': tag_info['asset_count'],
                'coverage': tag_info['coverage_percent'],
                'unique_values': tag_info['unique_values'],
                'most_common': tag_info['most_common_values']
            }
    
    recommended_tags = analyzer.recommend_grouping_tags(config)
    
    print(f"\n📊 Recommended grouping tags: {', '.join(recommended_tags[:5])}")
    
    primary_tag = None
    secondary_tag = None
    
    if mode == 'interactive':
        # Interactive tag selection
        print("\n🎯 Select primary grouping tag:")
        for idx, tag in enumerate(recommended_tags[:10], 1):
            stats = tag_analysis['tags_by_coverage']
            tag_info = next((t for t in stats if t['key'] == tag), None)
            if tag_info:
                print(f"  {idx}. {tag} ({tag_info['coverage_percent']:.1f}% coverage, "
                      f"{tag_info['unique_values']} unique values)")
        
        choice = input("\nEnter number (or press Enter for default): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(recommended_tags):
            primary_tag = recommended_tags[int(choice) - 1]
        else:
            primary_tag = recommended_tags[0] if recommended_tags else None
        
        # Ask for secondary tag
        if primary_tag and _confirm("Use secondary tag (e.g., Team)?"):
            print("\n🎯 Select secondary grouping tag:")
            for idx, tag in enumerate(recommended_tags[1:6], 1):
                if tag != primary_tag:
                    print(f"  {idx}. {tag}")
            
            choice = input("\nEnter number (or press Enter to skip): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= 5:
                secondary_tag = [t for t in recommended_tags[1:6] if t != primary_tag][int(choice) - 1]
    else:
        # Batch mode: use configuration
        primary_tag = recommended_tags[0] if recommended_tags else None
        
        # Check if secondary tag should be used
        strategy = config.get('grouping', {}).get('strategy', 'application_first')
        if strategy in ['application_first', 'team_first', 'hybrid'] and len(recommended_tags) > 1:
            secondary_tag = recommended_tags[1]
    
    if not primary_tag:
        print("\n❌ ERROR: No suitable grouping tags found!")
        print("   Falling back to asset type grouping...")
        use_tag_grouping = False
    else:
        print(f"\n✅ Selected grouping:")
        print(f"   Primary: {primary_tag}")
        print(f"   Secondary: {secondary_tag if secondary_tag else 'None'}")
        use_tag_grouping = True
    
    # ========================================================================
    # PHASE 3: ASSET GROUPING
    # ========================================================================
    
    print("\n" + "="*80)
    print("PHASE 3: ASSET GROUPING")
    print("="*80)
    
    phase_start = datetime.now()
    
    grouper = AssetGrouper(assets, config, tag_analysis)
    
    if use_tag_grouping:
        grouping_result = grouper.group_by_tags(primary_tag, secondary_tag)
        tagged_groups = grouping_result['tagged_groups']
        untagged_assets = grouping_result['untagged_assets']
    else:
        tagged_groups = {}
        untagged_assets = assets
    
    # Handle untagged assets with fallback strategies
    untagged_groups = {}
    
    if untagged_assets:
        print(f"\n🔄 Applying fallback strategies for {len(untagged_assets):,} untagged assets...")
        
        # Group by type first
        type_groups = grouper.group_untagged_by_type(untagged_assets)
        
        # Apply type-specific grouping
        for asset_type, type_assets in type_groups.items():
            if asset_type == 'INFRA':
                infra_groups = grouper.group_infra_by_network(type_assets)
                untagged_groups.update(infra_groups)
            elif asset_type in ['REPOSITORY', 'SOURCE_CODE', 'BUILD', 'FOSS', 'SAST']:
                software_groups = grouper.group_software_by_repository(type_assets)
                untagged_groups.update(software_groups)
            elif asset_type == 'CONTAINER':
                container_groups = grouper.group_containers_by_name(type_assets)
                untagged_groups.update(container_groups)
            elif asset_type == 'CLOUD':
                cloud_groups = grouper.group_cloud_by_provider(type_assets)
                untagged_groups.update(cloud_groups)
            else:
                # Generic grouping by type
                untagged_groups[f"{asset_type}-Unassigned"] = {
                    'assets': type_assets,
                    'metadata': {
                        'grouping_method': 'type',
                        'asset_type': asset_type,
                        'group_type': 'fallback'
                    }
                }
    
    # Combine all groups
    all_groups = {**tagged_groups, **untagged_groups}
    
    print(f"\n✅ Grouping complete:")
    print(f"   Tagged groups: {len(tagged_groups)}")
    print(f"   Untagged groups: {len(untagged_groups)}")
    print(f"   Total groups: {len(all_groups)}")
    
    # Create grouping plan
    grouping_plan = _create_grouping_plan(all_groups, config, primary_tag, secondary_tag)
    
    results['phases']['grouping'] = {
        'status': 'success',
        'tagged_groups': len(tagged_groups),
        'untagged_groups': len(untagged_groups),
        'total_groups': len(all_groups),
        'duration_seconds': (datetime.now() - phase_start).total_seconds()
    }
    
    # Save grouping plan checkpoint
    if config.get('checkpoint', {}).get('enabled', True):
        checkpoint_file = config.get('checkpoint', {}).get('grouping_plan_file', 'checkpoint-02-grouping-plan.yaml')
        checkpoint_manager.save_checkpoint('grouping_plan', grouping_plan, checkpoint_file)
    
    # Export grouping plan if configured
    if config.get('output', {}).get('export_grouping_plan', True):
        output_path = config_dir / config['output']['grouping_plan_path'].replace(
            '{timestamp}', datetime.now().strftime('%Y%m%d_%H%M%S')
        )
        export_to_yaml(grouping_plan, str(output_path))
    
    # ========================================================================
    # PHASE 3.5: YAML STRUCTURE GENERATION (ALWAYS RUNS)
    # ========================================================================
    
    print("\n" + "="*80)
    print("PHASE 3.5: YAML STRUCTURE GENERATION")
    print("="*80)
    
    phase_start = datetime.now()
    
    # Generate standard YAML structure (core-structure-container.yaml format)
    yaml_structure = generate_standard_yaml_structure(grouping_plan, config)
    
    # Save generated YAML
    yaml_config = config.get('yaml_generation', {})
    yaml_output_path = config_dir / yaml_config.get('output_path', 'generated-structure-{timestamp}.yaml').replace(
        '{timestamp}', datetime.now().strftime('%Y%m%d_%H%M%S')
    )
    
    export_to_yaml(yaml_structure, str(yaml_output_path))
    
    print(f"\n✅ Generated YAML structure saved to: {yaml_output_path}")
    
    results['phases']['yaml_generation'] = {
        'status': 'success',
        'output_file': str(yaml_output_path),
        'deployment_groups': len(yaml_structure.get('DeploymentGroups', [])),
        'environment_groups': len(yaml_structure.get('EnvironmentGroups', [])),
        'duration_seconds': (datetime.now() - phase_start).total_seconds()
    }
    
    # Preview in interactive mode
    if mode == 'interactive':
        _print_grouping_preview(grouping_plan)
        
        if not implementation_enabled:
            print("\n📝 YAML-only mode: No implementation will be performed")
            print(f"   Review the generated file: {yaml_output_path}")
            print(f"   To implement later, run with --action_code true and/or --action_cloud true")
            return results
        
        if not _confirm("\n✅ Proceed with implementation?"):
            print("\n❌ Implementation cancelled by user")
            print(f"   YAML structure saved to: {yaml_output_path}")
            return results
    
    # Dry run check
    if config.get('execution', {}).get('dry_run', False):
        print("\n🔍 DRY RUN MODE - No actual changes will be made")
        results['dry_run'] = True
        results['grouping_plan'] = grouping_plan
        results['yaml_structure'] = yaml_structure
        return results
    
    # Check if implementation is disabled (all action flags are False)
    if not implementation_enabled:
        print("\n✅ YAML generation complete!")
        print(f"   Generated file: {yaml_output_path}")
        print(f"\n📝 To implement this configuration, run:")
        print(f"   python run-phx.py --action_autogroup true --action_code true --action_cloud true")
        results['yaml_only_mode'] = True
        results['yaml_structure'] = yaml_structure
        return results
    
    # ========================================================================
    # PHASE 4: IMPLEMENTATION (Uses existing ingestion functions)
    # ========================================================================
    
    print("\n" + "="*80)
    print("PHASE 4: IMPLEMENTATION")
    print("="*80)
    print(f"Implementing generated YAML structure: {yaml_output_path}")
    
    phase_start = datetime.now()
    
    implementation_stats = {
        'teams_created': 0,
        'applications_created': 0,
        'components_created': 0,
        'environments_created': 0,
        'services_created': 0,
        'failed': 0
    }
    
    try:
        # Load the generated YAML structure
        with open(yaml_output_path, 'r') as f:
            yaml_data = yaml.safe_load(f)
        
        # ====================================================================
        # STEP 4.1: IMPLEMENT DEPLOYMENT GROUPS (CODE assets)
        # ====================================================================
        
        if action_code and yaml_data.get('DeploymentGroups'):
            print(f"\n📦 Implementing DeploymentGroups (CODE assets)...")
            print(f"   • Action: --action_code is ENABLED")
            print(f"   • Groups to process: {len(yaml_data['DeploymentGroups'])}")
            
            try:
                # Use existing ingestion function (pass file path, not data)
                populate_applications_from_config(str(yaml_output_path))
                
                implementation_stats['applications_created'] = len(yaml_data['DeploymentGroups'])
                total_components = sum(len(dg.get('Components', [])) for dg in yaml_data['DeploymentGroups'])
                implementation_stats['components_created'] = total_components
                
                print(f"   ✅ Created {len(yaml_data['DeploymentGroups'])} applications")
                print(f"   ✅ Created {total_components} components")
                
            except Exception as e:
                print(f"   ❌ DeploymentGroups implementation failed: {e}")
                implementation_stats['failed'] += 1
                
                if not config.get('advanced', {}).get('continue_on_error', True):
                    raise
        elif not action_code and yaml_data.get('DeploymentGroups'):
            print(f"\n⏭️  Skipping DeploymentGroups (--action_code is DISABLED)")
            print(f"   • {len(yaml_data['DeploymentGroups'])} groups available")
            print(f"   • To implement, run with: --action_code true")
        
        # ====================================================================
        # STEP 4.2: IMPLEMENT ENVIRONMENT GROUPS (CLOUD/INFRA assets)
        # ====================================================================
        
        if action_cloud and yaml_data.get('EnvironmentGroups'):
            print(f"\n☁️  Implementing EnvironmentGroups (CLOUD/INFRA assets)...")
            print(f"   • Action: --action_cloud is ENABLED")
            print(f"   • Groups to process: {len(yaml_data['EnvironmentGroups'])}")
            
            try:
                # Step 1: Load and validate environments from YAML
                environments = populate_environments_from_env_groups_from_config(str(yaml_output_path))
                
                if environments:
                    from providers.Phoenix import (
                        create_environment, update_environment, add_environment_services,
                        populate_applications_and_environments
                    )
                    
                    # Step 2: Create/update environments in Phoenix
                    print(f"\n   📋 Creating/updating {len(environments)} environments...")
                    app_environments = populate_applications_and_environments(headers)
                    
                    for environment in environments:
                        env_name = environment['Name']
                        existing_env = next(
                            (env for env in app_environments 
                             if env.get('type') == 'ENVIRONMENT' and env['name'] == env_name), 
                            None
                        )
                        
                        if not existing_env:
                            print(f"   └─ Creating environment: {env_name}")
                            create_environment(environment, headers)
                        else:
                            print(f"   └─ Updating environment: {env_name}")
                            update_environment(environment, existing_env, headers)
                    
                    # Step 3: Create services and rules
                    print(f"\n   🔧 Creating services and rules...")
                    add_environment_services(
                        repos=[],  # Not needed for environment creation
                        subdomains={},  # Not needed
                        environments=environments,
                        application_environments=app_environments,
                        phoenix_components=[],  # Not needed for environments
                        subdomain_owners={},  # Not needed
                        teams=[],  # Teams handled separately
                        access_token2=headers['Authorization'].replace('Bearer ', ''),
                        track_operation_callback=None,
                        quick_check_interval=10,
                        silent_mode=False
                    )
                    
                    implementation_stats['environments_created'] = len(environments)
                    total_services = sum(len(env.get('Services', [])) for env in environments)
                    implementation_stats['services_created'] = total_services
                    
                    print(f"\n   ✅ Created {len(environments)} environments")
                    print(f"   ✅ Created {total_services} services")
                else:
                    print(f"   ⚠️  No environments loaded from YAML")
                
            except Exception as e:
                print(f"   ❌ EnvironmentGroups implementation failed: {e}")
                implementation_stats['failed'] += 1
                
                if not config.get('advanced', {}).get('continue_on_error', True):
                    raise
        elif not action_cloud and yaml_data.get('EnvironmentGroups'):
            print(f"\n⏭️  Skipping EnvironmentGroups (--action_cloud is DISABLED)")
            print(f"   • {len(yaml_data['EnvironmentGroups'])} groups available")
            print(f"   • To implement, run with: --action_cloud true")
        
        # ====================================================================
        # STEP 4.3: IMPLEMENT TEAMS (if enabled)
        # ====================================================================
        
        if action_teams:
            print(f"\n👥 Implementing Teams...")
            print(f"   • Action: --action_teams is ENABLED")
            
            try:
                # Extract unique teams from YAML
                teams = set()
                
                for dg in yaml_data.get('DeploymentGroups', []):
                    for comp in dg.get('Components', []):
                        if comp.get('TeamNames'):
                            teams.update(comp['TeamNames'])
                
                for eg in yaml_data.get('EnvironmentGroups', []):
                    for svc in eg.get('Services', []):
                        if svc.get('TeamName'):
                            teams.add(svc['TeamName'])
                
                if teams:
                    # Use existing team creation function
                    populate_teams(list(teams), headers)
                    implementation_stats['teams_created'] = len(teams)
                    print(f"   ✅ Created/updated {len(teams)} teams")
                else:
                    print(f"   ℹ️  No teams found in configuration")
                    
            except Exception as e:
                print(f"   ❌ Team implementation failed: {e}")
                implementation_stats['failed'] += 1
        else:
            print(f"\n⏭️  Skipping Teams (--action_teams is DISABLED)")
            print(f"   • To implement, run with: --action_teams true")
        
    except Exception as e:
        print(f"\n❌ IMPLEMENTATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        implementation_stats['failed'] += 1
    
    results['phases']['implementation'] = {
        'status': 'completed' if implementation_stats['failed'] == 0 else 'completed_with_errors',
        **implementation_stats,
        'duration_seconds': (datetime.now() - phase_start).total_seconds()
    }
    
    print(f"\n✅ Implementation complete:")
    print(f"   • Teams: {implementation_stats['teams_created']}")
    print(f"   • Applications: {implementation_stats['applications_created']}")
    print(f"   • Components: {implementation_stats['components_created']}")
    print(f"   • Environments: {implementation_stats['environments_created']}")
    print(f"   • Services: {implementation_stats['services_created']}")
    if implementation_stats['failed'] > 0:
        print(f"   • Failed operations: {implementation_stats['failed']}")
    
    # ========================================================================
    # PHASE 5: FINALIZATION & EXPORT
    # ========================================================================
    
    print("\n" + "="*80)
    print("PHASE 5: FINALIZATION")
    print("="*80)
    
    # Export created components
    if config.get('output', {}).get('export_yaml', True):
        output_path = config_dir / config['output']['yaml_output_path'].replace(
            '{timestamp}', datetime.now().strftime('%Y%m%d_%H%M%S')
        )
        
        export_data = {
            'metadata': {
                'generated_by': 'Phoenix AutoConfig - Automatic Asset Grouping',
                'generated_at': datetime.now().isoformat(),
                'config': config_path,
                'mode': mode
            },
            'statistics': {
                'total_assets_processed': len(assets),
                'groups_created': len(all_groups),
                'tagged_groups': len(tagged_groups),
                'untagged_groups': len(untagged_groups)
            }
        }
        
        export_to_yaml(export_data, str(output_path))
    
    # Generate final report
    results['finished_at'] = datetime.now().isoformat()
    results['statistics'] = {
        'total_assets': len(assets),
        'groups_created': len(all_groups),
        'teams_created': implementation_stats.get('teams_created', 0),
        'applications_created': implementation_stats.get('applications_created', 0),
        'components_created': implementation_stats.get('components_created', 0),
        'environments_created': implementation_stats.get('environments_created', 0),
        'services_created': implementation_stats.get('services_created', 0),
        'failed_operations': implementation_stats.get('failed', 0),
        'implementation_enabled': implementation_enabled
    }
    
    # Export report
    if config.get('output', {}).get('generate_report', True):
        report_path = config_dir / config['output']['report_path'].replace(
            '{timestamp}', datetime.now().strftime('%Y%m%d_%H%M%S')
        )
        
        with open(report_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n✅ Execution report saved to: {report_path}")
    
    # Print summary
    _print_final_summary(results)
    
    return results


def _create_grouping_plan(groups: Dict, config: Dict, primary_tag: str, secondary_tag: str) -> Dict:
    """Create execution plan from groups"""
    plan = {
        'metadata': {
            'created_at': datetime.now().isoformat(),
            'primary_tag': primary_tag,
            'secondary_tag': secondary_tag
        },
        'groups': {}
    }
    
    min_assets = config.get('grouping', {}).get('min_assets_per_component', 2)
    
    for group_key, group_data in groups.items():
        if isinstance(group_data, dict):
            assets = group_data['assets']
            metadata = group_data.get('metadata', {})
        else:
            assets = group_data
            metadata = {}
        
        # Skip groups with too few assets
        if len(assets) < min_assets:
            continue
        
        # Determine application and component names
        app_name, component_name = _generate_names(group_key, metadata, config)
        
        plan['groups'][group_key] = {
            'application_name': app_name,
            'component_name': component_name,
            'asset_count': len(assets),
            'assets': assets,
            'metadata': metadata
        }
    
    return plan


def _generate_names(group_key: str, metadata: Dict, config: Dict) -> Tuple[str, str]:
    """Generate application and component names from group data"""
    primary_value = metadata.get('primary_value', group_key)
    secondary_value = metadata.get('secondary_value')
    
    # Application name (use primary value)
    app_name = primary_value.replace(' ', '-').replace('_', '-')[:100]
    
    # Component name
    template = config.get('component_naming', {}).get('default_template', 'application_with_team')
    
    if template == 'application_with_team' and secondary_value and secondary_value != 'NoTeam':
        component_name = f"{app_name}-{secondary_value}".replace(' ', '-')[:100]
    elif template == 'application_only':
        component_name = f"{app_name}-Component"[:100]
    else:
        # Use group key as fallback
        component_name = group_key.replace('|||', '-')[:100]
    
    # Apply prefix/suffix
    prefix = config.get('component_naming', {}).get('prefix', '')
    suffix = config.get('component_naming', {}).get('suffix', '')
    
    component_name = f"{prefix}{component_name}{suffix}"
    
    return app_name, component_name


def _create_application(app_name: str, config: Dict, headers: Dict):
    """Create application if it doesn't exist"""
    from providers.Phoenix import create_application
    
    app_config = {
        'AppName': app_name,
        'Status': 'Production',
        'Responsable': config.get('application', {}).get('defaults', {}).get('responsable', 'admin@phoenix.security'),
        'Tier': config.get('application', {}).get('defaults', {}).get('tier', 5),
        'TeamNames': [],
        'Components': []
    }
    
    create_application(app_config, headers)


def _print_grouping_preview(plan: Dict):
    """Print preview of grouping plan"""
    print("\n" + "="*80)
    print("📋 GROUPING PLAN PREVIEW")
    print("="*80)
    
    print(f"\n{'Application':<40} {'Component':<40} {'Assets':<8}")
    print("-" * 90)
    
    for group_data in plan['groups'].values():
        app = group_data['application_name'][:38]
        comp = group_data['component_name'][:38]
        count = group_data['asset_count']
        
        print(f"{app:<40} {comp:<40} {count:>6}")
    
    print("-" * 90)
    print(f"Total: {len(plan['groups'])} components to create")


def _print_final_summary(results: Dict):
    """Print final execution summary"""
    print("\n" + "="*80)
    print("📊 EXECUTION SUMMARY")
    print("="*80)
    
    stats = results.get('statistics', {})
    
    print(f"\n📥 Input:")
    print(f"   • Assets Processed: {stats.get('total_assets', 0):,}")
    print(f"   • Groups Created: {stats.get('groups_created', 0):,}")
    
    print(f"\n📤 Output:")
    yaml_phase = results.get('phases', {}).get('yaml_generation', {})
    if yaml_phase:
        print(f"   • YAML File Generated: {yaml_phase.get('output_file', 'N/A')}")
        print(f"   • Deployment Groups: {yaml_phase.get('deployment_groups', 0)}")
        print(f"   • Environment Groups: {yaml_phase.get('environment_groups', 0)}")
    
    if stats.get('implementation_enabled', False):
        print(f"\n🚀 Implementation Results:")
        print(f"   • Teams Created: {stats.get('teams_created', 0):,}")
        print(f"   • Applications Created: {stats.get('applications_created', 0):,}")
        print(f"   • Components Created: {stats.get('components_created', 0):,}")
        print(f"   • Environments Created: {stats.get('environments_created', 0):,}")
        print(f"   • Services Created: {stats.get('services_created', 0):,}")
        
        if stats.get('failed_operations', 0) > 0:
            print(f"   ⚠️  Failed Operations: {stats['failed_operations']}")
    else:
        print(f"\n📝 Implementation: SKIPPED (generate-only mode)")
        print(f"   • To implement, run with: --action_code true --action_cloud true")
    
    print("\n" + "="*80)


def _confirm(message: str) -> bool:
    """Ask for user confirmation"""
    response = input(f"{message} [Y/n]: ").strip().upper()
    return response in ['Y', 'YES', '']


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 4:
        print("Usage: python autogroup_orchestrator.py <client_id> <client_secret> <config_path> [mode]")
        sys.exit(1)
    
    client_id = sys.argv[1]
    client_secret = sys.argv[2]
    config_path = sys.argv[3]
    mode = sys.argv[4] if len(sys.argv) > 4 else 'batch'
    
    results = run_autogroup(client_id, client_secret, config_path, mode)
    
    print(f"\n✅ Execution completed!")
    print(f"   Components created: {results['statistics']['components_created']}")

