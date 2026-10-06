#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續六十五:map_attack_resolve 在出貨地圖地形上的受控交手(敵方回合、[0x53af9] = 1)。
# 敵 E 留在原格、MV 0、清法術與 MP、AP eap、DP edp、HIT 250、EV 0、HP 999;我方 P(種族 1)以 SM 搬到 (px,py)、AP pap、DP pdp、HIT 250、EV 0、HP 999。
# 其他敵人麻痺 9;我方除 R 外全部已行動,R 移一格(方向 DIR)休息以結束玩家回合。斷點 0x1edbf / 0x1ee04 / 0x1548e。
# 用法:map_atk.sh <instance> <out_dir> <tag> <units_base_hex> <unit_count> <E> <eap> <edp> <P> <px> <py> <pap> <pdp> <R>
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=$1; D=$2; tag=$3; UB=$4; N=$5; E=$6; EAP=$7; EDP=$8; P=$9; PX=${10}; PY=${11}; PAP=${12}; PDP=${13}; R=${14}
S=/c/Users/kg701/AppData/Local/Temp/claude/C--Users-kg701-Desktop-AI-stock-AI/064f5671-708e-478d-aa85-2e95400484d6/scratchpad
mkdir -p $D
a() { printf '%x' $((0x$UB + $1 * 0x50 + $2)); }
w2() { printf '%02x %02x' $(($1 & 0xff)) $((($1 >> 8) & 0xff)); }
PTR=$(printf '%08x' $((0x$UB)) | sed 's/\(..\)\(..\)\(..\)\(..\)/\4\3\2\1/')
halt() {
  for n in 1 2 3 4 5 6; do
    $H enter-debugger --instance $I >/dev/null 2>&1; sleep 3
    $H mem dump --instance $I --selector 0170 --linear 1efa45 --bytecount 4 --out $D/chk.bin >/dev/null 2>&1
    p=$(python -c "print(open('$D/chk.bin','rb').read().hex())")
    [ "$p" = "$PTR" ] && return 0
    $H resume --instance $I >/dev/null 2>&1; sleep 2
  done
  echo "halt failed"; return 1
}
halt || exit 1
cmds=("SM 0170:1efaf9 01"
  "SM 0170:$(a $E 0x3b) 00" "SM 0170:$(a $E 0x1a) 00 00 00 00 00" "SM 0170:$(a $E 0x44) 00 00 00 00" "SM 0170:$(a $E 0x26) 00"
  "SM 0170:$(a $E 0x40) e7 03 e7 03" "SM 0170:$(a $E 0x48) $(w2 $EAP) $(w2 $EDP) fa 00 00 00"
  "SM 0170:$(a $P 0) $(printf '%02x %02x' $PX $PY)" "SM 0170:$(a $P 0x40) e7 03 e7 03" "SM 0170:$(a $P 0x26) 00"
  "SM 0170:$(a $P 0x48) $(w2 $PAP) $(w2 $PDP) fa 00 00 00")
[ -n "${EX:-}" ] && cmds+=("SM 0170:$(a $E 0) $(printf '%02x %02x' $EX $EY)")
for i in $(seq 0 $((N - 1))); do
  [ $i -eq $E ] && continue
  cmds+=("SM 0170:$(a $i 0x26) 09")
done
for c in "${cmds[@]}"; do $H debugger-cmd --instance $I "$c" >/dev/null 2>&1; sleep 0.3; done
# 我方:除 R 以外設已行動(陣營 2 才改)
python -X utf8 -c "
u=open(r'$D/chk.bin','rb').read()" >/dev/null
$H mem dump --instance $I --selector 0170 --linear $UB --bytecount $(printf '%x' $((N * 80))) --out $D/${tag}_pre_units.bin >/dev/null 2>&1
for i in $(python -X utf8 -c "
u=open(r'$D/${tag}_pre_units.bin','rb').read()
print(' '.join(str(i) for i in range(len(u)//80) if u[i*80+6]==2 and not u[i*80+5]&1 and i!=$R))" | tr -d '\r'); do
  $H debugger-cmd --instance $I "SM 0170:$(a $i 5) 80" >/dev/null 2>&1; sleep 0.25
done
# 我方 P 被設麻痺 0、已行動 —— 但麻痺也會擋反擊,上面已清 0;其他單位的麻痺 9 也套到了我方,不影響(他們不出手)
$H debugger-cmd --instance $I "SM 0170:$(a $P 0x26) 00" >/dev/null 2>&1; sleep 0.3
$H mem dump --instance $I --selector 0170 --linear $UB --bytecount $(printf '%x' $((N * 80))) --out $D/${tag}_pre_units.bin >/dev/null 2>&1
for c in "BP 0170:1badbf" "BP 0170:1bae04" "BP 0170:1b148e" "BP 0170:1bafce" "BP 0170:1b1311"; do $H debugger-cmd --instance $I "$c" >/dev/null 2>&1; sleep 0.5; done
$H resume --instance $I >/dev/null 2>&1; sleep 2
$H key --instance $I --wait 1.5 Escape >/dev/null 2>&1
$H key --instance $I --wait 1.5 Return >/dev/null 2>&1
$H key --instance $I --wait 0.8 ${DIR:-Up} >/dev/null 2>&1
$H key --instance $I --wait 3 Return >/dev/null 2>&1
sleep 2
$H screenshot --instance $I --out $D/${tag}_ring.png >/dev/null 2>&1
$H key --instance $I --wait 1.3 Down >/dev/null 2>&1
$H key --instance $I --wait 2.5 Return >/dev/null 2>&1
rm -f $D/${tag}_stops.txt
IDLE=${IDLE:-8} bash $S/phase_log.sh $I $D $tag $UB $(printf '%x' $((N * 80)))
halt
$H debugger-cmd --instance $I "BPDEL *" >/dev/null 2>&1
$H mem dump --instance $I --selector 0170 --linear $UB --bytecount $(printf '%x' $((N * 80))) --out $D/${tag}_post_units.bin >/dev/null 2>&1
python -X utf8 -c "
import struct
for ph in ('pre','post'):
    u=open(r'$D/${tag}_'+ph+'_units.bin','rb').read()
    print(ph,[(i,(u[i*80],u[i*80+1]),struct.unpack_from('<H',u,i*80+0x40)[0],hex(u[i*80+5])) for i in ($E,$P)])
print('E ptr %x P ptr %x' % (0x$UB+$E*80, 0x$UB+$P*80))"
$H resume --instance $I >/dev/null 2>&1
