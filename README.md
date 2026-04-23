# Skribo - Microsoft 365 Administration

This repository contains a Skribo plugin for Microsoft 365 administration tasks.

The current implementation focuses on Microsoft Teams creation and related Microsoft Graph authentication.

## Project Structure

```text
m365-teams-creation/
├── config.json
└── scripts/
    └── teams-creation/
        ├── auth.py
        ├── cmd.py
        └── manifest.json
```

## Plugin Metadata (`config.json`)

Top-level plugin metadata:

```json
{
  "name": "Microsoft 365 Administration",
  "author": "Tenant365",
  "version": "0.0.1"
}
```

## Included Script (`scripts/teams-creation`)

The script metadata is defined in `scripts/teams-creation/manifest.json`.

Current configuration:

- `name`: `Microsoft 365 Teams Creation`
- `description`: creates a new Microsoft 365 Team using Microsoft Graph API
- `params`:
  - `team_name` (Team Name)
- `output`:
  - `team_id`
  - `team_name`

## Authentication

Authentication is implemented in `scripts/teams-creation/auth.py` using OAuth2 Authorization Code Flow with PKCE.

Key details:

- Uses Microsoft identity platform (`organizations` tenant)
- Opens a browser for interactive login
- Uses a localhost callback (`http://localhost:8765/callback`)
- Stores the access token in secure local storage (`keyring` on macOS/Windows)
- Reuses existing token when available

## Script Runtime (`cmd.py`)

The script entrypoint is:

```python
def run(app, script, params: dict[str, str]) -> dict[str, str]:
    ...
```

Behavior:

- validates or refreshes authentication state
- calls Microsoft Graph `/me` to verify access
- returns structured output for Skribo

## Usage in Skribo

1. Install or copy this plugin folder to your Skribo plugins directory.
2. Ensure Python dependencies are installed (for example `keyring` where required).
3. Open Skribo Workspace.
4. Select the `Microsoft 365 Teams Creation` script.
5. Fill in required parameters (for example `Team Name`).
6. Run the script (`Shift+Enter`).
7. Complete browser sign-in when prompted.

## Notes

- Keep script and metadata fields in English.
- Keep script folder names stable to avoid mapping issues.
- Extend this plugin by adding more scripts under `scripts/` for additional Microsoft 365 administration tasks.
