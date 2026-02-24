#!/usr/bin/env python3
"""
YAML Validation Script with Detailed Component and Service Success Rates
=========================================================================
This script validates a Phoenix Security YAML configuration file and provides
separate success rates for:
  - Components (under DeploymentGroups/Applications)
  - Services (under Environment Groups)
"""

import sys
import os
import io
from contextlib import redirect_stdout
from providers.YamlHelper import populate_applications_from_config, populate_environments_from_env_groups_from_config
from providers.Linter import validate_application, validate_component, validate_environment, validate_service, validate_yaml_structure

def validate_yaml_with_stats(yaml_file):
    """
    Validate YAML file and return detailed statistics
    """
    print("=" * 80)
    print("🔍 PHOENIX SECURITY YAML VALIDATION REPORT")
    print("=" * 80)
    print(f"📄 File: {yaml_file}\n")
    
    # ========================================================================
    # PART 0: Structural validation (duplicate keys, missing sections, etc.)
    # ========================================================================
    print("🏗️  VALIDATING YAML STRUCTURE")
    print("-" * 80)
    
    is_structure_valid, structure_errors = validate_yaml_structure(yaml_file)
    
    if not is_structure_valid:
        print("❌ CRITICAL STRUCTURAL ERRORS FOUND - Must fix before proceeding!\n")
        
        # Display all structural errors
        if structure_errors.get('duplicate_keys'):
            print("🔴 DUPLICATE KEYS:")
            for dup in structure_errors['duplicate_keys']:
                print(f"   • {dup['error']}")
                if 'line' in dup:
                    print(f"     Line {dup['line']} (first at line {dup.get('previous_line', 'N/A')})")
                print(f"     💡 {dup['suggestion']}\n")
        
        if structure_errors.get('missing_keys'):
            print("🔴 MISSING REQUIRED KEYS:")
            for missing in structure_errors['missing_keys']:
                print(f"   • {missing['error']}")
                print(f"     💡 {missing['suggestion']}\n")
        
        if structure_errors.get('structure_errors'):
            print("🔴 STRUCTURE ERRORS:")
            for struct in structure_errors['structure_errors']:
                print(f"   • {struct['error']}")
                print(f"     💡 {struct['suggestion']}\n")
        
        if structure_errors.get('empty_sections'):
            print("🔴 EMPTY SECTIONS:")
            for empty in structure_errors['empty_sections']:
                print(f"   • {empty['error']}")
                print(f"     💡 {empty['suggestion']}\n")
        
        print("=" * 80)
        print("⚠️  Fix structural errors above before validating individual components/services")
        print("=" * 80)
        return None
    else:
        print("✅ YAML structure is valid\n")
        
        # Display warnings if any
        if structure_errors.get('warnings'):
            print("⚠️  WARNINGS:")
            for warning in structure_errors['warnings']:
                print(f"   • {warning['warning']}")
                print(f"     💡 {warning['suggestion']}\n")
    
    # Initialize counters
    stats = {
        'deployment_groups': {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'details': []
        },
        'components': {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'details': []
        },
        'environment_groups': {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'details': []
        },
        'services': {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'details': []
        },
        'structure_warnings': structure_errors.get('warnings', [])
    }
    
    # ========================================================================
    # PART 1: Validate DeploymentGroups (Applications) and Components
    # ========================================================================
    print("📦 VALIDATING DEPLOYMENT GROUPS & COMPONENTS")
    print("-" * 80)
    
    try:
        # Suppress YamlHelper's verbose linter output
        with redirect_stdout(io.StringIO()):
            apps = populate_applications_from_config(yaml_file)
        stats['deployment_groups']['total'] = len(apps)
        
        for app in apps:
            app_name = app.get('AppName', 'Unknown')
            is_valid, errors = validate_application(app)
            
            if is_valid:
                stats['deployment_groups']['valid'] += 1
                print(f"✅ DeploymentGroup: {app_name}")
                print(f"   BU: {app.get('BU', 'Not set')}")
                print(f"   Status: {app.get('Status', 'Unknown')}")
                print(f"   Components: {len(app.get('Components', []))}")
            else:
                stats['deployment_groups']['invalid'] += 1
                print(f"❌ DeploymentGroup: {app_name} - INVALID")
                print(f"   Errors: {errors}")
                stats['deployment_groups']['details'].append({
                    'name': app_name,
                    'errors': errors
                })
            
            # Validate each component
            for comp in app.get('Components', []):
                stats['components']['total'] += 1
                comp_name = comp.get('ComponentName', 'Unknown')
                deployment_set = comp.get('Deployment_set', 'NOT SET')
                
                is_valid, errors = validate_component(comp)
                
                if is_valid:
                    stats['components']['valid'] += 1
                    print(f"   ✅ Component: {comp_name}")
                    print(f"      Deployment_set: {deployment_set}")
                    print(f"      Status: {comp.get('Status', 'Unknown')}")
                else:
                    stats['components']['invalid'] += 1
                    print(f"   ❌ Component: {comp_name} - INVALID")
                    print(f"      Deployment_set: {deployment_set}")
                    print(f"      Errors: {errors}")
                    stats['components']['details'].append({
                        'app': app_name,
                        'component': comp_name,
                        'deployment_set': deployment_set,
                        'errors': errors
                    })
            
            print()  # Blank line between apps
            
    except Exception as e:
        print(f"❌ ERROR loading DeploymentGroups: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # ========================================================================
    # PART 2: Validate Environment Groups and Services
    # ========================================================================
    print("\n🌍 VALIDATING ENVIRONMENT GROUPS & SERVICES")
    print("-" * 80)
    
    try:
        # Suppress YamlHelper's verbose linter output
        with redirect_stdout(io.StringIO()):
            envs = populate_environments_from_env_groups_from_config(yaml_file)
        stats['environment_groups']['total'] = len(envs)
        
        for env in envs:
            env_name = env.get('Name', 'Unknown')
            is_valid, errors = validate_environment(env)
            
            if is_valid:
                stats['environment_groups']['valid'] += 1
                print(f"✅ Environment Group: {env_name}")
                print(f"   Type: {env.get('Type', 'Unknown')}")
                print(f"   Status: {env.get('Status', 'Unknown')}")
                print(f"   Services: {len(env.get('Services', []))}")
            else:
                stats['environment_groups']['invalid'] += 1
                print(f"❌ Environment Group: {env_name} - INVALID")
                print(f"   Errors: {errors}")
                stats['environment_groups']['details'].append({
                    'name': env_name,
                    'errors': errors
                })
            
            # Validate each service
            for service in env.get('Services', []):
                stats['services']['total'] += 1
                service_name = service.get('Service', 'Unknown')
                deployment_set = service.get('Deployment_set', 'NOT SET')
                
                is_valid, errors = validate_service(service)
                
                if is_valid:
                    stats['services']['valid'] += 1
                    print(f"   ✅ Service: {service_name}")
                    print(f"      Deployment_set: {deployment_set}")
                    print(f"      Type: {service.get('Type', 'Unknown')}")
                else:
                    stats['services']['invalid'] += 1
                    print(f"   ❌ Service: {service_name} - INVALID")
                    print(f"      Deployment_set: {deployment_set}")
                    print(f"      Errors: {errors}")
                    stats['services']['details'].append({
                        'env': env_name,
                        'service': service_name,
                        'deployment_set': deployment_set,
                        'errors': errors
                    })
            
            print()  # Blank line between envs
            
    except Exception as e:
        print(f"❌ ERROR loading Environment Groups: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    return stats


def print_summary(stats):
    """
    Print comprehensive summary with success rates
    """
    print("\n" + "=" * 80)
    print("📊 VALIDATION SUMMARY")
    print("=" * 80)
    
    # Calculate success rates
    def calc_rate(valid, total):
        return (valid / total * 100) if total > 0 else 0
    
    # DeploymentGroups Summary
    dg_rate = calc_rate(stats['deployment_groups']['valid'], stats['deployment_groups']['total'])
    dg_icon = "✅" if dg_rate == 100 else "⚠️" if dg_rate >= 80 else "❌"
    
    print(f"\n{dg_icon} DEPLOYMENT GROUPS (Applications):")
    print(f"   Total:      {stats['deployment_groups']['total']}")
    print(f"   Valid:      {stats['deployment_groups']['valid']}")
    print(f"   Invalid:    {stats['deployment_groups']['invalid']}")
    print(f"   Success Rate: {dg_rate:.1f}%")
    
    # Components Summary
    comp_rate = calc_rate(stats['components']['valid'], stats['components']['total'])
    comp_icon = "✅" if comp_rate == 100 else "⚠️" if comp_rate >= 80 else "❌"
    
    print(f"\n{comp_icon} COMPONENTS (under Applications):")
    print(f"   Total:      {stats['components']['total']}")
    print(f"   Valid:      {stats['components']['valid']}")
    print(f"   Invalid:    {stats['components']['invalid']}")
    print(f"   Success Rate: {comp_rate:.1f}%")
    
    # Environment Groups Summary
    eg_rate = calc_rate(stats['environment_groups']['valid'], stats['environment_groups']['total'])
    eg_icon = "✅" if eg_rate == 100 else "⚠️" if eg_rate >= 80 else "❌"
    
    print(f"\n{eg_icon} ENVIRONMENT GROUPS:")
    print(f"   Total:      {stats['environment_groups']['total']}")
    print(f"   Valid:      {stats['environment_groups']['valid']}")
    print(f"   Invalid:    {stats['environment_groups']['invalid']}")
    print(f"   Success Rate: {eg_rate:.1f}%")
    
    # Services Summary
    svc_rate = calc_rate(stats['services']['valid'], stats['services']['total'])
    svc_icon = "✅" if svc_rate == 100 else "⚠️" if svc_rate >= 80 else "❌"
    
    print(f"\n{svc_icon} SERVICES (under Environment Groups):")
    print(f"   Total:      {stats['services']['total']}")
    print(f"   Valid:      {stats['services']['valid']}")
    print(f"   Invalid:    {stats['services']['invalid']}")
    print(f"   Success Rate: {svc_rate:.1f}%")
    
    # Overall Summary
    total_items = (stats['deployment_groups']['total'] + stats['components']['total'] + 
                   stats['environment_groups']['total'] + stats['services']['total'])
    total_valid = (stats['deployment_groups']['valid'] + stats['components']['valid'] + 
                   stats['environment_groups']['valid'] + stats['services']['valid'])
    total_invalid = (stats['deployment_groups']['invalid'] + stats['components']['invalid'] + 
                     stats['environment_groups']['invalid'] + stats['services']['invalid'])
    
    overall_rate = calc_rate(total_valid, total_items)
    overall_icon = "✅" if overall_rate == 100 else "⚠️" if overall_rate >= 80 else "❌"
    
    print(f"\n{overall_icon} OVERALL VALIDATION:")
    print(f"   Total Items:  {total_items}")
    print(f"   Valid:        {total_valid}")
    print(f"   Invalid:      {total_invalid}")
    print(f"   Success Rate: {overall_rate:.1f}%")
    
    # Error Details
    if total_invalid > 0:
        print("\n" + "=" * 80)
        print("❌ ERROR DETAILS")
        print("=" * 80)
        
        if stats['deployment_groups']['details']:
            print("\n📦 DeploymentGroup Errors:")
            for detail in stats['deployment_groups']['details']:
                print(f"   • {detail['name']}: {detail['errors']}")
        
        if stats['components']['details']:
            print("\n🔧 Component Errors:")
            for detail in stats['components']['details']:
                print(f"   • {detail['app']} → {detail['component']}")
                print(f"     Deployment_set: {detail['deployment_set']}")
                print(f"     Errors: {detail['errors']}")
        
        if stats['environment_groups']['details']:
            print("\n🌍 Environment Group Errors:")
            for detail in stats['environment_groups']['details']:
                print(f"   • {detail['name']}: {detail['errors']}")
        
        if stats['services']['details']:
            print("\n⚙️  Service Errors:")
            for detail in stats['services']['details']:
                print(f"   • {detail['env']} → {detail['service']}")
                print(f"     Deployment_set: {detail['deployment_set']}")
                print(f"     Errors: {detail['errors']}")
    
    print("\n" + "=" * 80)
    
    # Return exit code based on validation
    return 0 if total_invalid == 0 else 1


def main():
    """
    Main entry point
    """
    # Default YAML file
    default_yaml = 'Resources/q2/core-structure-backoffice-with-env-demo.yaml'
    
    # Check if file provided as argument
    if len(sys.argv) > 1:
        yaml_file = sys.argv[1]
    else:
        yaml_file = default_yaml
    
    # Check if file exists
    if not os.path.exists(yaml_file):
        print(f"❌ ERROR: File not found: {yaml_file}")
        print(f"\nUsage: python3 validate_yaml_detailed.py [yaml_file]")
        print(f"Example: python3 validate_yaml_detailed.py Resources/q2/core-structure-backoffice-with-env-demo.yaml")
        sys.exit(1)
    
    # Validate and get stats
    stats = validate_yaml_with_stats(yaml_file)
    
    if stats is None:
        print("\n❌ VALIDATION FAILED - Unable to parse YAML file")
        sys.exit(1)
    
    # Print summary and exit
    exit_code = print_summary(stats)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

