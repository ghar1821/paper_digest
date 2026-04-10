# Scheduling paper_digest with launchd on macOS

`launchd` is macOS's native job scheduler. Unlike `cron`, it runs as your full user session (no Full Disk Access issues) and will run a missed job when the Mac wakes from sleep.

## 1. Make the script executable

```bash
chmod +x ~/Documents/GitHub/paper_digest/run_digest.sh
```

## 2. Create the LaunchAgent plist

LaunchAgents live in `~/Library/LaunchAgents/`. Create the file:

```bash
nano ~/Library/LaunchAgents/com.putri.paper-digest.plist
```

Paste the following (the schedule below is every Friday at 10:30):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.putri.paper-digest</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/putri.g/projects/paper_digest/run_digest.sh</string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>5</integer>
        <key>Hour</key>
        <integer>10</integer>
        <key>Minute</key>
        <integer>30</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/putri.g/projects/paper_digest/output/logs/launchd-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/putri.g/projects/paper_digest/output/logs/launchd-stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>/Users/putri.g</string>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
```

`StartCalendarInterval` weekday values: 1 = Monday, 5 = Friday, 7 = Sunday.

## 3. Load the agent

```bash
launchctl load ~/Library/LaunchAgents/com.putri.paper-digest.plist
launchctl start com.putri.paper-digest
```

This registers the job, persists across reboots, and runs it immediately so you can confirm it works.

## 4. Verify it is loaded

```bash
launchctl list | grep paper-digest
```

You should see a line like:

```
-    0    com.putri.paper-digest
```

The second column is the last exit code. `0` means success (or not yet run). A non-zero value means the last run failed — check the logs.

## 5. Applying changes to the plist

**Any time you edit the plist, you must unload, reload, and restart for the changes to take effect:**

```bash
launchctl unload ~/Library/LaunchAgents/com.putri.paper-digest.plist
launchctl load ~/Library/LaunchAgents/com.putri.paper-digest.plist
```

Use start to immediately run the script and test that it runs correctly:

```bash
launchctl start com.putri.paper-digest
```

Then tail the log to confirm it ran correctly:

```bash
tail -f ~/projects/paper_digest/output/logs/digest-$(date +%Y-%m-%d).log
```

> **Note:** Editing the plist file on disk has no effect while the agent is loaded. Always unload first.

## Common commands

| Task | Command |
|------|---------|
| Load / register | `launchctl load ~/Library/LaunchAgents/com.putri.paper-digest.plist` |
| Unload / unregister | `launchctl unload ~/Library/LaunchAgents/com.putri.paper-digest.plist` |
| Apply plist changes | unload → load → start (see step 5) |
| Run now | `launchctl start com.putri.paper-digest` |
| Check status | `launchctl list \| grep paper-digest` |

## Troubleshooting

- **Job not appearing in `launchctl list`** — the plist has a syntax error. Validate it with `plutil ~/Library/LaunchAgents/com.putri.paper-digest.plist`.
- **Non-zero exit code in `launchctl list`** — check `~/projects/paper_digest/output/logs/launchd-stderr.log` for the error.
- **Ollama not starting** — confirm `ollama` is on the PATH set in the plist by running `/usr/local/bin/ollama --version`. Adjust the `PATH` value in the plist if it is installed elsewhere (`which ollama` will tell you).
- **Job skipped while Mac was asleep** — launchd will run the job the next time the Mac is awake and the scheduled time arrives. This is expected behaviour.
