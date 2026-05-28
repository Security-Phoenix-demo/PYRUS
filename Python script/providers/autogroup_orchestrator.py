"""
Phoenix Security - Autogroup Orchestrator
Main entry point for automatic asset grouping and component creation

Usage:
    from providers.autogroup_orchestrator import run_autogroup
    run_autogroup(client_id, client_secret, config_path, mode='batch')
"""

import sys
import json
import logging
import yaml
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, TextIO


# Dedicated logger for autogroup. We attach a per-run JSON file handler inside
# run_autogroup() so each invocation's audit trail lives in its own folder
# alongside the YAML artifacts. The console handler stays at WARNING by default
# so existing human-readable print() output continues to drive interactive UX.
_LOGGER = logging.getLogger("autogroup")
_LOGGER.setLevel(logging.INFO)
if not _LOGGER.handlers:
    _console = logging.StreamHandler()
    _console.setLevel(logging.WARNING)
    _console.setFormatter(logging.Formatter("%(asctime)s [autogroup:%(levelname)s] %(message)s"))
    _LOGGER.addHandler(_console)


class _TeeStream:
    """Mirror stdout/stderr to a log file (same pattern as batch-upload ``tee``)."""

    def __init__(self, stream: TextIO, log_file: TextIO) -> None:
        self._stream = stream
        self._log = log_file

    def write(self, data: str) -> int:
        if not data:
            return 0
        self._stream.write(data)
        self._log.write(data)
        return len(data)

    def flush(self) -> None:
        self._stream.flush()
        self._log.flush()

    def isatty(self) -> bool:
        return getattr(self._stream, "isatty", lambda: False)()


@contextmanager
def _capture_terminal_log(run_dir: Path, enabled: bool = True):
    """Write all autogroup ``print()`` output to ``run_dir/terminal.log``."""
    if not enabled:
        yield None
        return

    path = run_dir / "terminal.log"
    with open(path, "w", encoding="utf-8") as log_fp:
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout = _TeeStream(old_stdout, log_fp)
        sys.stderr = _TeeStream(old_stderr, log_fp)
        try:
            yield path
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr


class _JsonLineFormatter(logging.Formatter):
    """Emit one JSON object per record so the log file is machine-parseable."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "event": getattr(record, "event", record.msg if isinstance(record.msg, str) else "log"),
        }
        for key in ("phase", "duration_s", "input_count", "output_count", "source", "run_id", "details"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _attach_run_log(run_dir: Path, run_id: str) -> logging.Handler:
    """Attach a JSON file handler scoped to this run.

    Idempotent across invocations: any FileHandler left attached from a prior
    run_autogroup() call is detached and closed first so multi-run processes
    do not leak handles or duplicate log lines.
    """
    for existing in list(_LOGGER.handlers):
        if isinstance(existing, logging.FileHandler):
            _LOGGER.removeHandler(existing)
            try:
                existing.close()
            except Exception:
                pass

    handler = logging.FileHandler(run_dir / "autogroup.log")
    handler.setLevel(logging.INFO)
    handler.setFormatter(_JsonLineFormatter())
    _LOGGER.addHandler(handler)
    _LOGGER.info("run_started", extra={"event": "run_started", "run_id": run_id})
    return handler


def _log_phase(phase: str, *, duration_s: float, input_count: Optional[int] = None,
               output_count: Optional[int] = None, source: Optional[str] = None,
               status: str = "success", details: Optional[Dict] = None) -> None:
    """Structured per-phase audit event written to autogroup.log."""
    _LOGGER.info(
        "phase_complete",
        extra={
            "event": "phase_complete",
            "phase": phase,
            "duration_s": round(duration_s, 4),
            "input_count": input_count,
            "output_count": output_count,
            "source": source,
            "details": {"status": status, **(details or {})},
        },
    )

from providers.AutoGroupEngine import (
    CheckpointManager, TagAnalyzer, AssetGrouper,
    load_config, fetch_assets_from_api, load_assets_from_file, export_to_yaml,
    generate_standard_yaml_structure, create_grouping_plan,
)


class AutogroupEmptyResultError(RuntimeError):
    """Raised when autogroup completes a phase with zero results and the operator did not opt in.

    The historical behaviour was to emit an empty YAML and report success. That masked real
    failures (stale checkpoints, broken API filters, no unassigned assets). We now fail loud
    by default; set `validation.allow_empty_output: true` in the autogroup config to restore
    the old silent behaviour.
    """
from providers.Phoenix import get_auth_token, populate_applications_and_environments
from providers.YamlHelper import (
    populate_applications_from_config, populate_environments_from_env_groups_from_config,
    populate_repositories_from_config, populate_teams
)


REPO_ROOT = Path(__file__).resolve().parent.parent


def _resolve_output_root(output_dir: Optional[str], config: Dict) -> Path:
    """Resolve the autogroup output root.

    Precedence: explicit CLI/argument > config.output.base_dir > default 'autogroup-output'.
    Relative paths are interpreted from the repo root, not the current working directory,
    so the location is stable regardless of where the user launches the command from.
    """
    base = output_dir or config.get('output', {}).get('base_dir', 'autogroup-output')
    base_path = Path(base)
    if not base_path.is_absolute():
        base_path = (REPO_ROOT / base_path).resolve()
    return base_path


def _try_resume_assets(resume_manager: Optional[CheckpointManager], checkpoint_file: str,
                       mode: str, max_age_hours: float, allow_empty: bool) -> Optional[Tuple[List, Dict]]:
    """Return (assets, tag_analysis) from the newest usable checkpoint, or None to fetch fresh.

    "Usable" means all of: a reader exists, the checkpoint file is present, it is younger
    than max_age_hours, the operator consents (automatic in batch mode), it loads cleanly,
    and - unless allow_empty is set - it carries at least one asset. That last empty-asset
    guard is what stops a single failed fetch from poisoning every later run with an empty
    checkpoint (the historical silent empty-YAML regression).
    """
    if resume_manager is None or not resume_manager.checkpoint_exists(checkpoint_file):
        return None

    age = resume_manager.get_checkpoint_age(checkpoint_file)
    if not age or age.total_seconds() / 3600 >= max_age_hours:
        print(f"⚠️  Checkpoint too old (age: {age}), fetching fresh data")
        return None

    print(f"📌 Found recent checkpoint (age: {age})")
    if mode != 'batch' and not _confirm("Resume from checkpoint?"):
        return None

    checkpoint_data = resume_manager.load_checkpoint(checkpoint_file)
    if not checkpoint_data:
        return None

    assets = checkpoint_data.get('assets', [])
    tag_analysis = checkpoint_data.get('tag_analysis', {})
    if not assets and not allow_empty:
        print("⚠️  Refusing to resume from empty checkpoint (asset_count=0). Forcing fresh fetch.")
        return None

    return assets, tag_analysis


def run_autogroup(client_id: str,
                  client_secret: str,
                  config_path: str,
                  mode: str = 'batch',
                  asset_source: str = None,
                  asset_file: str = None,
                  action_teams: bool = False,
                  action_code: bool = False,
                  action_cloud: bool = False,
                  output_dir: Optional[str] = None) -> Dict:
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
        output_dir: Output root for run artifacts. Overrides config.output.base_dir.
            Default: <repo_root>/autogroup-output. Each invocation creates a
            timestamped subfolder inside the root.
    
    Returns:
        Dict with execution results and statistics
    """
    # ========================================================================
    # PHASE 0: INITIALIZATION (config + run folder before any console output)
    # ========================================================================

    config = load_config(config_path)

    if mode:
        config['execution']['mode'] = mode
    if asset_source:
        config['execution']['asset_source'] = asset_source
    if asset_file:
        config['execution']['asset_file'] = asset_file

    output_root = _resolve_output_root(output_dir, config)
    base_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_dir = output_root / base_timestamp
    _collision = 1
    while run_dir.exists():
        run_dir = output_root / f"{base_timestamp}_{_collision:02d}"
        _collision += 1
    run_dir.mkdir(parents=True, exist_ok=True)
    run_timestamp = run_dir.name

    capture_terminal = config.get('output', {}).get('capture_terminal_log', True)

    with _capture_terminal_log(run_dir, enabled=capture_terminal):
        return _run_autogroup_body(
            client_id=client_id,
            client_secret=client_secret,
            config_path=config_path,
            config=config,
            mode=mode,
            asset_source=asset_source,
            asset_file=asset_file,
            action_teams=action_teams,
            action_code=action_code,
            action_cloud=action_cloud,
            run_dir=run_dir,
            run_timestamp=run_timestamp,
            output_root=output_root,
        )


def _run_autogroup_body(
    *,
    client_id: str,
    client_secret: str,
    config_path: str,
    config: Dict,
    mode: str,
    asset_source: Optional[str],
    asset_file: Optional[str],
    action_teams: bool,
    action_code: bool,
    action_cloud: bool,
    run_dir: Path,
    run_timestamp: str,
    output_root: Path,
) -> Dict:
    """Autogroup phases 0–5; stdout/stderr are tee'd by the caller when enabled."""

    print("\n" + "="*80)
    print("🚀 PHOENIX SECURITY - AUTOMATIC ASSET GROUPING")
    print("="*80)
    print(f"Mode: {mode.upper()}")
    print(f"Config: {config_path}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n🎯 Action Flags:")
    print(f"   • Teams: {'✅ Enabled' if action_teams else '❌ Disabled'}")
    print(f"   • Code:  {'✅ Enabled' if action_code else '❌ Disabled'}")
    print(f"   • Cloud: {'✅ Enabled' if action_cloud else '❌ Disabled'}")

    implementation_enabled = action_teams or action_code or action_cloud
    if not implementation_enabled:
        print(f"\n📝 OPERATION MODE: Generate YAML Only (no implementation)")
    else:
        print(f"\n🚀 OPERATION MODE: Generate YAML + Implement")

    print("="*80)
    print(f"📁 Run output: {run_dir}")
    print(f"📝 Terminal log: {run_dir / 'terminal.log'}")

    checkpoint_folder_name = config.get('checkpoint', {}).get('folder', 'checkpoints')
    # Checkpoint writer: always anchored under this run's folder.
    checkpoint_manager = CheckpointManager(str(run_dir / checkpoint_folder_name))

    # Checkpoint reader for resume: the most recent prior run that actually has
    # checkpoint files. Decoupled from the writer so a clean new run never inherits
    # the previous run's empty/stale outputs.
    resume_manager: Optional[CheckpointManager] = None
    if config.get('checkpoint', {}).get('enabled', True) and config.get('execution', {}).get('resume_from_checkpoint', True):
        candidate_runs = sorted(
            [p for p in output_root.glob('*') if p.is_dir() and p != run_dir],
            reverse=True,
        )
        for candidate in candidate_runs:
            cp_dir = candidate / checkpoint_folder_name
            if cp_dir.is_dir() and any(cp_dir.iterdir()):
                resume_manager = CheckpointManager(str(cp_dir))
                break

    run_log_handler = _attach_run_log(run_dir, run_timestamp)

    # Initialize results tracking
    results = {
        'started_at': datetime.now().isoformat(),
        'config_path': config_path,
        'output_dir': str(run_dir),
        'terminal_log': str(run_dir / 'terminal.log'),
        'run_id': run_timestamp,
        'mode': config['execution']['mode'],
        'phases': {},
        'statistics': {},
        'errors': []
    }
    
    # Auth is only required for the API asset source or for any implementation
    # phase (action_teams / action_code / action_cloud). A pure file-mode
    # generate-only run produces YAML offline and should not need credentials,
    # so we skip the token call in that case.
    resolved_asset_source = (asset_source or config.get('execution', {}).get('asset_source', 'api')).lower()
    needs_auth = resolved_asset_source != 'file' or implementation_enabled
    if needs_auth:
        if not client_id or not client_secret:
            raise ValueError(
                "client_id and client_secret are required when asset_source is 'api' "
                "or when any --action_* flag is set."
            )
        access_token = get_auth_token(client_id, client_secret)
        headers = {"Authorization": f"Bearer {access_token}"}
    else:
        access_token = None
        headers = {}
        print("\nℹ️  File mode + generate-only: skipping Phoenix API auth")

    print("\n✅ Initialization complete")
    
    # ========================================================================
    # PHASE 1: ASSET LOADING
    # ========================================================================
    
    print("\n" + "="*80)
    print("PHASE 1: ASSET LOADING")
    print("="*80)
    
    phase_start = datetime.now()
    
    # Resume from the most recent prior run's checkpoint when one is usable; otherwise
    # fetch fresh. _try_resume_assets owns the age / empty-guard / confirm checks and
    # returns None to mean "no usable checkpoint - fetch fresh".
    checkpoint_file = config.get('checkpoint', {}).get('tag_analysis_file', 'checkpoint-01-tag-analysis.json')
    allow_empty_resume = config.get('validation', {}).get('allow_empty_output', False)
    max_age_hours = config.get('checkpoint', {}).get('max_checkpoint_age_hours', 168)

    resumed = _try_resume_assets(resume_manager, checkpoint_file, mode, max_age_hours, allow_empty_resume)

    if resumed is not None:
        assets, tag_analysis = resumed
        analyzer = TagAnalyzer(assets)
        analyzer.load_stats_from_analysis(tag_analysis)
        print(f"✅ Resumed from checkpoint: {len(assets):,} assets loaded")
        results['phases']['asset_loading'] = {
            'status': 'resumed_from_checkpoint',
            'asset_count': len(assets),
            'duration_seconds': (datetime.now() - phase_start).total_seconds(),
        }
        _log_phase(
            'asset_loading',
            duration_s=results['phases']['asset_loading']['duration_seconds'],
            output_count=len(assets),
            source='checkpoint',
            status='resumed_from_checkpoint',
        )
    else:
        # Fetch fresh assets. resolved_asset_source was computed once during init
        # (lowercased), so file/api routing here matches the earlier auth decision.
        if resolved_asset_source == 'file':
            asset_file_path = config['execution'].get('asset_file', 'example-data/assets.json')
            assets = load_assets_from_file(str(REPO_ROOT / asset_file_path))
        else:
            assets = fetch_assets_from_api(client_id, client_secret, config)

        results['phases']['asset_loading'] = {
            'status': 'success',
            'asset_count': len(assets),
            'source': resolved_asset_source,
            'duration_seconds': (datetime.now() - phase_start).total_seconds()
        }
        _log_phase(
            'asset_loading',
            duration_s=results['phases']['asset_loading']['duration_seconds'],
            output_count=len(assets),
            source=resolved_asset_source,
            status='success' if assets else 'empty',
        )

        # Loud-fail on zero assets: this is the single most common silent-failure mode
        # (stale token, wrong API filter, empty tenant). Operators must opt in to empty
        # runs via validation.allow_empty_output.
        if not assets:
            msg = (
                f"Phase 1 loaded 0 assets from {resolved_asset_source!r}. "
                "Common causes: wrong --api_domain/credentials, invalid /v1/assets search "
                "body (fixed in current engine - use per-type requests), empty tenant, "
                "or wrong asset_file path when asset_source=file."
            )
            print(f"\n❌ {msg}")
            if not allow_empty_resume:
                results['errors'].append(msg)
                results['phases']['asset_loading']['status'] = 'empty'
                raise AutogroupEmptyResultError(msg)
            print("   (validation.allow_empty_output is true - continuing anyway)")
        
        # Perform tag analysis
        print("\n" + "="*80)
        print("PHASE 1B: TAG ANALYSIS")
        print("="*80)
        
        analyzer = TagAnalyzer(assets)
        # Cache lives at the output_root (shared across runs) so identical asset sets
        # don't recompute tag analysis on every invocation.
        tag_cache_dir = output_root / '.cache' / 'tag-analysis'
        tag_analysis = analyzer.analyze(cache_dir=tag_cache_dir)
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
            output_path = run_dir / config['output']['tag_analysis_path'].replace(
                '{timestamp}', run_timestamp
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
    
    # analyzer already carries tag_stats - from the fresh analyze() above or, on a
    # resumed run, from load_stats_from_analysis() - so this works for both paths.
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

    # Empty-output safeguard: Phase 3 producing zero groups means there is nothing to
    # emit and any downstream YAML will be empty. Historically this was reported as
    # "success" - we now treat it as a hard failure unless the operator opts in.
    if not all_groups and not allow_empty_resume:
        msg = (
            f"Phase 3 produced 0 groups from {len(assets)} assets. "
            "Either all assets fell below min_assets_per_component, or the grouping "
            "configuration filtered everything out."
        )
        print(f"\n❌ {msg}")
        results['errors'].append(msg)
        results['phases']['grouping'] = {
            'status': 'empty',
            'tagged_groups': 0,
            'untagged_groups': 0,
            'total_groups': 0,
            'duration_seconds': (datetime.now() - phase_start).total_seconds(),
        }
        _log_phase(
            'grouping',
            duration_s=results['phases']['grouping']['duration_seconds'],
            input_count=len(assets),
            output_count=0,
            status='empty',
        )
        raise AutogroupEmptyResultError(msg)

    # Create grouping plan (shared with the synthetic regression test via the engine)
    grouping_plan = create_grouping_plan(all_groups, config, primary_tag, secondary_tag)

    results['phases']['grouping'] = {
        'status': 'success',
        'tagged_groups': len(tagged_groups),
        'untagged_groups': len(untagged_groups),
        'total_groups': len(all_groups),
        'duration_seconds': (datetime.now() - phase_start).total_seconds()
    }
    _log_phase(
        'grouping',
        duration_s=results['phases']['grouping']['duration_seconds'],
        input_count=len(assets),
        output_count=len(all_groups),
        status='success',
        details={'tagged': len(tagged_groups), 'untagged': len(untagged_groups)},
    )
    
    # Save grouping plan checkpoint
    if config.get('checkpoint', {}).get('enabled', True):
        checkpoint_file = config.get('checkpoint', {}).get('grouping_plan_file', 'checkpoint-02-grouping-plan.yaml')
        checkpoint_manager.save_checkpoint('grouping_plan', grouping_plan, checkpoint_file)
    
    # Export grouping plan if configured
    if config.get('output', {}).get('export_grouping_plan', True):
        output_path = run_dir / config['output']['grouping_plan_path'].replace(
            '{timestamp}', run_timestamp
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
    yaml_output_path = run_dir / yaml_config.get('output_path', 'core-structure-{timestamp}.yaml').replace(
        '{timestamp}', run_timestamp
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
    _log_phase(
        'yaml_generation',
        duration_s=results['phases']['yaml_generation']['duration_seconds'],
        input_count=len(all_groups),
        output_count=(
            len(yaml_structure.get('DeploymentGroups', []))
            + len(yaml_structure.get('EnvironmentGroups', []))
        ),
        details={
            'deployment_groups': len(yaml_structure.get('DeploymentGroups', [])),
            'environment_groups': len(yaml_structure.get('EnvironmentGroups', [])),
            'output_file': str(yaml_output_path),
        },
    )
    
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
    _log_phase(
        'implementation',
        duration_s=results['phases']['implementation']['duration_seconds'],
        status=results['phases']['implementation']['status'],
        details={
            'teams_created': implementation_stats['teams_created'],
            'applications_created': implementation_stats['applications_created'],
            'components_created': implementation_stats['components_created'],
            'environments_created': implementation_stats['environments_created'],
            'services_created': implementation_stats['services_created'],
            'failed': implementation_stats['failed'],
        },
    )
    
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
        output_path = run_dir / config['output']['yaml_output_path'].replace(
            '{timestamp}', run_timestamp
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
        report_path = run_dir / config['output']['report_path'].replace(
            '{timestamp}', run_timestamp
        )
        
        with open(report_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n✅ Execution report saved to: {report_path}")
    
    # Print summary
    _print_final_summary(results)
    
    return results


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
    # Minimal CLI shim. The primary entry point is run-phx.py --action_autogroup;
    # this exists for quick manual invocation. With no action flags it runs in
    # generate-only mode, so statistics stays empty until an implementation phase runs.
    if len(sys.argv) < 4:
        print("Usage: python autogroup_orchestrator.py <client_id> <client_secret> <config_path> [mode]")
        sys.exit(1)

    client_id = sys.argv[1]
    client_secret = sys.argv[2]
    config_path = sys.argv[3]
    mode = sys.argv[4] if len(sys.argv) > 4 else 'batch'

    results = run_autogroup(client_id, client_secret, config_path, mode)

    stats = results.get('statistics') or {}
    print(f"\n✅ Execution completed!")
    if results.get('yaml_only_mode') or not stats:
        print(f"   Generate-only mode - YAML written to: {results.get('output_dir', '?')}")
    else:
        print(f"   Components created: {stats.get('components_created', 0)}")

