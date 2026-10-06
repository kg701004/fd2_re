#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續六十五:出貨地圖戰場的傾印。保護模式停住後讀 [0x53a45] 單位陣列、[0x53beb] 筆數、[0x53a51] 地圖格、[0x53a69] 地形表、
# [0x53ac1]/[0x53ac5] 寬高,全部存到 <out>/<tag>_*.bin。
# 用法:terr_dump.sh <instance> <out_dir> <tag>
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=$1; D=$2; tag=$3
mkdir -p $D
dump() { $H mem dump --instance $I --selector 0170 --linear "$1" --bytecount "$2" --out "$3" >/dev/null 2>&1; }
for n in 1 2 3 4 5 6 7 8; do
  $H enter-debugger --instance $I >/dev/null 2>&1; sleep 3
  dump 1efa45 4 $D/${tag}_p45.bin
  p=$(python -X utf8 -c "import struct;print('%x'%struct.unpack('<I',open(r'$D/${tag}_p45.bin','rb').read())[0])" | tr -d '\r')
  case "$p" in 26*|27*) break;; esac
  echo "pointer $p (try $n), re-entering"; $H resume --instance $I >/dev/null 2>&1; sleep 2
done
dump 1efa51 4 $D/${tag}_p51.bin; dump 1efa69 4 $D/${tag}_p69.bin; dump 1efbeb 4 $D/${tag}_pbeb.bin
dump 1efac1 8 $D/${tag}_wh.bin; dump 1efab1 8 $D/${tag}_cursor.bin
read P45 P51 P69 CNT W HH < <(python -X utf8 -c "
import struct
r=lambda f,o=0: struct.unpack_from('<I',open(r'$D/${tag}_'+f+'.bin','rb').read(),o)[0]
print('%x %x %x %d %d %d'%(r('p45'),r('p51'),r('p69'),r('pbeb'),r('wh'),r('wh',4)))" | tr -d '\r')
echo "units=$P45 count=$CNT grid=$P51 terrain=$P69 W=$W H=$HH"
dump $P45 $(printf '%x' $((CNT * 80))) $D/${tag}_units.bin
dump $P51 $(printf '%x' $((4 + 4 * W * HH))) $D/${tag}_grid.bin
dump $P69 1000 $D/${tag}_tt.bin
dump 1f3646 244 $D/${tag}_costrows.bin
dump 1efa12 30 $D/${tag}_mods.bin
echo "dump done"
