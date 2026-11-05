#!/usr/bin/env bash
# Offline regression test for dosbox_harness.sh's display-port allocator.
#
# Covers the 2026-09-03 TOCTOU fix: the old `pick_display_port` chose a port
# but only published it ~5-10s later when the .state file was finally written,
# so concurrent launches handed out the same display (observed as
# `fd2_original_verify.py --jobs 2` failing where --jobs 1 passed). The fix
# makes scan+publish atomic under an flock, with the reservation held by the
# launcher's liveness until Xvfb takes over.
#
# Runs entirely offline: no Xvfb, no DOSBox-X, no game files. It uses a
# throwaway registry dir and a display range chosen to be unused on the host,
# so it is safe to run while real harness instances are live.
#
#   bash tools/test_dosbox_harness_ports.sh
#
# Exit 0 = all checks passed.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS="$SCRIPT_DIR/dosbox_harness.sh"
[[ -f "$HARNESS" ]] || { echo "ERROR: harness not found at $HARNESS" >&2; exit 1; }

TMPROOT=$(mktemp -d "${TMPDIR:-/tmp}/fd2-harness-porttest.XXXXXX")
BG_PIDS=()
cleanup() {
    local p
    for p in "${BG_PIDS[@]:-}"; do [[ -n "$p" ]] && kill "$p" 2>/dev/null; done
    rm -rf "$TMPROOT"
}
trap cleanup EXIT

# --- configure the harness for an isolated, guaranteed-unused range ----------
# 21999/22099/... -> X TCP 27999/28099/...
export FD2_HARNESS_REGISTRY_DIR="$TMPROOT/instances"
export FD2_HARNESS_DISPLAY_BASE=21999
export FD2_HARNESS_DISPLAY_STEP=100
export FD2_HARNESS_DISPLAY_MAX=22399   # -> exactly 5 slots: 21999..22399
export FD2_HARNESS_PORT_LOCK_TIMEOUT=30
SLOTS=(21999 22099 22199 22299 22399)

for p in "${SLOTS[@]}"; do
    if ss -tln 2>/dev/null | grep -q ":$((6000 + p)) "; then
        echo "ERROR: something is already listening on X TCP $((6000 + p)); pick a different test range" >&2
        exit 1
    fi
done

mkdir -p "$FD2_HARNESS_REGISTRY_DIR"

# shellcheck source=/dev/null
source "$HARNESS"

PASS=0; FAIL=0
ok()   { PASS=$((PASS + 1)); printf '  \033[32mPASS\033[0m %s\n' "$1"; }
bad()  { FAIL=$((FAIL + 1)); printf '  \033[31mFAIL\033[0m %s\n' "$1"; }
check() { # check <desc> <actual> <expected>
    if [[ "$2" == "$3" ]]; then ok "$1"; else bad "$1 (got '$2', want '$3')"; fi
}

reset_registry() { rm -f "$FD2_HARNESS_REGISTRY_DIR"/*.state 2>/dev/null; }

# A process whose argv[0] is literally "Xvfb", so xvfb_alive() accepts it.
# stdout/stderr MUST be redirected: these run inside $(...), and a background
# child that inherits the substitution pipe keeps it open, so the substitution
# would block for the child's whole lifetime.
spawn_fake_xvfb() { bash -c 'exec -a Xvfb sleep 300' >/dev/null 2>&1 & echo $!; }
spawn_idle()      { sleep 300 >/dev/null 2>&1 & echo $!; }
# A pid that has definitely exited. Retries in the (vanishingly unlikely) case
# the kernel immediately recycled it, so the test can't flake on pid reuse.
dead_pid() {
    local p i
    for i in 1 2 3 4 5; do
        sleep 0 & p=$!
        wait "$p" 2>/dev/null
        kill -0 "$p" 2>/dev/null || { echo "$p"; return 0; }
    done
    echo "ERROR: could not obtain a reliably-dead pid" >&2
    return 1
}

write_entry() { # write_entry <name> <port> <xvfb_pid> <launcher_pid> <status>
    cat >"$FD2_HARNESS_REGISTRY_DIR/$1.state" <<EOF
NAME=$1
DISPLAY_PORT=$2
TMUX_SESSION=harness-$1
WORKDIR=/nonexistent/$1
XVFB_PID=$3
XVFB_LOG=/dev/null
LAUNCHER_PID=$4
START_TIME=$(date +%s)
STATUS=$5
EOF
}

echo "== dosbox_harness.sh display-port allocator =="
echo "registry: $FD2_HARNESS_REGISTRY_DIR   range: ${SLOTS[0]}..${SLOTS[-1]}"
echo

# --- 1. empty registry -------------------------------------------------------
reset_registry
port_in_use "${SLOTS[0]}" && bad "empty registry: base port reported in use" \
                          || ok  "empty registry: base port is free"
check "empty registry: scan returns base" "$(scan_free_display_port)" "${SLOTS[0]}"

# --- 2. a live RESERVATION holds its port (the actual bug) -------------------
reset_registry
LP=$(spawn_idle); BG_PIDS+=("$LP")
write_entry resv "${SLOTS[0]}" "" "$LP" reserving
port_in_use "${SLOTS[0]}" && ok  "live reservation (no XVFB_PID yet) holds its port" \
                          || bad "live reservation did NOT hold its port -- this is the original race"
check "scan skips a reserved port" "$(scan_free_display_port)" "${SLOTS[1]}"

# --- 3. a reservation from a dead launcher does not leak the port ------------
reset_registry
write_entry resv "${SLOTS[0]}" "" "$(dead_pid)" reserving
port_in_use "${SLOTS[0]}" && bad "dead launcher's reservation still holds its port (would leak slots)" \
                          || ok  "dead launcher's reservation releases its port"
check "scan reuses a dead reservation's port" "$(scan_free_display_port)" "${SLOTS[0]}"

# --- 4. a launched instance is held by Xvfb, not by its launcher ------------
reset_registry
XP=$(spawn_fake_xvfb); BG_PIDS+=("$XP")
write_entry run "${SLOTS[0]}" "$XP" "$(dead_pid)" running
port_in_use "${SLOTS[0]}" && ok  "running instance holds its port via a live Xvfb" \
                          || bad "running instance did not hold its port"

reset_registry
LP2=$(spawn_idle); BG_PIDS+=("$LP2")
write_entry run "${SLOTS[0]}" "$(dead_pid)" "$LP2" running
port_in_use "${SLOTS[0]}" && bad "dead Xvfb still holds its port even though the keepalive lives" \
                          || ok  "dead Xvfb releases its port even while the keepalive lives"

# --- 5. reserve_display_port publishes immediately ---------------------------
reset_registry
reserve_display_port alpha
check "reserve_display_port sets RESERVED_PORT" "$RESERVED_PORT" "${SLOTS[0]}"
SF="$FD2_HARNESS_REGISTRY_DIR/alpha.state"
if [[ -f "$SF" ]]; then ok "reservation state file exists straight after reserving"
else bad "no reservation state file written"; fi
check "reservation records the port"   "$(grep -oP '^DISPLAY_PORT=\K.*' "$SF")" "${SLOTS[0]}"
check "reservation has no XVFB_PID"    "$(grep -oP '^XVFB_PID=\K.*' "$SF")"     ""
check "reservation status"             "$(grep -oP '^STATUS=\K.*' "$SF")"       "reserving"
reserve_display_port beta
check "second reservation takes the next slot" "$RESERVED_PORT" "${SLOTS[1]}"

# A reservation stub must still be a COMPLETE entry: status/teardown source it
# under `set -u`, so a missing field would abort them on an unbound variable.
for shape in reserving running; do
    reset_registry
    if [[ "$shape" == reserving ]]; then
        reserve_display_port shaped
    else
        XPS=$(spawn_fake_xvfb); BG_PIDS+=("$XPS")
        write_state_file shaped "${SLOTS[0]}" "$XPS" running
    fi
    SRC_ERR=$( ( set -u
                 # shellcheck source=/dev/null
                 source "$FD2_HARNESS_REGISTRY_DIR/shaped.state"
                 echo "$NAME $DISPLAY_PORT $TMUX_SESSION $WORKDIR $XVFB_PID $XVFB_LOG $LAUNCHER_PID $START_TIME $STATUS" >/dev/null
               ) 2>&1 )
    if [[ -z "$SRC_ERR" ]]; then ok "$shape entry sources cleanly under set -u"
    else bad "$shape entry incomplete: $SRC_ERR"; fi
done

# --- 6. exhaustion fails loudly instead of looping forever -------------------
reset_registry
for i in "${!SLOTS[@]}"; do
    XPI=$(spawn_fake_xvfb); BG_PIDS+=("$XPI")
    write_entry "full$i" "${SLOTS[$i]}" "$XPI" "$(dead_pid)" running
done
ERR=$( (scan_free_display_port) 2>&1 >/dev/null )
RC=$?
if [[ $RC -ne 0 && "$ERR" == *"no free display port"* ]]; then
    ok "exhausted range fails with a clear error (no infinite loop)"
else
    bad "exhausted range did not fail cleanly (rc=$RC, err='$ERR')"
fi

# --- 7. concurrency: THE regression test ------------------------------------
# PORT_RESERVE_DELAY widens the scan->publish window to 1s so this is
# deterministic rather than a timing lottery. First the control: N concurrent
# bare scans, which publish nothing and therefore MUST all collide -- that is
# exactly the pre-fix behaviour, and it proves this test can actually detect it.
reset_registry
N=5
CONTROL="$TMPROOT/control"; mkdir -p "$CONTROL"
# NOTE: bare `wait` would also block on the long-lived fake-Xvfb/idle helpers
# spawned by the earlier cases, so always wait on an explicit pid list.
WAIT_PIDS=()
for i in $(seq 1 $N); do
    ( FD2_HARNESS_PORT_RESERVE_DELAY=1 bash -c "
        source '$HARNESS'
        sleep 1
        scan_free_display_port > '$CONTROL/$i'
      " ) &
    WAIT_PIDS+=("$!")
done
wait "${WAIT_PIDS[@]}"
CONTROL_DISTINCT=$(cat "$CONTROL"/* | sort -u | wc -l)
check "control: $N unlocked scans all collide (pre-fix behaviour)" "$CONTROL_DISTINCT" "1"

reset_registry
RESULTS="$TMPROOT/results"; mkdir -p "$RESULTS"
WAIT_PIDS=()
for i in $(seq 1 $N); do
    ( FD2_HARNESS_PORT_RESERVE_DELAY=1 bash -c "
        source '$HARNESS'
        reserve_display_port 'conc$i'
        echo \"\$RESERVED_PORT\" > '$RESULTS/$i'
        sleep 4
      " ) &
    WAIT_PIDS+=("$!"); BG_PIDS+=("$!")
done
wait "${WAIT_PIDS[@]}"
GOT=$(cat "$RESULTS"/* 2>/dev/null | sort -n | tr '\n' ' ')
DISTINCT=$(cat "$RESULTS"/* 2>/dev/null | sort -u | wc -l)
COUNT=$(cat "$RESULTS"/* 2>/dev/null | wc -l)
check "concurrent reserve: all $N produced a port" "$COUNT" "$N"
check "concurrent reserve: all ports distinct"     "$DISTINCT" "$N"
check "concurrent reserve: ports are the $N slots" "$GOT" "$(printf '%s ' "${SLOTS[@]}")"

reset_registry
echo
echo "passed: $PASS   failed: $FAIL"
[[ $FAIL -eq 0 ]] || exit 1
