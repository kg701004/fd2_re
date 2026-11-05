#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 0x14237 第 2 輪(第 2 回合)。第 1 輪發現 0x14237 的地形閘門與實戰相反(0x1f183 回 0 才跳過),
# 所以種族 1 的盜賊攻方不修正 AP;本輪用 DP 98 讓原始分數正好是 2。
# A = #12 (15,3) MV 2 AP 100 DP 20 武器 31:#1 (13,5) HP 1 DP 98 麻痺 → 2 > HP → 0x12、×2;
#     #2 (17,5) DP 50;#4 (18,2) 樹林、種族 5(套地形)DP 55;索爾 (15,0) DP 95、AP 30。
# B = #13 (15,15) MV 1:#3 (15,13) DP 98 麻痺 → 原始 2、優先級 0,應被記下但不攻擊。
# C = #15 (4,19) MV 1 武器 0:NPC #7 復活在 (4,17)、麻痺、HP 42、DP 8 → 92 > HP → 0x12、184。
# 假人 D = #14 (14,0) 麻痺 3。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
D=.wsl_build/ctr/pa
a() { printf '%x' $((0x26bdc8 + $1 * 0x50 + $2)); }
xy() { printf '%02x %02x' $1 $2; }
cmds=(
  "SM 0170:$(a 0 0) $(xy 15 0)" "SM 0170:$(a 0 5) 00" "SM 0170:$(a 0 0x26) 00" "SM 0170:$(a 0 0x48) 1e 00 5f 00"
  "SM 0170:$(a 1 0) $(xy 13 5)" "SM 0170:$(a 1 5) 80" "SM 0170:$(a 1 0x26) 03" "SM 0170:$(a 1 0x40) 01 00"
  "SM 0170:$(a 1 0x48) 1e 00 62 00"
  "SM 0170:$(a 2 0) $(xy 17 5)" "SM 0170:$(a 2 5) 80" "SM 0170:$(a 2 0x26) 00" "SM 0170:$(a 2 0x48) 1e 00 32 00"
  "SM 0170:$(a 3 0) $(xy 15 13)" "SM 0170:$(a 3 5) 80" "SM 0170:$(a 3 0x26) 03" "SM 0170:$(a 3 0x48) 1e 00 62 00"
  "SM 0170:$(a 4 0) $(xy 18 2)" "SM 0170:$(a 4 5) 80" "SM 0170:$(a 4 0x26) 03" "SM 0170:$(a 4 0x1f) 05"
  "SM 0170:$(a 4 0x48) 1e 00 37 00"
  "SM 0170:$(a 7 0) $(xy 4 17)" "SM 0170:$(a 7 5) 00" "SM 0170:$(a 7 0x26) 03" "SM 0170:$(a 7 0x40) 2a 00"
  "SM 0170:$(a 12 0) $(xy 15 3)" "SM 0170:$(a 12 5) 00" "SM 0170:$(a 12 0x26) 00" "SM 0170:$(a 12 0x3b) 02"
  "SM 0170:$(a 12 0x40) e7 03 e7 03" "SM 0170:$(a 12 0x48) 64 00 14 00" "SM 0170:$(a 12 0xb) 1f"
  "SM 0170:$(a 13 0) $(xy 15 15)" "SM 0170:$(a 13 5) 00" "SM 0170:$(a 13 0x26) 00" "SM 0170:$(a 13 0x3b) 01"
  "SM 0170:$(a 13 0x40) e7 03 e7 03" "SM 0170:$(a 13 0x48) 64 00 14 00"
  "SM 0170:$(a 14 0) $(xy 14 0)" "SM 0170:$(a 14 5) 00" "SM 0170:$(a 14 0x26) 03"
  "SM 0170:$(a 14 0x40) e7 03 e7 03" "SM 0170:$(a 14 0x4a) e7 03"
  "SM 0170:$(a 15 0) $(xy 4 19)" "SM 0170:$(a 15 5) 00" "SM 0170:$(a 15 0x26) 00" "SM 0170:$(a 15 0x3b) 01"
  "SM 0170:$(a 15 0x40) e7 03 e7 03" "SM 0170:$(a 15 0x48) 64 00 14 00"
)
for i in 11 16 17 18 19 20; do cmds+=("SM 0170:$(a $i 5) 01"); done
cmds+=("BP 0170:1b0237" "BP 0170:1b0368" "BP 0170:1b04c5" "BP 0170:1b059f" "BP 0170:1b148e")
for c in "${cmds[@]}"; do
  $H debugger-cmd --instance $I "$c" >/dev/null 2>&1; sleep 0.5
done
$H mem dump --instance $I --selector 0170 --linear 26bdc8 --bytecount 690 --out $D/pre2.bin >/dev/null 2>&1
$H mem dump --instance $I --selector 0170 --linear 1efab1 --bytecount 8 --out $D/cursor_r2.bin >/dev/null 2>&1
echo "setup done (${#cmds[@]} commands)"
