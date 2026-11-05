#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續六十五:collect_targets_in_range selector 2..3。悠妮 #1 (23,16) 施放法術 23(距離 3、selector 3、特例內圈 1)。
# 擺位(距悠妮的曼哈頓距離):#3 (23,14) 2、#4 (24,15) 2、#2 (25,17) 3、索爾 #0 (21,18) 4(我方 +6 == 2);
#   NPC #5 (22,16) 1、#6 (23,18) 2、#7 (26,16) 3(+6 == 1);敵 #11 (24,16) 1、#12 (21,16) 2(+6 == 0)。
# 前提:除錯器暫停中、玩家回合第 1 回合。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
D=.wsl_build/ctr/sel
a() { printf '%x' $((0x26bdc8 + $1 * 0x50 + $2)); }
xy() { printf '%02x %02x' $1 $2; }
cmds=(
  "SM 0170:$(a 2 0) $(xy 25 17)" "SM 0170:$(a 0 0) $(xy 21 18)"
  "SM 0170:$(a 5 0) $(xy 22 16)" "SM 0170:$(a 6 0) $(xy 23 18)" "SM 0170:$(a 7 0) $(xy 26 16)"
  "SM 0170:$(a 11 0) $(xy 24 16)" "SM 0170:$(a 12 0) $(xy 21 16)"
)
for c in "${cmds[@]}"; do
  $H debugger-cmd --instance $I "$c" >/dev/null 2>&1; sleep 0.5
done
$H mem dump --instance $I --selector 0170 --linear 26bdc8 --bytecount 690 --out $D/pre_units.bin >/dev/null 2>&1
python -X utf8 -c "
b=open(r'$D/pre_units.bin','rb').read()
for i in (0,1,2,3,4,5,6,7,11,12): r=b[i*80:i*80+80]; print(i,(r[0],r[1]),'side',r[6],'f5',hex(r[5]))"
echo "setup done (${#cmds[@]} commands)"
