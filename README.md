# claude-speaks

Make your locked iPhone announce out loud when Claude Code needs you.

Claude Code fires a hook → the hook POSTs to [ntfy](https://ntfy.sh) → the ntfy iOS app
raises a notification → iOS Announce Notifications speaks it. No paid apps, no Shortcuts,
stdlib Python only.

| Event | Spoken |
|---|---|
| `Notification` / `idle_prompt` | "Claude is waiting for your input" |
| `Stop` | "Prompt has finished execution" |

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/pleomax00/claude-speaks/main/install.py | python3 -
```

You'll be asked for a topic. **Press Enter to get a random one** — pick something
unguessable, because ntfy.sh topics are public to anyone who knows the name.

Non-interactive:

```bash
curl -fsSL https://raw.githubusercontent.com/pleomax00/claude-speaks/main/install.py \
  | CLAUDE_NTFY_TOPIC=your_topic python3 -
```

Installs `~/.claude/hooks/ntfy_notify.py` and merges the hooks into
`~/.claude/settings.json` (backed up first, other settings untouched).
Re-running replaces the hooks instead of duplicating them.

**Restart Claude Code** afterwards.

## iPhone setup

1. Install **ntfy** from the App Store.
2. **Add subscription** → your topic → server `ntfy.sh`. Allow notifications.
3. **Settings → Apple Intelligence & Siri → Announce Notifications** → on → enable **ntfy** in the app list.
4. **Settings → Accessibility → Siri → Announce Notifications on Speaker** → on.

Step 4 is the one everyone misses. Without it iOS only speaks through AirPods or CarPlay.

**The screen must be off and the phone locked.** iOS deliberately stays silent while
you're using the phone.

## Test

```bash
CLAUDE_NTFY_TOPIC=your_topic python3 ~/.claude/hooks/ntfy_notify.py "speech test"
```

Silent? Check, in order: screen actually off · Focus mode filtering ntfy · ring/silent
switch · ntfy set to Deliver Quietly under Settings → Notifications.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `CLAUDE_NTFY_TOPIC` | *(required)* | Topic to publish to. Set by the installer in the `env` block of `~/.claude/settings.json`. |
| `CLAUDE_NTFY_SERVER` | `https://ntfy.sh` | Point at your own ntfy server. |
| `CLAUDE_NTFY_TITLE` | `Claude` | Notification title. Siri reads it before the body, so keep it short. |

Every send is logged to `notify.log` next to the script — use it to confirm what fired
and when:

```bash
cut -f2 ~/.claude/hooks/notify.log | sort | uniq -c
```

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/pleomax00/claude-speaks/main/install.py | python3 - --uninstall
```

Removes the hooks and the script, leaves the rest of your settings alone, backs up
`settings.json` first.

## Known limits

- **Siri says "ntfy" first.** iOS has no setting to suppress the app-name prefix on
  third-party announcements. The only real fix is building the open-source ntfy iOS
  client yourself with a different `CFBundleDisplayName`.
- **`Stop` fires every turn**, including after `/clear` and `/compact` — not just after
  long jobs.
- **ntfy.sh topics are public.** Anyone who knows the topic can read *and* publish to it.
  Keep messages content-free; don't put code, paths, or secrets in them.
- `python3` must be on `PATH` for the hooks to run.

## License

[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) — © 2026 [pleomax00](https://github.com/pleomax00).

Share and adapt freely, with attribution; derivative works must carry the same license. Full text in [LICENSE](LICENSE).
