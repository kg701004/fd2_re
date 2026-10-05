#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 物理攻擊經驗值的受控測試(單次攻擊)。
# 用法:exp_test.sh <攻方序號> <盜賊X> <盜賊Y> <盜賊等級> <盜賊HP> <游標按鍵(逗號分隔,可空)> <標籤>
# 前提:除錯器暫停中。盜賊 #11:+0x26=1(不反擊)、DP0/EV0、MaxHP 20。攻方:AP19/DP0/HIT250/EV0、EX 歸 0、清已行動。
# 斷點 0x2fa9f(EAX = 基礎經驗值)、0x2fab9(EAX = 依傷害比例縮放後),執行期 +0x19c000。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
S="C:/Users/kg701/AppData/Local/Temp/claude/C--Users-kg701-Desktop-AI-stock-AI/064f5671-708e-478d-aa85-2e95400484d6/scratchpad"
idx=$1; bx=$2; by=$3; lv=$4; hp=$5; keys=$6; tag=$7
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
  "SM 0170:$(h $((base + 0x3c))) 00" \
  "SM 0170:$(h $((base + 0x48))) 13 00 00 00 fa 00 00 00" \
  "BP 0170:1cba9f" "BP 0170:1cbab9"; do
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
python -X utf8 - "$tag" "$idx" <<'PY'
import struct, sys
tag, idx = sys.argv[1], int(sys.argv[2])
d = r'C:/Users/kg701/Desktop/GAME/fd2_re/.wsl_build/ctr/'
for ph in ('pre', 'post'):
    b = open(d + f'{ph}_{tag}.bin', 'rb').read()
    for i in (idx, 11):
        r = b[i*80:(i+1)*80]; w = lambda o: struct.unpack_from('<H', r, o)[0]
        print(ph, i, (r[0], r[1]), 'side', r[6], 'port', hex(r[7]), '+8', hex(r[8]), 'f5', hex(r[5]), 'class', r[0x20],
              'lv', r[0x21], 'EX', r[0x3c], 'HP', w(0x40), w(0x42))
PY
