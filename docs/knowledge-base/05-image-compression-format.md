# 05 — 圖像壓縮格式完整規格

> 《炎龍騎士團2》(漢堂國際, 1995) 的圖像壓縮格式，由本專案第 2 輪逆向工程還原並驗證。
> 這份文件刻意寫得完整、可重現，作為 1990 年代台灣 DOS 遊戲技術的一份保存紀錄。

## 背景

本作為 VGA mode 13h(320×200, 256 色)遊戲。所有圖像存於 `.DAT` 容器(見 `01-container-and-asset-formats.md`)。
全螢幕圖若不壓縮為 64000 byte;原版用一套極簡的 **位元組導向 RLE**(run-length encoding)把標題與
戰鬥背景壓到約 1/3。本格式無查表、無 Huffman、無字典——是當年「夠快又夠省」的務實設計。

## 像素容器標頭

```
偏移  型別        說明
+0    uint16 LE   width   (寬,像素)
+2    uint16 LE   height  (高,像素)
+4    …           像素資料(見下)
```

像素為 **8-bit 調色盤索引**。資料分兩型:

### 型 A — 未壓縮

當 `資源長度 - 4 == width × height`，`+4` 之後即原始逐列像素，無壓縮。
實例:`FDOTHER` 容器資源 #15、#55(皆 320×200，size = 64004)。

### 型 B — RLE 壓縮

當 `資源長度 - 4 < width × height`，像素資料為下列 RLE 串流。

## RLE 演算法

串流由一連串 **token** 組成。每個 token 先讀一個控制位元組 `c`：

```
c = next_byte()
if c >= 0x80:                      # 文字串 (literal)
    n = (c & 0x7F) + 1             #   接下來 n 個 byte 原樣輸出
    output( next_bytes(n) )
else:                              # 連續執行 (run)
    v = next_byte()               #   下一個 byte 是像素值
    output( v repeated (c + 1) times )
```

- literal 一次最多 `0x7F + 1 = 128` 個像素。
- run 一次最多 `0x7F + 1 = 128` 個相同像素。
- 解碼到輸出累計達 `width × height` 即結束。

**判定強約束(驗證用)**：正確的解碼器對任一圖必輸出**剛好 `width × height`** 個像素;
長度不符即代表演算法或起點錯誤。本演算法在 `TITLE_000`(320×200)、`BG_*`(320×100)、
`FDOTHER` 背景上全部精確命中，並渲染出可辨識的正確畫面。

## 逐步實例(TITLE_000 開頭)

標頭 `40 01 c8 00` → width=0x0140=320, height=0x00C8=200, target=64000。
像素串流開頭：

```
3F F0 3F F0 3F …
```

| token | c | 動作 | 產生像素 |
|---|---|---|---|
| 1 | `3F` | run，c<0x80，重複下一 byte `F0` 共 0x3F+1=64 次 | 64×0xF0 |
| 2 | `3F` | run，重複 `F0` 64 次 | 64×0xF0 |
| … | | (標題背景大片同色 → 連續多個 64 長 run) | |

(標題畫面四周為大片單色背景，故開頭是一連串長 run;進入 logo 區後才出現 literal。)

## 調色盤

256 色 VGA 調色盤存於 `FDOTHER` 容器資源 #0，768 byte = 256 × (R, G, B)，每分量 6-bit(0–63)。
轉 8-bit:`v8 = (v6 << 2) | (v6 >> 4)`。此調色盤對標題與多數戰鬥背景正確;不同場景可能切換調色盤，
其餘調色盤資源待後輪清點。

## 參考實作

`tools/decode_image.py`：

```bash
# 單張轉 PNG(需自備原版,先用 unpack_dat.py 解出資源)
python3 tools/decode_image.py 資源.bin 調色盤.bin 輸出.png
```

核心解碼函式 `decode_rle(body, target)` 即上述演算法。

## 已驗證成果

| 資源 | 尺寸 | 型 | 還原內容 |
|---|---|---|---|
| `TITLE_000` | 320×200 | RLE | 遊戲標題「FLAME DRAGON 2 — Legend of Golden Castle」 |
| `BG_003` | 320×100 | RLE | 戰鬥背景:連綿山脈 |
| `BG_010` | 320×100 | RLE | 戰鬥背景:村莊房舍 + 石牆 |
| `FDOTHER_015` | 320×200 | 未壓縮 | 熔岩材質 |
| `FDOTHER_055` | 320×200 | 未壓縮 | 藍色雲層 |

全幅背景 / 標題類約 125 張已可解。**sprite 類**(24×24 圖塊、戰鬥動畫格、人物立繪)
推測使用本 RLE 的**透明(skip)變體**以支援非矩形圖形，於 `06-animation-format.md` 接續處理。

## ch10 少數 tile 雜色查因（2026-08-18 複查，非 bug 結論維持）

> 對應 `91-worklist.md` 第 620 行「ch10 等圖少數 tile 雜色查因」。本輪為純靜態複查（未用
> DOSBox-X/WSL2，因另一並行任務正在用該環境），方法與證據如下；**未發現任何可歸咎於我方
> decode 工具或 Go 渲染程式碼的 bug，故未修改程式碼**。

**1. 確認 ch10 戰鬥地圖資產**：`remake/assets/scenarios/campaign_full.json` 第 1878-1880 行，
`ch10` 戰場 `"map": "assets/maps/map9"`，對應原始 `extracted/raw/FDFIELD/FDFIELD_027.bin`
(31×45 格構成，27 = 9×3)配 `extracted/raw/FDSHAP/FDSHAP_036.bin`(第 19 個「大資源」tileset，
36 = 2×9+... 實測即 `2N` 規則的第 9 張)。tileset 為地底洞穴主題(火把/岩壁/寶箱)，非草原。

**2. FDSHAP tile RLE 解碼完整性(four-mode，非本文上方的 2-mode RLE，格式見 `01`§8/`31`§1)**：
逐 byte 重放 `FDSHAP_036.bin` 192 個 tile 的 4-mode token 流，檢查是否有 span 溢出 tile 寬度、
literal/run 讀到資源尾、或解碼後仍有剩餘 bytes——**192/192 全部乾淨解完，0 個邊界異常**。
把同一檢查跑遍全部 33 張地圖的 tileset(`FDSHAP` 全部「大資源」)，**0/33 出現任何 tile 解碼
邊界問題**，與 2026-07-03(commit `d831496e`)「全 33 圖 index 零越界」的結論一致，這次是
用逐 byte token 重放（更嚴格於單純「index 越界」檢查）獨立覆核。

**3. FDFIELD composition entry byte+3(raw/LUT 分支選擇位)**：`FDFIELD_027.bin` 全部 1395 格的
第 4 byte(= event 欄位高位)實測**全部是 `0x00`，沒有一格是 `0xff`**。按 `56-fd2-remake-sdd.md`
§6.0 的 `0x11eee` 契約，archive byte+3 `==0xff` 才選 raw `0x4deda`，其餘理論上要走
destination-LUT `0x4dcc6`。但同一節已證實**這不是 runtime 實際狀態**：`0x4dbfc` 在每次重繪前
會把 runtime 的 byte+3 全部覆寫成 `0xff`，所以靜態封存檔的 byte+3 值不能拿來預測玩家實際看到
的 raw/LUT 分支——這解釋了為何 `export_engine_assets.py`/`compose-map-image` 的 raw-only 靜態
匯出路徑，經視覺比對仍與玩家看到的畫面一致，不是巧合。

**4. 視覺複查**：把 `map9/tileset.png.orig4x`(pre-upscale 原生 16×12 格 tileset)放大 3 倍逐格
檢視，以及用 `remake/cmd/compose-map-image` 重新合成 map9 全圖(744×1080 原生解析度)，兩者皆為
一致的洞穴/火把/寶箱美術，**沒有發現任何獨立於美術本身、看起來像解碼錯誤的孤立雜訊像素**——
畫面中唯一的高對比邊緣落在火把火焰高光、寶箱金屬邊框這類原本就是手繪 dither 的細節上。另外，
`docs/knowledge-base/evidence/battle_ch10_20260816.png`(2026-08-16 remake 引擎實跑截圖，已於
`58-remake-live-verification-log.md` 第 801-804 行記錄為「正確渲染、地城類型地圖首次確認」)
同樣未見雜色/雜訊格。

**結論**：本輪獨立複查(RLE 解碼完整性 + raw/LUT 分支語意 + 兩種靜態合成 + 既有實機截圖交叉比對)
**沒有找到任何新證據支持 ch10/map9 存在解碼或渲染 bug**，維持 2026-07-03 的「非 bug——原版
地底裂谷美術」結論；**未修改任何程式碼**。`91-worklist.md` 第 620 行項目：本輪視為已充分複查
確認 non-bug，可視同與同檔第 634 行「tile 雜色結案」合併結案；若日後有人能指出具體「哪一格」
看起來雜色(座標/截圖框選)，需要新證據才能重啟調查，本文檔的檢查方法(FDSHAP 逐 tile RLE 重放
+ FDFIELD byte+3 分布)可直接重跑於任一地圖。
