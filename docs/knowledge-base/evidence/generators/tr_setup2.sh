#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續六十四第 2 回合。第 1 回合 E2 站在屋頂(型別 1,步行 row 7 成本 20)動不了,只有 1 個候選格。
# 本回合 E2 = #13 移到平地 (14,14) MV 1,item 77 +0xc 再改 0x13(十字半徑 3,+0xb 2)。
#   #4 (14,12) 未麻痺、無裝備武器:從 (14,13) 相鄰 → 十字照收(內圈 2 不排除)、0x1debe 走無武器分支回 -1。
#   NPC 麻痺 #9 (11,14) HP 42 DP 8;#8 (16,15) HP 36 DP 11;#5 移到 (25,4) 不參與。
# S1 原樣重做一次:#1 被 0x1548e 保護改成 DP 999,改回 60;#1..#4 +5 = 0x80。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
D=.wsl_build/ctr/tr
a() { printf '%x' $((0x26bdc8 + $1 * 0x50 + $2)); }
xy() { printf '%02x %02x' $1 $2; }
cmds=(
  "SM 0170:1f29a4 13"
  "SM 0170:$(a 0 5) 00"
  "SM 0170:$(a 1 0x40) e7 03 e7 03" "SM 0170:$(a 1 0x4a) 3c 00"
  "SM 0170:$(a 4 0) $(xy 14 12)" "SM 0170:$(a 4 0x26) 00"
  "SM 0170:$(a 12 0) $(xy 5 8)" "SM 0170:$(a 12 0x40) e7 03 e7 03"
  "SM 0170:$(a 13 0) $(xy 14 14)" "SM 0170:$(a 13 0x40) e7 03 e7 03"
  "SM 0170:$(a 14 0x26) 03"
  "SM 0170:$(a 5 0) $(xy 25 4)"
  "SM 0170:$(a 9 0) $(xy 11 14)" "SM 0170:$(a 9 0x40) 2a 00" "SM 0170:$(a 9 0x4a) 08 00"
  "SM 0170:$(a 8 0) $(xy 16 15)" "SM 0170:$(a 8 0x40) 24 00" "SM 0170:$(a 8 0x4a) 0b 00"
)
for i in 1 2 3 4; do cmds+=("SM 0170:$(a $i 5) 80"); done
for i in 5 6 7 8 9 10; do cmds+=("SM 0170:$(a $i 0x26) 03"); done
for c in "${cmds[@]}"; do
  $H debugger-cmd --instance $I "$c" >/dev/null 2>&1; sleep 0.5
done
dump() { $H mem dump --instance $I --selector 0170 --linear "$1" --bytecount "$2" --out "$3" >/dev/null 2>&1; }
dump 26bdc8 690 $D/post2_units.bin
dump 21934c 8e0 $D/post2_map.bin
dump 1f2998 17 $D/post2_item77.bin
dump 1efab1 8 $D/cursor2.bin
echo "setup2 done (${#cmds[@]} commands)"
