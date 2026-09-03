#!/usr/bin/env bash
# N-way parallel DOSBox-X (heavy-debug) live-verification harness.
#
# Boots fully-isolated dosbox-x instances inside WSL2 Ubuntu so multiple
# unrelated worklist items (docs/knowledge-base/91-worklist.md) can be
# verified concurrently instead of one session at a time. Each instance gets
# its own Xvfb TCP display, its own tmux server (a private socket, not the
# default one), and its own working-directory copy of the game files — so it
# can run side-by-side with the doc48 §8 canonical single-instance recipe
# (Xvfb :99 / tmux session "dbg" / ~/fd2-run) without ever touching it.
#
# See docs/knowledge-base/98-tooling-infrastructure.md for the full writeup
# (gotchas, proven concurrency level) and docs/knowledge-base/48-dosbox-x-
# debugger-build.md §8 for the underlying single-instance recipe this
# parallelizes.
#
# Usage:
#   dosbox_harness.sh launch <name> [keepalive_seconds]
#   dosbox_harness.sh screenshot <name> [output_path]
#   dosbox_harness.sh send-keys <name> <key> [key2 ...]
#   dosbox_harness.sh enter-debugger <name>
#   dosbox_harness.sh debugger-cmd <name> <cmd text...>
#   dosbox_harness.sh status
#   dosbox_harness.sh teardown <name>
#   dosbox_harness.sh teardown-all
#
# IMPORTANT: `launch` ends in a long `sleep` and must stay alive for the
# instance's whole lifetime (doc48 §8.4: the Xvfb/tmux/dosbox-x process tree
# gets reaped by WSLg within 15-60s if the WSL connection that started it
# doesn't stay open). Invoke it as a single backgrounded call, e.g. from the
# Windows side:
#   MSYS_NO_PATHCONV=1 wsl -d Ubuntu bash /mnt/c/.../tools/dosbox_harness.sh launch alpha
# with the calling tool's background/async option — do NOT expect it to
# return promptly, and do NOT wrap it in extra `&` backgrounding of your own
# (doc48 §8.4 "續四十六的教訓": that lets the outer wsl.exe return immediately
# and the whole tree gets reaped).
#
# All other subcommands are quick one-shot calls, safe to invoke normally.
#
# The display-port allocator has an offline regression test:
#   bash tools/test_dosbox_harness_ports.sh
# It uses a throwaway registry and an unused display range, so it is safe to
# run even while real instances are live.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

REGISTRY_DIR="${FD2_HARNESS_REGISTRY_DIR:-$HOME/.fd2-harness/instances}"
TMUX_SOCKET="${FD2_HARNESS_TMUX_SOCKET:-fd2harness}"
SOURCE_GAME_DIR="${FD2_HARNESS_SOURCE_DIR:-$HOME/fd2-run}"
DOSBOX_BIN="${FD2_HARNESS_DOSBOX_BIN:-$HOME/fd2-dosbox-build/dosbox-x/src/dosbox-x}"
SCREENSHOT_DIR="${FD2_HARNESS_SHOT_DIR:-$REPO_ROOT/.wsl_build/harness}"
# Overridable so the offline port-allocator regression test
# (tools/test_dosbox_harness_ports.sh) can run in a display range that is
# guaranteed unused on the host instead of fighting real instances on :199.
DISPLAY_BASE="${FD2_HARNESS_DISPLAY_BASE:-199}"
DISPLAY_STEP="${FD2_HARNESS_DISPLAY_STEP:-100}"
DISPLAY_MAX="${FD2_HARNESS_DISPLAY_MAX:-1999}"
KEEPALIVE_DEFAULT=3600
RESERVED_NAMES=("dbg")
PORT_LOCK="$REGISTRY_DIR/.portlock"
PORT_LOCK_TIMEOUT_S="${FD2_HARNESS_PORT_LOCK_TIMEOUT:-60}"
# Test-only hook: artificially widens the scan->reserve window so the
# concurrency regression test is deterministic rather than timing-dependent.
PORT_RESERVE_DELAY="${FD2_HARNESS_PORT_RESERVE_DELAY:-0}"

die() { echo "ERROR: $*" >&2; exit 1; }

validate_name() {
    local name=$1
    [[ "$name" =~ ^[a-zA-Z0-9_-]+$ ]] || die "instance name must match [a-zA-Z0-9_-]+, got: $name"
    for r in "${RESERVED_NAMES[@]}"; do
        [[ "$name" == "$r" ]] && die "instance name '$name' is reserved (collides with the single-instance recipe's tmux session name)"
    done
}

# Single source of truth for every per-instance path/name, so the reservation
# stub and the final registry entry can never drift apart.
state_file()      { echo "$REGISTRY_DIR/$1.state"; }
instance_session() { echo "harness-$1"; }
instance_workdir() { echo "$HOME/fd2-run-harness-$1"; }
instance_xvfblog() { echo "$REGISTRY_DIR/$1.xvfb.log"; }

# Sources a state file into the CURRENT shell. Caller should run this in a
# subshell/function scope where clobbering NAME/DISPLAY_PORT/etc is fine.
load_state() {
    local name=$1
    local sf; sf=$(state_file "$name")
    [[ -f "$sf" ]] || die "no such instance: $name (no state file at $sf)"
    # shellcheck disable=SC1090
    source "$sf"
}

xvfb_alive() { local pid=$1; kill -0 "$pid" 2>/dev/null && ps -p "$pid" -o args= 2>/dev/null | grep -q "Xvfb"; }
launcher_alive() { local pid=$1; kill -0 "$pid" 2>/dev/null; }
session_alive() { local session=$1; tmux -L "$TMUX_SOCKET" has-session -t "$session" 2>/dev/null; }

# --- display-port allocation -------------------------------------------------
#
# 2026-09-03: this used to be a single `pick_display_port` that scanned the
# registry and returned a port, with the caller only publishing that choice
# ~5-10s later (workdir copy + Xvfb spawn + two sleeps) when it finally wrote
# the .state file. That is a TOCTOU race: two launches started at the same
# instant both scanned an empty registry, both took :199, and the second
# Xvfb failed while xdotool keystrokes went to whichever window won -- observed
# as `fd2_original_verify.py --jobs 2` failing where --jobs 1 passed.
# The `ss -tln` check did not close it either; it only starts reporting once
# Xvfb is already listening, which is after the window opens.
#
# Fixed by making scan+publish atomic: the port is chosen and a RESERVATION
# state file is written while holding an exclusive flock, so the choice is
# visible to every other launcher before the lock is released. A reservation
# holds its port for as long as its launcher process is alive; once Xvfb is up
# the same state file is rewritten with XVFB_PID and the port is then held by
# Xvfb's liveness instead (a launcher that dies mid-setup therefore frees its
# port automatically, and a keepalive that outlives a dead Xvfb does not
# wrongly keep holding one).

# True if `port` is held by a running instance, a live reservation, or any
# process outside our registry (e.g. doc48 §8's canonical :99 recipe).
port_in_use() {
    local port=$1 f p xpid lpid
    for f in "$REGISTRY_DIR"/*.state; do
        [[ -e "$f" ]] || continue
        p=$(grep -oP '^DISPLAY_PORT=\K.*' "$f")
        [[ "$p" == "$port" ]] || continue
        xpid=$(grep -oP '^XVFB_PID=\K.*' "$f")
        lpid=$(grep -oP '^LAUNCHER_PID=\K.*' "$f")
        # Launched: held by Xvfb. Reservation (no XVFB_PID yet): held by the
        # launcher that is still setting it up.
        if [[ -n "$xpid" ]]; then
            xvfb_alive "$xpid" && return 0
        elif [[ -n "$lpid" ]] && launcher_alive "$lpid"; then
            return 0
        fi
    done
    ss -tln 2>/dev/null | grep -q ":$((6000 + port)) " && return 0
    return 1
}

scan_free_display_port() {
    local port=$DISPLAY_BASE
    while (( port <= DISPLAY_MAX )); do
        port_in_use "$port" || { echo "$port"; return 0; }
        port=$((port + DISPLAY_STEP))
    done
    die "no free display port in [$DISPLAY_BASE, $DISPLAY_MAX] step $DISPLAY_STEP (stale state files in $REGISTRY_DIR?)"
}

# Writes the registry entry for <name>. XVFB_PID empty => reservation.
write_state_file() {
    local name=$1 port=$2 xvfb_pid=$3 status=$4
    cat >"$(state_file "$name")" <<EOF
NAME=$name
DISPLAY_PORT=$port
TMUX_SESSION=$(instance_session "$name")
WORKDIR=$(instance_workdir "$name")
XVFB_PID=$xvfb_pid
XVFB_LOG=$(instance_xvfblog "$name")
LAUNCHER_PID=$$
START_TIME=$(date +%s)
STATUS=$status
EOF
}

# Atomically claims a free port for <name> and publishes the reservation.
# Sets RESERVED_PORT (a global, because a command substitution would put the
# flock in a subshell that exits before the caller can use the reservation).
RESERVED_PORT=""
reserve_display_port() {
    local name=$1
    mkdir -p "$REGISTRY_DIR"
    : >>"$PORT_LOCK" || die "cannot create port lock file: $PORT_LOCK"
    exec 9<>"$PORT_LOCK"
    flock -w "$PORT_LOCK_TIMEOUT_S" 9 \
        || die "timed out after ${PORT_LOCK_TIMEOUT_S}s waiting for the display-port lock ($PORT_LOCK)"
    local port; port=$(scan_free_display_port) || { flock -u 9; exec 9>&-; exit 1; }
    [[ "$PORT_RESERVE_DELAY" == "0" ]] || sleep "$PORT_RESERVE_DELAY"
    write_state_file "$name" "$port" "" reserving
    flock -u 9
    exec 9>&-
    RESERVED_PORT=$port
}

cmd_launch() {
    local name=${1:-}; [[ -n "$name" ]] || die "usage: launch <name> [keepalive_seconds]"
    local keepalive=${2:-$KEEPALIVE_DEFAULT}
    validate_name "$name"

    local sf; sf=$(state_file "$name")
    if [[ -f "$sf" ]]; then
        # A live reservation counts as "already running" too, otherwise two
        # concurrent launches of the SAME name would each delete the other's
        # registry entry and leak an instance.
        # shellcheck disable=SC1090
        ( source "$sf"
          if [[ -n "$XVFB_PID" ]]; then xvfb_alive "$XVFB_PID"
          else launcher_alive "$LAUNCHER_PID"; fi
        ) && die "instance '$name' already running or being launched (state file $sf); teardown first"
        rm -f "$sf"
    fi

    # Validate the environment BEFORE reserving, so a misconfigured host does
    # not leave reservation stubs behind.
    [[ -d "$SOURCE_GAME_DIR" ]] || die "canonical game dir not found: $SOURCE_GAME_DIR"
    [[ -x "$DOSBOX_BIN" ]] || die "dosbox-x binary not found/executable: $DOSBOX_BIN"

    reserve_display_port "$name"
    # Drop the reservation if setup dies before Xvfb exists, so a failed launch
    # does not leave a stale stub behind. Cleared as soon as XVFB_PID is
    # recorded -- from that point the entry MUST survive, or teardown would lose
    # track of a live Xvfb/tmux tree.
    # $sf expanded now, not at trap time: it is a function-local and may already
    # be out of scope when an EXIT trap actually runs.
    trap "rm -f '$sf'" EXIT
    local port=$RESERVED_PORT
    local session; session=$(instance_session "$name")
    local workdir; workdir=$(instance_workdir "$name")
    echo "[$name] reserved display :$port (registry entry published before setup starts)"

    echo "[$name] preparing isolated workdir: $workdir"
    rm -rf "$workdir"
    mkdir -p "$workdir"
    cp -r "$SOURCE_GAME_DIR"/. "$workdir"/

    mkdir -p "$REGISTRY_DIR" "$SCREENSHOT_DIR"
    local xvfblog; xvfblog=$(instance_xvfblog "$name")

    echo "[$name] starting Xvfb on :$port (tcp-reachable as 127.0.0.1:$port)"
    Xvfb ":$port" -screen 0 1024x768x24 -ac -nolisten local -listen tcp >"$xvfblog" 2>&1 &
    local xvfb_pid=$!
    # Upgrade the reservation to a real entry the instant Xvfb exists, so the
    # port is never held by anything that teardown cannot find: from here on it
    # is held by Xvfb's liveness rather than the launcher's, and this process
    # dying no longer orphans an unregistered Xvfb.
    write_state_file "$name" "$port" "$xvfb_pid" starting
    trap - EXIT
    sleep 3

    # Optional continuous audio capture (FD2_HARNESS_AUDIO_DISK=1).
    #
    # DOSBox-X's own wave capture is a HOST hotkey (Ctrl+F6) handled by its internal
    # mapper, not a key passed to the DOS program -- measured 2026-09-03: game-bound
    # chords like Ctrl+F1 are delivered fine by xdotool, but Ctrl+F6 produced no
    # capture directory at all. SDL's disk audio driver sidesteps the mapper entirely:
    # the mixer output is written straight to a headerless PCM file for the whole
    # session, which also makes it timestamp-sliceable against screenshots instead of
    # needing a start/stop key to land at the right moment.
    # Optional pass-through mapper (FD2_HARNESS_MAPPER=<path>).
    #
    # DOSBox-X binds some Ctrl+Fn chords to its own capture actions, and a chord the
    # host mapper consumes never reaches the DOS program. That matters here because the
    # game's secret-shop gates require specific BIOS scan codes: Ctrl+F1 (ch12) works,
    # while Ctrl+F2 (ch03) and Ctrl+F5 (ch06) do not fire -- and Ctrl+F5 is exactly the
    # kind of chord DOSBox reserves. tools/dosbox/passthrough.map lists those actions
    # with no binds, freeing the chords for the guest.
    #
    # TESTED 2026-09-03 AND IT DID NOT FIX THAT: a 2x2 (mapper on/off x key mode
    # window/xtest) on ch06's town at selection 4 left all four cells with no response,
    # so DOSBox-X consuming the chord is NOT the explanation. Kept because freeing the
    # host bindings is a legitimate capability, but do not cite it as the gate fix.
    local mapper_arg=()
    if [[ -n "${FD2_HARNESS_MAPPER:-}" ]]; then
        mapper_arg=(-set "sdl mapperfile=${FD2_HARNESS_MAPPER}")
        echo "[$name] mapper: ${FD2_HARNESS_MAPPER}"
    fi

    local audio_env=""
    if [[ "${FD2_HARNESS_AUDIO_DISK:-0}" != "0" ]]; then
        local audio_raw="$workdir/sdlaudio.raw"
        # Do NOT set SDL_DISKAUDIODELAY=0: that removes the driver's real-time
        # throttle, so it writes as fast as the disk allows. Measured 2026-09-03:
        # 4.3 GB in ~75 seconds, and -- worse than the size -- the audio timeline
        # then bears no relation to wall-clock, which destroys the whole point of
        # syncing clips against timestamped screenshots. Leaving it unset keeps the
        # driver pacing at roughly real time.
        audio_env="SDL_AUDIODRIVER=disk SDL_DISKAUDIOFILE='$audio_raw' "
        echo "[$name] audio: SDL disk driver -> $audio_raw (real-time paced)"
    fi

    echo "[$name] starting dosbox-x in tmux session '$session' (socket $TMUX_SOCKET)"
    DISPLAY="127.0.0.1:$port" tmux -L "$TMUX_SOCKET" new-session -d -s "$session" -x 200 -y 50 \
        "cd '$workdir' && ${audio_env}DISPLAY=127.0.0.1:$port '$DOSBOX_BIN' ${mapper_arg[*]@Q} -c 'MOUNT C $workdir' -c 'C:' -c 'config -set core=normal' -c 'config -set cycles=5000' -c 'FD2.EXE'"
    sleep 2
    tmux -L "$TMUX_SOCKET" set-option -t "$session" remain-on-exit on

    echo "[$name] waiting for DOSBox window on display 127.0.0.1:$port ..."
    local winid="" i
    for i in $(seq 1 30); do
        winid=$(DISPLAY="127.0.0.1:$port" xdotool search --name DOSBox 2>/dev/null | head -1)
        [[ -n "$winid" ]] && break
        sleep 1
    done
    if [[ -z "$winid" ]]; then
        echo "[$name] WARNING: DOSBox window did not appear within 30s"
        sed -i 's/^STATUS=.*/STATUS=window_not_found/' "$sf"
    else
        echo "[$name] window found ($winid). NOTE: boot/intro is not finished yet -"
        echo "[$name] screenshot-confirm the title screen yourself before send-keys/debugger-cmd"
        echo "[$name] (doc48 gotcha: sending keys mid-load can route into unexpected paths)."
        sed -i 's/^STATUS=.*/STATUS=running/' "$sf"
    fi

    echo "[$name] launch setup done, holding WSL connection alive for ${keepalive}s (do not kill this call)"
    exec sleep "$keepalive"
}

cmd_screenshot() {
    local name=${1:-}; [[ -n "$name" ]] || die "usage: screenshot <name> [output_path]"
    load_state "$name"
    local out=${2:-"$SCREENSHOT_DIR/${name}_$(date +%s).png"}
    mkdir -p "$(dirname "$out")"
    DISPLAY="127.0.0.1:$DISPLAY_PORT" import -window root "$out" \
        || die "import screenshot failed for $name (display 127.0.0.1:$DISPLAY_PORT)"
    echo "$out"
}

# windowfocus --sync before every xdotool key send (2026-09-02): doc58
# 續七十三(7840-7947行)found `xdotool key --window <win>` internally picks
# between XTestFakeKeyEvent (reliable) and XSendEvent (many apps ignore it)
# depending on whether the CURRENTLY-focused window happens to already be
# <win> at the instant xdotool checks -- in this WM-less Xvfb (no
# _NET_ACTIVE_WINDOW support, no click-to-focus maintenance) that can be
# ambiguous. That round's own evidence ruled this out as the root cause of
# the project's separately-tracked selective Enter/Space key-drop problem
# (a same-instant control test showed Up unaffected, which this branch could
# not explain), but it flagged forcing `windowfocus --sync` first as a
# cheap, never-applied defensive fix to stop this real, sourced-code-backed
# branch from adding noise to future input-reliability measurements.
# CONFIRMED LIVE 2026-09-02 (this project's first actual test of it, not
# just reading xdo.c): unlike the remake/GLFW window (doc58 續八十几, ~9566
# 行), `windowfocus --sync` does NOT error for the DOSBox-X/SDL window in
# this same WM-less Xvfb -- it returns rc=0 and getwindowfocus confirms the
# window took focus. Kept non-fatal (warn, don't die) since a future
# window/toolkit combination might still hit the GLFW-style failure.
_focus_window_best_effort() {
    local win=$1
    DISPLAY="127.0.0.1:$DISPLAY_PORT" xdotool windowfocus --sync "$win" 2>/dev/null \
        || echo "WARNING: windowfocus --sync failed for window $win (non-fatal, proceeding with the key send anyway -- see cmd_send_keys header comment)" >&2
}

cmd_send_keys() {
    local name=${1:-}; shift || true
    [[ -n "$name" && $# -gt 0 ]] || die "usage: send-keys <name> <key> [key2 ...]"
    load_state "$name"
    local win
    win=$(DISPLAY="127.0.0.1:$DISPLAY_PORT" xdotool search --name DOSBox 2>/dev/null | head -1)
    [[ -n "$win" ]] || die "no DOSBox window found for $name on 127.0.0.1:$DISPLAY_PORT"
    # Key delivery mode. Default changed to XTest on 2026-09-03 -- see below.
    #
    # `xdotool key --window <win>` addresses a specific window, but to do that it uses
    # XSendEvent for anything that is not the currently-focused window, and SDL (and
    # DOSBox-X's own key mapper) ignore synthetic XSendEvent keys. This harness's
    # existing header comment already flagged that xdotool switches between XTest and
    # XSendEvent depending on focus state, which in a WM-less Xvfb is ambiguous.
    #
    # The evidence that this was actually biting: DOSBox-X's mapper never reacted to
    # ANY host chord. Ctrl+F6 (record wave) produced no audio file and Ctrl+F5 (save
    # screenshot) produced no image -- verified by diffing the instance workdir's file
    # list before and after each chord. Guest-bound keys mostly worked, so the problem
    # was invisible until something needed the mapper.
    #
    # Dropping --window makes xdotool use XTest, which injects at the server and is
    # indistinguishable from real hardware, so both SDL and the mapper see it. Each
    # instance owns its own Xvfb display with exactly one DOSBox window, so "the
    # focused window" is unambiguous here -- this is safe precisely because of the
    # per-instance display isolation.
    #
    # DEFAULT STAYS `window` -- the mode every currently-passing scenario was proven
    # with. `xtest` was added and tested on 2026-09-03 against the one open question it
    # might have explained (the ch06 secret-gate chord not firing) and made NO
    # difference, so there is no evidence for changing what everything else relies on.
    # Set FD2_HARNESS_KEY_MODE=xtest to use it.
    local mode="${FD2_HARNESS_KEY_MODE:-window}"
    local k nkeys=$#
    for k in "$@"; do
        _focus_window_best_effort "$win"
        if [[ "$mode" == "window" ]]; then
            DISPLAY="127.0.0.1:$DISPLAY_PORT" xdotool key --window "$win" "$k"
        else
            DISPLAY="127.0.0.1:$DISPLAY_PORT" xdotool windowactivate --sync "$win" 2>/dev/null
            DISPLAY="127.0.0.1:$DISPLAY_PORT" xdotool key --clearmodifiers "$k"
        fi
        sleep 0.1
    done
    echo "[$name] sent $nkeys key(s) to window $win (mode=$mode)"
}

cmd_enter_debugger() {
    local name=${1:-}; [[ -n "$name" ]] || die "usage: enter-debugger <name>"
    load_state "$name"
    local win
    win=$(DISPLAY="127.0.0.1:$DISPLAY_PORT" xdotool search --name DOSBox 2>/dev/null | head -1)
    [[ -n "$win" ]] || die "no DOSBox window found for $name on 127.0.0.1:$DISPLAY_PORT"
    _focus_window_best_effort "$win"
    DISPLAY="127.0.0.1:$DISPLAY_PORT" xdotool key --window "$win" alt+Pause
    echo "[$name] sent Alt+Pause (toggle debugger TUI) to window $win"
}

cmd_debugger_cmd() {
    local name=${1:-}; shift || true
    [[ -n "$name" && $# -gt 0 ]] || die "usage: debugger-cmd <name> <command text...>"
    load_state "$name"
    session_alive "$TMUX_SESSION" || die "tmux session $TMUX_SESSION (socket $TMUX_SOCKET) is not alive for $name"
    local text="$*"
    # doc48 §8.4: -l literal flag is mandatory, Enter must be sent as its
    # own literal \r, not mixed with the named Enter/C-m key.
    tmux -L "$TMUX_SOCKET" send-keys -t "$TMUX_SESSION" -l "$text"
    tmux -L "$TMUX_SOCKET" send-keys -t "$TMUX_SESSION" -l $'\r'
    echo "[$name] sent debugger command: $text"
}

cmd_status() {
    mkdir -p "$REGISTRY_DIR"
    printf '%-12s %-10s %-8s %-14s %-8s %-8s %-10s %s\n' NAME DISPLAY XVFB_OK TMUX_SESSION SESS_OK LAUNCHER UPTIME_S WORKDIR
    local f any=0
    for f in "$REGISTRY_DIR"/*.state; do
        [[ -e "$f" ]] || continue
        any=1
        # shellcheck disable=SC1090
        ( source "$f"
          xvfb_ok="no"; xvfb_alive "$XVFB_PID" && xvfb_ok="yes"
          sess_ok="no"; session_alive "$TMUX_SESSION" && sess_ok="yes"
          launch_ok="no"; launcher_alive "$LAUNCHER_PID" && launch_ok="yes"
          now=$(date +%s); uptime=$((now - START_TIME))
          printf '%-12s %-10s %-8s %-14s %-8s %-8s %-10s %s\n' \
              "$NAME" "127.0.0.1:$DISPLAY_PORT" "$xvfb_ok" "$TMUX_SESSION" "$sess_ok" "$launch_ok" "$uptime" "$WORKDIR"
        )
    done
    [[ $any -eq 1 ]] || echo "(no harness instances registered)"
}

cmd_teardown() {
    local name=${1:-}; [[ -n "$name" ]] || die "usage: teardown <name>"
    local sf; sf=$(state_file "$name")
    if [[ ! -f "$sf" ]]; then
        echo "[$name] no state file, nothing to do"
        return 0
    fi
    # shellcheck disable=SC1090
    source "$sf"

    if session_alive "$TMUX_SESSION"; then
        echo "[$name] killing tmux session $TMUX_SESSION (socket $TMUX_SOCKET) - kills dosbox-x with it"
        tmux -L "$TMUX_SOCKET" kill-session -t "$TMUX_SESSION"
    else
        echo "[$name] tmux session $TMUX_SESSION already gone"
    fi

    if kill -0 "$XVFB_PID" 2>/dev/null; then
        if ps -p "$XVFB_PID" -o args= 2>/dev/null | grep -q "Xvfb"; then
            echo "[$name] killing Xvfb pid $XVFB_PID"
            kill "$XVFB_PID" 2>/dev/null
            sleep 0.5
            kill -0 "$XVFB_PID" 2>/dev/null && kill -9 "$XVFB_PID" 2>/dev/null
        else
            echo "[$name] WARNING: pid $XVFB_PID no longer looks like Xvfb (reused?) - not killing, just cleaning registry"
        fi
    else
        echo "[$name] Xvfb pid $XVFB_PID already gone"
    fi

    if kill -0 "$LAUNCHER_PID" 2>/dev/null; then
        if ps -p "$LAUNCHER_PID" -o args= 2>/dev/null | grep -qE 'sleep|dosbox_harness'; then
            echo "[$name] killing launcher/keepalive pid $LAUNCHER_PID"
            kill "$LAUNCHER_PID" 2>/dev/null
        else
            echo "[$name] WARNING: launcher pid $LAUNCHER_PID doesn't look like our keepalive (reused?) - not killing"
        fi
    fi

    rm -f "$sf"
    echo "[$name] torn down (workdir left in place: $WORKDIR - delete manually if not needed)"
}

cmd_teardown_all() {
    mkdir -p "$REGISTRY_DIR"
    local f name any=0
    for f in "$REGISTRY_DIR"/*.state; do
        [[ -e "$f" ]] || continue
        any=1
        name=$(basename "$f" .state)
        cmd_teardown "$name"
    done
    [[ $any -eq 1 ]] || echo "(no harness instances registered, nothing to tear down)"
}

main() {
    local cmd=${1:-}; shift || true
    case "$cmd" in
        launch)          cmd_launch "$@" ;;
        screenshot)      cmd_screenshot "$@" ;;
        send-keys)       cmd_send_keys "$@" ;;
        enter-debugger)  cmd_enter_debugger "$@" ;;
        debugger-cmd)    cmd_debugger_cmd "$@" ;;
        status)          cmd_status "$@" ;;
        teardown)        cmd_teardown "$@" ;;
        teardown-all)    cmd_teardown_all "$@" ;;
        *)
            cat >&2 <<EOF
usage: $0 <command> [args]
  launch <name> [keepalive_seconds]     start an isolated instance (long-lived, background it)
  screenshot <name> [output_path]       capture framebuffer PNG
  send-keys <name> <key> [key2 ...]     send game keypresses (xdotool key names)
  enter-debugger <name>                 send Alt+Pause to toggle the ncurses debugger TUI
  debugger-cmd <name> <text...>         type a debugger console command + Enter
  status                                list all harness-managed instances
  teardown <name>                       kill one instance (dosbox-x/Xvfb/tmux only, its own)
  teardown-all                          kill all harness-managed instances
EOF
            exit 2
            ;;
    esac
}

# Only dispatch when executed. Sourcing this file (as
# tools/test_dosbox_harness_ports.sh does) gets the functions without running
# any command.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
