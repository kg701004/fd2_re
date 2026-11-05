#!/bin/bash
# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 續一百零三:原始軌跡去重成 <name>_unique_cseip.txt(背景跑,完成寫 <name>.done)。用法:s103_dedup.sh <workdir> <raw 檔> <name>
cd "$1" || exit 1
LC_ALL=C awk '!seen[$0]++' "$2" > "$3_unique_cseip.txt"
echo "rc=$? lines=$(wc -l < "$3_unique_cseip.txt") sha256=$(sha256sum "$3_unique_cseip.txt" | cut -c1-16)" > "$3.done"
