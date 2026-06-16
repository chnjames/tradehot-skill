# Examples

This directory contains stable fixtures and sample reports for the `tradehot` Skill. Generated local outputs are intentionally ignored by Git.

## Included Files

| File | Purpose |
| --- | --- |
| `daily_report_example.md` | Example daily foreign trade HOT report |
| `tiktok_shop_example.md` | Example platform report for TikTok Shop |
| `hs_code_9403_example.md` | Example HS Code opportunity report |
| `external_items_sample.json` | External item input sample |
| `rss_feed_sample.xml` | Local RSS fixture used by tests and pipeline demos |

## Regenerate Local Outputs

From the repository root:

```powershell
python scripts\run_pipeline.py `
  --type daily `
  --config sources\rss_sources.json `
  --items-output examples\generated_rss_batch_items.json `
  --report-output examples\generated_rss_daily_report.md
```

Generated files such as `generated_*.md`, `generated_*.json`, `pipeline_*.md`, and `pipeline_*.json` are ignored by Git so the public repository stays focused on stable examples.
