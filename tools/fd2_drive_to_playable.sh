#!/bin/bash
# 驅動到「玩家真的可以操作」為止。
# 判準用 ensure_browse(以 0x18890 斷點自證在瀏覽游標層),**不是** in_battle ——
# 單位陣列在戰前演出期間就已存在,in_battle 會提早成立,導致後續操作全部送錯層。
cd /c/Users/kg701/Desktop/GAME/fd2_re || exit 1
export PYTHONIOENCODING=utf-8
H="python tools/fd2_dosbox_live_helper.py"
I="$1"
[ "$2" = "boot" ] && { sleep 70; $H key --instance $I confirm --wait 3 >/dev/null 2>&1; }
for r in $(seq 1 20); do
  for i in $(seq 1 10); do $H key --instance $I confirm --wait 1.3 >/dev/null 2>&1; done
  out=$(python tools/fd2_battle_autoplay.py --instance $I --ensure-browse 2>&1 | tail -1)
  echo "第 $r 批(累計 $((r*10)) 次確認): $out"
  case "$out" in *已確定*) echo "READY"; break;; esac
done
