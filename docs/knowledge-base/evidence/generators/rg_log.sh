#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 0x13fd4 記錄:入口印 (返回位址, unit) 並傾印該單位記錄;0x14012 = 回 0;0x1410a 印 EDI(寫入的 HP)、ESI(MaxHP)、EAX(MaxHP/5)。
# 用法:IDLE=<次> rg_log.sh <標籤>
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
D=.wsl_build/ctr
tag=$1
IDLE=${IDLE:-6}
pane() { wsl -d Ubuntu tmux -L fd2harness capture-pane -t harness-$I -p; }
idle=0
for n in $(seq 1 120); do
  sleep 3
  p=$(pane)
  if echo "$p" | tail -1 | grep -q "Running"; then
    idle=$((idle + 1)); [ $idle -ge $IDLE ] && break; continue
  fi
  idle=0
  eip=$(echo "$p" | grep -o "EIP=[0-9A-F]*" | head -1)
  esp=$(echo "$p" | grep -o "ESP=[0-9A-F]*" | head -1)
  reg() { echo "$p" | grep -o "$1=[0-9A-F]*" | head -1 | cut -d= -f2; }
  sp=$(printf '%x' $((0x${esp#ESP=})))
  case "$eip" in
    EIP=001AFFD4)
      $H mem dump --instance $I --selector 0170 --linear "$sp" --bytecount 8 --out $D/rg_s.bin >/dev/null 2>&1
      u=$(python -X utf8 -c "import struct;r,u=struct.unpack('<II',open(r'C:/Users/kg701/Desktop/GAME/fd2_re/$D/rg_s.bin','rb').read()[:8]);print(u, '%#x'%(r-0x19c000))")
      set -- $u
      $H mem dump --instance $I --selector 0170 --linear $(printf '%x' $((0x26bdc8 + $1 * 0x50))) --bytecount 50 --out $D/rg_u_${tag}_$n.bin >/dev/null 2>&1
      st=$(python -X utf8 -c "
import struct
r=open(r'C:/Users/kg701/Desktop/GAME/fd2_re/$D/rg_u_${tag}_$n.bin','rb').read()
print('+25=%d +26=%d HP=%d/%d'%(r[0x25],r[0x26],*struct.unpack_from('<HH',r,0x40)))")
      echo "stop $n: rest-entry unit=$1 ret=$2 $st";;
    EIP=001B0012) echo "stop $n: rest-rejected (return 0)";;
    EIP=001B010A) echo "stop $n: rest-write newHP=$((0x$(reg EDI))) max=$((0x$(reg ESI))) maxHP/5=$((0x$(reg EAX)))";;
    *) echo "stop $n: other $eip";;
  esac
  $H resume --instance $I >/dev/null 2>&1
done
echo "loop ended (idle=$idle)"
