#!/bin/bash
# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# cast5.sh COL ROW:悠妮再行動 → 選她 → 環形選單 Left(魔法,讀回確認)→ 清單 (COL, ROW) → 目標選擇畫面截圖。
# COL 0/1(Right 次數)、ROW = Down 次數。停在目標選擇,最後的 Return 由人看截圖後再送。
cd "$(dirname "$0")" || exit 1
k() { timeout 120 python -X utf8 cl.py k cl5 "$1" "$2" 2>&1 | tail -1; }
a=$(timeout 200 python -X utf8 cl5.py act 1 2>&1 | tail -1); echo "$a"
case "$a" in *"cursor (23, 17)"*) k 6 Up >/dev/null;; *"cursor (23, 16)"*) ;; *) echo "unexpected cursor"; exit 1;; esac
k 6 Return >/dev/null; k 6 Return >/dev/null; k 6 Left >/dev/null
r=$(timeout 200 python -X utf8 cl5.py ring 2>&1 | tail -1); echo "$r"
[ "$r" = "ring 1" ] || { echo "ring not magic"; exit 1; }
k 7 Return >/dev/null
for ((i = 0; i < $1; i++)); do k 6 Right >/dev/null; done
for ((i = 0; i < $2; i++)); do k 6 Down >/dev/null; done
timeout 120 python -X utf8 cl.py shot cl5 list 2>&1 | tail -1
k 7 Return
