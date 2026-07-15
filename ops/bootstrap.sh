#!/usr/bin/env bash
# premura — one-time bootstrap.
# Installs prerequisites, generates an `age` keypair, walks the user through `rclone config`.
# Idempotent: re-running skips steps that are already done.

set -euo pipefail

CONFIG_DIR="${HOME}/.config/premura"
AGE_KEY="${CONFIG_DIR}/age.key"
RECIPIENTS="${CONFIG_DIR}/recipients.txt"
RCLONE_REMOTE="${PREMURA_RCLONE_REMOTE:-gdrive}"

echo ">>> Step 1/5: Homebrew dependencies"
if ! command -v brew >/dev/null 2>&1; then
    echo "    Homebrew is required. Install it from https://brew.sh and re-run." >&2
    exit 1
fi
for pkg in age uv; do
    if ! command -v "${pkg}" >/dev/null 2>&1; then
        echo "    brew install ${pkg}"
        brew install "${pkg}"
    else
        echo "    ${pkg} already installed"
    fi
done
# rclone is OPTIONAL — only needed if you want `premura upload` to push to Drive.
# Skip the prompt by setting PREMURA_SKIP_RCLONE=1.
if [[ "${PREMURA_SKIP_RCLONE:-0}" != "1" ]]; then
    if ! command -v rclone >/dev/null 2>&1; then
        read -r -p "Install rclone for optional Drive upload? [y/N] " WANT_RCLONE
        if [[ "${WANT_RCLONE}" =~ ^[Yy]$ ]]; then
            brew install rclone
        else
            echo "    skipping rclone — `premura upload` will not be available until installed"
        fi
    fi
fi

echo ">>> Step 2/5: Python deps (uv sync)"
# Reinstall the local `premura` editable wheel so console scripts declared in
# `[project.scripts]` (e.g. `premura`) are always materialized in `.venv/bin/`.
# Plain `uv sync` is incremental and will NOT rewrite bin scripts when the
# entry_points table changes without a version bump, which has left stale
# checkouts unable to invoke `uv run premura`.
uv sync --reinstall-package premura
uv sync --extra dev --reinstall-package premura

# Expose the CLI on PATH so you can run `premura …` from anywhere instead of
# `uv run premura …`. Isolated uv-tool env; --editable tracks this checkout,
# --force re-points a global install at the current clone.
uv tool install --editable . --force

# Install bundled Claude Code skills into ./.claude/skills/.
# Skip when PREMURA_SKIP_SKILLS=1 or when stdin is not a TTY (CI / pipelines).
if [[ "${PREMURA_SKIP_SKILLS:-0}" != "1" && -t 0 ]]; then
    echo "    Installing bundled Claude Code skills"
    uv run premura install-skills
else
    echo "    Skipping 'premura install-skills' (non-interactive or PREMURA_SKIP_SKILLS=1)"
fi

echo ">>> Step 3/5: Config directory"
mkdir -p "${CONFIG_DIR}"
chmod 700 "${CONFIG_DIR}"

echo ">>> Step 4/5: age keypair"
if [[ -f "${AGE_KEY}" ]]; then
    echo "    age key already exists at ${AGE_KEY}"
else
    echo "    Generating new age keypair at ${AGE_KEY}"
    age-keygen -o "${AGE_KEY}"
    chmod 600 "${AGE_KEY}"
fi
PUBKEY=$(grep -E '^# public key:' "${AGE_KEY}" | awk '{print $NF}')
if [[ -z "${PUBKEY}" ]]; then
    echo "    Could not read public key from ${AGE_KEY}" >&2
    exit 1
fi
printf '%s\n' "${PUBKEY}" > "${RECIPIENTS}"
chmod 600 "${RECIPIENTS}"
echo "    Recipient (public key): ${PUBKEY}"
echo
echo "*** ATTENTION ***"
echo "Back up ${AGE_KEY} NOW. WITHOUT IT YOUR BACKUPS ARE UNRECOVERABLE."
echo "Two recommended options:"
echo "  (a) Local file in a backed-up location (Time Machine, external drive, …)."
echo "  (b) Bitwarden secure note. Quick recipe (requires \`bw login\` already done):"
echo "      bw create item \"\$(jq -n --arg n 'premura age key' --arg c \"\$(cat ${AGE_KEY})\" \\"
echo "          '{type:2,name:\$n,secureNote:{type:0},notes:\$c}' | bw encode)\""
echo "      Retrieve later with:  bw get notes 'premura age key' > ${AGE_KEY}"
read -r -p "Type 'confirmed' once you have backed up the key: " ACK
if [[ "${ACK}" != "confirmed" ]]; then
    echo "Aborting — please back up the age key and re-run." >&2
    exit 1
fi

echo ">>> Step 5/5: rclone remote (OPTIONAL — only needed for \`premura upload\`)"
if ! command -v rclone >/dev/null 2>&1; then
    echo "    rclone not installed — skipping. \`premura upload\` will be unavailable until you install it."
elif rclone listremotes | grep -q "^${RCLONE_REMOTE}:$"; then
    echo "    rclone remote '${RCLONE_REMOTE}' already configured"
else
    read -r -p "Configure rclone Drive remote '${RCLONE_REMOTE}' now? [y/N] " WANT_CONFIG
    if [[ "${WANT_CONFIG}" =~ ^[Yy]$ ]]; then
        echo "    Launching 'rclone config' — choose:"
        echo "      n) new remote     -> name: ${RCLONE_REMOTE}"
        echo "      storage type      -> drive (Google Drive)"
        echo "      scope             -> drive.file  (per-app sandbox, NOT 'drive')"
        echo "      everything else   -> defaults"
        rclone config
    else
        echo "    skipping — re-run 'rclone config' later when you want upload."
    fi
fi

echo
echo "Bootstrap complete. Next steps:"
echo "  1. premura doctor                 # verify environment"
echo "  2. drop inputs into data/inbox/ and 'touch data/inbox/.ready'"
echo "  3. premura run-monthly            # ingest + encrypt (no auto-upload)"
echo "  4. premura upload --month YYYY-MM # push to Drive only when YOU choose to"
