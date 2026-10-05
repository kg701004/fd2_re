#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 法術 9 分流斷點記錄:依 EIP 印入口引數/暫存器後 resume,直到窗格末行連續 IDLE 次 "(Running)"。
# 用法:IDLE=<次> s9_log.sh <標籤>
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
D=.wsl_build/ctr
tag=$1
IDLE=${IDLE:-6}
pane() { wsl -d Ubuntu tmux -L fd2harness capture-pane -t harness-$I -p; }
args() {  # 函式入口:[ESP]=返回位址、[ESP+4]、[ESP+8]
  $H mem dump --instance $I --selector 0170 --linear "$1" --bytecount c --out $D/s9_stk.bin >/dev/null 2>&1
  python -X utf8 -c "
import struct
r,a,b=struct.unpack('<III',open(r'C:/Users/kg701/Desktop/GAME/fd2_re/$D/s9_stk.bin','rb').read()[:12])
print('ret=%#x a1=%d a2=%d'%(r-0x19c000,a,b))"
}
idle=0
for n in $(seq 1 80); do
  sleep 3
  p=$(pane)
  if echo "$p" | tail -1 | grep -q "Running"; then
    idle=$((idle + 1)); [ $idle -ge $IDLE ] && break; continue
  fi
  idle=0
  eip=$(echo "$p" | grep -o "EIP=[0-9A-F]*" | head -1)
  esp=$(echo "$p" | grep -o "ESP=[0-9A-F]*" | head -1)
  esi=$(echo "$p" | grep -o "ESI=[0-9A-F]*" | head -1)
  edx=$(echo "$p" | grep -o "EDX=[0-9A-F]*" | head -1)
  sp=$(printf '%x' $((0x${esp#ESP=})))
  case "$eip" in
    EIP=001B1311) echo "stop $n: ai_spell_execute $(args $sp)";;
    EIP=001CBF01) echo "stop $n: spell_cast_scene(0x2ff01) $(args $sp)";;
    EIP=001BD4AD) echo "stop $n: handler 0x214ad $(args $sp)";;
    EIP=001B875E) echo "stop $n: spell_damage_resolve $(args $sp)";;
    EIP=001B87FE) echo "stop $n: 0x1c7fe base=$((0x${esi#ESI=})) hit_roll=$((0x${edx#EDX=}))";;
    EIP=001B887F) echo "stop $n: 0x1c87f dmg_roll=$((0x${edx#EDX=}))";;
    *) echo "stop $n: other $eip";;
  esac
  $H resume --instance $I >/dev/null 2>&1
done
echo "loop ended (idle=$idle)"
