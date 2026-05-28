# Autogroup examples

Self-contained inputs you can use to exercise the autogroup pipeline
end-to-end without touching a real Phoenix tenant or providing credentials.

## Files

| File | Purpose |
|---|---|
| `synthetic-assets.json` | 16 assets spanning every type the engine handles (CLOUD, CONTAINER, INFRA, REPOSITORY, WEB, WEBSITE_API). Some are fully tagged, some intentionally partial so the fallback strategies get exercised - including one untagged REPOSITORY (`legacy-reporting-tool`) that forces a teamless DeploymentGroup component (`TeamNames: []`), the regression case behind the schema-parity test. |
| `autogroup-config.example.yaml` | A minimal config that consumes the fixture above and writes outputs into `autogroup-output/<timestamp>/`. |

## Full terminal log (optional)

To capture the entire `run-phx.py` session to `autogroup-output/run-logs/` (same pattern as batch-upload `tee`):

```bash
./autogroup-output/run-autogroup.sh \
  --action_autogroup true \
  --autogroup_mode batch \
  --autogroup_config autogroup-output/examples/autogroup-config.example.yaml \
  --autogroup_asset_source file \
  --autogroup_asset_file autogroup-output/examples/synthetic-assets.json
```

Each run folder also gets `terminal.log` (autogroup phases only) when `output.capture_terminal_log` is true.

## Reproduce the example run

```bash
python run-phx.py \
  --action_autogroup true \
  --autogroup_mode batch \
  --autogroup_config autogroup-output/examples/autogroup-config.example.yaml \
  --autogroup_asset_source file \
  --autogroup_asset_file autogroup-output/examples/synthetic-assets.json
```

No `--client_id` / `--client_secret` needed for file-mode generate-only runs.

## What you get

A new `autogroup-output/<YYYYMMDD_HHMMSS>/` folder containing:

- `core-structure-*.yaml` - the schema-shaped YAML the upload pipeline ingests
- `grouping-plan-*.yaml` - intermediate plan (audit / debug)
- `tag-analysis-*.json` - tag coverage report from Phase 1B
- `execution-report-*.json` - phase timings and counts
- `autogroup.log` - JSON-lines audit trail (one `phase_complete` per phase)
- `checkpoints/` - resume points for incremental runs

Open `core-structure-*.yaml` to inspect the emitted YAML schema; it's
the canonical reference for what autogroup will produce on real inventory.
