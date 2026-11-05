#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 0x14b78 落點選擇的逐段記錄。每個停點:存 pane 暫存器、ESP 起 0x60 bytes;依停點另存地圖、方向陣列、落點清單。
# 斷點(執行期 +0x19c000):1b0b78 入口、1b0c42 mode 0 結果、1b0c85 mode 1 結果、1b0ccf 泛洪後地圖、1b0d37 T'、
#   1b0d95 0x146d1 後地圖、1b0da1 落點清單、1b0e5b 最終選擇、1b0ec4 呼叫 0x13488 前。
# 用法:IDLE=<次> sl_log.sh <標籤>
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
D=.wsl_build/ctr/sl
mkdir -p $D
tag=$1
IDLE=${IDLE:-6}
pane() { wsl -d Ubuntu tmux -L fd2harness capture-pane -t harness-$I -p; }
dump() { $H mem dump --instance $I --selector 0170 --linear "$1" --bytecount "$2" --out "$3" >/dev/null 2>&1; }
# 由已存的堆疊檔讀 [ESP+off] 的 dword(十六進位輸出)
sword() { python -X utf8 -c "import struct;print('%x'%struct.unpack_from('<I',open(r'$1','rb').read(),$2)[0])"; }
idle=0
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
  echo "EIP=$eip EAX=$eax ESP=$esp" > $f.regs
  dump $(printf '%x' $((0x$esp))) 60 $f.stack.bin
  case "$eip" in
    001B0CCF|001B0D95) dump 21934c 900 $f.map.bin;;
    001B0C85)
      # 方向陣列指標在 [ESP+0x1c],長度 = EAX(0xff 表示找不到)
      [ $((0x$eax)) -ne 255 ] && dump $(sword $f.stack.bin 0x1c) 40 $f.dirs.bin;;
    001B0DA1)
      # 落點清單指標在 [ESP+0x18],筆數 = EAX
      dump $(sword $f.stack.bin 0x18) $(printf '%x' $((0x$eax * 2 + 2))) $f.list.bin;;
    001B0B78) dump 26bdc8 690 $f.units.bin;;
  esac
  echo "stop $n: EIP=$eip EAX=$eax"
  $H resume --instance $I >/dev/null 2>&1
done
echo "loop ended (idle=$idle)"
