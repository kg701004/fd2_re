#!/bin/bash
# 存檔:原 scratchpad 驅動腳本(續一百 ~ 一百三十三),路徑保留當時的工作環境,不保證能直接執行(見 README.md)。
# 找出哪幾份 unique_cseip 軌跡含指令表第 0..9 格的 handler 入口(native = linear + 0x19c000)
find "$HOME" -maxdepth 5 -name '*unique_cseip.txt' 2>/dev/null > /tmp/h4_list.txt
echo "files: $(wc -l < /tmp/h4_list.txt)"
head -1 /tmp/h4_list.txt | xargs -I{} head -3 {}
while IFS= read -r f; do
  h=$(sha256sum "$f" | cut -c1-12)
  hits=""
  for a in 1bd206 1bd34b 1bd364 1bd37d 1bd396 1bd449 1bd462 1bd47b 1bd494 1bd4ad 1b141f; do
    if grep -qi "$a" "$f"; then hits="$hits $a"; fi
  done
  [ -n "$hits" ] && echo "$h|$hits|$f"
done < /tmp/h4_list.txt | sort -t'|' -k1,1 -u
