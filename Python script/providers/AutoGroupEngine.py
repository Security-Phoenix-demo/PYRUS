"""
Phoenix Security - Automatic Asset Grouping Engine
Intelligently groups assets by tags and creates Components/Services with checkpoint/resume support

Author: Phoenix Security Team
Date: 2025-11-19
Version: 1.0.0
"""

import re
import json
import hashlib
import yaml
import ipaddress
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional, Set
from collections import defaultdict, Counter
from pathlib import Path
import Levenshtein
import requests


# --- Performance tuning constants ---------------------------------------------------
# Prefix length used to bucket hostnames/image names before Levenshtein comparison.
# Larger -> stricter bucketing (fewer collisions, more buckets); smaller -> looser.
# 3 chars is a good default - most app/team naming prefixes are at least that long.
BUCKET_PREFIX_LEN = 3
# Default CIDR mask used to group INFRA assets without an Application tag.
DEFAULT_INFRA_CIDR_MASK = 24
# Default API page size for fetch_assets_from_api when not overridden in config.
DEFAULT_API_PAGE_SIZE = 1000
# Default maximum number of concurrent in-flight API page requests.
DEFAULT_API_MAX_CONCURRENCY = 4
# Asset types accepted by POST /v1/assets search (one type per request).
API_SEARCH_ASSET_TYPES: Tuple[str, ...] = (
    "CLOUD",
    "INFRA",
    "CONTAINER",
    "WEBSITE_API",
    "REPOSITORY",
    "SOURCE_CODE",
    "BUILD",
)

_STATUS_SHORTNAMES = {
    'Develop': 'dev',
    'Development': 'dev',
    'develop': 'dev',
    'Production': 'prod',
    'production': 'prod',
    'prod': 'prod',
    'Staging': 'stg',
    'staging': 'stg',
    'stage': 'stg',
    'Test': 'test',
    'testing': 'test',
    'QA': 'qa',
    'qa': 'qa',
}

# Import Phoenix API functions. Only fetch_assets_from_api talks to the live API;
# all component/environment creation is delegated to the YAML-ingestion path in
# autogroup_orchestrator (populate_applications_from_config et al.).
from providers.Phoenix import get_auth_token, construct_api_url


class CheckpointManager:
    """Manages checkpoints for resumable execution"""
    
    def __init__(self, checkpoint_folder: str):
        self.checkpoint_folder = Path(checkpoint_folder)
        self.checkpoint_folder.mkdir(parents=True, exist_ok=True)
        
    def save_checkpoint(self, checkpoint_type: str, data: Any, filename: str = None):
        """Persist checkpoint data, choosing format from the filename extension.

        '.yaml'/'.yml' -> YAML, anything else -> JSON. This keeps the on-disk
        artifact honest (e.g. checkpoint-02-grouping-plan.yaml is real YAML you
        can diff) instead of writing JSON into a .yaml file. load_checkpoint
        reverses the choice symmetrically.
        """
        if filename is None:
            filename = f"checkpoint-{checkpoint_type}-{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        filepath = self.checkpoint_folder / filename

        with open(filepath, 'w') as f:
            if filename.endswith(('.yaml', '.yml')):
                # Normalise through JSON first so non-YAML-native types (datetime,
                # set, ...) are coerced just as the JSON path would, then emit YAML.
                yaml.safe_dump(
                    json.loads(json.dumps(data, default=str)),
                    f, default_flow_style=False, sort_keys=False,
                )
            elif isinstance(data, (dict, list)):
                json.dump(data, f, indent=2, default=str)
            else:
                f.write(str(data))

        print(f"✅ Checkpoint saved: {filepath}")
        return str(filepath)

    def load_checkpoint(self, filename: str) -> Optional[Any]:
        """Load checkpoint data, parsing by extension (YAML for .yaml/.yml, else JSON)."""
        filepath = self.checkpoint_folder / filename

        if not filepath.exists():
            return None

        try:
            with open(filepath, 'r') as f:
                if filename.endswith(('.yaml', '.yml')):
                    return yaml.safe_load(f)
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

    def _content_hash(self) -> str:
        """Stable fingerprint of (assetName, type, sorted-tags) per asset.

        Two asset lists with the same fingerprint produce identical analyses,
        so we can short-circuit a re-analysis by reusing a cached result.
        """
        h = hashlib.sha256()
        for asset in self.assets:
            h.update((asset.get('assetName') or '').encode('utf-8', 'ignore'))
            h.update(b'|')
            h.update((asset.get('type') or '').encode('utf-8', 'ignore'))
            h.update(b'|')
            tags = asset.get('tags') or []
            tag_repr = sorted(
                f"{t.get('key', '')}={t.get('value', '')}" for t in tags if isinstance(t, dict)
            )
            h.update(';'.join(tag_repr).encode('utf-8', 'ignore'))
            h.update(b'\n')
        return h.hexdigest()

    def analyze(self, cache_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Perform comprehensive tag analysis.

        If cache_dir is provided and a cached analysis exists for the current
        asset-set fingerprint, return it instead of recomputing. Cache hit/miss
        is logged but never fatal - the cache is best-effort.
        """
        cache_key: Optional[str] = None
        if cache_dir is not None:
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
                cache_key = self._content_hash()
                cache_path = cache_dir / f"tag-analysis-{cache_key}.json"
                if cache_path.exists():
                    print(f"\n🔁 Tag analysis cache hit ({cache_key[:12]}...) - skipping recompute")
                    try:
                        return json.loads(cache_path.read_text())
                    except (OSError, ValueError) as e:
                        print(f"   (cache read failed: {e}; falling through to recompute)")
            except OSError:
                cache_key = None

        result = self._analyze_uncached()

        if cache_dir is not None and cache_key is not None:
            try:
                (cache_dir / f"tag-analysis-{cache_key}.json").write_text(json.dumps(result, indent=2))
            except OSError as e:
                print(f"   (tag analysis cache write failed: {e})")

        return result

    def _analyze_uncached(self) -> Dict[str, Any]:
        """Always-runs analysis core. Kept separate so analyze() owns the cache logic."""
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

    def load_stats_from_analysis(self, tag_analysis: Dict) -> None:
        """Rehydrate tag_stats from a previously-computed analysis dict (checkpoint resume).

        recommend_grouping_tags only reads each tag's 'count', but we restore the
        coverage / unique_values / most_common fields too so a resumed analyzer is
        indistinguishable from one that just ran analyze().
        """
        for tag_info in (tag_analysis or {}).get('tags_by_coverage', []):
            self.tag_stats[tag_info['key']] = {
                'count': tag_info['asset_count'],
                'coverage': tag_info['coverage_percent'],
                'unique_values': tag_info['unique_values'],
                'most_common': tag_info['most_common_values'],
            }

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
        """Group INFRA assets by CIDR or hostname similarity.

        Performance note: hostname similarity grouping uses prefix bucketing
        (first BUCKET_PREFIX_LEN chars of the hostname, lowercased) so the
        Levenshtein comparison is O(n*k) instead of O(n^2), where k is the
        average bucket size. On real INFRA inventories this is typically
        10-50x faster than the original nested loop.
        """
        print(f"\n🔄 Grouping {len(infra_assets):,} INFRA assets by network/hostname...")

        config_fallback = self.config.get('fallback', {}).get('infra', {})
        use_cidr = config_fallback.get('cidr_grouping', True)
        hostname_threshold = config_fallback.get('hostname_similarity_threshold', 0.8)

        cidr_groups = defaultdict(list)
        hostname_buckets: Dict[str, List[List[Dict]]] = defaultdict(list)
        ungrouped = []

        for asset in infra_assets:
            # Try CIDR grouping
            if use_cidr:
                ip = asset.get('ip')
                if ip:
                    try:
                        network = ipaddress.IPv4Network(f"{ip}/{DEFAULT_INFRA_CIDR_MASK}", strict=False)
                        cidr_groups[str(network)].append(asset)
                        continue
                    except (ValueError, ipaddress.AddressValueError, ipaddress.NetmaskValueError):
                        pass

            # Hostname similarity with prefix bucketing
            hostname = asset.get('hostname') or asset.get('assetName')
            if hostname:
                bucket_key = hostname[:BUCKET_PREFIX_LEN].lower()
                bucket = hostname_buckets[bucket_key]
                added = False
                for group in bucket:
                    ref_hostname = group[0].get('hostname') or group[0].get('assetName')
                    if ref_hostname and Levenshtein.ratio(hostname, ref_hostname) >= hostname_threshold:
                        group.append(asset)
                        added = True
                        break
                if not added:
                    bucket.append([asset])
            else:
                ungrouped.append(asset)

        hostname_groups = [g for groups in hostname_buckets.values() for g in groups]
        
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
        """Group CONTAINER assets by name similarity.

        Uses the same prefix-bucketed Levenshtein as INFRA hostname grouping
        to keep the cost O(n*k) on large container inventories.
        """
        print(f"\n🔄 Grouping {len(container_assets):,} CONTAINER assets by name similarity...")

        threshold = self.config.get('fallback', {}).get('container', {}).get('name_similarity_threshold', 0.85)

        buckets: Dict[str, List[List[Dict]]] = defaultdict(list)
        for asset in container_assets:
            name = asset.get('imageName') or asset.get('assetName', '')
            if not name:
                continue
            bucket_key = name[:BUCKET_PREFIX_LEN].lower()
            bucket = buckets[bucket_key]
            added = False
            for group in bucket:
                ref_name = group[0].get('imageName') or group[0].get('assetName', '')
                if Levenshtein.ratio(name, ref_name) >= threshold:
                    group.append(asset)
                    added = True
                    break
            if not added:
                bucket.append([asset])

        groups = [g for bucket in buckets.values() for g in bucket]
        
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


def load_config(config_path: str) -> Dict:
    """Load configuration from YAML file"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def _api_error_snippet(response: requests.Response) -> str:
  """Return a short, safe error detail from a failed Phoenix API response."""
  try:
    payload = response.json()
    if isinstance(payload, dict) and payload.get("error"):
      return str(payload["error"])[:200]
  except (ValueError, TypeError):
    pass
  return (response.text or "")[:200]


def _normalize_api_asset(raw: Dict) -> Dict:
  """Map Phoenix /v1/assets records into the shape autogroup expects."""
  asset: Dict[str, Any] = dict(raw)
  asset["assetName"] = raw.get("assetName") or raw.get("name") or raw.get("id") or ""

  tags = raw.get("tags")
  if tags is None:
    normalized_tags: List[Dict[str, str]] = []
  elif isinstance(tags, dict):
    normalized_tags = [
      {"key": str(k), "value": str(v)}
      for k, v in tags.items()
      if v is not None and str(v).strip()
    ]
  else:
    normalized_tags = list(tags)

  asset["tags"] = normalized_tags

  for entry in raw.get("data") or []:
    if not isinstance(entry, dict):
      continue
    attrs = entry.get("attributes") or {}
    if not isinstance(attrs, dict):
      continue
    if attrs.get("repository") and not asset.get("repository"):
      asset["repository"] = attrs["repository"]
    if attrs.get("buildFile") and not asset.get("buildFile"):
      asset["buildFile"] = attrs["buildFile"]
    if attrs.get("providerType") and not asset.get("cloudProvider"):
      asset["cloudProvider"] = attrs["providerType"]
    if attrs.get("providerAccountId") and not asset.get("account"):
      asset["account"] = attrs["providerAccountId"]
    if attrs.get("imageName") and not asset.get("imageName"):
      asset["imageName"] = attrs["imageName"]
    if attrs.get("ip") and not asset.get("ip"):
      asset["ip"] = attrs["ip"]
    if attrs.get("hostname") and not asset.get("hostname"):
      asset["hostname"] = attrs["hostname"]

  return asset


def _resolve_api_asset_types(config: Dict) -> List[str]:
  """Return the asset types to query, intersected with what /v1/assets accepts."""
  asset_types_cfg = config.get("grouping", {}).get("asset_types", {})
  if asset_types_cfg.get("enabled") and asset_types_cfg.get("types"):
    requested = list(asset_types_cfg["types"])
  else:
    requested = list(API_SEARCH_ASSET_TYPES)

  allowed = set(API_SEARCH_ASSET_TYPES)
  valid = [t for t in requested if t in allowed]
  skipped = [t for t in requested if t not in allowed]
  for t in skipped:
    print(f"  ⚠️  Skipping unsupported API asset type: {t}")
  return valid or list(API_SEARCH_ASSET_TYPES)


def _build_assets_search_body(asset_type: str) -> Dict[str, Any]:
  """Phoenix requires exactly one search request with a type (or types) field."""
  return {"requests": [{"type": asset_type}]}


def _fetch_assets_for_type(
  headers: Dict[str, str],
  asset_type: str,
  page_size: int,
  max_pages: int,
  max_concurrency: int,
) -> List[Dict]:
  """Paginate POST /v1/assets for a single asset type."""
  from concurrent.futures import ThreadPoolExecutor, as_completed

  search_body = _build_assets_search_body(asset_type)

  def _fetch_page(page_number: int) -> Tuple[int, List[Dict], bool, Optional[int]]:
    api_url = construct_api_url(f"/v1/assets?pageNumber={page_number}&pageSize={page_size}")
    response = requests.post(api_url, headers=headers, json=search_body, timeout=120)
    if response.status_code != 200:
      detail = _api_error_snippet(response)
      print(
        f"  ⚠️  {asset_type} page {page_number} failed: HTTP {response.status_code}"
        + (f" ({detail})" if detail else "")
      )
      return page_number, [], True, None
    data = response.json()
    try:
      tp = int(data.get("totalPages") or 0) or None
    except (TypeError, ValueError):
      tp = None
    return (
      page_number,
      data.get("content", []) or [],
      bool(data.get("last", False)),
      tp,
    )

  type_assets: List[Dict] = []
  _, first_content, first_last, total_pages = _fetch_page(0)
  type_assets.extend(first_content)

  if first_last or not first_content:
    return type_assets

  if total_pages and total_pages > 1:
    upper = total_pages
    if max_pages > 0:
      upper = min(upper, max_pages)
    pages_to_fetch = list(range(1, upper))
    with ThreadPoolExecutor(max_workers=max_concurrency) as ex:
      futures = {ex.submit(_fetch_page, p): p for p in pages_to_fetch}
      for fut in as_completed(futures):
        _, content, _, _ = fut.result()
        type_assets.extend(content)
  else:
    page = 1
    while True:
      if max_pages > 0 and page >= max_pages:
        break
      _, content, last, _ = _fetch_page(page)
      if not content:
        break
      type_assets.extend(content)
      if last:
        break
      page += 1

  return type_assets


def fetch_assets_from_api(client_id: str, client_secret: str, config: Dict) -> List[Dict]:
  """Fetch assets from Phoenix API with concurrent pagination per asset type.

  The /v1/assets endpoint requires POST body ``{"requests": [{"type": "CLOUD"}]}``
  (one type per call). The legacy top-level ``onlyUnassigned`` field is rejected
  with HTTP 400 and is not sent.
  """
  print("\n🌐 Fetching assets from Phoenix API...")

  if config.get("grouping", {}).get("only_unassigned", True):
    print(
      "  ℹ️  grouping.only_unassigned is enabled but the API has no supported filter;"
      " fetching all assets (filter in Phoenix UI if you need unassigned only)."
    )

  access_token = get_auth_token(client_id, client_secret)
  headers = {"Authorization": f"Bearer {access_token}"}

  page_size = config.get("execution", {}).get("api_fetch_page_size", DEFAULT_API_PAGE_SIZE)
  max_pages = config.get("execution", {}).get("api_fetch_max_pages", 0)
  rate_cfg = config.get("validation", {}).get("api_rate_limit", {})
  max_concurrency = min(
    max(int(rate_cfg.get("requests_per_second", DEFAULT_API_MAX_CONCURRENCY)), 1),
    DEFAULT_API_MAX_CONCURRENCY * 4,
  )

  asset_types = _resolve_api_asset_types(config)
  seen_ids: Set[str] = set()
  all_assets: List[Dict] = []

  for asset_type in asset_types:
    print(f"  → {asset_type}...")
    raw_for_type = _fetch_assets_for_type(
      headers, asset_type, page_size, max_pages, max_concurrency
    )
    added = 0
    for raw in raw_for_type:
      asset_id = raw.get("id")
      if asset_id:
        if asset_id in seen_ids:
          continue
        seen_ids.add(asset_id)
      all_assets.append(_normalize_api_asset(raw))
      added += 1
    print(f"     {added:,} assets ({len(raw_for_type):,} raw, deduped)")

  print(f"\n✅ Total assets fetched: {len(all_assets):,}")
  return all_assets


def load_assets_from_file(file_path: str) -> List[Dict]:
    """Load assets from JSON file"""
    print(f"\n📄 Loading assets from file: {file_path}")
    
    with open(file_path, 'r') as f:
        assets = json.load(f)
    
    print(f"✅ Loaded {len(assets):,} assets from file")
    
    return assets


def generate_names(group_key: str, metadata: Dict, config: Dict) -> Tuple[str, str]:
    """Derive (application_name, component_name) from a group's key and metadata.

    Naming template is driven by config.component_naming.default_template:
      - application_with_team: '<app>-<team>' when a team is known, else the group key
      - application_only:      '<app>-Component'
    A configured prefix/suffix is applied to the component name in all cases.
    """
    primary_value = metadata.get('primary_value', group_key)
    secondary_value = metadata.get('secondary_value')

    app_name = str(primary_value).replace(' ', '-').replace('_', '-')[:100]

    template = config.get('component_naming', {}).get('default_template', 'application_with_team')
    if template == 'application_with_team' and secondary_value and secondary_value != 'NoTeam':
        component_name = f"{app_name}-{secondary_value}".replace(' ', '-')[:100]
    elif template == 'application_only':
        component_name = f"{app_name}-Component"[:100]
    else:
        component_name = str(group_key).replace('|||', '-')[:100]

    prefix = config.get('component_naming', {}).get('prefix', '')
    suffix = config.get('component_naming', {}).get('suffix', '')
    return app_name, f"{prefix}{component_name}{suffix}"


def create_grouping_plan(groups: Dict, config: Dict,
                         primary_tag: Optional[str], secondary_tag: Optional[str]) -> Dict:
    """Turn raw {group_key: {assets, metadata}} groups into a sized, named execution plan.

    Groups smaller than grouping.min_assets_per_component are dropped. The result is the
    single hand-off contract between grouping (Phase 3) and YAML generation (Phase 3.5),
    and is also what the synthetic regression test feeds to generate_standard_yaml_structure.
    """
    plan = {
        'metadata': {
            'created_at': datetime.now().isoformat(),
            'primary_tag': primary_tag,
            'secondary_tag': secondary_tag,
        },
        'groups': {},
    }

    min_assets = config.get('grouping', {}).get('min_assets_per_component', 2)

    for group_key, group_data in groups.items():
        if isinstance(group_data, dict):
            assets = group_data.get('assets', [])
            metadata = group_data.get('metadata', {})
        else:
            assets = group_data
            metadata = {}

        if len(assets) < min_assets:
            continue

        app_name, component_name = generate_names(group_key, metadata, config)
        plan['groups'][group_key] = {
            'application_name': app_name,
            'component_name': component_name,
            'asset_count': len(assets),
            'assets': assets,
            'metadata': metadata,
        }

    return plan


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
    # Pre-split heterogeneous groups by asset type so routing is correct
    # ========================================================================
    # A single tag-driven group (e.g. Application=Checkout) can legitimately contain
    # mixed asset types (CLOUD + REPOSITORY + WEB). Routing must therefore happen
    # per-type, not per-group. We build sub-groups keyed by (original_group, asset_type)
    # and let the existing DG/EG builders consume them.
    type_split_groups: Dict[str, Dict[str, Any]] = {}
    for group_key, group_data in grouping_plan.get('groups', {}).items():
        assets = group_data.get('assets', []) or []
        if not assets:
            continue

        type_buckets: Dict[str, List[Dict]] = defaultdict(list)
        for asset in assets:
            atype = asset.get('type', 'UNKNOWN')
            type_buckets[atype].append(asset)

        # Single-type group: keep the original key (avoids churn for hand-written
        # checkpoints / tests that depend on stable group names).
        if len(type_buckets) == 1:
            atype = next(iter(type_buckets))
            split = dict(group_data)
            split['asset_type'] = atype
            split['assets'] = type_buckets[atype]
            type_split_groups[group_key] = split
            continue

        # Multi-type group: emit one sub-group per type.
        base_app = group_data.get('application_name', 'Ungrouped')
        base_comp = group_data.get('component_name', base_app)
        for atype, items in type_buckets.items():
            split_key = f"{group_key}|||{atype}"
            split = dict(group_data)
            split['asset_type'] = atype
            split['assets'] = items
            split['component_name'] = f"{base_comp}-{atype.lower()}"[:100]
            split['application_name'] = base_app
            type_split_groups[split_key] = split

    # ========================================================================
    # DEPLOYMENT GROUPS (Applications / Components)
    # ========================================================================
    deployment_groups = []

    components_by_app = defaultdict(list)

    for group_key, group_data in type_split_groups.items():
        asset_type = group_data.get('asset_type', 'UNKNOWN')

        if asset_type in deployment_types:
            app_name = group_data.get('application_name', group_data.get('component_name', 'Ungrouped'))

            # Flatten metadata to top level for rule generation (kept for back-compat
            # with downstream consumers that read these keys directly).
            metadata = group_data.get('metadata', {})
            for key, value in metadata.items():
                if key not in group_data:
                    group_data[key] = value

            components_by_app[app_name].append(group_data)
    
    # Build DeploymentGroups (full core-structure schema field set)
    for app_name, components in components_by_app.items():
        # Aggregate every asset under this application so App-level fields can be derived from the
        # union of tags across all components.
        app_assets: List[Dict] = []
        for comp in components:
            app_assets.extend(comp.get('assets', []) or [])

        app_status = _derive_status(app_assets, default_status)
        app_tier = _derive_app_tier(app_assets, default_tier)
        app_deployment_set = _slugify(app_name)

        app_group = {
            'AppName': app_name,
            'BU': _derive_bu(app_assets, app_name, config),
            'Status': app_status,
            'ReleaseDefinitions': [],
            'Responsable': default_responsable,
            'Tier': app_tier,
            'Tags_label': _derive_tags_label_app(app_name),
            'Tag_label': [],
            'Deployment_set': app_deployment_set,
        }

        if default_domain:
            app_group['Domain'] = default_domain
        if default_subdomain:
            app_group['SubDomain'] = default_subdomain
        if include_appid:
            app_group['AppID'] = ''  # Leave empty for Phoenix to generate

        app_components = []
        for comp in components:
            comp_assets = comp.get('assets', []) or []
            comp_status = _derive_status(comp_assets, app_status)
            comp_tier = _derive_app_tier(comp_assets, app_tier)
            comp_deployment_set = _slugify(
                comp.get('secondary_value')
                or comp.get('component_name', '')
            ) or app_deployment_set
            comp_domain = _derive_domain(app_name, comp_status) or app_deployment_set

            component = {
                'ComponentName': comp.get('component_name', 'Unknown'),
                'Status': comp_status,
                'Type': _derive_component_type(comp.get('asset_type', '')),
                'Tier': comp_tier,
                'Domain': comp_domain,
                'SubDomain': comp_domain,
                'TeamNames': [],
            }

            if comp.get('team'):
                component['TeamNames'] = [comp['team']]
            elif comp.get('secondary_value') and comp.get('secondary_value') != 'NoTeam':
                component['TeamNames'] = [comp['secondary_value']]

            component['Deployment_set'] = comp_deployment_set
            component['Tags_label'] = _derive_tags_label_component(comp_assets, config)

            rule = _generate_multi_condition_rule(comp, config)
            if rule:
                component['MULTI_MultiConditionRules'] = [rule]

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

    for group_key, group_data in type_split_groups.items():
        asset_type = group_data.get('asset_type', 'UNKNOWN')

        if asset_type in environment_types:
            env_config = environment_types[asset_type]
            env_type = env_config.get('environment_type', 'CLOUD')
            env_subtype = env_config.get('environment_subtype', 'CLOUD')

            env_name = group_data.get('environment', group_data.get('application_name', f"{asset_type}-Environment"))

            group_data['_env_type'] = env_type
            group_data['_env_subtype'] = env_subtype
            group_data['service_name'] = group_data.get('component_name', 'Unknown-Service')
            metadata = group_data.get('metadata', {})
            for key, value in metadata.items():
                if key not in group_data:
                    group_data[key] = value

            services_by_env[env_name].append(group_data)
    
    # Build EnvironmentGroups (full core-structure schema field set)
    for env_name, services in services_by_env.items():
        env_type = services[0].get('_env_type', 'CLOUD')
        env_assets: List[Dict] = []
        for svc in services:
            env_assets.extend(svc.get('assets', []) or [])

        env_status = _derive_status(env_assets, default_status)
        env_tier = _derive_app_tier(env_assets, default_tier)
        env_deployment_set = _slugify(env_name)

        env_group = {
            'Name': env_name,
            'Type': env_type,
            'Status': env_status,
            'Responsable': default_responsable,
            'Tier': env_tier,
            'Tags_label': _derive_tags_label_app(env_name),
            'Tag_label': [],
            'Deployment_set': env_deployment_set,
        }

        env_services = []
        for svc in services:
            svc_assets = svc.get('assets', []) or []
            svc_status = _derive_status(svc_assets, env_status)
            svc_tier = _derive_app_tier(svc_assets, env_tier)
            svc_deployment_set = _slugify(
                svc.get('secondary_value')
                or svc.get('service_name', '')
            ) or env_deployment_set
            svc_domain = _derive_domain(env_name, svc_status) or env_deployment_set

            service = {
                'Service': svc.get('service_name', 'Unknown'),
                'Type': svc.get('_env_subtype', 'CLOUD'),
                'Status': svc_status,
                'Tier': svc_tier,
                'Domain': svc_domain,
                'SubDomain': svc_domain,
            }

            if svc.get('team'):
                service['TeamName'] = svc['team']
            elif svc.get('secondary_value') and svc.get('secondary_value') != 'NoTeam':
                service['TeamName'] = svc['secondary_value']

            service['Deployment_set'] = svc_deployment_set
            service['Tags_label'] = _derive_tags_label_component(svc_assets, config)

            rule = _generate_multi_condition_rule(svc, config)
            if rule:
                service['MULTI_MultiConditionRules'] = [rule]

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


def _slugify(value: str) -> str:
    """Lowercase, replace whitespace/underscores with hyphens, strip non-alphanumeric."""
    if not value:
        return ''
    value = str(value).strip().lower().replace(' ', '-').replace('_', '-')
    value = re.sub(r'[^a-z0-9\-]', '', value)
    value = re.sub(r'-+', '-', value).strip('-')
    return value


def _collect_tag_values(assets: List[Dict], tag_keys: List[str]) -> List[str]:
    """Return de-duplicated tag values present for any of the given keys across the group."""
    values: List[str] = []
    seen: Set[str] = set()
    for asset in assets:
        tags = asset.get('tags') or []
        for tag in tags:
            if not isinstance(tag, dict):
                continue
            if tag.get('key') in tag_keys:
                v = tag.get('value')
                if v and v not in seen:
                    seen.add(v)
                    values.append(v)
    return values


def _tag_keys_for(config: Dict, concept: str, fallback: List[str]) -> List[str]:
    """Resolve the list of asset-tag keys mapped to a semantic concept (application, team, costcenter, environment)."""
    mappings = config.get('tag_mapping', {}).get('mappings', {})
    mapped = mappings.get(concept)
    if mapped:
        return mapped
    return fallback


def _derive_bu(assets: List[Dict], app_name: str, config: Dict) -> str:
    """Build the App-level BU field.

    Format follows the standard core-structure schema: '<primary>' on its own,
    or '<primary>, <suffix>' when defaults.bu_suffix is configured.
    """
    bu_keys = _tag_keys_for(config, 'costcenter', ['CostCenter', 'BU', 'business_unit', 'Department'])
    bu_values = _collect_tag_values(assets, bu_keys)
    primary = bu_values[0] if bu_values else app_name
    bu_suffix = config.get('yaml_generation', {}).get('defaults', {}).get('bu_suffix', '')
    if bu_suffix and bu_suffix.lower() != primary.lower():
        return f"{primary}, {bu_suffix}"
    return primary


def _derive_status(assets: List[Dict], default: str) -> str:
    """Pick a Status from tags (Status / status / lifecycle / Environment) before falling back to default."""
    for key_set in (['Status', 'status', 'lifecycle'], ['Environment', 'environment', 'env']):
        vals = _collect_tag_values(assets, key_set)
        if vals:
            return vals[0]
    return default


def _derive_tags_label_app(app_name: str) -> List[str]:
    """App-level Tags_label: [<AppName>] - standard core-structure convention."""
    return [app_name] if app_name else []


def _derive_tags_label_component(assets: List[Dict], config: Dict) -> List[str]:
    """Component-level Tags_label: ['Environment: <env>', 'ComponentType: <type>', 'productowner:<name>']."""
    labels: List[str] = []
    env_keys = _tag_keys_for(config, 'environment', ['Environment', 'environment', 'env', 'Name'])
    env_values = _collect_tag_values(assets, env_keys)
    if env_values:
        labels.append(f"Environment: {env_values[0]}")

    ct_values = _collect_tag_values(assets, ['ComponentType', 'componenttype', 'component_type'])
    if ct_values:
        labels.append(f"ComponentType: {ct_values[0]}")

    po_values = _collect_tag_values(assets, ['productowner', 'ProductOwner', 'product_owner', 'owner'])
    if po_values:
        labels.append(f"productowner:{po_values[0]}")

    return labels


def _derive_domain(app_name: str, status: str) -> str:
    """Build Domain as '<slug(app)>-<status-shortname>' (e.g. 'checkout-prod').

    Falls back to just '<slug(app)>' when status is empty or unknown. Status
    shortnames come from _STATUS_SHORTNAMES.
    """
    slug = _slugify(app_name)
    if not slug:
        return ''
    if not status:
        return slug
    short = _STATUS_SHORTNAMES.get(status, _slugify(status))
    return f"{slug}-{short}" if short else slug


def _derive_app_tier(assets: List[Dict], default: int) -> int:
    """Tier from a Tier/criticality tag if present, else default."""
    vals = _collect_tag_values(assets, ['Tier', 'tier', 'Criticality', 'criticality'])
    if vals:
        try:
            return int(vals[0])
        except (TypeError, ValueError):
            pass
    return default


def _derive_component_type(asset_type: str) -> str:
    """Map raw asset type to the component Type field expected by core-structure YAML."""
    if asset_type in {'REPOSITORY', 'SOURCE_CODE', 'BUILD', 'FOSS', 'SAST'}:
        return 'BUILD'
    if asset_type in {'WEB', 'WEBSITE_API'}:
        return 'Release'
    return asset_type or 'Release'


def export_to_yaml(data: Any, output_path: str):
    """Export data to YAML file"""
    with open(output_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    print(f"✅ Exported to: {output_path}")

