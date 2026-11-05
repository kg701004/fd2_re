#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 地形修正受控測試:攻方固定用索爾 #0,盜賊 #11 當守方,兩者都可搬位置、改種族。
# 用法:terr_test.sh <攻X> <攻Y> <攻種族> <攻AP> <守X> <守Y> <守種族> <守DP> <游標按鍵(逗號分隔,可空)> <標籤>
# 前提:除錯器暫停中。斷點(執行期 +0x19c000):0x2f8dc(EAX = AP 修正)、0x2f921(EAX = DP 修正)、0x2f9fc(EAX = 傷害)。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
S="C:/Users/kg701/AppData/Local/Temp/claude/C--Users-kg701-Desktop-AI-stock-AI/064f5671-708e-478d-aa85-2e95400484d6/scratchpad"
ax=$1; ay=$2; ar=$3; aap=$4; bx=$5; by=$6; br=$7; bdp=$8; keys=$9; tag=${10}
b2() { printf '%02x' "$1"; }
w2() { printf '%02x %02x' $(($1 & 0xff)) $((($1 >> 8) & 0xff)); }
for c in \
  "SM 0170:26bdc8 $(b2 $ax) $(b2 $ay)" \
  "SM 0170:26bdcd 00" \
  "SM 0170:26bde7 $(b2 $ar) $(b2 ${ACLS:-9})" \
  "SM 0170:26bdcf $(b2 ${AP7:-32})" \
  "SM 0170:26be10 $(w2 $aap) 00 00 fa 00 00 00" \
  "SM 0170:26c138 $(b2 $bx) $(b2 $by)" \
  "SM 0170:26c157 $(b2 $br)" \
  "SM 0170:26c15e 01" \
  "SM 0170:26c178 e7 03 e7 03" \
  "SM 0170:26c180 13 00 $(w2 $bdp) fa 00 00 00" \
  "BP 0170:1cb8dc" "BP 0170:1cb921" "BP 0170:1cb9fc"; do
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
python -X utf8 - "$tag" <<'PY'
import struct, sys
tag = sys.argv[1]
d = r'C:/Users/kg701/Desktop/GAME/fd2_re/.wsl_build/ctr/'
for ph in ('pre', 'post'):
    b = open(d + f'{ph}_{tag}.bin', 'rb').read()
    for i in (0, 11):
        r = b[i*80:(i+1)*80]; w = lambda o: struct.unpack_from('<H', r, o)[0]
        print(ph, i, (r[0], r[1]), 'race', r[0x1f], 'class', r[0x20], '+7', hex(r[7]), 'f5', hex(r[5]),
              'HP', w(0x40), 'AP DP HIT EV', w(0x48), w(0x4a), w(0x4c), w(0x4e))
PY
