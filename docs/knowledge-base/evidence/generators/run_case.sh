#!/usr/bin/env bash
# 存檔:原 scratchpad 驅動腳本,路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 一個完整的升級測試案例:攻擊 -> 推進對話 -> 最終傾印。
# 用法:run_case.sh <對話步數> <lvl_test.sh 的 9 個參數...>
# 前提:除錯器暫停中;結束時也停在除錯器。
set -u
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 2
H="python -X utf8 tools/fd2_dosbox_live_helper.py"
I=vf_recon
S="C:/Users/kg701/AppData/Local/Temp/claude/C--Users-kg701-Desktop-AI-stock-AI/064f5671-708e-478d-aa85-2e95400484d6/scratchpad"
D=.wsl_build/ctr
steps=$1; shift
idx=$1; tag=$9
bash "$S/lvl_test.sh" "$@" | grep -E "^stop|^loop|pointer"
cp $D/post_$tag.bin $D/mid_$tag.bin
$H debugger-cmd --instance $I "BP 0170:1ba55a" >/dev/null 2>&1; sleep 1
$H resume --instance $I >/dev/null 2>&1; sleep 2
$H screenshot --instance $I --out $D/${tag}_d0.png >/dev/null 2>&1
if [ "$steps" -gt 0 ]; then bash "$S/dlg_step.sh" "$tag" "$steps"; fi
for n in 1 2 3 4; do
  $H enter-debugger --instance $I >/dev/null 2>&1; sleep 3
  q=$($H mem read-global --instance $I --selector 0170 --ghidra-addr 53a45 --bytecount 4 --delta 19c000 --out-dir $D/pp 2>&1 | grep raw)
  case "$q" in *c8bd2600*) break;; esac
  $H resume --instance $I >/dev/null 2>&1; sleep 2
done
$H debugger-cmd --instance $I "BPDEL *" >/dev/null 2>&1; sleep 1
$H mem dump --instance $I --selector 0170 --linear 26bdc8 --bytecount 690 --out $D/post_$tag.bin >/dev/null 2>&1
python -X utf8 "$S/lvl_print.py" "$tag" "$idx"
