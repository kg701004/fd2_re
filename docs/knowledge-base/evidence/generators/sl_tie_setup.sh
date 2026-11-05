#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 0x14b78 同距平手規則的受控場景。前提:除錯器暫停中、玩家回合(第 2 回合開始)。
# 右下空地:#13 在 (24,14);NPC #7 屍體與麻痺的敵人 #14 同在 T = (24,18);麻痺敵人 #15..#18 站 T 的四鄰。
# T 由 mode 0 直接到得了(夥伴不擋路)→ T' = T;0x146d1 把 #14..#18 的格標 0xff → 距離 1 的格全不能落。
# 距離 2 的候選:(24,16)(abs 差 2,清單在第 16 列、較前)與 (23,17)/(25,17)(abs 差 0,第 17 列)。
# 規則預測 (23,17);「同距取清單第一個」預測 (24,16)。
# 活的我方、NPC #5/#6、索爾與 #12 都搬到左上角(曼哈頓 >= 32,超過 0x14121 的 28 上限)。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
a() { printf '%x' $((0x26bdc8 + $1 * 0x50 + $2)); }
xy() { printf '%02x %02x' $1 $2; }
cmds=(
  "SM 0170:$(a 0 0) $(xy 2 0)" "SM 0170:$(a 0 5) 00"
  "SM 0170:$(a 12 0) $(xy 3 0)" "SM 0170:$(a 12 5) 00" "SM 0170:$(a 12 0x26) 01" "SM 0170:$(a 12 0x40) e7 03 e7 03"
  "SM 0170:$(a 1 0) $(xy 0 1)" "SM 0170:$(a 1 5) 80" "SM 0170:$(a 2 0) $(xy 1 1)" "SM 0170:$(a 2 5) 80"
  "SM 0170:$(a 3 0) $(xy 2 1)" "SM 0170:$(a 3 5) 80" "SM 0170:$(a 4 0) $(xy 3 1)" "SM 0170:$(a 4 5) 80"
  "SM 0170:$(a 5 0) $(xy 0 0)" "SM 0170:$(a 6 0) $(xy 1 0)"
  "SM 0170:$(a 7 0) $(xy 24 18)" "SM 0170:$(a 7 5) 01"
  "SM 0170:$(a 13 0) $(xy 24 14)" "SM 0170:$(a 13 5) 00" "SM 0170:$(a 13 0x26) 00"
  "SM 0170:$(a 14 0) $(xy 24 18)" "SM 0170:$(a 15 0) $(xy 24 17)" "SM 0170:$(a 16 0) $(xy 23 18)"
  "SM 0170:$(a 17 0) $(xy 25 18)" "SM 0170:$(a 18 0) $(xy 24 19)"
)
for i in 14 15 16 17 18; do cmds+=("SM 0170:$(a $i 5) 00" "SM 0170:$(a $i 0x26) 03"); done
for i in 11 19 20; do cmds+=("SM 0170:$(a $i 5) 01"); done
for c in "${cmds[@]}"; do
  $H debugger-cmd --instance $I "$c" >/dev/null 2>&1; sleep 0.5
done
$H mem dump --instance $I --selector 0170 --linear 26bdc8 --bytecount 690 --out .wsl_build/ctr/sl/pre_tie.bin >/dev/null 2>&1
echo "setup done tie (${#cmds[@]} commands)"
