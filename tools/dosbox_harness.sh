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

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

REGISTRY_DIR="${FD2_HARNESS_REGISTRY_DIR:-$HOME/.fd2-harness/instances}"
TMUX_SOCKET="${FD2_HARNESS_TMUX_SOCKET:-fd2harness}"
SOURCE_GAME_DIR="${FD2_HARNESS_SOURCE_DIR:-$HOME/fd2-run}"
DOSBOX_BIN="${FD2_HARNESS_DOSBOX_BIN:-$HOME/fd2-dosbox-build/dosbox-x/src/dosbox-x}"
SCREENSHOT_DIR="${FD2_HARNESS_SHOT_DIR:-$REPO_ROOT/.wsl_build/harness}"
DISPLAY_BASE=199
DISPLAY_STEP=100
KEEPALIVE_DEFAULT=3600
RESERVED_NAMES=("dbg")

die() { echo "ERROR: $*" >&2; exit 1; }

validate_name() {
    local name=$1
    [[ "$name" =~ ^[a-zA-Z0-9_-]+$ ]] || die "instance name must match [a-zA-Z0-9_-]+, got: $name"
    for r in "${RESERVED_NAMES[@]}"; do
        [[ "$name" == "$r" ]] && die "instance name '$name' is reserved (collides with the single-instance recipe's tmux session name)"
    done
}

state_file() { echo "$REGISTRY_DIR/$1.state"; }

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

pick_display_port() {
    mkdir -p "$REGISTRY_DIR"
    local port=$DISPLAY_BASE
    while true; do
        local conflict=0
        local f
        for f in "$REGISTRY_DIR"/*.state; do
            [[ -e "$f" ]] || continue
            local p pid
            p=$(grep -oP '^DISPLAY_PORT=\K.*' "$f")
            pid=$(grep -oP '^XVFB_PID=\K.*' "$f")
            if [[ "$p" == "$port" ]] && xvfb_alive "$pid"; then
                conflict=1
                break
            fi
        done
        # Belt-and-suspenders: also check nothing is actually listening on
        # the X TCP port already (covers the canonical :99 recipe and any
        # stray process not in our registry).
        if ss -tln 2>/dev/null | grep -q ":$((6000 + port)) "; then
            conflict=1
        fi
        if [[ $conflict -eq 0 ]]; then
            echo "$port"
            return
        fi
        port=$((port + DISPLAY_STEP))
    done
}

cmd_launch() {
    local name=${1:-}; [[ -n "$name" ]] || die "usage: launch <name> [keepalive_seconds]"
    local keepalive=${2:-$KEEPALIVE_DEFAULT}
    validate_name "$name"

    local sf; sf=$(state_file "$name")
    if [[ -f "$sf" ]]; then
        # shellcheck disable=SC1090
        ( source "$sf"; xvfb_alive "$XVFB_PID" ) && die "instance '$name' already running (state file $sf); teardown first"
        rm -f "$sf"
    fi

    local port; port=$(pick_display_port)
    local session="harness-$name"
    local workdir="$HOME/fd2-run-harness-$name"

    [[ -d "$SOURCE_GAME_DIR" ]] || die "canonical game dir not found: $SOURCE_GAME_DIR"
    [[ -x "$DOSBOX_BIN" ]] || die "dosbox-x binary not found/executable: $DOSBOX_BIN"

    echo "[$name] preparing isolated workdir: $workdir"
    rm -rf "$workdir"
    mkdir -p "$workdir"
    cp -r "$SOURCE_GAME_DIR"/. "$workdir"/

    mkdir -p "$REGISTRY_DIR" "$SCREENSHOT_DIR"
    local xvfblog="$REGISTRY_DIR/$name.xvfb.log"

    echo "[$name] starting Xvfb on :$port (tcp-reachable as 127.0.0.1:$port)"
    Xvfb ":$port" -screen 0 1024x768x24 -ac -nolisten local -listen tcp >"$xvfblog" 2>&1 &
    local xvfb_pid=$!
    sleep 3

    echo "[$name] starting dosbox-x in tmux session '$session' (socket $TMUX_SOCKET)"
    DISPLAY="127.0.0.1:$port" tmux -L "$TMUX_SOCKET" new-session -d -s "$session" -x 200 -y 50 \
        "cd '$workdir' && DISPLAY=127.0.0.1:$port '$DOSBOX_BIN' -c 'MOUNT C $workdir' -c 'C:' -c 'config -set core=normal' -c 'config -set cycles=5000' -c 'FD2.EXE'"
    sleep 2
    tmux -L "$TMUX_SOCKET" set-option -t "$session" remain-on-exit on

    # Write state BEFORE the long keepalive sleep so other subcommands can
    # see this instance immediately.
    cat >"$sf" <<EOF
NAME=$name
DISPLAY_PORT=$port
TMUX_SESSION=$session
WORKDIR=$workdir
XVFB_PID=$xvfb_pid
XVFB_LOG=$xvfblog
LAUNCHER_PID=$$
START_TIME=$(date +%s)
STATUS=starting
EOF

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
    local k nkeys=$#
    for k in "$@"; do
        _focus_window_best_effort "$win"
        DISPLAY="127.0.0.1:$DISPLAY_PORT" xdotool key --window "$win" "$k"
        sleep 0.1
    done
    echo "[$name] sent $nkeys key(s) to window $win"
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

main "$@"
