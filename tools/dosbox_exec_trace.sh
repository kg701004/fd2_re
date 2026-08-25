#!/usr/bin/env bash
# DOSBox-X heavy-debug LOGC ground-truth execution-trace capture tool.
#
# Background: doc35 §9's "party montage" ending-CG-renderer hunt spent 15+ rounds
# guessing candidate addresses and verifying them one at a time -- every candidate
# failed (wrong instruction boundaries, zero callers, coincidental address overlap
# with an unrelated subsystem, see doc35 §9.1-§9.14). This tool flips the approach:
# capture *every* CS:IP the CPU actually visits during a live-reproduced scene, then
# cross-reference the deduplicated, native-translated address set against Ghidra to
# find genuinely un-analyzed code regions -- those are evidence-backed candidates,
# not guesses.
#
# It works because the WSL2-native dosbox-x build in this project is compiled with
# --enable-debug=heavy (doc48 §2), which compiles in a *built-in* instruction-trace
# family of debugger console commands (LOG/LOGS/LOGL/LOGC/ADDLOG/HEAVYLOG -- verified
# present via `strings` on the built binary and confirmed live 2026-08-25, see doc98).
# LOGC <hex-count> is the one this tool uses: it logs *only* "CCCC:IIIIIIII" (CS:EIP)
# per executed instruction to LOGCPU.TXT in the dosbox-x working directory -- the
# lightest of the four formats (~14 bytes/line), and the one relevant for address
# hunting (LOG/LOGS/LOGL also dump full register state per instruction, which nobody
# needs here and which multiplies file size for no benefit).
#
# Critically (verified live, not assumed): issuing LOGC from the debugger console
# resumes real emulation (DOSBOX_SetNormalLoop() under the hood) and the game keeps
# rendering frames AND accepting xdotool keyboard input for the whole duration of the
# capture -- it is NOT a frozen/blocking debugger operation. That means you can arm a
# trace and then drive the game exactly as you normally would (screenshots, xdotool
# key sends) while it silently logs every instruction in the background. When the
# requested instruction count is exhausted, dosbox-x automatically re-enters the
# debugger (game freezes at that point) and prints "DEBUG: cpu log LOGCPU.TXT created".
#
# Throughput measured on this project's WSL2 VM (2026-08-25): roughly 3-8 million
# instructions/second logged to disk (10M instructions ~= 3.8s wall clock; 600M
# instructions ~= well under 2 minutes). This is decoupled from the *emulated* game
# speed (cycles=5000 does not mean "5000 real instructions/second" -- see doc98 for
# why), so in practice a generous count (hundreds of millions) comfortably covers
# several real seconds of on-screen action while still finishing in under a minute
# of wall-clock capture time.
#
# See docs/knowledge-base/98-tooling-infrastructure.md for the full writeup
# (worked example, LOGC internals, throughput numbers, known limitations) and
# docs/knowledge-base/48-dosbox-x-debugger-build.md §10 for a pointer from the
# environment-recipe doc. docs/knowledge-base/58-remake-live-verification-log.md
# 續六十六 has the first real capture's results.
#
# Usage:
#   dosbox_exec_trace.sh arm <tmux-session> <hex-count> [workdir]
#       Debugger console must already be active (Alt+Pause already sent) and idle
#       at the "I->" prompt. Sends `LOGC <hex-count>` + Enter. Returns immediately
#       -- the trace runs in the background inside dosbox-x. Send your trigger/
#       advance keys (xdotool) right after calling this; do not wait for it.
#       workdir defaults to ~/fd2-run (doc48 §8.4 canonical single-instance dir);
#       pass a harness instance's workdir (~/fd2-run-harness-<name>) if using
#       tools/dosbox_harness.sh instead.
#
#   dosbox_exec_trace.sh wait-done <tmux-session> <expected-decimal-count> [timeout-s]
#       Polls LOGCPU.TXT's line count (cheap `wc -l`) every 0.5s until it reaches
#       expected-decimal-count (i.e. LOGC finished and dosbox-x auto re-entered the
#       debugger -- the game is now frozen) or timeout-s elapses (default 120).
#       Optional convenience; you can also just keep sending keys and check status
#       yourself, since the game stays responsive until the count is reached.
#
#   dosbox_exec_trace.sh status [workdir]
#       Prints LOGCPU.TXT's current size and line count. Does not touch the
#       debugger. Useful to check whether an armed trace has finished.
#
#   dosbox_exec_trace.sh dedup [workdir] [out-file]
#       Single-pass `awk '!seen[$0]++'` dedup of LOGCPU.TXT (fast: ~70s for a
#       600M-line / 7.9GB file in this project's measurements, vs. `sort -u`
#       which is impractical at this size). Writes unique "CCCC:IIIIIIII" lines
#       to out-file (default workdir/trace_unique_cseip.txt) and prints the count.
#       LOGCPU.TXT itself is never committed or copied out of WSL -- it is a
#       multi-GB process artifact; only the deduplicated address list is small
#       enough to carry around (typically tens of thousands of unique addresses
#       even from a 600M-instruction capture, since most instructions are inside
#       tight loops).
#
# Cross-referencing the dedup'd address list against Ghidra (translate live->native,
# classify into known/documented, Ghidra-analyzed-but-undocumented, or genuinely
# unanalyzed) is NOT done by this shell script -- that's
# tools/dosbox_exec_trace_analyze.py, which runs on the Windows side against the
# local Ghidra install via tools/ghidra_batch_probe.py. Typical flow:
#   1. (WSL)  dosbox_exec_trace.sh arm dbg <hex-count>
#   2. (WSL)  <send xdotool keys to drive the scene you want to capture>
#   3. (WSL)  dosbox_exec_trace.sh dedup   # -> workdir/trace_unique_cseip.txt
#   4. copy that file to the Windows side (e.g. via \\wsl.localhost\...)
#   5. (Win)  python tools/dosbox_exec_trace_analyze.py trace_unique_cseip.txt \
#                 --out-dir .wsl_build/trace_analysis
#
# IMPORTANT: this tool only ever ARMS/READS the trace; it never sends the game
# keys for you (every scene's trigger sequence is different -- see doc58 for the
# specific button sequences this project has already worked out). Compose it with
# ordinary xdotool/tmux calls exactly as doc48 §8.4 describes.

set -uo pipefail

die() { echo "ERROR: $*" >&2; exit 1; }

DEFAULT_SOCKET_ARGS=()  # default tmux server (no -L) unless FD2_TRACE_TMUX_SOCKET is set
if [[ -n "${FD2_TRACE_TMUX_SOCKET:-}" ]]; then
    DEFAULT_SOCKET_ARGS=(-L "$FD2_TRACE_TMUX_SOCKET")
fi

tmux_cmd() { tmux "${DEFAULT_SOCKET_ARGS[@]}" "$@"; }

cmd_arm() {
    local session=${1:?usage: arm <tmux-session> <hex-count> [workdir]}
    local hexcount=${2:?usage: arm <tmux-session> <hex-count> [workdir]}
    local workdir=${3:-$HOME/fd2-run}
    [[ "$hexcount" =~ ^[0-9A-Fa-f]+$ ]] || die "hex-count must be plain hex digits, no 0x prefix (debugger console syntax) -- got: $hexcount"
    tmux_cmd has-session -t "$session" 2>/dev/null || die "no such tmux session: $session"
    rm -f "$workdir/LOGCPU.TXT"
    tmux_cmd send-keys -t "$session" -l "LOGC $hexcount"
    tmux_cmd send-keys -t "$session" -l $'\r'
    echo "armed: LOGC $hexcount ($((16#$hexcount)) instructions) on session '$session', workdir $workdir"
    echo "game is live again -- send your trigger/advance keys now"
}

cmd_wait_done() {
    local session=${1:?usage: wait-done <tmux-session> <expected-decimal-count> [timeout-s]}
    local expected=${2:?usage: wait-done <tmux-session> <expected-decimal-count> [timeout-s]}
    local timeout=${3:-120}
    local workdir=${4:-$HOME/fd2-run}
    local waited=0
    while (( waited < timeout )); do
        if [[ -f "$workdir/LOGCPU.TXT" ]]; then
            n=$(wc -l < "$workdir/LOGCPU.TXT" 2>/dev/null || echo 0)
            if (( n >= expected )); then
                echo "done: $n lines (>= $expected) after ~${waited}s"
                return 0
            fi
        fi
        sleep 0.5
        waited=$((waited + 1))  # coarse (0.5s ticks counted as 1 each) -- fine for a rough bound
    done
    echo "timeout after ${timeout} 0.5s-ticks -- trace may still be running, or count was never reached" >&2
    return 1
}

cmd_status() {
    local workdir=${1:-$HOME/fd2-run}
    if [[ ! -f "$workdir/LOGCPU.TXT" ]]; then
        echo "no LOGCPU.TXT in $workdir"
        return 1
    fi
    ls -la "$workdir/LOGCPU.TXT"
    echo "lines: $(wc -l < "$workdir/LOGCPU.TXT")"
}

cmd_dedup() {
    local workdir=${1:-$HOME/fd2-run}
    local outfile=${2:-$workdir/trace_unique_cseip.txt}
    [[ -f "$workdir/LOGCPU.TXT" ]] || die "no LOGCPU.TXT in $workdir"
    local t0 t1
    t0=$(date +%s)
    awk '!seen[$0]++' "$workdir/LOGCPU.TXT" > "$outfile"
    t1=$(date +%s)
    echo "deduped $(wc -l < "$workdir/LOGCPU.TXT") lines -> $(wc -l < "$outfile") unique in $((t1 - t0))s -> $outfile"
}

main() {
    local sub=${1:-}
    shift || true
    case "$sub" in
        arm) cmd_arm "$@" ;;
        wait-done) cmd_wait_done "$@" ;;
        status) cmd_status "$@" ;;
        dedup) cmd_dedup "$@" ;;
        *)
            echo "usage: $0 {arm|wait-done|status|dedup} ..." >&2
            echo "  see the header comment in this file for full usage" >&2
            exit 2
            ;;
    esac
}

main "$@"
