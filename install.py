#!/usr/bin/env python3
"""Install the ntfy notification hooks into Claude Code.

Run it straight from GitHub:

    curl -fsSL https://raw.githubusercontent.com/pleomax00/claude-speaks/main/install.py | python3 -

The topic is asked for interactively. To stay non-interactive, pass it in:

    curl -fsSL .../install.py | CLAUDE_NTFY_TOPIC=my_topic python3 -

Leave the topic blank at the prompt and a random one is generated for you.
Re-running is safe: the hooks are replaced rather than duplicated.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import secrets
import shutil
import string
import sys
import urllib.request

RAW_BASE = os.environ.get(
    "CLAUDE_NTFY_SOURCE",
    "https://raw.githubusercontent.com/pleomax00/claude-speaks/main",
)

CLAUDE_DIR = os.path.expanduser("~/.claude")
HOOKS_DIR = os.path.join(CLAUDE_DIR, "hooks")
SCRIPT_PATH = os.path.join(HOOKS_DIR, "ntfy_notify.py")
SETTINGS_PATH = os.path.join(CLAUDE_DIR, "settings.json")

INPUT_MESSAGE = "Claude is waiting for your input"
STOP_MESSAGE = "Prompt has finished execution"

# agent_needs_input fires when Claude actually wants an answer. The similar
# idle_prompt fires on a 60s idle timer instead, which announces every turn
# you walk away from whether or not anything is waiting on you.
INPUT_MATCHER = "agent_needs_input"


def generate_topic() -> str:
    alphabet = string.ascii_letters + string.digits
    return "claude_alerts_" + "".join(secrets.choice(alphabet) for _ in range(16))


def ask(prompt: str) -> str:
    """Prompt the user even when stdin is the piped-in installer itself."""
    try:
        with open("/dev/tty", "r+") as tty:
            tty.write(prompt)
            tty.flush()
            return tty.readline().strip()
    except OSError:
        return ""


def resolve_topic(explicit: str | None) -> str:
    for candidate in (explicit, os.environ.get("CLAUDE_NTFY_TOPIC")):
        if candidate:
            return candidate.strip()

    answer = ask("ntfy topic (blank generates a random one): ")
    if answer:
        return answer

    topic = generate_topic()
    print(f"Generated a random topic: {topic}")
    return topic


def read_notify_source() -> bytes:
    """Prefer a checked-out copy, fall back to the published one."""
    # __file__ is the literal "<stdin>" when piped in, which would otherwise
    # resolve against the caller's cwd and pick up an unrelated notify.py.
    script = globals().get("__file__", "")
    here = os.path.dirname(os.path.abspath(script)) if os.path.isfile(script) else ""
    local = os.path.join(here, "notify.py") if here else ""
    if local and os.path.isfile(local):
        print(f"Using local {local}")
        with open(local, "rb") as handle:
            return handle.read()

    url = f"{RAW_BASE}/notify.py"
    print(f"Downloading {url}")
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read()


def load_settings() -> dict:
    if not os.path.isfile(SETTINGS_PATH):
        return {}
    with open(SETTINGS_PATH, encoding="utf-8") as handle:
        text = handle.read().strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except ValueError as exc:
        sys.exit(
            f"{SETTINGS_PATH} is not valid JSON ({exc}). Fix it before installing, "
            "otherwise every setting in that file is already being ignored."
        )


def backup_settings() -> str | None:
    if not os.path.isfile(SETTINGS_PATH):
        return None
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = f"{SETTINGS_PATH}.bak-{stamp}"
    shutil.copy2(SETTINGS_PATH, destination)
    return destination


def is_our_group(group: dict) -> bool:
    """True if this hook group was written by a past run of this installer.

    Matched on the exact path this installer writes, never on a looser name
    like "notify.py" -- an unrelated hook that happens to share a basename
    must not be silently deleted.
    """
    for hook in group.get("hooks", []):
        if SCRIPT_PATH in (hook.get("args") or []):
            return True
        if hook.get("command") == SCRIPT_PATH:
            return True
    return False


def strip_our_hooks(settings: dict) -> int:
    removed = 0
    hooks = settings.get("hooks", {})
    for event in ("Notification", "Stop"):
        groups = hooks.get(event)
        if not isinstance(groups, list):
            continue
        kept = [g for g in groups if not is_our_group(g)]
        removed += len(groups) - len(kept)
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)
    return removed


def make_group(message: str, matcher: str | None) -> dict:
    hook = {
        "type": "command",
        "command": "/usr/bin/env",
        "args": ["python3", SCRIPT_PATH, message],
        "async": True,
    }
    group: dict = {"hooks": [hook]}
    if matcher:
        group["matcher"] = matcher
    return group


def install(topic: str) -> None:
    source = read_notify_source()

    os.makedirs(HOOKS_DIR, exist_ok=True)
    with open(SCRIPT_PATH, "wb") as handle:
        handle.write(source)
    os.chmod(SCRIPT_PATH, 0o755)
    print(f"Installed {SCRIPT_PATH}")

    settings = load_settings()
    backup = backup_settings()

    replaced = strip_our_hooks(settings)
    if replaced:
        print(f"Replaced {replaced} hook(s) from a previous install")

    settings.setdefault("env", {})["CLAUDE_NTFY_TOPIC"] = topic
    hooks = settings.setdefault("hooks", {})
    hooks.setdefault("Notification", []).append(make_group(INPUT_MESSAGE, INPUT_MATCHER))
    hooks.setdefault("Stop", []).append(make_group(STOP_MESSAGE, None))

    with open(SETTINGS_PATH, "w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2)
        handle.write("\n")

    print(f"Updated {SETTINGS_PATH}" + (f" (backup: {backup})" if backup else ""))
    print()
    print("Topic:", topic)
    print("Subscribe to that topic in the ntfy iOS app, then restart Claude Code.")


def uninstall() -> None:
    settings = load_settings()
    backup = backup_settings()

    removed = strip_our_hooks(settings)
    settings.get("env", {}).pop("CLAUDE_NTFY_TOPIC", None)
    if settings.get("env") == {}:
        settings.pop("env")

    with open(SETTINGS_PATH, "w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2)
        handle.write("\n")

    if os.path.isfile(SCRIPT_PATH):
        os.remove(SCRIPT_PATH)

    print(f"Removed {removed} hook(s) and {SCRIPT_PATH}")
    if backup:
        print(f"Backup: {backup}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install ntfy hooks for Claude Code.")
    parser.add_argument("--topic", help="ntfy topic to publish to")
    parser.add_argument("--uninstall", action="store_true", help="remove the hooks")
    args = parser.parse_args()

    if args.uninstall:
        uninstall()
    else:
        install(resolve_topic(args.topic))
    return 0


if __name__ == "__main__":
    sys.exit(main())
