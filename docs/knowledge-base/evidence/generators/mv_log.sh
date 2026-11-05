#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 備援移動記錄:函式入口印 [ESP]=返回位址與前四個引數;0x141cd / 0x14230 印 0x14121 的結果(EBP)。
# 用法:IDLE=<次> mv_log.sh <標籤>
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
D=.wsl_build/ctr
tag=$1
IDLE=${IDLE:-6}
pane() { wsl -d Ubuntu tmux -L fd2harness capture-pane -t harness-$I -p; }
args() {
  $H mem dump --instance $I --selector 0170 --linear "$1" --bytecount 14 --out $D/mv_s.bin >/dev/null 2>&1
  python -X utf8 -c "
import struct
r,a,b,c,d=struct.unpack('<IIIII',open(r'C:/Users/kg701/Desktop/GAME/fd2_re/$D/mv_s.bin','rb').read()[:20])
print('ret=%#x args=(%d,%d,%d,%d)'%(r-0x19c000,a,b,c,d))"
}
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
  ebp=$(echo "$p" | grep -o "EBP=[0-9A-F]*" | head -1)
  sp=$(printf '%x' $((0x${esp#ESP=})))
  case "$eip" in
    EIP=001B0121) echo "stop $n: 0x14121 entry $(args $sp)";;
    EIP=001B01CD) echo "stop $n: 0x14121 found nothing (return 0)";;
    EIP=001B0230) echo "stop $n: 0x14121 end, return=$((0x${ebp#EBP=}))";;
    EIP=001AFE9C)
      $H mem dump --instance $I --selector 0170 --linear 26bdc8 --bytecount 690 --out $D/mv_u_${tag}_$n.bin >/dev/null 2>&1
      echo "stop $n: 0x13e9c entry $(args $sp) units -> mv_u_${tag}_$n.bin";;
    EIP=001B0B78) echo "stop $n: 0x14b78 move $(args $sp)";;
    EIP=001AFFD4) echo "stop $n: rest 0x13fd4 $(args $sp)";;
    *) echo "stop $n: other $eip";;
  esac
  $H resume --instance $I >/dev/null 2>&1
done
echo "loop ended (idle=$idle)"
