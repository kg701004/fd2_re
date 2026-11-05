#!/usr/bin/env bash
# Offline regression test for dosbox_harness.sh's mapper guard (doc98 s193).
#
# A DOSBox-X mapper file replaces ALL default binds, so tools/dosbox/passthrough.map is only valid
# for a dosbox-x whose own default map equals tools/dosbox/default_sdl2.map. The sidecar
# "<mapper>.binmd5" lists the attested binary md5s (make_passthrough_map.py generate / attest);
# `launch` with FD2_HARNESS_MAPPER must refuse any other binary BEFORE reserving a display port.
#
# Runs entirely offline: no Xvfb, no DOSBox-X, no game files (fake binary / game dir / registry in a
# throwaway dir), so it is safe to run while real harness instances are live.
#
#   bash tools/test_dosbox_harness_mapper.sh
#
# Exit 0 = all checks passed.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS="$SCRIPT_DIR/dosbox_harness.sh"
[[ -f "$HARNESS" ]] || { echo "ERROR: harness not found at $HARNESS" >&2; exit 1; }

T=$(mktemp -d "${TMPDIR:-/tmp}/fd2-harness-mappertest.XXXXXX")
trap 'rm -rf "$T"' EXIT

export FD2_HARNESS_REGISTRY_DIR="$T/instances"
export FD2_HARNESS_SOURCE_DIR="$T/game"
export FD2_HARNESS_DOSBOX_BIN="$T/fake-dosbox-x"
mkdir -p "$FD2_HARNESS_REGISTRY_DIR" "$FD2_HARNESS_SOURCE_DIR"
printf '#!/bin/sh\nexit 0\n' > "$FD2_HARNESS_DOSBOX_BIN"
chmod +x "$FD2_HARNESS_DOSBOX_BIN"
BIN_MD5=$(md5sum "$FD2_HARNESS_DOSBOX_BIN" | cut -d' ' -f1)
OTHER_MD5=$(printf 'other' | md5sum | cut -d' ' -f1)
MAP="$T/passthrough.map"
printf '[SDL2]\nkey_f1 "key 58" \n' > "$MAP"

# shellcheck source=/dev/null
source "$HARNESS"

PASS=0; FAIL=0
ok()  { PASS=$((PASS + 1)); printf '  PASS %s\n' "$1"; }
bad() { FAIL=$((FAIL + 1)); printf '  FAIL %s\n' "$1"; }
# expect <desc> <want_rc> <want_substring|-> -- runs mapper_guard "$MAP" "$FD2_HARNESS_DOSBOX_BIN"
expect() {
    local out rc
    out=$(mapper_guard "${GUARD_MAP:-$MAP}" "$FD2_HARNESS_DOSBOX_BIN"); rc=$?
    if [[ "$rc" != "$2" ]]; then bad "$1 (rc $rc, want $2; out '$out')"; return; fi
    if [[ "$3" == "-" ]]; then
        [[ -z "$out" ]] && ok "$1" || bad "$1 (unexpected output '$out')"
    else
        [[ "$out" == *"$3"* ]] && ok "$1" || bad "$1 (output '$out' lacks '$3')"
    fi
}

echo "mapper_guard:"
rm -f "$MAP.binmd5"
expect "no sidecar -> refuse" 1 "has no $MAP.binmd5"
printf '%s\n' "$OTHER_MD5" > "$MAP.binmd5"
expect "sidecar without this binary -> refuse" 1 "not attested for $FD2_HARNESS_DOSBOX_BIN (md5 $BIN_MD5)"
printf '%s\n%s\n' "$OTHER_MD5" "$BIN_MD5" > "$MAP.binmd5"
expect "sidecar lists this binary -> allow" 0 -
printf 'x%s\n' "$BIN_MD5" > "$MAP.binmd5"
expect "md5 only as a substring of a line -> refuse (whole-line match)" 1 "not attested"
printf '%s\n' "$OTHER_MD5" > "$MAP.binmd5"
FD2_HARNESS_MAPPER_UNCHECKED=1 expect "UNCHECKED=1 skips the md5 check" 0 -
GUARD_MAP="$T/missing.map" FD2_HARNESS_MAPPER_UNCHECKED=1 expect "unreadable mapper refused even with UNCHECKED=1" 1 "not readable"

echo "cmd_launch (refuses before reserving a display port):"
# If the guard ever fails open, launch must still not start anything real: private HOME (the workdir is
# $HOME/fd2-run-harness-NAME), Xvfb / tmux / xdotool stubs that fail at once, an unused display range,
# and a timeout. (s193: a fail-open mutant without these started a real launch.)
mkdir -p "$T/home" "$T/stubs"
for s in Xvfb tmux xdotool; do printf '#!/bin/sh\necho "stub %s" >&2\nexit 1\n' "$s" > "$T/stubs/$s"; chmod +x "$T/stubs/$s"; done
printf '%s\n' "$OTHER_MD5" > "$MAP.binmd5"
out=$(HOME="$T/home" PATH="$T/stubs:$PATH" FD2_HARNESS_DISPLAY_BASE=23999 FD2_HARNESS_DISPLAY_MAX=23999 \
      FD2_HARNESS_MAPPER="$MAP" timeout 30 bash "$HARNESS" launch mt1 2>&1); rc=$?
[[ "$rc" != 0 && "$out" == *"not attested"* ]] && ok "unattested binary -> launch dies with the guard's reason" \
    || bad "unattested launch (rc $rc, out '$out')"
[[ ! -e "$FD2_HARNESS_REGISTRY_DIR/mt1.state" && ! -e "$T/home/fd2-run-harness-mt1" ]] \
    && ok "no reservation stub or workdir left behind" || bad "state file or workdir left behind"
# paired control: the same launch with an attested binary gets PAST the guard -- it prints its
# "[mt2] mapper: <path>" line (after reserving and the stub Xvfb), then waits for a window that never
# comes, so it is cut by the timeout.
printf '%s\n' "$BIN_MD5" > "$MAP.binmd5"
out=$(HOME="$T/home" PATH="$T/stubs:$PATH" FD2_HARNESS_DISPLAY_BASE=23999 FD2_HARNESS_DISPLAY_MAX=23999 \
      FD2_HARNESS_MAPPER="$MAP" timeout 8 bash "$HARNESS" launch mt2 2>&1); rc=$?
[[ "$out" == *"[mt2] mapper: $MAP"* && "$out" != *"not attested"* && "$out" != *"has no"* ]] \
    && ok "attested binary passes the guard (control; launch reaches the mapper line, rc $rc)" \
    || bad "attested control (rc $rc, out '$out')"

echo "committed sidecar:"
REAL="$SCRIPT_DIR/dosbox/passthrough.map.binmd5"
if [[ -r "$REAL" ]] && ! grep -qvxE '[0-9a-f]{32}' "$REAL" && [[ -z "$(sort "$REAL" | uniq -d)" ]]; then
    ok "tools/dosbox/passthrough.map.binmd5 is one md5 per line, no duplicates"
else
    bad "tools/dosbox/passthrough.map.binmd5 malformed or missing"
fi

echo "passed: $PASS   failed: $FAIL"
[[ "$FAIL" == 0 ]]
