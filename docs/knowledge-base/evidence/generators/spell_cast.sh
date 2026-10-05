#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 法術傷害受控測試:悠妮 #1 對盜賊 #11 施放清單第一項(聖光彈),在 0x1c7fe / 0x1c87f 讀暫存器。
# 用法:spell_cast.sh <游標按鍵序列(逗號分隔,可空)> <標籤>
# 前提:遊戲在地圖操作狀態(非除錯器暫停),盜賊狀態已設好。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
keys=$1; tag=$2
regs() { wsl -d Ubuntu tmux -L fd2harness capture-pane -t harness-$I -p | grep -E "EAX|EBX|EDX" | head -3; }
$H enter-debugger --instance $I >/dev/null 2>&1; sleep 3
for c in "BP 0170:1b87fe" "BP 0170:1b887f"; do $H debugger-cmd --instance $I "$c" >/dev/null 2>&1; sleep 1; done
$H resume --instance $I >/dev/null 2>&1; sleep 2
if [ -n "$keys" ]; then
  IFS=',' read -ra K <<< "$keys"
  for k in "${K[@]}"; do $H key --instance $I --wait 0.8 "$k" >/dev/null 2>&1; done
fi
# 選單位 -> 開環 -> 左(法術) -> 確認 -> 選第一個法術 -> 確認目標
for k in Return Return Left Return Return; do $H key --instance $I --wait 1.3 $k >/dev/null 2>&1; done
$H screenshot --instance $I --out .wsl_build/ctr/tgt_$tag.png >/dev/null 2>&1
$H key --instance $I --wait 1.5 Return >/dev/null 2>&1; sleep 4
echo "--- BP1 (0x1c7fe: ESI=base, EDX=命中亂數)"; regs
$H resume --instance $I >/dev/null 2>&1; sleep 4
echo "--- BP2 (0x1c87f: EDX=傷害亂數, EDI=HP)"; regs
$H debugger-cmd --instance $I "BPDEL *" >/dev/null 2>&1; sleep 1
$H resume --instance $I >/dev/null 2>&1; sleep 18
$H screenshot --instance $I --out .wsl_build/ctr/after_$tag.png >/dev/null 2>&1
for n in 1 2 3 4; do
  $H enter-debugger --instance $I >/dev/null 2>&1; sleep 3
  p=$($H mem read-global --instance $I --selector 0170 --ghidra-addr 53a45 --bytecount 4 --delta 19c000 --out-dir .wsl_build/ctr/pp 2>&1 | grep raw)
  case "$p" in *c8bd2600*) break;; esac
  echo "pointer read '$p' (try $n), re-entering"; $H resume --instance $I >/dev/null 2>&1; sleep 2
done
$H mem dump --instance $I --selector 0170 --linear 26bdc8 --bytecount 400 --out .wsl_build/ctr/post_$tag.bin >/dev/null 2>&1
python -X utf8 - "$tag" <<'PY'
import struct, sys
b = open(r'C:/Users/kg701/Desktop/GAME/fd2_re/.wsl_build/ctr/post_%s.bin' % sys.argv[1], 'rb').read()
for i in (1, 11):
    r = b[i*80:(i+1)*80]; w = lambda o: struct.unpack_from('<H', r, o)[0]
    print('post', i, (r[0], r[1]), 'f5', hex(r[5]), 'class', r[0x20], 'HP', w(0x40), 'MP', w(0x44))
PY
