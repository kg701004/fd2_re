#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續六十五:敵我回合的斷點記錄。每次停下記 EIP/EAX/EDX/ESI/EDI/ESP 與 [ESP..+0x10],0x1b148e(ai_attack_execute)時另傾印單位表。
# 用法:IDLE=<次> phase_log.sh <instance> <out_dir> <tag> <units_base_hex> <units_bytes_hex>
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=$1; D=$2; tag=$3; UB=$4; UN=$5
IDLE=${IDLE:-5}
idle=0
for n in $(seq 1 200); do
  sleep 2
  p=$(wsl -d Ubuntu tmux -L fd2harness capture-pane -t harness-$I -p)
  if echo "$p" | tail -1 | grep -q Running; then
    idle=$((idle + 1)); [ $idle -ge $IDLE ] && break; continue
  fi
  idle=0
  r() { echo "$p" | grep -o "$1=[0-9A-F]*" | head -1 | cut -d= -f2; }
  eip=$(r EIP); esp=$(r ESP)
  f=$D/${tag}_$(printf '%03d' $n)_$eip
  $H mem dump --instance $I --selector 0170 --linear $(printf '%x' $((0x$esp))) --bytecount 40 --out $f.stack.bin >/dev/null 2>&1
  [ "$eip" = "001B148E" ] && $H mem dump --instance $I --selector 0170 --linear $UB --bytecount $UN --out $f.units.bin >/dev/null 2>&1
  echo "$n EIP=$eip EAX=$(r EAX) EDX=$(r EDX) ESI=$(r ESI) EDI=$(r EDI) ESP=$esp" | tee -a $D/${tag}_stops.txt
  $H resume --instance $I >/dev/null 2>&1
done
echo "loop ended (idle=$idle)"
