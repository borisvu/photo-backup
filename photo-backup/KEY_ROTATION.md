# 🔑 Wasabi Key Rotation Guide

How to rotate the Wasabi S3 access key/secret used by the backup service —
because a key was exposed, on a schedule, or when offboarding a machine.

Rotation is **zero-downtime**: Wasabi lets the old and new key pair coexist, so
you create the new key, switch the app over, verify, and only then delete the
old one.

---

## Where the credentials live

This install does **not** use 1Password (the `access_key`/`secret_key` fields in
`config.yaml` are `null`). The real credentials are stored in **two** places on
the machine, and both must be updated during rotation:

| Location | Field(s) | Role |
|---|---|---|
| `~/Library/LaunchAgents/com.example.photo-backup.plist` | `EnvironmentVariables` → `WASABI_ACCESS_KEY`, `WASABI_SECRET_KEY` | **Primary.** The launchd service reads these env vars and generates a temporary rclone config from them on every run. |
| `~/.config/rclone/rclone.conf` | `[wasabi-photo]` → `access_key_id`, `secret_access_key` | Standing rclone remote, used for manual `rclone`/`photo-backup test-auth` commands. |

> The temporary rclone config you may see in `/var/folders/.../tmp*.conf` (remote
> named `test`) is **generated at runtime** from the env vars above — never edit
> it; it is recreated each run.

> Names are specific to this machine (`com.example.photo-backup`, `wasabi-photo`).
> On another install, list services with `launchctl list | grep photo` and remotes
> with `rclone listremotes`.

---

## Step 1 — Create a new key in the Wasabi console

1. Sign in at **https://console.wasabisys.com**.
2. Open **Access Keys** (top-right profile menu for the root account, or under the
   sub-user in **IAM → Users → <user> → Access Keys** if you use IAM users).
3. Click **Create New Access Key** and copy both the new **Access Key ID** and
   **Secret Key**. The secret is shown **only once** — copy it now.
4. Leave the old key active for the moment.

## Step 2 — Update the two local files

Edit both files and replace the key/secret. Keep the new secret out of shell
history and out of any chat — edit the files directly.

**`~/Library/LaunchAgents/com.example.photo-backup.plist`** — update:

```xml
<key>WASABI_ACCESS_KEY</key>
<string>NEW_ACCESS_KEY_ID</string>
<key>WASABI_SECRET_KEY</key>
<string>NEW_SECRET_KEY</string>
```

**`~/.config/rclone/rclone.conf`** — under `[wasabi-photo]`:

```ini
access_key_id = NEW_ACCESS_KEY_ID
secret_access_key = NEW_SECRET_KEY
```

## Step 3 — Reload the service

The launchd service caches env vars for the life of the process, so it must be
restarted to pick up the new key:

```bash
launchctl kickstart -k gui/$(id -u)/com.example.photo-backup
```

## Step 4 — Verify the new key works

```bash
photo-backup test-auth
# or list the bucket directly:
rclone lsd wasabi-photo:my-photo-backup-bucket
photo-backup status            # 🔐 Credentials should show ✅ Available
```

## Step 5 — Delete the old key

Only after Step 4 succeeds, return to the Wasabi console → **Access Keys** and
**delete (or disable) the old key**. Deleting immediately invalidates it, so
confirm the new key is live first.

---

## Rollback

If `test-auth` fails after switching, the old key is still valid until you delete
it — restore the previous values in both files and re-run
`launchctl kickstart -k gui/$(id -u)/com.example.photo-backup`.

## Rotation checklist

- [ ] New key pair created in Wasabi console
- [ ] `com.example.photo-backup.plist` env vars updated
- [ ] `rclone.conf` `[wasabi-photo]` updated
- [ ] Service reloaded (`launchctl kickstart -k …`)
- [ ] `photo-backup test-auth` passes
- [ ] Old key deleted/disabled in Wasabi console
