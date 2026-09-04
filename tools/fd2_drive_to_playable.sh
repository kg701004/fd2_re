#!/bin/bash
# 驅動到「玩家真的可以操作」為止。
#
# ⚠ 不要串在 launch 後面:`fd2_dosbox_live_helper.sh launch <name> <keepalive>`
#    會**佔住那個 keepalive 秒數不返回**(它就是 keepalive 的持有者),所以
#    `launch ... && drive ...` 的第二段永遠不會執行,而實例其實早就起來了。
#    2026-09-04 因此空等了半小時,現象是「實例在跑、log 檔卻始終不存在」。
#    正確做法:launch 自己一個背景工作(別殺它,殺了會連帶拆掉實例),
#    確認 tmux session 出現後,再另外跑這支腳本。
#
# ⚠ 也不要在它執行中編輯這個檔:bash 是**邊執行邊讀取**腳本的,檔案長度一變
#    就會從錯誤的位元組位置續讀,吐出看似荒謬的語法錯誤(2026-09-04 實例:
#    報「第 10 行」但引用的是第 8 行的片段,而檔案本身 `bash -n` 完全正常)。
#    要改就先讓它跑完,或改完再重跑。
# 判準用 ensure_browse(以 0x18890 斷點自證在瀏覽游標層),**不是** in_battle ——
# 單位陣列在戰前演出期間就已存在,in_battle 會提早成立,導致後續操作全部送錯層。
# 用腳本自身位置定位,不要寫死 `/c/...`——那是 Git Bash 的掛載,
# 從 Python subprocess 呼叫時解析到的 bash 可能沒有它(2026-09-04 實測:
# `cd: /c/Users/...: No such file or directory`,而 stdout 是空的,
# 於是 trial runner 六次試驗全部 drive_failed 卻看不出原因)。
cd "$(dirname "$0")/.." || exit 1
export PYTHONIOENCODING=utf-8
H="python tools/fd2_dosbox_live_helper.py"
I="$1"
[ "$2" = "boot" ] && { sleep 70; $H key --instance $I confirm --wait 3 >/dev/null 2>&1; }
# 探測的代價遠高於按鍵:一次 ensure_browse 要 BPDEL/下斷點/送鍵/讀 EIP,約 30-60 秒,
# 而一次確認只要 1.3 秒。2026-09-04 八次實測(sfx2/win3/ctl1/ctl2/ctl3/dbg1/rv1/lad1):
# **最早也要第 7 批才成立**(觀察到的落點是 7、9、11——上限比我第一次寫的「7-9」寬,
# 第 8 個樣本就跑到 11 了,所以這裡只用**下界**做最佳化,不假設上界)。
# 前 6 次探測是穩定的浪費,那才是 10 分鐘裡的大頭。
# 改成:前 60 次確認完全不探測,之後每 10 次探一次。省下約 6 次探測。
SKIP_PROBE_UNTIL=${FD2_DRIVE_SKIP_PROBE_UNTIL:-6}
for r in $(seq 1 20); do
  for i in $(seq 1 10); do $H key --instance $I confirm --wait 1.3 >/dev/null 2>&1; done
  if [ "$r" -lt "$SKIP_PROBE_UNTIL" ]; then
    echo "第 $r 批(累計 $((r*10)) 次確認): 略過探測(實測最早也要第 7 批才成立)"
    continue
  fi
  out=$(python tools/fd2_battle_autoplay.py --instance $I --ensure-browse 2>&1 | tail -1)
  echo "第 $r 批(累計 $((r*10)) 次確認): $out"
  case "$out" in *已確定*) echo "READY"; break;; esac
done
