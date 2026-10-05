#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 真實擊殺後屍體座標是否保留:受控場景。前提:除錯器暫停中、玩家回合(第 1 回合)。
# NPC #7 活著在 (1,7):HP 1、DP 0、麻痺 3(NPC 階段不動);敵人 #11 在 (2,7) 緊鄰 #7(HP/DP 999),由它真的打死 #7。
# 敵人 #13 在 (1,1):活目標都在 30 格外;#11 先行動(索引小),#13 在擊殺之後才走備援移動。
# 若屍體保留座標 → 0x14b78 目標 (1,7);若死亡時座標被清掉/移走 → 目標索爾 (22,15)。
# 斷點(執行期 +0x19c000):0x14121 入口/0x141cd/0x14230、0x13e9c、0x14b78、0x13fd4、死亡旗標寫入 0x1dc61 / 0x1dd4c。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
a() { printf '%x' $((0x26bdc8 + $1 * 0x50 + $2)); }
xy() { printf '%02x %02x' $1 $2; }
cmds=(
  "SM 0170:$(a 0 0) $(xy 22 15)" "SM 0170:$(a 0 5) 00"
  "SM 0170:$(a 1 0) $(xy 20 18)" "SM 0170:$(a 1 5) 80" "SM 0170:$(a 2 0) $(xy 21 18)" "SM 0170:$(a 2 5) 80"
  "SM 0170:$(a 3 0) $(xy 22 18)" "SM 0170:$(a 3 5) 80" "SM 0170:$(a 4 0) $(xy 23 18)" "SM 0170:$(a 4 5) 80"
  "SM 0170:$(a 5 0) $(xy 25 17)" "SM 0170:$(a 6 0) $(xy 26 17)"
  "SM 0170:$(a 7 0) $(xy 1 7)" "SM 0170:$(a 7 5) 00" "SM 0170:$(a 7 0x26) 03" "SM 0170:$(a 7 0x40) 01 00" "SM 0170:$(a 7 0x4a) 00 00"
  "SM 0170:$(a 8 0) $(xy 24 20)" "SM 0170:$(a 8 5) 01" "SM 0170:$(a 9 0) $(xy 25 20)" "SM 0170:$(a 9 5) 01"
  "SM 0170:$(a 10 0) $(xy 26 20)" "SM 0170:$(a 10 5) 01"
  "SM 0170:$(a 11 0) $(xy 2 7)" "SM 0170:$(a 11 5) 00" "SM 0170:$(a 11 0x26) 00" "SM 0170:$(a 11 0x40) e7 03 e7 03" "SM 0170:$(a 11 0x4a) e7 03"
  "SM 0170:$(a 13 0) $(xy 1 1)" "SM 0170:$(a 13 5) 00" "SM 0170:$(a 13 0x26) 00"
  "SM 0170:$(a 12 0) $(xy 23 15)" "SM 0170:$(a 12 5) 00" "SM 0170:$(a 12 0x26) 01" "SM 0170:$(a 12 0x40) e7 03 e7 03"
)
for i in 14 15 16 17 18 19 20; do cmds+=("SM 0170:$(a $i 5) 01"); done
cmds+=("BP 0170:1b0121" "BP 0170:1b01cd" "BP 0170:1b0230" "BP 0170:1afe9c" "BP 0170:1b0b78" "BP 0170:1affd4" "BP 0170:1b9c61" "BP 0170:1b9d4c")
for c in "${cmds[@]}"; do
  $H debugger-cmd --instance $I "$c" >/dev/null 2>&1; sleep 0.5
done
$H mem dump --instance $I --selector 0170 --linear 26bdc8 --bytecount 690 --out .wsl_build/ctr/kc_pre.bin >/dev/null 2>&1
echo "setup done (${#cmds[@]} commands)"
