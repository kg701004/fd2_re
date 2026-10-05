#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# AI 備援移動(0x14121 / 0x13e9c)受控場景。前提:除錯器暫停中、玩家回合。
# 用法:mv_setup.sh <屍體 NPC #7 的 x> <y> <標籤>
# 敵人 #13 在 (1,1)(左上角),其餘敵人設 +5 bit0(#12 除外,給索爾打);我方與活的 NPC #5/#6 都在右下(曼哈頓距離 >= 36,超過 0x14121 的 0x1c 搜尋上限);
# NPC #7 設 +5 bit0(屍體)放在指定位置,#8..#10 屍體移到右下角。
# 斷點:0x14b78 內部各段(見 sl_log.sh)。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
cx=$1; cy=$2; tag=$3
a() { printf '%x' $((0x26bdc8 + $1 * 0x50 + $2)); }
xy() { printf '%02x %02x' $1 $2; }
cmds=(
  "SM 0170:$(a 0 0) $(xy 22 15)" "SM 0170:$(a 0 5) 00"
  "SM 0170:$(a 1 0) $(xy 20 18)" "SM 0170:$(a 1 5) 80" "SM 0170:$(a 2 0) $(xy 21 18)" "SM 0170:$(a 2 5) 80"
  "SM 0170:$(a 3 0) $(xy 22 18)" "SM 0170:$(a 3 5) 80" "SM 0170:$(a 4 0) $(xy 23 18)" "SM 0170:$(a 4 5) 80"
  "SM 0170:$(a 5 0) $(xy 25 17)" "SM 0170:$(a 6 0) $(xy 26 17)"
  "SM 0170:$(a 7 0) $(xy $cx $cy)" "SM 0170:$(a 7 5) 01"
  "SM 0170:$(a 8 0) $(xy 24 20)" "SM 0170:$(a 8 5) 01" "SM 0170:$(a 9 0) $(xy 25 20)" "SM 0170:$(a 9 5) 01"
  "SM 0170:$(a 10 0) $(xy 26 20)" "SM 0170:$(a 10 5) 01"
  "SM 0170:$(a 13 0) $(xy 1 1)" "SM 0170:$(a 13 5) 00" "SM 0170:$(a 13 0x26) 00"
  "SM 0170:$(a 12 0) $(xy 23 15)" "SM 0170:$(a 12 5) 00" "SM 0170:$(a 12 0x26) 01" "SM 0170:$(a 12 0x40) e7 03 e7 03"
)
for i in 11 14 15 16 17 18 19 20; do cmds+=("SM 0170:$(a $i 5) 01"); done
cmds+=("BP 0170:1b0b78" "BP 0170:1b0c42" "BP 0170:1b0c85" "BP 0170:1b0ccf" "BP 0170:1b0d37" "BP 0170:1b0d95" "BP 0170:1b0da1" "BP 0170:1b0e5b" "BP 0170:1b0ec4")
for c in "${cmds[@]}"; do
  $H debugger-cmd --instance $I "$c" >/dev/null 2>&1; sleep 0.5
done
$H mem dump --instance $I --selector 0170 --linear 26bdc8 --bytecount 690 --out .wsl_build/ctr/sl/pre_$tag.bin >/dev/null 2>&1
echo "setup done $tag (${#cmds[@]} commands)"
