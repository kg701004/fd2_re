#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 通用斷點記錄:每次停在函式入口就讀 [ESP](返回位址)、[ESP+4]、[ESP+8](前兩個參數),記錄後 resume;
# 最後一行持續是 "(Running)" 達 IDLE 次(每次 3 秒)就結束。
# 用法:IDLE=<次數> bp_log.sh <標籤>
# 前提:遊戲執行中、斷點已設。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
tag=$1
IDLE=${IDLE:-8}
pane() { wsl -d Ubuntu tmux -L fd2harness capture-pane -t harness-$I -p; }
idle=0
for n in $(seq 1 60); do
  sleep 3
  p=$(pane)
  if echo "$p" | tail -1 | grep -q "Running"; then
    idle=$((idle + 1)); [ $idle -ge $IDLE ] && break; continue
  fi
  idle=0
  eip=$(echo "$p" | grep -o "EIP=[0-9A-F]*" | head -1)
  esp=$(echo "$p" | grep -o "ESP=[0-9A-F]*" | head -1)
  a=$(printf '%x' $((0x${esp#ESP=})))
  $H mem dump --instance $I --selector 0170 --linear "$a" --bytecount c --out .wsl_build/ctr/stk_$tag.bin >/dev/null 2>&1
  st=$(python -X utf8 -c "
import struct
b=open(r'C:/Users/kg701/Desktop/GAME/fd2_re/.wsl_build/ctr/stk_$tag.bin','rb').read()
r,x,y=struct.unpack('<III',b[:12])
print('ret=%#x (static %#x) arg1=%d arg2=%d'%(r,r-0x19c000,x,y))")
  name=""
  case "$eip" in
    EIP=001BACC7) name="map_attack_resolve";;
    EIP=001BA856) name="map_attack_sequence";;
    EIP=001CB7B6) name="scene_attack_resolve";;
    EIP=001B148E) name="ai_attack_exec(0x1548e)";;
    EIP=001B1311) name="ai_spell_execute(0x15311)";;
    EIP=001B875E) name="spell_damage_resolve";;
    EIP=001CBF01) name="scene_cast(0x2ff01)";;
    EIP=001B87FE) name="spell hit check 0x1c7fe"; st="";;
    EIP=001B887F) name="spell dmg roll 0x1c87f"; st="";;
  esac
  regs=$(echo "$p" | grep -oE "(ESI|EDX)=[0-9A-F]*" | head -2 | tr '\n' ' ')
  echo "stop $n: $eip $name $st $regs"
  $H resume --instance $I >/dev/null 2>&1
done
echo "loop ended (idle=$idle)"
