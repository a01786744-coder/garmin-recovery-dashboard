# Installing on macOS — getting past Gatekeeper

The Garmin Recovery Dashboard is a small open‑source app. Its Mac build is
**not signed with an Apple Developer certificate and not notarized by Apple**
(that costs $99/year, and this is a personal project). Because of that, macOS's
**Gatekeeper** refuses to open it on the first try — even though the app is
perfectly safe and was built in the open on GitHub.

This guide walks you through opening it anyway. It takes about a minute.

> **Is this safe?** Yes. "Unsigned" and "not notarized" mean *Apple hasn't been
> paid to vouch for the developer* — it does **not** mean the app is dangerous.
> You're choosing to trust an app whose full source and build steps are public.
> The steps below simply tell macOS "I trust this one."

---

## What you'll see

When you double‑click the app the first time, macOS shows one of these:

| Message | Why | Which fix |
|---|---|---|
| *"…can't be opened because Apple cannot check it for malicious software."* | Unsigned / not notarized | **Method A** or **B** |
| *"…is damaged and can't be opened. You should move it to the Trash."* | The download got a *quarantine* flag (common on Apple Silicon) | **Method A** (the right‑click trick will **not** fix "damaged") |
| *"…cannot be opened because the developer cannot be verified."* | Unsigned | **Method A** or **B** |

If you ever see **"damaged"**, skip straight to **Method A** — it's the only one
that clears it.

---

## Before you start

1. Go to the **[Releases page](https://github.com/a01786744-coder/garmin-recovery-dashboard/releases/latest)**.
2. Under **Assets**, download the macOS file — it ends in **`-arm64.dmg`**
   (for example `GarminRecoveryDashboard-5.4.0-arm64.dmg`; the number is just the
   current version — the exact file name for this release is shown right on the
   release page).
3. Double‑click the downloaded `.dmg`, then **drag the app icon onto the
   Applications folder** in the window that appears.
4. Eject the disk image (drag it to the Trash / click the ⏏ next to it in Finder).

You should now have **Garmin Recovery Dashboard** in your Applications folder.
Now use one of the two methods below to open it.

---

## Method A — Terminal (most reliable, works for every message)

This removes the "quarantine" flag macOS put on the download. It's one command,
and it's the standard fix used by most open‑source Mac apps.

1. Open **Terminal** (press `⌘ Space`, type `Terminal`, press Return).
2. Copy‑paste this line **exactly**, then press Return:

   ```bash
   xattr -dr com.apple.quarantine "/Applications/Garmin Recovery Dashboard.app"
   ```

   - It prints nothing if it worked — that's normal.
   - If it says *"No such file…"*, the app isn't in Applications yet — finish the
     **Before you start** steps above (drag it into Applications), then retry.
   - You do **not** need to type your password for this command.

3. Now open the app normally — double‑click it in Applications, or find it in
   Launchpad. It opens straight away, this time and every time after.

**What the command does:** `xattr` edits a file's hidden "extended attributes".
`com.apple.quarantine` is the flag macOS adds to anything downloaded from the
internet; `-dr` deletes it recursively (for the whole app bundle). Nothing else
about the app or your system changes.

---

## Method B — Open it from System Settings (no Terminal)

Use this if you'd rather not touch Terminal **and** you did *not* see the
"damaged" message.

1. In **Applications**, double‑click **Garmin Recovery Dashboard**. You'll get a
   warning — click **Done** / **Cancel** (do not click "Move to Trash").
2. Open the Apple menu  → **System Settings** → **Privacy & Security**.
3. Scroll down to the **Security** section. You'll see a line like
   *"Garmin Recovery Dashboard was blocked to protect your Mac."* with an
   **Open Anyway** button next to it. Click **Open Anyway**.
4. Confirm with **Open Anyway** again, and authenticate with Touch ID or your
   password if asked.
5. The app launches. macOS remembers your choice — future launches are normal.

> On older macOS you can instead **right‑click (or Control‑click) the app →
> Open → Open**. Apple removed that shortcut for unsigned apps in **macOS 15
> (Sequoia)**, so on recent systems use the **Privacy & Security → Open Anyway**
> route above, or **Method A**.

---

## After it opens

- Sign in with your **Garmin Connect** account. Your password is sent once to
  Garmin to get a login token and is **never stored**; all your health data
  stays on your Mac.
- To use it from your **iPhone**, follow the phone‑access steps in the main
  [README](../README.md#use-it-on-your-phone-lan--tailscale).

## Updating later

When a new version comes out, download the new `-arm64.dmg` from the
[Releases page](https://github.com/a01786744-coder/garmin-recovery-dashboard/releases/latest),
drag it into Applications (replacing the old one), and run **Method A** once more
(the fresh download gets a new quarantine flag). Your data and settings are kept
separately and carry over automatically.

## Uninstalling

Quit the app (right‑click its icon in the menu‑bar tray → **Quit** if it's
running there), then drag **Garmin Recovery Dashboard** from Applications to the
Trash.

---

## Still stuck?

- **"Operation not permitted" when running the Terminal command:** you may have
  copied a smart‑quote. Retype the double‑quotes `"` by hand, or paste into a
  plain‑text editor first.
- **App bounces in the Dock then quits:** it's usually still quarantined — run
  **Method A** again and make sure the path matches the app's exact name.
- **You have an Intel Mac (not Apple Silicon):** this build targets Apple
  Silicon (M‑series). It can run under Rosetta on some setups, but a native
  Intel build isn't published yet — open an issue on the repo if you need one.
