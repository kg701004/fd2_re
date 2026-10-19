#!/bin/bash
# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# item5.sh COL ROW:悠妮再行動 → 環形選單 Right(道具,讀回確認)→ 子選單 Up(使用)→ 道具清單 (COL, ROW) → 目標畫面截圖。
cd "$(dirname "$0")" || exit 1
k() { timeout 120 python -X utf8 cl.py k cl5 "$1" "$2" 2>&1 | tail -1; }
a=$(timeout 200 python -X utf8 cl5.py act 1 2>&1 | tail -1); echo "$a"
case "$a" in *"cursor (23, 17)"*) k 6 Up >/dev/null;; *"cursor (23, 16)"*) ;; *) echo "unexpected cursor"; exit 1;; esac
k 6 Return >/dev/null; k 6 Return >/dev/null; k 6 Right >/dev/null
r=$(timeout 200 python -X utf8 cl5.py ring 2>&1 | tail -1); echo "$r"
[ "$r" = "ring 2" ] || { echo "ring not item"; exit 1; }
k 7 Return >/dev/null; k 6 Up >/dev/null; k 7 Return >/dev/null
for ((i = 0; i < $1; i++)); do k 6 Right >/dev/null; done
for ((i = 0; i < $2; i++)); do k 6 Down >/dev/null; done
timeout 120 python -X utf8 cl.py shot cl5 list 2>&1 | tail -1
k 8 Return
