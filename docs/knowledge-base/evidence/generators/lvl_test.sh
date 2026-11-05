#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 升級的受控測試(單次攻擊,攻方 EX 與等級可設)。
# 用法:lvl_test.sh <攻方序號> <攻方等級> <攻方EX> <盜賊X> <盜賊Y> <盜賊等級> <盜賊HP> <游標按鍵(逗號分隔,可空)> <標籤>
# 前提:除錯器暫停中。盜賊 #11:+0x26=1(不反擊)、DP0/EV0、MaxHP 20。攻方:AP19/DP0/HIT250/EV0、清已行動。
# 斷點(執行期 +0x19c000):0x2fa9f 基礎經驗、0x2fab9 縮放後、0x1e55a 成長量(EBP)。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
S="C:/Users/kg701/AppData/Local/Temp/claude/C--Users-kg701-Desktop-AI-stock-AI/064f5671-708e-478d-aa85-2e95400484d6/scratchpad"
idx=$1; alv=$2; aex=$3; bx=$4; by=$5; lv=$6; hp=$7; keys=$8; tag=$9
base=$((0x26bdc8 + idx * 0x50))
h() { printf '%x' "$1"; }
b2() { printf '%02x' "$1"; }
for c in \
  "SM 0170:26c138 $(b2 $bx) $(b2 $by)" \
  "SM 0170:26c159 $(b2 $lv)" \
  "SM 0170:26c15e 01" \
  "SM 0170:26c178 $(b2 $hp) 00 14 00" \
  "SM 0170:26c180 13 00 00 00 fa 00 00 00" \
  "SM 0170:$(h $((base + 5))) 00" \
  "SM 0170:$(h $((base + 0x21))) $(b2 $alv)" \
  "SM 0170:$(h $((base + 0x3c))) $(b2 $aex)" \
  "SM 0170:$(h $((base + 0x48))) 13 00 00 00 fa 00 00 00" \
  "BP 0170:1cba9f" "BP 0170:1cbab9" "BP 0170:1ba55a"; do
  $H debugger-cmd --instance $I "$c" >/dev/null 2>&1; sleep 1
done
$H mem dump --instance $I --selector 0170 --linear 26bdc8 --bytecount 690 --out .wsl_build/ctr/pre_$tag.bin >/dev/null 2>&1
$H resume --instance $I >/dev/null 2>&1; sleep 2
if [ -n "$keys" ]; then
  IFS=',' read -ra K <<< "$keys"
  for k in "${K[@]}"; do $H key --instance $I --wait 0.8 "$k" >/dev/null 2>&1; done
  sleep 1
fi
$H screenshot --instance $I --out .wsl_build/ctr/cur_$tag.png >/dev/null 2>&1
for k in Return Return Up Return Return; do $H key --instance $I --wait 1.2 $k >/dev/null 2>&1; done
NOKEY=1 bash "$S/bp_loop.sh" $tag | grep -E "^stop|^loop|pointer"
python -X utf8 "$S/lvl_print.py" "$tag" "$idx"
