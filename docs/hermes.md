# Hermes Agent Compatibility

`tradehot` is structured as a portable agent Skill and is designed to work in both Codex and Hermes Agent environments.

## Compatibility Summary

| Capability | Status |
| --- | --- |
| `SKILL.md` entrypoint | Supported |
| YAML frontmatter metadata | Supported |
| Slash command style usage | Supported in Hermes as `/tradehot` after installation |
| Helper scripts | Supported through terminal/tool execution |
| Templates and source configs | Supported as local Skill resources |
| Offline report skeletons | Supported |
| Real-time intelligence reports | Requires web/search tools |

## Recommended Hermes Install

Windows PowerShell:

```powershell
$src = "$env:TEMP\tradehot-skill"
if (Test-Path $src) { git -C $src pull } else { git clone https://github.com/chnjames/tradehot-skill.git $src }
New-Item -ItemType Directory -Force "$HOME\.hermes\skills\business\tradehot"
robocopy $src "$HOME\.hermes\skills\business\tradehot" /MIR /XD .git __pycache__ _cache /XF generated_* pipeline_* test_* *.pyc
```

GitHub install, if your Hermes build supports repository installs:

```powershell
hermes skills install chnjames/tradehot-skill
```

## Recommended Toolsets

Minimum:

```text
skills,terminal
```

For current news, policy, logistics, tariff, and platform reports:

```text
skills,terminal,web
```

Example:

```powershell
hermes chat --toolsets skills,terminal,web -q "/tradehot 今天外贸 HOT"
```

## Local Validation

Run from the Skill root:

```powershell
cd scripts
python test_all.py
```

Expected result:

```text
ALL TESTS PASSED
```

## Notes for Hermes Usage

- `scripts/*.py` are written with Python standard library only.
- `sources/*.json` provides source presets, platform lists, markets, RSS sources, and user preferences.
- `templates/*.md` defines the report output structure.
- Generated outputs should remain local and are ignored by `.gitignore`.
- If the runtime cannot access web/search tools, the Skill can still generate report skeletons and process user-provided JSON/RSS inputs.
