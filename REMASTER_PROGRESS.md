# FD2 重製專案進度（本地個人分支，未推送回 fd2_re 上游）

此檔記錄使用者個人重製目標（Win11 原生執行、1080P、角色美術升級、過場加速、
關卡隱藏條件顯示）在 `wicanr2/fd2_re` 這份 clone 上的實作進度。**這是本地個人
使用的衍生工作，不是要推送回上游 GitHub repo 的貢獻**，所以沒有完全套用
`AGENTS.md` 裡針對多人協作/上游 PR 的流程規則（例如 Docker-only IDA/Capstone、
commit 身分等），但沿用了其核心工程紀律：型別化資料、單元測試、誠實的證據等級
標示、不確定就不硬做（fail-closed）。

## 第 0 步：原生 Windows 11 建置與執行 —— ✅ 完成

- 安裝 Go 1.26.5（`winget install GoLang.Go --silent`）。
- Clone 至 `C:\Users\kg701\Desktop\GAME\fd2_re`。
- **原生 `go build`，不需要 Docker、不需要 CGO/gcc**——比 fd2_re 自己 README 記載
  的「只驗證過 Docker 交叉編譯，執行未在真機驗證」更簡單的路徑，這次直接證實可行。
- 用 `tools/unpack_dat.py --all` 解包使用者自己的原版遊戲檔案，資源數（FDFIELD
  100／FDOTHER 104／FDSHAP 67）跟本專案另一份格式逆向筆記（`FD2_format_notes.md`）
  的結果逐一吻合。
- 用 `tools/export_engine_assets.py` 產生 stage 0 資產，**實際執行成功**，視窗
  標題「炎龍騎士團2 重製 (fd2_re)」，畫面渲染出序章村莊小島地圖，且畫布本來就是
  hi-res 可縮放渲染，不是死板 320×200。

## Windows CJK 字型相依性修正 —— ✅ 完成（真實 bug fix）

`cmd/fd2/font.go` 原本的 `fontPaths` 只列 Linux 系統字型路徑
（`/usr/share/fonts/...`），在 Windows 上 `loadFont()` 會直接回傳 `nil`，
所有文字完全不渲染、且沒有任何錯誤訊息。已加入 Windows 內建繁體中文 UI 字型
「微軟正黑體」（`C:\Windows\Fonts\msjh.ttc`）與備援「細明體」路徑。用
`git stash` 前後對照確認：這個修正**不影響**既有 `cmd/fd2` 測試套件的通過/
失敗狀態（既有失敗全部是缺少 `assets/maps/mapN/tileset.png` 這類尚未產生的
逐章資產，跟這次的修改無關，已用 stash 前後對照驗證過是同樣的失敗）。

## 關卡隱藏條件顯示 —— ✅ 資料層＋獨立畫面完成，尚未接進主遊戲迴圈

**資料層**：新增 `remake/internal/objectives` package，把
`docs/knowledge-base/28-chapter-objectives-and-recruits.md` 整理的全 30 章
勝利/失敗/加入條件轉成型別化 Go 資料，標明證據等級 E3（玩家攻略整理，非原始
執行檔逐位元組驗證），並附完整單元測試（章節數完整性、必要欄位非空、抽樣
核對三個章節的實際內容）。

**畫面層**：新增獨立可執行檔 `remake/cmd/objectives-viewer`，用 Ebiten 渲染
一個乾淨的關卡目標畫面（章節標題、勝利條件、失敗條件含額外護衛目標、可能
加入角色與條件、置底的證據等級與操作提示）。**已實際建置並執行成功**，視覺
截圖確認排版、配色、中文字型渲染全部正常。章節切換邏輯（←/→鍵，1-30 夾邊）
抽出成純函式並用單元測試覆蓋（`nextChapter`/`prevChapter`），因為 OS 層級
的 `SendKeys` 按鍵無法可靠送達 Ebiten 這類走 raw input 的遊戲視窗，改用單元
測試驗證比硬套 UI 自動化更可靠。

**刻意不做的部分（誠實記錄）**：沒有把這個畫面接進 `cmd/fd2/main.go` 現有
7897 行、高度精細的原生行為重現狀態機（`Game.Update()`/`Draw()`）。那份狀態
機有大量 `native_*` 前綴的欄位跟邏輯，是逐一比對反組譯結果做出來的，貿然在
有限時間內插入未經完整理解的新畫面，風險遠高於「先交付一個獨立、乾淨、可驗證
正確的垂直切片」。**這是刻意的技術決策，不是没做完**：資料層跟畫面渲染都已經
是可以直接運作的東西，真正整合進主遊戲迴圈（在哪個時機點呼叫、如何跟現有
`campaign` package 的章節推進邏輯串接）需要先完整讀懂主迴圈的既有慣例，
是下一階段的工作。

## 過場加速 —— ✅ 完成

新增 `remake/cmd/fd2/cutscene_speed.go`：全域加速倍率 `cutsceneSpeedUp`（預設
5 倍，環境變數 `FD2_CUTSCENE_SPEED=1` 可還原原版節奏做 A/B 對照）。做法刻意
保守：只調整鏡頭平移（pan）、走位（walk）、淡出淡入（fade）、delay 拍、
native 過場揭幕（transition_reveal）、行軍蒙太奇自動轉場、戰鬥中過場事件
延遲、片頭 AFM/靜態幕等**計時器每 tick 前進多少**，不改 `beatStart` 等處
設定的原始 frames/delay 數值——那些數值仍是逐一對照反組譯位址的證據
（doc50/doc46 註解保持真實有效）。**刻意不動** `stepOriginalActing`
（doc50 §1.2 逐 tick 精確重現原版格線位移）：那段每個 tick 值本身就是行為
的一部分，跳 tick 會漏放中間格，風險評估後排除。

新增 5 個單元測試涵蓋環境變數解析與倒數計時 floor-at-0 邏輯，全部通過。跑
全套 `cmd/fd2` 既有測試時，發現這個改動讓 3 個逐 tick 精確節奏驗證測試失敗
（它們預設 1 tick=1 原生幀）；修法是加 `TestMain` 讓整個測試套件固定用原版
節奏跑，只有實際遊玩才吃加速倍率。用 `git stash` 前後對照確認：現在的失敗
數（13個）跟改動前 baseline 完全一致，都是既有缺資產（`assets/maps/mapN/
tileset.png`）問題，沒有引入新迴歸。

## 關卡目標畫面接進主迴圈 —— ✅ 完成

觸發點是 beat「loadch」(`cmd/fd2/main.go` case "loadch"):`applyLoadCH` 成功
套用章節 map/roster/script 後,若 `internal/objectives.ByNumber(chapter)` 有該
章資料,就設 `g.objChapter` 並直接 `return`(不呼叫 `beatAdvance()`),讓畫面
先擋住過場;沒有資料的章節(序章、31-33 尾聲/番外)完全不受影響,行為跟這次
改動前一樣直接往下跑。

**索引換算是真正的風險點**,原本我在 `beat "loadch"` 那行直接寫
`objectives.ByNumber(b.LoadCH.Chapter)`,是錯的——比對
`assets/cutscenes/bindings/ch01_pre.json`(它的 loadch 設 `"chapter": 1` 但
`"script": "assets/story/ch02.json"`)跟 `TestApplyLoadCHDirectReplayUsesBindingPartyOrder`
(`Chapter: 0` 對應 `ch01.json`)兩份既有證據,加上 `internal/objectives`
package doc 自己就寫明「walkthrough chapter N == remake chapter index N-1」,
確認 `LoadCHState.Chapter` 是 0-based stage 編號,要 `+1` 才是攻略慣用的
1-based 章節數。改對後新增 2 個整合測試
(`objectives_screen_test.go`)用真實編譯出的 `ch01_pre.json` binding 全流程
驗證:loadch 成功套用 → 畫面擋住 beat runner(`beatIdx` 停在原地)→
`dismissObjectivesScreen()`(從 `campInput()` 的 Enter/Space 分支抽出的純
邏輯,理由同 objectives-viewer 抽 `nextChapter`/`prevChapter`:ebiten raw
input 視窗不保證吃得到 OS 層模擬按鍵)清畫面 → `beatIdx` 正確前進。

阻塞機制完全比照既有的「dialog beat 擋住直到 Enter」慣例(`campInput()` 裡
`case "cutscene":` 那段),畫面渲染重用引擎既有 `g.font`,沒有像
`cmd/objectives-viewer` 那樣另外複製一份字型載入邏輯。

**意外收穫(範圍外但值得記錄的真 bug)**:為了讓上面的整合測試真的跑得動,
需要 `assets/maps/map1/tileset.png`,而既有 `remake/assets/maps/` 底下 34 個
章節目錄都只有 `map.json`/`mapN_units.json`,完全沒有 `tileset.png`(這是
Phase 0 就誠實記錄過的已知缺口)。追查 `tools/export_engine_assets.py` 為何
對 map1 產生「cannot write empty image」時,發現 `extracted/raw/FDSHAP/` 的
67 個資源其實是「真實 tileset(大檔)/固定 1200 bytes 的非 tileset 資源」
交錯排列——**stage N 對應的是 FDSHAP 資源 `2×N`,不是資源 `N`**(2×0=0,
2×1=2,2×2=4…共 33 個偶數索引 tileset + 33 個奇數索引的其他資源 + 1 = 67,
數字剛好對得上)。用修正後的索引重跑,33 張地圖的 tileset.png 全部產出成功
(逐張比對 map.json 的 w/h/cols 與已入庫版本一致才覆蓋,只換 tileset.png,
沒動任何 map.json/units.json)。`cmd/fd2` 測試套件因此從 13 個既有失敗降到
2 個(`TestBattleWalkActivatesMap26Event63OnlyAfterLeftStepCommit` 是 map26
event63 觸發時機的既有邏輯問題、`TestBattleCh27...` 是另一個測試檔案自己的
相對路徑問題,都跟這次改動無關,也跟 tileset 資產無關)。這些 `tileset.png`
依 `remake/.gitignore`(`assets/maps/*/*.png`)不會進版本控制,跟其他玩家
衍生素材規則一致。

## 1080P 縮放渲染管線 —— ✅ 完成

調查後發現這項比想像中小:視窗**本來就可拖曳縮放**
(`ebiten.SetWindowResizingMode(WindowResizingModeEnabled)` 早已存在於
`main()`),Ebiten 對非整數縮放也**預設套用平滑 box filter**(`run.go`
`SetScreenFilterEnabled` 文件寫明「default state is true」)——渲染管線本身
不用重做,真正缺的只是「一啟動就已經很大」的預設體驗跟全螢幕捷徑:

- **F11 切換全螢幕**(`cmd/fd2/main.go` `Update()`,跟既有 F2/F3 全域鍵同一
  段):`ebiten.SetFullscreen(!ebiten.IsFullscreen())`。
- **`defaultWindowSize()`**:啟動時用 `ebiten.ScreenSizeInFullscreen()` 抓
  螢幕實際尺寸,選一個 640×400 邏輯畫布的最大整數倍(抓不到螢幕尺寸則退回
  原本的 2 倍 1280×800,行為不變)。純數學部分抽成 `windowScaleFor(sw,sh int)
  int`,4 個單元測試涵蓋:1920×1080 標準螢幕(驗到剛好是 2 倍,3 倍的
  1920 寬會壓線超過留白邊界)、2560×1440 大螢幕(3 倍)、螢幕尺寸查詢失敗
  fallback、小螢幕不會縮到比原本預設更小。
- `ebiten.SetWindowSizeLimits(logicalW, logicalH, -1, -1)`:最小維持 1 倍
  (640×400),避免玩家把視窗拖到不能用的大小。

實機驗證:重新建置後啟動,視窗確實大幅放大(截圖確認地圖渲染清晰、box
filter 平滑縮放無鋸齒),關掉背景程序後確認乾淨結束。F11 全螢幕切換因為
是按鍵輸入,沿用本專案已知的限制(SendKeys 類 OS 層按鍵不保證送達 Ebiten
raw input 視窗)不做 UI 自動化驗證,靠程式碼審閱(`ebiten.SetFullscreen`
是官方公開 API,用法直接)。

## 角色美術升級 —— 🔶 索爾單人試驗完成，尚未推廣/接線

完整過程、最終配方、踩過的坑、已知取捨,都記在
`C:\Users\kg701\Desktop\GAME\FD2\character_art_pilot_sol\README.md`
(連同定案圖檔),不重複寫在這裡。摘要:

- Real-ESRGAN(純放大銳利化)證實不夠——它不能做風格轉換,只能讓原圖「同風格
  更銳利」。
- 純 img2img 會被原圖的壓縮構圖(索爾原圖額頭空間窄)卡死比例,調 strength
  只能在「比例對但角色特徵跑掉」跟「特徵保留但比例不對」之間二選一。
- 最終解法是 txt2img **從零文字重建**(不碰原圖像素),身份特徵詞(深藍髮、
  紅頭巾、側臉)放 prompt 最前段避開 CLIP 77 token 截斷,模型用
  `gsdf/Counterfeit-V2.5`。定案版本經多輪外觀調整(髮型、體格、服裝、髮色)
  收斂而成。
- **已知未解決,留給下一階段**:(1) 這是靜態立繪,不是原本 DATO.DAT 的 4
  嘴型動畫幀;(2) 已實測比對證實原版頭像跟 FDFIELD/FIGANI 小精靈是同一套
  像素美術語言,新畫風跟它們會有明顯落差,要不要跟進重畫小精靈待決定;
  (3) 還沒接進 `cmd/fd2` 引擎的實際對話畫面;(4) 還沒推廣到其他 31 個角色。

## 待辦（依序）

1. ~~過場加速~~ —— 已完成，見上。
2. ~~關卡目標畫面接進主迴圈~~ —— 已完成，見上。
3. ~~1080P 縮放渲染管線~~ —— 已完成，見上。
4. 角色美術升級 —— 索爾單人試驗完成(見上),下一步待決定:4 嘴型動畫處理、
   接進引擎、FDFIELD/FIGANI 是否跟進、推廣到其他角色。

---
*最後更新：2026-08-09*
