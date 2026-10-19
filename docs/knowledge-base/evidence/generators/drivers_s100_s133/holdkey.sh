#!/bin/bash
# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續一百二十九:cycles 2500 下按鍵會掉,改成 keydown -> 持續 HOLD 秒 -> keyup(只送給該 instance 的 DOSBox 視窗,harness 不改)。
# 用法:holdkey.sh NAME KEY [HOLD]
set -u
name=$1; key=$2; hold=${3:-0.15}
source /mnt/c/Users/kg701/Desktop/GAME/fd2_re/tools/dosbox_harness.sh
load_state "$name"
win=$(DISPLAY="127.0.0.1:$DISPLAY_PORT" xdotool search --name DOSBox 2>/dev/null | head -1)
[ -n "$win" ] || { echo "no window"; exit 1; }
DISPLAY="127.0.0.1:$DISPLAY_PORT" xdotool keydown --window "$win" "$key"
sleep "$hold"
DISPLAY="127.0.0.1:$DISPLAY_PORT" xdotool keyup --window "$win" "$key"
echo "[$name] held $key for $hold s (window $win, display $DISPLAY_PORT)"
