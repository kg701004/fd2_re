#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 0x14ef0 決策點記錄:0x14f62 停下時 ESI = 單位、EBP = +0x34 & 0x40、[ESP] = AP - 物理目標 DP,並傾印 [0x53c23..0x53c52];
# 之後停在哪個執行函式(0x1548e 物理、0x15311 法術、0x15055 道具)就是勝者。用法:IDLE=<次> mix_log.sh <標籤>
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
D=.wsl_build/ctr
tag=$1
IDLE=${IDLE:-6}
pane() { wsl -d Ubuntu tmux -L fd2harness capture-pane -t harness-$I -p; }
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
  ebp=$(echo "$p" | grep -o "EBP=[0-9A-F]*" | head -1)
  sp=$(printf '%x' $((0x${esp#ESP=})))
  case "$eip" in
    EIP=001B0F62)
      $H mem dump --instance $I --selector 0170 --linear "$sp" --bytecount 4 --out $D/mix_d_${tag}_$n.bin >/dev/null 2>&1
      $H mem dump --instance $I --selector 0170 --linear 1efc23 --bytecount 30 --out $D/mix_g_${tag}_$n.bin >/dev/null 2>&1
      st=$(python -X utf8 -c "
import struct
g=open(r'C:/Users/kg701/Desktop/GAME/fd2_re/$D/mix_g_${tag}_$n.bin','rb').read()
d=struct.unpack('<i',open(r'C:/Users/kg701/Desktop/GAME/fd2_re/$D/mix_d_${tag}_$n.bin','rb').read()[:4])[0]
v=lambda o: struct.unpack_from('<i',g,o-0x23)[0]
print('P=%d S=%d I=%d spell=%d ptarget=%d d=%d'%(v(0x4f),v(0x23),v(0x33),v(0x2f),v(0x4b),d))")
      echo "stop $n: decide unit=$((0x${esi#ESI=})) bit40=$((0x${ebp#EBP=})) $st";;
    EIP=001B148E) echo "stop $n: -> physical 0x1548e";;
    EIP=001B1311) echo "stop $n: -> spell 0x15311";;
    EIP=001B1055) echo "stop $n: -> item 0x15055";;
    *) echo "stop $n: other $eip";;
  esac
  $H resume --instance $I >/dev/null 2>&1
done
echo "loop ended (idle=$idle)"
