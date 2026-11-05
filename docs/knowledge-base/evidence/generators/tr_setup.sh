#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 0x14237 未驗證三項(續六十四)。前提:除錯器暫停中、第 1 回合玩家回合、[0x53a45] 已讀到 c8bd2600。
# S1 地形 3..5 + 弓:地形表 tile 2/3/6 的 +1 改成 3/4/5;地圖格 (6,8)→tile 3、(4,7)→tile 2、(5,10)→tile 6。
#   攻方 E1 = #12 (5,8) 種族 5(0x1f183 回 1 → 攻方套地形)、MV 1、AP 100、DP 20、item 31(射程 1..2)。
#   候選格型別:(5,7)=3、(4,8)=0、(5,8)=5、(6,8)=4、(5,9)=0。
#   目標(種族 5、未麻痺、AP 50、DP 60):#1 (6,7) 型別 4、裝 item 44(弓,+0xb 2);#2 (4,7) 型別 3、item 31;
#   #3 (5,10) 型別 5、item 31。
# S2 射程 >= 0x10:item 77 列 +0xc 06 → 0x13(十字半徑 3,執行期在 E2 的 0x14237 迴圈結束時改回)。
#   攻方 E2 = #13 (15,9) 種族 1、MV 1、AP 100、DP 20、item 77。
#   目標:#4 (14,8) 未麻痺、武器全部卸下(0x1debe 無武器分支);NPC 麻痺:#5 (15,12) HP 42 DP 0、#6 (16,10) HP 36 DP 11、
#   #8 (12,9) HP 36 DP 11、#9 (13,9) HP 42 DP 8。
# 索爾留在原位 (20,14),假人 #14 (19,14) 麻痺。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
D=.wsl_build/ctr/tr
mkdir -p $D
a() { printf '%x' $((0x26bdc8 + $1 * 0x50 + $2)); }
xy() { printf '%02x %02x' $1 $2; }
cell() { printf '%x' $((0x21934c + 4 + 4 * ($2 * 27 + $1))); }
tt() { printf '%x' $((0x22841c + 4 * $1 + 1)); }
tgt() {  # 序號 x y 武器旗標 武器
  cmds+=("SM 0170:$(a $1 0) $(xy $2 $3)" "SM 0170:$(a $1 5) 80" "SM 0170:$(a $1 0x26) 00" "SM 0170:$(a $1 0x1f) 05" \
    "SM 0170:$(a $1 0x40) e7 03 e7 03" "SM 0170:$(a $1 0x48) 32 00 3c 00" "SM 0170:$(a $1 0xa) $4 $5")
}
npc() {  # 序號 x y HP DP
  cmds+=("SM 0170:$(a $1 0) $(xy $2 $3)" "SM 0170:$(a $1 0x26) 03" "SM 0170:$(a $1 0x40) $(printf '%02x' $4) 00" \
    "SM 0170:$(a $1 0x4a) $(printf '%02x' $5) 00")
}
cmds=(
  "SM 0170:$(tt 2) 03" "SM 0170:$(tt 3) 04" "SM 0170:$(tt 6) 05"
  "SM 0170:$(cell 6 8) 03 00" "SM 0170:$(cell 4 7) 02 00" "SM 0170:$(cell 5 10) 06 00"
  "SM 0170:1f29a4 13"
  "SM 0170:$(a 0 5) 00" "SM 0170:$(a 0 0x26) 00" "SM 0170:$(a 0 0x40) e7 03 e7 03" "SM 0170:$(a 0 0x4a) e7 03"
)
tgt 1 6 7 40 2c
tgt 2 4 7 40 1f
tgt 3 5 10 40 1f
tgt 4 14 8 00 2b
cmds+=("SM 0170:$(a 4 0xe) 00 5d")
cmds+=(
  "SM 0170:$(a 12 0) $(xy 5 8)" "SM 0170:$(a 12 5) 00" "SM 0170:$(a 12 0x26) 00" "SM 0170:$(a 12 0x1f) 05"
  "SM 0170:$(a 12 0x3b) 01" "SM 0170:$(a 12 0x40) e7 03 e7 03" "SM 0170:$(a 12 0x48) 64 00 14 00" "SM 0170:$(a 12 0xa) 40 1f"
  "SM 0170:$(a 13 0) $(xy 15 9)" "SM 0170:$(a 13 5) 00" "SM 0170:$(a 13 0x26) 00" "SM 0170:$(a 13 0x3b) 01"
  "SM 0170:$(a 13 0x40) e7 03 e7 03" "SM 0170:$(a 13 0x48) 64 00 14 00" "SM 0170:$(a 13 0xa) 40 4d"
  "SM 0170:$(a 14 0) $(xy 19 14)" "SM 0170:$(a 14 5) 00" "SM 0170:$(a 14 0x26) 03"
  "SM 0170:$(a 14 0x40) e7 03 e7 03" "SM 0170:$(a 14 0x4a) e7 03"
)
for i in 11 15 16 17 18 19 20; do cmds+=("SM 0170:$(a $i 5) 01"); done
for i in 7 10; do cmds+=("SM 0170:$(a $i 0x26) 03"); done
npc 5 15 12 42 0
npc 6 16 10 36 11
npc 8 12 9 36 11
npc 9 13 9 42 8
cmds+=("BP 0170:1b0237" "BP 0170:1b0368" "BP 0170:1b049e" "BP 0170:1b04c5" "BP 0170:1b059f" "BP 0170:1b148e")
for c in "${cmds[@]}"; do
  $H debugger-cmd --instance $I "$c" >/dev/null 2>&1; sleep 0.5
done
dump() { $H mem dump --instance $I --selector 0170 --linear "$1" --bytecount "$2" --out "$3" >/dev/null 2>&1; }
dump 26bdc8 690 $D/post_units.bin
dump 21934c 8e0 $D/post_map.bin
dump 22841c 400 $D/post_tt.bin
dump 1f22ad b80 $D/post_items.bin
echo "setup done (${#cmds[@]} commands)"
