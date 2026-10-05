#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 0x14237 物理攻擊候選評分的受控場景。前提:除錯器暫停中、第 1 回合玩家回合。
# 攻方 A = 盜賊 #12 在 (15,3)(平地菱形中心),種族 1、MV 2、AP 100、DP 20、武器改成 item 31(射程 2、+0xb 1)。
# 目標:索爾 #0 (15,0) AP 30 DP 100(+8 == 0,可反擊);#1 (13,5) HP 1、DP 103、麻痺;#2 (17,5) DP 50、AP 30;
#       #4 (18,2) 樹林、種族改 1、DP 55、麻痺。
# 攻方 B = 盜賊 #13 在 (15,15),MV 1、AP 100、DP 20;目標 #3 (15,13) DP 103、麻痺。
# 假人 D = 盜賊 #14 在 (14,0)(索爾打它結束玩家回合),麻痺 3、HP/DP 999。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
D=.wsl_build/ctr/pa
mkdir -p $D
a() { printf '%x' $((0x26bdc8 + $1 * 0x50 + $2)); }
xy() { printf '%02x %02x' $1 $2; }
cmds=(
  "SM 0170:$(a 0 0) $(xy 15 0)" "SM 0170:$(a 0 5) 00" "SM 0170:$(a 0 0x26) 00" "SM 0170:$(a 0 0x48) 1e 00 64 00"
  "SM 0170:$(a 1 0) $(xy 13 5)" "SM 0170:$(a 1 5) 80" "SM 0170:$(a 1 0x26) 03" "SM 0170:$(a 1 0x40) 01 00"
  "SM 0170:$(a 1 0x48) 1e 00 67 00"
  "SM 0170:$(a 2 0) $(xy 17 5)" "SM 0170:$(a 2 5) 80" "SM 0170:$(a 2 0x26) 00" "SM 0170:$(a 2 0x48) 1e 00 32 00"
  "SM 0170:$(a 3 0) $(xy 15 13)" "SM 0170:$(a 3 5) 80" "SM 0170:$(a 3 0x26) 03" "SM 0170:$(a 3 0x48) 1e 00 67 00"
  "SM 0170:$(a 4 0) $(xy 18 2)" "SM 0170:$(a 4 5) 80" "SM 0170:$(a 4 0x26) 03" "SM 0170:$(a 4 0x1f) 01"
  "SM 0170:$(a 4 0x48) 1e 00 37 00"
  "SM 0170:$(a 12 0) $(xy 15 3)" "SM 0170:$(a 12 5) 00" "SM 0170:$(a 12 0x26) 00" "SM 0170:$(a 12 0x3b) 02"
  "SM 0170:$(a 12 0x40) e7 03 e7 03" "SM 0170:$(a 12 0x48) 64 00 14 00" "SM 0170:$(a 12 0xb) 1f"
  "SM 0170:$(a 13 0) $(xy 15 15)" "SM 0170:$(a 13 5) 00" "SM 0170:$(a 13 0x26) 00" "SM 0170:$(a 13 0x3b) 01"
  "SM 0170:$(a 13 0x40) e7 03 e7 03" "SM 0170:$(a 13 0x48) 64 00 14 00"
  "SM 0170:$(a 14 0) $(xy 14 0)" "SM 0170:$(a 14 5) 00" "SM 0170:$(a 14 0x26) 03"
  "SM 0170:$(a 14 0x40) e7 03 e7 03" "SM 0170:$(a 14 0x4a) e7 03"
)
for i in 11 15 16 17 18 19 20; do cmds+=("SM 0170:$(a $i 5) 01"); done
cmds+=("BP 0170:1b0237" "BP 0170:1b0368" "BP 0170:1b04c5" "BP 0170:1b059f" "BP 0170:1b148e")
for c in "${cmds[@]}"; do
  $H debugger-cmd --instance $I "$c" >/dev/null 2>&1; sleep 0.5
done
$H mem dump --instance $I --selector 0170 --linear 26bdc8 --bytecount 690 --out $D/pre.bin >/dev/null 2>&1
$H mem dump --instance $I --selector 0170 --linear 21934c --bytecount 8e0 --out $D/map0.bin >/dev/null 2>&1
$H mem dump --instance $I --selector 0170 --linear 22841c --bytecount 1000 --out $D/tt.bin >/dev/null 2>&1
$H mem dump --instance $I --selector 0170 --linear 1eda12 --bytecount 30 --out $D/mods.bin >/dev/null 2>&1
$H mem dump --instance $I --selector 0170 --linear 1efab1 --bytecount 8 --out $D/cursor.bin >/dev/null 2>&1
echo "setup done (${#cmds[@]} commands)"
