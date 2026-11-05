#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 0x14237 的逐段記錄(續六十四:另停 1b049e 讀 0x1debe 回傳值;E2 #13 的迴圈結束時把 item 77 +0xc 改回 06)。斷點(執行期 +0x19c000):1b0237 入口、1b0368 候選格清單、1b04c5 每組(格, 目標)比較前、
#   1b059f 迴圈結束、1b148e ai_attack_execute 入口(在此把 #1 的 HP 補回 782,避免被打死)。
# 用法:IDLE=<次> pa_log.sh <標籤>
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
D=.wsl_build/ctr/tr
mkdir -p $D
tag=$1
IDLE=${IDLE:-6}
pane() { wsl -d Ubuntu tmux -L fd2harness capture-pane -t harness-$I -p; }
dump() { $H mem dump --instance $I --selector 0170 --linear "$1" --bytecount "$2" --out "$3" >/dev/null 2>&1; }
sword() { python -X utf8 -c "import struct;print('%x'%struct.unpack_from('<I',open(r'$1','rb').read(),$2)[0])"; }
idle=0
actor=-1
for n in $(seq 1 300); do
  sleep 2
  p=$(pane)
  if echo "$p" | tail -1 | grep -q "Running"; then
    idle=$((idle + 1)); [ $idle -ge $IDLE ] && break; continue
  fi
  idle=0
  eip=$(echo "$p" | grep -o "EIP=[0-9A-F]*" | head -1); eip=${eip#EIP=}
  eax=$(echo "$p" | grep -o "EAX=[0-9A-F]*" | head -1); eax=${eax#EAX=}
  esp=$(echo "$p" | grep -o "ESP=[0-9A-F]*" | head -1); esp=${esp#ESP=}
  f=$D/${tag}_$(printf '%03d' $n)_$eip
  echo "$p" | grep -E "E[A-D]X=|E[SD]I=|EBP=|ESP=|EIP=" > $f.regs
  dump $(printf '%x' $((0x$esp))) 60 $f.stack.bin
  case "$eip" in
    001B0237)
      dump 26bdc8 690 $f.units.bin; dump 1f2998 17 $f.item77.bin
      actor=$(python -X utf8 -c "import struct;print(struct.unpack_from('<I',open(r'$f.stack.bin','rb').read(),4)[0])");;
    001B0368)
      dump $(sword $f.stack.bin 0x20) $(printf '%x' $((0x$eax * 2 + 2))) $f.list.bin
      dump 21934c 8e0 $f.map.bin;;
    001B04C5) dump 1efc43 10 $f.glob.bin;;
    001B059F)
      dump 1efc43 10 $f.glob.bin
      if [ "$actor" = "13" ]; then
        $H debugger-cmd --instance $I "SM 0170:1f29a4 06" >/dev/null 2>&1; sleep 0.5
        dump 1f2998 17 $f.item77_restored.bin
      fi;;
    001B148E)
      # 先存選中當下的單位表與結果,再把目標 [0x53c4b] 的 HP 補回最大值、DP 改 999(分數已定,避免被打死)
      dump 26bdc8 690 $f.units.bin; dump 1efc43 10 $f.glob.bin
      sm=$(python -X utf8 -c "
import struct
g=open(r'$f.glob.bin','rb').read(); u=open(r'$f.units.bin','rb').read()
t=struct.unpack_from('<I',g,8)[0]; base=0x26bdc8+t*0x50; mx=u[t*80+0x42:t*80+0x44]
print('%x %02x %02x' % (base+0x40, mx[0], mx[1]), '%x' % (base+0x4a))")
      set -- $sm
      $H debugger-cmd --instance $I "SM 0170:$1 $2 $3" >/dev/null 2>&1; sleep 0.5
      $H debugger-cmd --instance $I "SM 0170:$4 e7 03" >/dev/null 2>&1; sleep 0.5
      dump 26bdc8 690 $f.units_after_sm.bin;;
  esac
  echo "stop $n: EIP=$eip EAX=$eax actor=$actor"
  $H resume --instance $I >/dev/null 2>&1
done
echo "loop ended (idle=$idle)"
