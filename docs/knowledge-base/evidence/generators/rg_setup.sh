#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# AI 休息回復(0x13fd4)受控場景。前提:除錯器暫停中、第 1 回合玩家回合。
# 左上一群敵人附近沒有我方(物理 P = 0、沒有法術與道具)→ ai_choose_action 回 0 → 模式 0 的備援 → 0x13fd4。
#   #13 HP 9/28、#14 HP 26/28(封頂)、#15 HP 28/28(不寫)、#16 HP 9/28 且 +0x25 = 1、#17 HP 9/28 且 +0x26 = 1、#18 HP 9/34(floor 6)
# 斷點(執行期 +0x19c000):0x13fd4 入口、0x14012(回 0)、0x1410a(寫入 HP)。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
a() { printf '%x' $((0x26bdc8 + $1 * 0x50 + $2)); }
w2() { printf '%02x %02x' $(($1 & 0xff)) $((($1 >> 8) & 0xff)); }
xy() { printf '%02x %02x' $1 $2; }
party() { cmds+=("SM 0170:$(a $1 0) $(xy $2 $3)" "SM 0170:$(a $1 5) $4"); }
# 敵人:序號 x y HP MaxHP +0x25 +0x26
enemy() {
  cmds+=("SM 0170:$(a $1 0) $(xy $2 $3)" "SM 0170:$(a $1 5) 00" "SM 0170:$(a $1 0x25) $(printf '%02x %02x' $6 $7)"
         "SM 0170:$(a $1 0x40) $(w2 $4) $(w2 $5)" "SM 0170:$(a $1 0x4a) e7 03")
}
cmds=()
party 0 16 15 00
party 1 15 14 80
party 2 23 2 80
party 3 14 14 80
party 4 22 19 80
enemy 11 4 4 28 28 0 0
enemy 13 3 4 9 28 0 0
enemy 14 5 4 26 28 0 0
enemy 15 4 5 28 28 0 0
enemy 16 4 3 9 28 1 0
enemy 17 6 4 9 28 0 1
enemy 18 4 6 9 34 0 0
enemy 12 17 15 999 999 0 0
cmds+=("SM 0170:$(a 12 0x26) 01")
for i in 5 6; do cmds+=("SM 0170:$(a $i 0x40) e7 03 e7 03" "SM 0170:$(a $i 0x4a) e7 03"); done
cmds+=("SM 0170:$(a 5 0) $(xy 12 20)" "SM 0170:$(a 6 0) $(xy 13 20)")
for i in 7 8 9 10 19 20; do cmds+=("SM 0170:$(a $i 5) 01"); done
cmds+=("BP 0170:1affd4" "BP 0170:1b0012" "BP 0170:1b010a")
for c in "${cmds[@]}"; do
  $H debugger-cmd --instance $I "$c" >/dev/null 2>&1; sleep 0.5
done
$H mem dump --instance $I --selector 0170 --linear 26bdc8 --bytecount 690 --out .wsl_build/ctr/rg_pre.bin >/dev/null 2>&1
echo "setup done (${#cmds[@]} commands)"
