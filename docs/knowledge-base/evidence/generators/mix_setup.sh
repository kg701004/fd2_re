#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# AI 物理/法術勝者選擇(0x14ef0 的 0x14f62..0x15050)受控場景。前提:除錯器暫停中、第 1 回合玩家回合。
# 四個角落各放一組「敵人 + 專屬我方目標」,中央放索爾與恢復術的兩個敵人;所有我方 DP 0,NPC 與敵人 DP 999(互打不掉血)。
#   左上 #11 AP 100 會法術 8 → 悠妮 #1 HP 300:物理優先級 8、法術 24 → 施法
#   右上 #13 AP 441 會法術 8 → #2 HP 999:8 = 8,法術 < 11,440 < 441 → 物理
#   左下 #14 AP 501 會法術 8 → #3 HP 500:物理 0x12(501 > 500)> 8 → 物理
#   右下 #15 AP 440 會法術 8 → #4 HP 999:8 = 8,440 < 440 不成立 → 施法
#   中央 #16 / #17 會法術 13,#18 HP 5 當恢復目標;物理打索爾(HP 823):8 = 8,法術 >= 11 → #16(+0x34 bit 0x40)物理、#17 施法
# 斷點(執行期 +0x19c000):0x14f62(決策點)、0x1548e(物理)、0x15311(法術)、0x15055(道具)。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
a() { printf '%x' $((0x26bdc8 + $1 * 0x50 + $2)); }
w2() { printf '%02x %02x' $(($1 & 0xff)) $((($1 >> 8) & 0xff)); }
xy() { printf '%02x %02x' $1 $2; }
# 我方:序號 x y HP f5
party() { cmds+=("SM 0170:$(a $1 0) $(xy $2 $3)" "SM 0170:$(a $1 5) $5" "SM 0170:$(a $1 0x40) $(w2 $4)" "SM 0170:$(a $1 0x4a) 00 00"); }
# 敵人:序號 x y AP 法術位元欄(5 bytes) +0x34 HP
enemy() {
  cmds+=("SM 0170:$(a $1 0) $(xy $2 $3)" "SM 0170:$(a $1 5) 00" "SM 0170:$(a $1 0x26) 00"
         "SM 0170:$(a $1 0x48) $(w2 $4) e7 03" "SM 0170:$(a $1 0x1a) $5" "SM 0170:$(a $1 0x34) $6"
         "SM 0170:$(a $1 0x40) $(w2 $7)" "SM 0170:$(a $1 0x44) 64 00 64 00")
}
cmds=()
party 0 16 15 823 00
party 1 3 3 300 80
party 2 23 2 999 80
party 3 2 15 500 80
party 4 22 19 999 80
enemy 11 4 3 100 "00 01 00 00 00" 00 28
enemy 13 22 2 441 "00 01 00 00 00" 00 28
enemy 14 3 15 501 "00 01 00 00 00" 00 28
enemy 15 21 19 440 "00 01 00 00 00" 00 28
enemy 16 16 17 100 "00 20 00 00 00" 40 28
enemy 17 15 17 100 "00 20 00 00 00" 00 28
enemy 18 14 17 100 "00 00 00 00 00" 00 5
enemy 12 17 15 100 "00 00 00 00 00" 00 999
cmds+=("SM 0170:$(a 12 0x26) 01")
# NPC #5/#6 留著(全部 NPC 設 bit0 會回到標題畫面),HP / DP 999;其餘 NPC 與 #19/#20 設 +5 bit0
for i in 5 6; do cmds+=("SM 0170:$(a $i 0x40) e7 03 e7 03" "SM 0170:$(a $i 0x4a) e7 03"); done
cmds+=("SM 0170:$(a 5 0) $(xy 12 20)" "SM 0170:$(a 6 0) $(xy 13 20)")
for i in 7 8 9 10 19 20; do cmds+=("SM 0170:$(a $i 5) 01"); done
cmds+=("BP 0170:1b0f62" "BP 0170:1b148e" "BP 0170:1b1311" "BP 0170:1b1055")
for c in "${cmds[@]}"; do
  $H debugger-cmd --instance $I "$c" >/dev/null 2>&1; sleep 0.5
done
$H mem dump --instance $I --selector 0170 --linear 26bdc8 --bytecount 690 --out .wsl_build/ctr/mix_pre.bin >/dev/null 2>&1
echo "setup done (${#cmds[@]} commands)"
