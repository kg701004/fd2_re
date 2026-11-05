#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續六十五:出貨地圖上的受控物理攻擊。索爾 #0 搬到 (ax,ay)、種族 1、AP aap、DP 0、HIT 250、EV 0;
# 守方 #def 留在原格(劇本放置的地形 3..5 格),HP 999、AP 19、DP ddp、HIT 250、EV 0、麻痺 1(不反擊)。
# 斷點(執行期 +0x19c000):0x2f8dc(EAX = AP 修正、EDX = 餘數)、0x2f921(DP 修正)、0x2f9fc(傷害)。
# 用法:terr_attack.sh <instance> <out_dir> <tag> <units_base_hex> <ax> <ay> <aap> <def_index> <ddp> <游標按鍵,逗號分隔>
# 前提:除錯器暫停中(保護模式,已確認單位指標)。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=$1; D=$2; tag=$3; ub=$4; ax=$5; ay=$6; aap=$7; di=$8; ddp=$9; keys=${10}
b2() { printf '%02x' "$1"; }
w2() { printf '%02x %02x' $(($1 & 0xff)) $((($1 >> 8) & 0xff)); }
A=$((0x$ub)); B=$((0x$ub + di * 0x50))
ad() { printf '%x' $((A + $1)); }
bd() { printf '%x' $((B + $1)); }
dump() { $H mem dump --instance $I --selector 0170 --linear "$1" --bytecount "$2" --out "$3" >/dev/null 2>&1; }
dump 1eda12 30 $D/${tag}_mods.bin
for c in \
  "SM 0170:$(ad 0) $(b2 $ax) $(b2 $ay)" "SM 0170:$(ad 5) 00" "SM 0170:$(ad 0x1f) 01" \
  "SM 0170:$(ad 0x48) $(w2 $aap) 00 00 fa 00 00 00" \
  "SM 0170:$(bd 0x40) e7 03 e7 03" "SM 0170:$(bd 0x48) 13 00 $(w2 $ddp) fa 00 00 00" "SM 0170:$(bd 0x26) 01" \
  "BP 0170:1cb8dc" "BP 0170:1cb921" "BP 0170:1cb9fc"; do
  $H debugger-cmd --instance $I "$c" >/dev/null 2>&1; sleep 0.8
done
dump $ub $(printf '%x' $(((di + 1) * 0x50))) $D/${tag}_pre_units.bin
$H resume --instance $I >/dev/null 2>&1; sleep 2
if [ -n "$keys" ]; then
  IFS=',' read -ra K <<< "$keys"
  for k in "${K[@]}"; do $H key --instance $I --wait 0.5 "$k" >/dev/null 2>&1; done
  sleep 1
fi
$H screenshot --instance $I --out $D/${tag}_cursor.png >/dev/null 2>&1
for k in Return Return Up Return Return; do $H key --instance $I --wait 1.2 $k >/dev/null 2>&1; done
for n in $(seq 1 12); do
  sleep 3
  p=$(wsl -d Ubuntu tmux -L fd2harness capture-pane -t harness-$I -p)
  if echo "$p" | tail -1 | grep -q Running; then echo "poll $n running"; continue; fi
  eip=$(echo "$p" | grep -o "EIP=[0-9A-F]*" | head -1)
  regs=$(echo "$p" | grep -o -E "E(AX|DX)=[0-9A-F]*" | head -2 | tr '\n' ' ')
  echo "stop: $eip $regs"
  echo "$eip $regs" >> $D/${tag}_stops.txt
  $H resume --instance $I >/dev/null 2>&1
done
$H debugger-cmd --instance $I "BPDEL *" >/dev/null 2>&1
