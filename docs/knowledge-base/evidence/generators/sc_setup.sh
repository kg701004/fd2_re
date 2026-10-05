#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# AI 法術評分(0x1598a / 0x15b77)受控場景設定。前提:除錯器暫停中、玩家回合開始。
# 用法:sc_setup.sh <#2 的 HP> <#1 的 HP> <盜賊 #11 的 MP> <標籤>
# 盜賊 #11 搬到 (19,17),只會法術 8(聖光彈)與 12(裂地術),拿掉武器;NPC #5 在 (10,17)(距離 9)、#6 在 (9,17)(距離 10),
# 兩者 +0x26=1、其他 NPC 與 #13..#20 設 +5 bit0(移出目標清單與行動);#12 在 (21,14) 當索爾的攻擊對象(HP 999、不反擊)。
# 隊員 #1..#4 設已行動,只剩索爾 #0 可動。斷點(執行期 +0x19c000):0x1598a 入口、0x15add(評分回傳)、0x15b6d(出口)、0x15311。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
hp2=$1; hp1=$2; mp=$3; tag=$4
a() { printf '%x' $((0x26bdc8 + $1 * 0x50 + $2)); }
w2() { printf '%02x %02x' $(($1 & 0xff)) $((($1 >> 8) & 0xff)); }
cmds=(
  "SM 0170:$(a 0 5) 00"
  "SM 0170:$(a 1 5) 80" "SM 0170:$(a 2 5) 80" "SM 0170:$(a 3 5) 80" "SM 0170:$(a 4 5) 80"
  "SM 0170:$(a 1 0x40) $(w2 $hp1)"
  "SM 0170:$(a 2 0x40) $(w2 $hp2)"
  "SM 0170:$(a 5 0) 0a 11" "SM 0170:$(a 5 0x26) 01"
  "SM 0170:$(a 6 0) 09 11" "SM 0170:$(a 6 0x26) 01"
  "SM 0170:$(a 11 0) 13 11" "SM 0170:$(a 11 5) 00" "SM 0170:$(a 11 0xa) 00"
  "SM 0170:$(a 11 0x1a) 00 11 00 00 00" "SM 0170:$(a 11 0x44) $(w2 $mp) $(w2 $mp)"
  "SM 0170:$(a 12 0) 15 0e" "SM 0170:$(a 12 0x26) 01" "SM 0170:$(a 12 0x40) e7 03 e7 03"
)
for i in 7 8 9 10 13 14 15 16 17 18 19 20; do cmds+=("SM 0170:$(a $i 5) 01"); done
# 其餘隊員 HP 回滿(索爾 823、#3 867、#4 918);RACES="單位:種族 ..." 改種族(+0x1f)
cmds+=("SM 0170:$(a 0 0x40) $(w2 823)" "SM 0170:$(a 3 0x40) $(w2 867)" "SM 0170:$(a 4 0x40) $(w2 918)")
for ur in ${RACES:-}; do cmds+=("SM 0170:$(a ${ur%%:*} 0x1f) $(printf '%02x' ${ur##*:})"); done
cmds+=("BP 0170:1b198a" "BP 0170:1b1add" "BP 0170:1b1b6d" "BP 0170:1b1311")
for c in "${cmds[@]}"; do
  $H debugger-cmd --instance $I "$c" >/dev/null 2>&1; sleep 0.7
done
$H mem dump --instance $I --selector 0170 --linear 26bdc8 --bytecount 690 --out .wsl_build/ctr/sc_pre_$tag.bin >/dev/null 2>&1
echo "setup done $tag"
