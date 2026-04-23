# Skribo - Microsoft 365 Teams Creation

This folder is a ready-to-copy starter template for Skribo plugins.

You can move this folder into your plugin directory (for example `~/.t365/skribo/plugins/`) and then customize it.

## Folder Structure

```text
starter-template/
├── config.json
└── scripts/
    ├── hello-world/
    │   ├── manifest.json
    │   └── cmd.py
    ├── hello-shell/
    │   ├── manifest.json
    │   └── cmd.sh
    └── hello-pwsh/
        ├── manifest.json
        └── cmd.ps1
```

---

## Plugin Metadata (`config.json`)

Each plugin must have a top-level `config.json`.

Example:

```json
{
  "name": "starter-plugin-template",
  "author": "Tenant365",
  "version": "0.0.1"
}
```

---

## Script Metadata (`scripts/<script>/manifest.json`)

Each script must have its own `manifest.json`.

Important fields:

- `name`: script display name
- `description`: short explanation
- `version`: script version
- `params`: UI form fields shown in Workspace
- `output`: output keys for structured output scripts

---

## Supported Entrypoints

In each script folder, Skribo resolves entrypoints in this order:

1. `cmd.py`
2. `cmd.sh`
3. `cmd.ps1`

### Runtime visibility rules

- `cmd.py`: always supported
- `cmd.sh`: shown on Linux/macOS
- `cmd.ps1`: shown on Windows, and on Linux/macOS only if `pwsh` is installed

---

## Parameter Passing

For `cmd.py`:

- Skribo calls `run(app, script, params)`
- `params` is a Python dictionary

For `cmd.sh` / `cmd.ps1`, Skribo passes params via:

- `SKRIBO_PARAMS_JSON` (JSON string)
- `SKRIBO_PARAM_<KEY>` (env vars)
- CLI args:
  - `--skribo-params-json <json>`
  - `--<param-name> <value>`

---

## Python Script Contract (`cmd.py`)

Expected function signature:

```python
def run(app, script, params: dict[str, str]) -> dict:
    ...
```

Return:

- A dictionary for structured output (displayed in output popup table)

---

## Console Script Output (`cmd.sh` / `cmd.ps1`)

Console stdout/stderr is captured and shown as console output popup.

Use normal print/write commands:

- Bash: `echo`
- PowerShell: `Write-Output`

---

## Developer Workflow

1. Copy/rename this template folder.
2. Update `config.json`.
3. Create or rename scripts under `scripts/`.
4. Define `manifest.json` and script entrypoint.
5. Install plugin in Skribo Plugin Manager.
6. Enable script if needed.
7. Select script in workspace and run with `Shift+Enter`.

---

## Notes

- Keep all plugin source in English.
- Keep script names stable to avoid config mapping issues.
- Prefer explicit parameter defaults in `manifest.json`.
