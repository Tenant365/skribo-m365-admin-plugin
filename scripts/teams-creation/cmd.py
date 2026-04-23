from __future__ import annotations

import json
import urllib.error
import urllib.request

from auth import (
    AuthError,
    authenticate_with_microsoft_common,
    delete_access_token,
    load_access_token,
)


def __fetch_me(access_token: str) -> dict[str, str]:
    request = urllib.request.Request(
        "https://graph.microsoft.com/v1.0/me",
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))

def __fetch_teams(access_token: str) -> dict[str, str]:
    request = urllib.request.Request(
        "https://graph.microsoft.com/v1.0/me/joinedTeams",
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))

def __check_if_team_exists(team_name: str, access_token: str) -> bool:
    teams = __fetch_teams(access_token)
    return any(team["displayName"] == team_name for team in teams["value"])

def __create_team(team_name: str, access_token: str, user_id: str) -> dict[str, str]:
    payload = {
        "template@odata.bind": "https://graph.microsoft.com/v1.0/teamsTemplates('standard')",
        "displayName": team_name,
        "description": "Team",
        "visibility": "private",
        "members": [
            {
                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                "roles": ["owner"],
                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{user_id}')",
            }
        ],
    }
    request = urllib.request.Request(
        "https://graph.microsoft.com/v1.0/teams",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
        if not body:
            return {}
        return json.loads(body)

def run(app, script, params: dict[str, str]) -> dict[str, str]:
    is_script_mode = app is None

    try:
        existing_token = load_access_token()
    except Exception as exc:
        message = f"Unable to read saved access token: {exc}"
        if app:
            app.notify(message)
        return {"text": message}

    me_data = None
    access_token = existing_token

    if existing_token:
        if app:
            app.notify("Checking existing access token...")
        try:
            me_data = __fetch_me(existing_token)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                # Stored token is no longer valid/usable for Graph /me.
                try:
                    delete_access_token()
                except Exception:
                    pass
                if app:
                    app.notify("Saved token is invalid. Starting re-authentication...")
            else:
                body = exc.read().decode("utf-8", errors="replace")
                message = f"/me request failed (HTTP {exc.code}): {body}"
                if app:
                    app.notify(message)
                return {"text": message}
        except Exception as exc:
            message = f"/me request failed: {exc}"
            if app:
                app.notify(message)
            return {"text": message}

    if me_data is None:
        if app:
            app.notify("Starting authentication...")
        try:
            auth_result = authenticate_with_microsoft_common(
                show_auth_url=is_script_mode,
                require_browser_confirmation=False,
            )
        except AuthError as exc:
            message = f"Authentication failed: {exc}"
            if app:
                app.notify(message)
            return {"text": message}
        except Exception as exc:
            message = f"Unexpected authentication error: {exc}"
            if app:
                app.notify(message)
            print(message)
            return {"text": message}

        if app:
            app.notify("Authentication successful. Testing Microsoft Graph /me...")
        try:
            access_token = auth_result.access_token
            me_data = __fetch_me(access_token)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            message = f"/me request failed (HTTP {exc.code}): {body}"
            if app:
                app.notify(message)
            return {"text": message}
        except Exception as exc:
            message = f"/me request failed: {exc}"
            if app:
                app.notify(message)
            return {"text": message}
    display_name = me_data.get("displayName") or "Unknown user"
    principal_name = me_data.get("userPrincipalName") or "unknown"
    success_message = f"Authenticated as {display_name} ({principal_name}). /me request successful."
    if app:
        app.notify(success_message)
    print(success_message)

    if access_token is None:
        return {"text": "Missing access token after authentication"}

    try:
        if __check_if_team_exists(params["team_name"], access_token):
            return {"text": "Team already exists"}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        message = f"/me/joinedTeams request failed (HTTP {exc.code}): {body}"
        if app:
            app.notify(message)
        return {"text": message}
    except Exception as exc:
        message = f"/me/joinedTeams request failed: {exc}"
        if app:
            app.notify(message)
        return {"text": message}

    try:
        __create_team(params["team_name"], access_token, me_data["id"])
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        message = f"Team creation failed (HTTP {exc.code}): {body}"
        if app:
            app.notify(message)
        return {"text": message}
    except Exception as exc:
        message = f"Team creation failed: {exc}"
        if app:
            app.notify(message)
        return {"text": message}

    return {"text": "Team created successfully"}

if __name__ == "__main__":
    run(None, None, {})