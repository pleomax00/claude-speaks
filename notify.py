#!/usr/bin/env python3
"""Publish a Claude Code lifecycle event to ntfy so a nearby iPhone announces it.

Invoked two ways:

  * By hand, to test the phone end of the pipeline:
        CLAUDE_NTFY_TOPIC=your_topic python3 notify.py "hello from the terminal"

  * By a Claude Code hook, which pipes the event JSON in on stdin. The JSON is
    drained and ignored; the message comes from argv so each hook can say
    something different.

Only the standard library is used, so there is nothing to install and nothing
that can go stale between Python upgrades.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import threading
import urllib.error
import urllib.request

TOPIC = os.environ.get("CLAUDE_NTFY_TOPIC", "")
SERVER = os.environ.get("CLAUDE_NTFY_SERVER", "https://ntfy.sh").rstrip("/")

# Siri reads the title before the body, so keep the title to one short word.
# The server stores no title when the header is omitted, but the iOS client may
# then display the topic name -- which Siri would read out in full.
TITLE = os.environ.get("CLAUDE_NTFY_TITLE", "Claude")

TIMEOUT_SECONDS = 5.0
STDIN_TIMEOUT_SECONDS = 2.0

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notify.log")


def log(event: str, session: str, message: str) -> None:
    """Append one audit line. Best effort -- logging must never break a hook."""
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(f"{stamp}\t{event}\t{session}\t{message}\n")
    except OSError:
        pass


def read_stdin_with_timeout(seconds: float = STDIN_TIMEOUT_SECONDS):
    """Return stdin's contents, or None if nothing arrives in time.

    A hook harness closes stdin as soon as it has written the event JSON. Any
    other caller might leave the pipe open forever, so never block on it.
    """
    box = []

    def collect() -> None:
        try:
            box.append(sys.stdin.read())
        except (OSError, ValueError):
            pass

    reader = threading.Thread(target=collect, daemon=True)
    reader.start()
    reader.join(seconds)
    return box[0] if box else None


def publish(message: str, title: str = TITLE, priority: str = "default") -> None:
    """POST one message to the topic. Raises on any transport or HTTP error."""
    request = urllib.request.Request(
        f"{SERVER}/{TOPIC}",
        data=message.encode("utf-8"),
        headers={"Title": title, "Priority": priority},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        response.read()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("message", help="text spoken by the phone")
    parser.add_argument("--title", default=TITLE)
    parser.add_argument(
        "--priority",
        default="default",
        choices=["min", "low", "default", "high", "urgent"],
    )
    args = parser.parse_args()

    # Hooks pipe their event JSON in. Read it so the writer never sees EPIPE,
    # and so the log can attribute each send to a real event and session.
    event, session = "manual", "-"
    if not sys.stdin.isatty():
        raw = read_stdin_with_timeout()
        if raw is None:
            event = "no-stdin"
        else:
            try:
                payload = json.loads(raw or "{}")
                event = payload.get("hook_event_name", "unknown")
                session = str(payload.get("session_id", "-"))[:8]
            except ValueError:
                event = "unparsed"

    log(event, session, args.message)

    if not TOPIC:
        print(
            "CLAUDE_NTFY_TOPIC is not set. Export it, or add it to the env block "
            "of ~/.claude/settings.json.",
            file=sys.stderr,
        )
        return 1

    try:
        publish(args.message, title=args.title, priority=args.priority)
    except urllib.error.HTTPError as exc:
        print(f"ntfy rejected the message: HTTP {exc.code} {exc.reason}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, OSError) as exc:
        print(f"could not reach {SERVER}: {exc}", file=sys.stderr)
        return 1

    print(f"sent to {SERVER}/{TOPIC}: {args.message}")
    return 0


if __name__ == "__main__":
    # Never exit 2 -- Claude Code reads that as "block the turn".
    sys.exit(main())
