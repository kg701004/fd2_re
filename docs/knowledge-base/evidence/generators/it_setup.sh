#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# AI 道具評分(0x1567e / 0x15880)與道具分支受控場景。前提:除錯器暫停中、第 1 回合玩家回合。
#   左上 #11 在 (4,4),slot2 = 道具 58(恢復,type 0xd,距離 2、範圍 0);四周己方 #13 HP 9、#14 HP 14、#15 HP 15、#16 HP 10(+0x34 bit7),MaxHP 28;附近沒有我方(P = 0)
#   右上 #17 道具 38(type 0x15,數值 = 法術 1 的 120)→ #2 HP 120:I 0x12 > P 8 → 道具
#   右下 #18 道具 38 → #4 HP 121、+0x34 bit 0x40:I 8 = P 8 → 物理
#   左下 #19 道具 38 → #3 HP 121:I 8 = P 8、bit 0 → 道具
#   中央:索爾 (16,15)、悠妮 (15,14)、#12 (17,15) 給索爾打。我方 DP 0;敵人與 NPC DP 999。
# 斷點(執行期 +0x19c000):0x157fd(道具評分回傳)、0x14f62(決策點)、0x1548e、0x15311、0x15055。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
a() { printf '%x' $((0x26bdc8 + $1 * 0x50 + $2)); }
w2() { printf '%02x %02x' $(($1 & 0xff)) $((($1 >> 8) & 0xff)); }
xy() { printf '%02x %02x' $1 $2; }
party() { cmds+=("SM 0170:$(a $1 0) $(xy $2 $3)" "SM 0170:$(a $1 5) $5" "SM 0170:$(a $1 0x40) $(w2 $4)" "SM 0170:$(a $1 0x4a) 00 00"); }
# 敵人:序號 x y AP slot2 道具(0 = 不放) +0x34 HP
enemy() {
  cmds+=("SM 0170:$(a $1 0) $(xy $2 $3)" "SM 0170:$(a $1 5) 00" "SM 0170:$(a $1 0x26) 00"
         "SM 0170:$(a $1 0x48) $(w2 $4) e7 03" "SM 0170:$(a $1 0x34) $6" "SM 0170:$(a $1 0x40) $(w2 $7)")
  if [ "$5" != 0 ]; then cmds+=("SM 0170:$(a $1 0xe) 00 $(printf '%02x' $5)"); fi
}
cmds=()
party 0 16 15 823 00
party 1 15 14 782 80
party 2 23 2 120 80
party 3 2 15 121 80
party 4 22 19 121 80
enemy 11 4 4 50 58 00 28
enemy 13 3 4 50 0 00 9
enemy 14 5 4 50 0 00 14
enemy 15 4 5 50 0 00 15
enemy 16 4 3 50 0 80 10
enemy 17 22 2 50 38 00 28
enemy 18 21 19 50 38 40 28
enemy 19 3 15 50 38 00 28
enemy 12 17 15 50 0 00 999
cmds+=("SM 0170:$(a 12 0x26) 01")
for i in 5 6; do cmds+=("SM 0170:$(a $i 0x40) e7 03 e7 03" "SM 0170:$(a $i 0x4a) e7 03"); done
cmds+=("SM 0170:$(a 5 0) $(xy 12 20)" "SM 0170:$(a 6 0) $(xy 13 20)")
for i in 7 8 9 10 20; do cmds+=("SM 0170:$(a $i 5) 01"); done
cmds+=("BP 0170:1b17fd" "BP 0170:1b0f62" "BP 0170:1b148e" "BP 0170:1b1311" "BP 0170:1b1055")
for c in "${cmds[@]}"; do
  $H debugger-cmd --instance $I "$c" >/dev/null 2>&1; sleep 0.5
done
$H mem dump --instance $I --selector 0170 --linear 26bdc8 --bytecount 690 --out .wsl_build/ctr/it_pre.bin >/dev/null 2>&1
echo "setup done (${#cmds[@]} commands)"
