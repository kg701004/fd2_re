# 91 — Worklist(逐輪更新，依序執行)

> 目標:完成《炎龍騎士團2》反組譯研究，並考證當年開發工具。
> 每輪結束更新本表(打勾 / 補新項 / 調整順序)，與 `99-reflections-log.md` 互補。
> 圖例:✅ 完成 · 🟡 進行中 · ⬜ 待辦 · ❌ 放棄(註明原因)

> **工具提示(2026-08-20)**:要用 Ghidra 查多個位址(disasm/decompile/xref/function bounds)時,
> 不要再各寫一支 `Probe*.java` 各跑一次 `analyzeHeadless`——改用 `tools/ghidra_batch_probe.py`
> 一次餵一份 queries.json,一次 JVM 啟動查完整批,細節見 `98-tooling-infrastructure.md`。

## 稽核索引(2026-08-19)

> 對稽核當時全部`[ ]`/`[~]`項目逐一分類，交叉核對`docs/knowledge-base/*.md`與`remake/`程式碼後產出，方便日後快速掃描而不必每次重讀全文。分類：**A**=已在別處完整解決只是狀態未同步（下方已直接改回`[x]`並附依據，不再重複列出）、**B**=需使用者本人（實聽/人眼校對/遊玩判斷）、**C**=純程式實作/資產/打包工作、**D**=真正開放、agent可續靜態分析的RE項目、**E**=需live DOSBox-X驗證、**F**=卡在外部限制（遺失素材/更大範圍重構前置）。稽核當時另發現2項（215、390）在稽核開始前就已是`[x]`（初次掃描誤判為開放項），未計入下方164項統計。標「未深入查證」者代表在合理時間內無法完全確認，已保守歸類，未來若要精查請優先看這些行。
>
> **統計（164項，扣除215/390誤判）**：A=18（已在下方對應行改回`[x]`）、B=7、C=38、D=67、E=29、F=5。

19 - E - UI-VIS-TOWN variant1(ch12)/variant2(ch03)已於2026-08-25用平行harness(townE2)DOSBox原版對照，5個真實selection視覺+統計比對確認，但非variant0等級的byte-exact RGB MD5，且secret gate reveal未成功，故仍標`[~]`。
20 - E - UI-VIS-SHOP 自述下一gate為四人以上recipient scroll等，需DOSBox。
24 - E - UI-SHOP-RECIPIENT-INPUT-E2 selection0↔1已閉合，僅剩四人以上scroll原版E2待DOSBox。
26 - E - UI-VIS-PREPARATION已於2026-08-25用prepE2 harness以機器上唯一真實存檔(ch27)補上出發確認→bypass直達戰場的完整E2且與production邏輯吻合，但同時發現該存檔（及機器上其餘3槽）結構上無法觸及選人核取/0x320fc重排/0x31d3c最終確認三段（逐章旗標表顯示僅23/24/25/28-31章顯示選人畫面，機器僅有的4槽全在略過區間，且全遊戲僅13名可招募角色永遠不超門檻），故仍標`[~]`。**2026-08-26續輪(純靜態)重新derive「19 vs 13」矛盾**：確認doc56 UI-11引用的整備UI位址(0x318ad等8個)在FD2Analysis3全部`in_function:false`(舊版殘留)，但同一套cap/confirm/cursor-skip邏輯已由`58-remake-live-verification-log.md`續九～續十一(task #118,早於prepE2一週)對照實際509158-byte`FD2.EXE`做純檔案byte-signature驗證過：15/19門檻與「選滿才能離開」都是真的，不是誤讀；「僅13名可招募角色」這句話只對機器上現有的合成/早期存檔成立——獨立核對`docs/data/chapter_beats/ch{NN}_post.json`的join op數量，ch11-22共13次加入(與續九的獨立查證吻合)，真的照劇情推進的存檔抵達23-31章時名冊規模應在20+，並非結構性上限。仍待下一輪驗證的唯一開放問題：選人畫面渲染迴圈是否真的硬編碼上限12(不論roster多大)——若成立則推翻上述樂觀結論，需要`roster_count≥15`的存檔實測。詳見doc25§9.1與`known_address_errata.json`。
45 - E - UI-VIS-LOAD自述成功native restore/delete/overwrite/roster ABI仍待E2。
53 - E - UI-VIS-DIFF-HARNESS本質即輸出DOSBox與remake pixel diff，需live擷取。
54 - F - ENGINE-REPOSITORY-EXTRACTION-GATE明文待核心垂直路徑穩定＋授權/貢獻規範等前置決策才啟動。
69 - C - 文件維護政策宣告（專題文件不合併），非可關閉的分析任務。
145 - D - doc11已閉合部分(0x14237/0x15AD8→0x15B77)，候選格順序/turn-camp/runtime execution仍待靜態RE。
155 - E - RE-BATTLE-AI-SPECIAL-TOPIC自述下一步需固定存檔trace驗證實際選中command/畫面順序，需DOSBox。
210 - D - REMAKE-AI-MODE-RUNTIME剩餘模式玩法名稱/event82觸發/回合orchestration可續靜態RE。
212 - D - REMAKE-GLOBAL-EVENT-DISPATCH的58..89 handler高階語意仍待逐一靜態反組譯。**大幅推進(2026-08-24,doc25§11)**:32個handler全部取得明確狀態(22個具體行為描述、10個確認table artifact)，但event58/76/78三個既有「[驗]乾淨」結論被新發現的指令邊界疑慮動搖、尚未re-verify，checkbox維持`[~]`。——**re-verify完成(2026-08-24續輪,doc25§11.7)**:找到第二條獨立管道(直接讀`0x51b91`跳表原始bytes，用4個既驗錨點(event0/59/77/82)校準出一致的relocation偏移量`0x356`)，逐byte確認event58/76/78三個table槽位的原始值**precisely等於**既有登記位址(`0x354fe`/`0x35d60`/`0x35ed2`)，排除誤讀；再交叉指令邊界回溯(58新補、76/78重驗)確認三者皆落在鄰居handler(58→event57`0x354dd`、76/78→§11.5已找到的`0x35d5d`/`0x35ec1`)中段，無獨立語意。**三者definitively確認為table artifact**，58..89最終統計更正為18個具體行為描述/14個table artifact。副作用：doc25§6.3「event58:map25五選一寶物」的入口位址`0x354FE`與「透過event_id58觸發」歸因已撤回(邏輯描述本身不受影響)，該寶物邏輯真正的runtime觸發路徑變成新的未解問題，見doc25§11.7.5。**checkbox可視為此項本身已閉合**；剩餘的「各dispatcher selector生產路徑」與新開的「map25 event58真正觸發路徑」屬另外的開放項，不影響本項58..89 handler語意的收斂結論。
245 - D - doc27§5已列明確剩餘清單(經驗值攻守等級因子/0x2f7b6內cVar4分支/6種傳送魔刃經驗公式/法術命中逐ID核對)，可續靜態分析。
246 - D - 物品系統裝備加成精確累加點與使用效果碼仍未反組譯。
247 - D - 核對doc32 L271/411-435，class_change_targets.json portrait11-13輪轉錯位仍「待查」，未被其他doc解決。
248 - D - 角色名對應需逐圖解FDFIELD roster才能繼續補，屬可離線靜態分析。
252 - E - FD2.SAV剩餘主要gate為一般玩家有效槽E2與current-battle restore，需DOSBox。
264 - B - SoundFont試聽+TIMB配器對映屬人耳判斷，agent無法自主完成。
272 - C - 讀`tools/decode_story_text.py`確認無`--script-json`旗標，純未實作。
273 - C - `gen_campaign.py`自動生成campaign.json仍是純implementation，且本檔74行已將其降級為candidate scaffold。
274 - D - `remake/internal/campaign`已有`handler_script.go`/`menu_state.go`等疑似涵蓋ScenarioRunner需求，但未逐一核對是否等同完整需求，保守標D（A傾向強，建議下輪覆核）。
302 - C - Grep `remake/internal/battle`與`main.go`均無戰場選單狀態機(移動/攻擊/待機/道具/結束)對應實作，純未做。
304 - D - 敵方AI回合完整權重/target selection仍缺，可續靜態分析（runtime execution另偏E）。
305 - E - 敵方AI雙預選bridge自述尚缺同一原版runtime動態trace，需DOSBox。
343 - C - Grep未見winCondition/checkVictory/advanceTurn等函式，純未實作。
344 - C - headless確定性回歸(固定種子)屬測試基礎建設實作。
348 - C - 與272同一工具(`--script-json`)，同樣未實作。
353 - E - DATO頭像剩「完整frame/grid、speaker layout與runtime dialogue parity」，依專案慣例需DOSBox E2判定。
359 - C - 音效系統開關(SoundFont/MT-32 selector)屬UI功能實作。
360 - C - SFX接入是把已抽取音效資產接進引擎，屬工程實作。
364 - C - 自動生成campaign.json工具屬工具鏈實作。
365 - C - ScenarioRunner狀態機屬引擎實作。
366 - D - 核對doc32 L150-186，0x602ad table base/stride/215-row prefix仍未閉合，可續靜態RE。**已解(2026-08-24,doc32§1.3)**:base`0x602ad`/stride`0x17`/215列(ID0..214)/與相鄰table零間隙邊界，獨立覆核`FUN_0004e8bc`四項核對全數byte級吻合。
367 - E - doc58 L560明載church僅60-70%完成度且無DOSBox逐幀比對(未達E2)。
368 - D - 剩餘+0x22/+0x23/+0x24 DX/race/multiplier欄位資料化屬靜態RE工作。**已勘誤+已解(2026-08-24,doc27§8)**:這三個offset根本不是DX/race/multiplier，是指令17/18/19暫時buff持續時間byte，2026-08-19已逐指令反組譯完成，剩下只是remake工程接線非RE缺口。
369 - E - 明文「raw race/multiplier欄位與實機回歸」需DOSBox對照。
370 - D - 未見殘留任務語句但也未找到其他doc明示已結案，保守留D（未深入查證）。
371 - E - 明文「仍需原版實機數值回歸」，需DOSBox驗證。
372 - D - 外部攻略頁交叉盤點需持續以EXE table/campaign_full.json靜態核對，不能由攻略頁直接推論。
389 - D - 核對doc50 L35/288與doc56 L1104，`0x3241f` raw FDICON key producer仍未追出，可續靜態RE。**已解(2026-08-24,doc50)**:完整鏈`0x205da→0x1088d`(無條件`SPAWN(0)`)`→0x10b4e→0x10c50→0x11019`已用`call_scan`窮舉caller並反編譯確認。
406 - E - 明文「HIT/EV/DX實機數值差分仍待」，需DOSBox對照。
407 - D - 段落本身已描述完整靜態結論，但未見獨立doc佐證已結案，保守留D（未深入查證）。
408 - C - 剩餘工作是供xvfb驗證remake自身fixture行為，屬對重製引擎（非原版DOSBox）的工程QA。
409 - D - 護衛目標表已大致由doc28涵蓋，但retreat後整備語意未見覆蓋，仍可續靜態比對。
410 - C - 完整GUI/Xvfb讀檔回歸是對重製自身存檔系統的工程測試，非原版RE。
414 - C - 匯出戰場資產+數值表接入屬內容/資產工程工作。
415 - C - 全劇情/對話接入(35章)屬內容整合工程工作。
416 - F - 引用文件`83`在現有`docs/knowledge-base`(僅到58號)中不存在，依賴尚未建立的更大範圍盤點文件。
417 - B - 正常玩法可達性驗證需實際完整遊玩破關鏈，屬人類體驗判斷工作。
421 - C - 桌面交叉編譯+打包純屬建置工程工作。
422 - C - WASM上網頁屬建置工程工作。
423 - C - Android APK打包屬建置工程工作。
424 - C - 玩家向README撰寫屬文件工作，非分析性。
428 - C - EventSystem實作屬程式撰寫工作。
429 - C - 自創戰場+自訂劇本屬內容創作工程工作。
430 - C - 多分支劇情線/多結局屬功能實作工作。
431 - C - 中文編碼回寫工具屬工具開發工作。
437 - E - 剩餘核心「未修改一般玩家有效槽E2」，需DOSBox驗證CONTINUE/delete-overwrite語意。
446 - D - 剩餘「補zero-HP初始record／所有LOADCH分支」屬靜態RE延續工作。
447 - D - 剩餘「完成LOADCH raw record materialization」屬靜態資料抽取延續工作。
458 - E - 自述剩餘門檻是同roster/event/tick的未修改DOSBox一般玩家比較，須live DOSBox。
463 - F - 完整逐欄佈局已由項目自身標記為[阻]設計面擱置(remake用自有struct，不需)。
510 - D - 「0x1cff0 command table」部分已由524-531等[x]項與doc56閉合，但「完整native演出」子句仍未解，整項未達完整A門檻，保守留D。
518 - E - 剩餘清單明文列出DOSBox visual diff為待辦項，須live比對。
532 - D - doc56 L608-616補充更多反組譯細節，但獨立resolver/renderer/SFX/UI仍未接入remake，可續靜態RE。
533 - D - doc56 L618-627與worklist敘述一致，renderer/UI/timing仍未接，可續靜態RE。
534 - D - doc56 L775確認multi-hit/SFX/native UI未接，可續靜態RE。
536 - D - doc56補充equipment recalc已接住，但command transaction/phase-expiry caller/UI仍未接。
538 - D - doc56 2026-08-14補充(L677-689)以`command_labels.json`已解出command20/21/26/27狀態名稱，但engine/UI整合未接，未達整項A門檻。
539 - D - 同538性質，command22="封咒術"名稱已由`command_labels.json`解出，但UI/expiry recompute整合未接。
540 - D - doc56 L698-722已完整反組譯`0x1a30b`全流程並在`main.go:completeTurn()`接線，但equipment recompute/UI/status icon/native command executor未接，非完整關閉。
541 - D - doc56 L724-729與worklist一致，legality/camera/render/UI仍未接，可續靜態RE。
548 - D - doc56 L731-734確認IDs25-27 jump table，並受益於538的status name resolution，UI/status labels仍未接。
555 - D - doc56 L600確認一致，scroll/composite/專用演出/SFX/UI仍未接，可續靜態RE。
557 - D - AoE(range>0)、命中率完全未解，輔助系效果部分已推進但未整合進施法UI，可續靜態RE。
564 - E - doc56 L1354明文sell/equip/transfer仍需own same-state DOSBox traces。
572 - D - doc37結論與worklist一致(spell id不選FIGANI已定論)，`0x2a6bd` command-specific presentation/SFX/命中分支仍待，可續靜態RE。**大幅推進(2026-08-24,doc27§6.5)**:真正位址`0x2cf30`(ID24/28-31)與`0x2d80d`(ID32-35四大絕招)已完整反組譯，倍率/傷害/buff/異常與SFX來源全數釘死；剩逐command命中率數值核對與remake presentation/SFX接線，checkbox維持`[~]`。
575 - D - 歷史snapshot澄清note列出的3個缺口未查到專門解決文件，可續靜態RE（未深入查證每一子項）。
584 - D - round10(本檔約595行)已解決「導出」半部(FDOTHER戰鬥音效池匯出)，但「逐招對照」核心未解，與604/622重複未閉合。
587 - E - UI音效index 2-0xb語意畫面實測需要逐項操作介面聽測對應畫面，需live(DOSBox或使用者)驗證。
603 - B - 使用者聽辨任務；本檔約599行僅解出FDMUS_018=商店，戰鬥曲聽辨本身仍待使用者。
604 - D - 核心「index陣列填值上游、#48-64逐招對照」可續靜態RE，remake接入為次要工程部分。
605 - E - 與587同一項目(UI音效index 2-0xb語意畫面實測)，同理需live驗證。
618 - B - 與603重複，戰鬥曲/勝利曲聽辨屬使用者聽辨任務。
622 - D - 與604同一「+0xd0填值」低優先項，可續靜態RE。
640 - C - 戰場編輯器MVP(網頁HTML/JS+FSA API)屬實作工作。
642 - C - 劇情編輯器(對白+事件表單+商店)屬實作工作。
643 - C - 編輯器能力清單同步(Go --dump-registry)屬工具維護工作。
644 - C - campaign節點圖編輯器(拖線/旗標/敗北路線可視化)屬實作工作。
659 - B - round14(本檔約697行)已完成全33章自動轉錄，但緊接段落指出未經人工精確校對，本項要求的人眼精校性質仍需使用者。
660 - D - 視窗縮放filter查證(可能linear暈染)未見他doc解決，可續靜態code inspection，不需DOSBox（未深入查證）。**已解(2026-08-24,doc35§10)**:交叉核對既有反組譯證據(`0x4e63d` blit無任何imul/fild/fmul縮放運算、present routine`0x11eb0`是逐列320-byte memcpy、標題「2」logo zoom是AFM VM直寫`0xA0000`的預繪幀非runtime resample、VGA mode13h+DOS/4GW純記憶體extender)顯示原版EXE完全沒有數位縮放/內插碼，只在原生320×200渲染；「640-wide work buffer」是離屏scroll-prep區非2x顯示縮放。無原版filter可比對，remake現有`Scale(2,2)`(Ebiten預設`FilterNearest`)即為忠實選擇，不需改動。
678 - B - 明文「容器nosound無法驗;使用者聽辨」。
768 - C - ch02-33全章story節點接script(gen_campaign修+重生成)屬campaign製作工作，非分析。
769 - C - runtime fallback heuristic wiring屬實作工作，項目自述ch02/03 handler beats仍待接線。
791 - D - 緊接的`[x]`項重申MAP/TURN/ENEMY/FRIEND/NPC資源與YES/NO input仍未證實，確實仍開放，可續靜態Capstone/IDA。
819 - C - batch1已提交，剩餘scope(#3 camera-on-party)屬實作工作。
823 - B - 明文「待使用者釐清…不瞎編視覺」。
848 - D - save/chest已由doc25§9解決，入隊/等級上限仍待逐一轉成可編輯規則，可續靜態RE。
849 - D - 核對`campaign_full.json`，`story_ch23`節點無`handler_binding`，「不能僅因renderer存在就接story_ch23」現況仍真，可續靜態Docker Capstone。
851 - D - doc58續十六(約L3072-3089,2026-08-18)證實`0x24d22`/`0x11d40`實屬ch24 handler非ch23，項目位址前提有誤，但`postbattle_ch23_persist`在`campaign_full.json`仍是無`handler_binding`的空placeholder，實質缺口仍開放。
852 - D - 剩餘「indexed double-buffer visual adapter」屬渲染管線RE缺口，可續靜態分析。
853 - E - 自述mapping僅關閉文字索引非event61玩家路徑；本檔約966行確認ch26 event61僅達E1，完整玩家路徑驗證需live E2。
854 - E - 明文「仍缺未修改一般玩家/CONTINUE的同狀態E2」，需live DOSBox。
857 - D - 剩餘「視覺/效果calls…資料化」屬RE工作（對話/gate本身已解，cf. 約1021行）。
862 - D - 卡在`0x2bce5` ending renderer(party montage資產解碼)，與1017-1020同一鏈仍開放。
863 - D - 同862之blocker(`0x2bce5` ending renderer)。
864 - D - 同862之blocker。
865 - D - 同862之blocker。
866 - D - 同862之blocker。
867 - D - 同862之blocker(terminal handler，此cluster的master item)。
874 - D - 項目自述「既有unit_present metadata不完整，維持fail-closed」，後續項目未完全關閉此缺口。
897 - C - 剩餘工作純屬BIOS-tick clock adapter實作，非分析。
898 - D - 可能已部分由`ComposeNativeTransitionFrame`覆蓋，但同性質的874仍明文fail-closed，保守留D而非冒進判A。
899 - D - 鏈條延續至1017-1020(仍為`[~]`，party-montage renderer未完成)。
966 - D - 項目自述準確反映現況(ch01已完成,ch02+逐章view/gate provenance仍缺)，非過時，可續靜態逐章RE。
1017 - D - 卡在`0x2c548`後的party montage資產解碼(FDOTHER#56/TAI#3/FIGANI/DATO)，可續靜態RE。
1018 - D - 同1017之montage解碼blocker。
1019 - D - frame-decoder contract大致關閉，剩餘gate同1017。
1020 - D - editable IR已建，卡在同1017之montage renderer。
1038 - D - native end-turn完整caller/team predicate/AI completion timing未見後續doc關閉，可續靜態反組譯。
1042 - D - 庭院段已由`scene-decode/ch1-meadow.md`完整解出，但項目文字涵蓋的森林段仍由doc53 L44與doc44 L115-117標記partial，因半數仍開放不判A，保留半解狀態。
1065 - D - 此項本身即doc57本身，該矩陣持續更新到2026-08-15仍多欄位partial，屬持續性靜態IDA/Capstone稽核工作。
1069 - C - 項目內文子問題已由後續1100-1116(`[x]`)閉合，結尾自承唯一剩下的是「仍未接runtime renderer」，屬工程整合。
1117 - D - doc57 UI-04 row仍列native argument↔weapon min/max mapping/AOE/LOS/不可用目標灰化未解，與項目描述一致仍開放。
1118 - D - doc32 L169明確remake暫沿用獨立驗證的normalized武器射程，不得臆測raw `+0x0b..+0x0d`，仍待對位`0x14344` caller，屬靜態RE。
1138 - D - doc57 UI-03 row明列剩餘缺口含end-turn entry，需更多`0x1a30b`家族靜態trace，非必須live DOSBox。
1139 - D - doc57 UI-07 postbattle row顯示大量逐章audit已完成，但仍有章節(如ch16)fail-closed待handler-offset層級靜態稽核。
1148 - E - 項目自陳仍待DOSBox E2 visual/input diff；doc57 UI-10 church row同樣列此為唯一剩餘缺口。
1150 - E - 項目自陳仍需DOSBox E2視聽diff，doc57同章節row確認此為唯一阻擋點。
1160 - E - doc57 UI-11 row同樣措辭確認剩餘缺口為跨畫面初始相位+合法晚期存檔DOSBox差分。
1182 - E - 項目自陳battle field/action/dialog的DOSBox pixel differential仍待補齊，未見任何doc宣稱已補齊。
1183 - C - 防呆性宣告，其要求的resource provenance與indexed buffer contract實質已由後續`[x]`項閉合，剩下是組裝成完整renderer的工程整合。
1192 - C - 與1183同一缺口具體化版本，FDOTHER#56/FIGANI/DATO/fade皆已由後續項目個別RE並`[x]`關閉，剩純組裝工程。
1249 - C - 項目自陳七拍movement已知但尚未materialize進runtime loop，屬工程接線而非新RE。
1314 - D - doc56 L2064-2069(2026-08-02)記載幾乎逐字相同的未解狀態，確認仍未解，需更多靜態反組譯把ch29/ch30結局流程接起來。
1318 - C - 項目自陳剩餘缺口是item selector UI/indexed presentations/engine integration，`0x20c6f`本身RE已關閉。
1344 - C - 項目自陳仍未完成全roster/save/export的raw record接線，raw identity byte本身RE已由前一項關閉，剩下為工程接線。
1354 - D - 項目自陳剩餘為`0x602ad` table真正邊界與未命名欄位語意，屬可續靜態Capstone/IDA分析。
1509 - E - doc58(約L2219-3451)記載此位址跨十餘輪live DOSBox-X session追至2026-08-19仍未解，使用者已決定暫緩，確屬需live驗證。
1511 - D - `docs/data/chapter_beats/ch22_post.json`的`0x24838`呼叫仍標記`op:unknown`，campaign binding真正未解，可用靜態FDTXT對照方式續做（未深入查證確認能否完全靠靜態解決）。
1515 - D - 核對`remake/internal/battle/native_inventory_search.go`與`main.go:2683-2695`，raw gate已完整實作並如實反映項目自身描述的minor殘留範圍，非其他doc額外解決，非A但近乎完成。
1578 - C - 成功/扣款動畫已由DOSBox E2閉合，剩餘阻擋是把其他子面板接進正常campaign/save生產路徑，屬工程整合而非新RE。
1604 - F - 明文卡在動態turn-writer/group-formula通用pending-group binding及`battle.State`→`Game`/controller的原子handoff，屬更大範圍重構前置依賴。
1630 - F - 與1604同一家族/blocker(`ReadyForContinue=false`)，子項仍`[~]`，同樣卡在controller handoff重構。
1790 - E - 明文尚缺一般玩家有效槽E2，需DOSBox live比對。
1828 - E - 明文要求「DOSBox同camera/roster/tick逐幀比對」，依定義需live驗證。

已改標`[x]`的18項A類（依據見各行內文）：265、303、349、357、358、384、585、586、601、619、680、844、901、959、960、1053、1385、1431。

> **⚠ 位址勘誤總註記(2026-08-19/20，兩個獨立批次交叉印證)**：`0x2a6bd`與`0x276ec`這兩個在`13-battle-menu-system.md`／
> `37-spell-effect-figani.md`／`56-fd2-remake-sdd.md`／本檔多處被引用為「native command 大型 presentation/state
> dispatcher」與「ID24 special分支」的位址，經`doc27`§6.3(法術AoE/命中率批次，經`0x1cff0→0x2ff01`逐層反組譯)與
> `doc13`§6(native command 20-27批次，經`getReferencesTo(0x1c81f)`反查)兩個獨立方法各自證實：**在目前
> `FD2Analysis3`(Ghidra headless)project裡，`0x2a6bd`與`0x276ec`都不是有效的指令邊界**（分別落在無關函式
> `FUN_0002a694`調色盤特效與`FUN_000275e6`選單方向鍵cursor handler的中段）。真正的位址是：**`0x2a6bd`→
> `0x2ff01`**（大型 command presentation dispatcher，body `0x2ff01..0x30e24`，3876 bytes，id 0-8走AoE套用迴圈、
> id 24/28-31走derived-strike、id≥32走`0x2d80d`）；**`0x276ec`→`0x2cf30`**（ID 24/28/29/31 derived-strike的真正
> 宿主函式，倍率15/20/12/18數值本身不變，只有位址標籤需修正）。既有功能性結論（如derived-strike公式、command0
> generic pipeline等）本身仍成立，不受影響。本檔對應行（538/539等已在下方逐行加註修正，見「native command ID24
> player special route」／「native commands28/29/31 derived-strike siblings」兩項）；`13`/`37`/`56`三份文件的
> 既有引用因數量多、風險高（怕破壞既有位址級 provenance 敘述），僅在`13`（已有完整勘誤章節）與`37`/`56`各自
> 補一則簡短訂正註記，不逐一改寫每個引用點，讀者遇到`0x2a6bd`/`0x276ec`字面引用時請一律換算為`0x2ff01`/`0x2cf30`。

## Visual parity correction（2026-07-28）

- [x] **RE/FUTURE-GROUP-CONSTRUCTOR-10C50-1B750**：合法 IDA Pro 9.4 固定
  `0x1B750..0x1B83D`、12個直接 caller、即時名冊base與四個raw destination；
  Capstone重核八格`0x40`裝備、`+0x22/+0x23` binary64 1.15＋x87朝零及
  `+0x24` HIT/EV各加15。撤回「`0x1B750`等同`0x1145A`」斷言。production
  現將table base、inventory、exact重算、placement及selector全數在私有candidate
  預檢後原子發布，來源roster失敗不改。三套件Docker回歸通過；完整0x50-byte
  identity、其他caller、phase expiry與DOSBox E2仍待。
- [x] **DOC-ASSERTION-GOVERNANCE-20260728**：repo-wide掃描66個Markdown，撤回會污染remake的現行斷言：攻略不能取代逐章handler/postbattle route；`battle_events.json`與`gen_campaign.py`只是candidate scaffold；DATO／FDICON cache slot／runtime identity不全域恆等；cutscene DSL不是33關完整oracle；historical decision freeze已標superseded。同步修正README、42/56/57目前town/shop E2範圍，並保留「悠妮」與`DATO_075=商店店員`的已核實對應。
- [x] 逐項重審 title、field/HUD、action/target、dialogue、battle、postbattle、town、shop、church、preparation、save/load、ending；town indexed production接線後，完整操作界面視覺還原估計40–45%，不能以75–85%的asset/codec完成度代替。
- [x] README撤回將 `docs/figures/title.png`／`dialogue.png` 標成 remake runtime對照；兩張是raw decode／字型研究圖。
- [~] **UI-VIS-TOWN**：`0x2cd16/0x2cf71/0x11eb0`已閉合3個FDOTHER背景variant、#10 label、FDTXT `0x1ef+selection`、FDICON `0,1,2,1` pulse、6組variant座標與312×192→VGA `(4,4)`；23個town保存raw `native_town_variant`。ch02 variant0 [`selection0–5`](../figures/town-hub-six-selections-original-vs-remake.png) 都達原版／remake raw RGB 整幀相同，Left/Right wrap、Shift+F1 reveal、Enter進variant5及Escape返回selection5亦有input E2；共用 glyph shadow 與誤 reset pulse 已修。**variant1/2已於2026-08-25用平行harness(`townE2`instance,Xvfb`:299`,不干擾同時在跑的`loadE2`)補上原版對照**：由`campaign_full.json`確認`native_town_variant`最早出現1的是`town_ch12`(北山道)、最早出現2的是`town_ch03`(往塞拉村途中)；用既有`fd2save.py`chapter-jump技巧（把機器上ch10進度`FD2/FD2.SAV`的slot0章節byte分別patch成`0x0B`/`0x02`，round-trip自檢通過）LOAD直達`town_ch12`/`town_ch03`hub，不需真的打到該章。原版逐一Right鍵cycle（`0→4→3→2→1`，與既有`nativeTownMoveSelection`一致）截到5個真實selection(0酒店/1武器店/2出口/3道具店/4教會)，並用`FD2_ORIGINAL_FDOTHER`指向機器上原版`FDOTHER.DAT`＋`FD2_CAMP_NODE=town_ch03|town_ch12`＋`FD2_SHOT_TOWN_STATE=<sel>,0`跑同一份`fd2-linux-verify`(2026-08-15 build)產生remake對照幀，兩兩視覺完全一致（背景/帳篷造型顏色/角色站位/label文字皆符）；統計上兩個variant全部10對selection的320×200裁切後resize比對，matched pair mean-abs-diff穩定落在18(variant2)/23(variant1)、exact-pixel比例51%/35%，對照故意錯配的negative control（ch03原版vs ch12 remake）mean-abs-diff躍升至~56、exact-pixel驟降至5.4%，量化排除巧合比對。**誠實限制**：這次用的是`import -window root`截全螢幕再手動裁切/resize比對，不是variant0當時用的320×200 raw framebuffer精確擷取，故未達variant0等級的byte-exact RGB MD5全幀雜湊；ch03的secret gate reveal（`native_secret_gate.scan_code=95`＝BIOS Ctrl+F2）依`selection=1`gate要求送出`ctrl+F2`兩次均未觀察到selection5出現，未排除是scan code換算錯誤或xdotool合成鍵不被BIOS層接受，此點誠實記錄為未解決。截圖：[`town-hub-variant1-original-vs-remake.png`](../figures/town-hub-variant1-original-vs-remake.png)、[`town-hub-variant2-original-vs-remake.png`](../figures/town-hub-variant2-original-vs-remake.png)（各為5×2 grid，上排原版DOSBox-X、下排remake）。剩餘缺口：variant1/2的byte-exact MD5全幀比對、secret gate reveal、Left/Right wrap與Shift+F1在這兩個variant的input E2。
- [~] **UI-VIS-SHOP**：四個callee與secret selection+BIOS-scan gate皆已接production；ch02 variant1/3/5的service0 selected phase均達原版／production raw RGB整幀相同，variant5另閉合四service、wrap及Escape→town selection5。ch02 weapon purchase list四個selection、Yes/No、gold0不足金及gold1000裝備收件者selection0/cycle1也已全幀AE=0；selection0按Down到selection1經exact-pixel相位同步後，remake三cycle亦各有整幀AE=0（recipient E2僅screenshot-only typed-party bootstrap，不代表完整campaign/save trace）。success裸畫面撤回過早DATO第0幀覆蓋後，25個原版原子樣本各有整幀AE=0；唯一非零樣本只差`0x16886`效果寫入途中的兩點。`0x2d516`扣款odometer修正roll y=98後，16個原版atomic samples各有整幀AE=0。**四人以上recipient scroll已於2026-08-25用平行harness（`shopE2`instance）live DOSBox-X實測閉合**：LOAD既有ch06進度真實存檔（非chapter-jump合成、非screenshot-only bootstrap）進`town_ch07`武器店，9人真實roster對硬皮甲有6人合格收件者（索爾/亞雷斯/哈諾/希莉亞/鐡諾/貝克威），連續Down/Up操作證實原版三列視窗一次只捲動一列（第4次Down才觸發捲動，非跳3列）、上下皆bounded不wrap、Left/Right on此畫面no-op、捲動箭頭指示於頂/底端正確消失，與production `NativeThreeRowWindow`/`advanceNativeShopEquipmentRecipient`（`remake/internal/campaign/church.go`、`remake/cmd/fd2/native_shop_ui.go`）演算法逐步吻合。截圖見[`shop-equipment-recipient-scroll-window1/2/3-original-dosbox.png`](../figures/)。下一gate是no-recipient/full、sell/equip/transfer child panel DOSBox E2與其他章節狀態。
- [x] **CAMPAIGN-JOIN-LOADCH-PERSISTENT-PARTY-BOOTSTRAP**：修正正常ch00 JOIN只記`partyMembers/partyJoinOrder`、首次LOADCH未建`partyRoster`，導致帶native identity的第一個`sync_party`因找不到既有record而全數skip。`applyLoadCH`現只在已有JOIN chronology時依typed scenario補缺少record，既有進度優先，direct/debug replay不造persistent state。真實ch00 scenario/order `[0,9,4,30]` regression驗證ch02布衣候選為`[0,9,4]`且首次native-identity sync可命中；這是remake runtime bridge，不宣稱native FD2.SAV或完整campaign E2。
- [x] **UI-SHOP-STANDALONE-EQUIP-PRODUCTION**：Docker Capstone重讀`0x2f883/0x1bffe/0x17e0b/0x1b9de`，撤回「獨立裝備沿用purchase商品／收件者widget」的假設。production現走service2→兩欄角色roster→11→0完整item/status panel；相容item經`0x1c1c3→0x1c142→0x1b750`原地更新flags/能力並重畫，incompatible無發明feedback，離開0→11 restore shop再回roster。`EquipNativeCompactSlot`驗證raw occupied order與compact inventory/equipped一致，保留ignored raw hole/stale byte，divergence原子拒絕。Docker/Xvfb production regression通過；DOSBox E2仍待。
- [x] **UI-SHOP-TRANSFER-PRODUCTION**：`0x2f8ea`同時由shop service3與church raw1呼叫，不是任一場景專屬。shop production已接FDTXT512 source prompt→全party roster→FDTXT511 empty或`0x2dc55(mode1)` item list→FDTXT510→全party destination roster→FDTXT506 full或raw remove/append/recalc→512 loop。重核撤回「destination排除source」的高階假設：source本人保留為候選，未滿欄時self-transfer會把item以unequipped狀態移到尾端。`ValidateNativeInventoryProjection`與full raw-flag gate原子拒絕投影分歧；Docker/Xvfb production、empty/full/self regression通過。
- [~] **UI-SHOP-RECIPIENT-INPUT-E2**：原版已實測裝備收件者由selection0按Down到selection1、再按Up回selection0，Left/Right不改selection。production共用純`advanceNativeShopEquipmentRecipient`：bounded Up/Down、horizontal no-op、同tick Up後Down順序與`NativeThreeRowWindow`stateful origin均有直接input regression；helper-level invalid count/selection/start rejection亦有測試，production caller會在索引recipient前fail closed回purchase list。以乾淨原始SAV/TMP加三處已驗route patch重跑，`waitpixel(175,90)=101,121,121`在Down前同步人物動畫相位；0.05／0.20／0.40秒原版樣本分別與remake cycle1／cycle1／cycle0取得整幀AE=0，另兩張對上cycle2，沒有遮罩。故selection0↔1 input/E2已關閉。**四人以上scroll的原版E2已於2026-08-25補上**（獨立平行harness instance`shopE2`，Xvfb`:299`，不干擾同時在跑的ch27 canonical session）：不用screenshot-only bootstrap或chapter-jump合成存檔，改LOAD機器上既有的真實ch06進度`FD2.SAV`（`~/fd2-run`預設來源，9人真實roster）進`town_ch07→武器店`買硬皮甲（`shops.json`未收錄的更晚章節商品，但共用同一套native shop UI/recipient code path，不是ch02專屬邏輯）；6名合格收件者（索爾/亞雷斯/哈諾/希莉亞/鐡諾/貝克威）逐一Down/Up操作，逐幀screenshot證實：三列視窗、選到第4個候選人才觸發捲動（非提前跳頁）、每次只捲動一列、上下端bounded不wrap、Left/Right不影響此畫面、捲動箭頭於頂/底端正確隱藏——與`NativeThreeRowWindow`（`remake/internal/campaign/church.go:76`）＋`advanceNativeShopEquipmentRecipient`（`remake/cmd/fd2/native_shop_ui.go:29`）的既有演算法逐步一致。截圖：[`shop-equipment-recipient-scroll-window1-original-dosbox.png`](../figures/shop-equipment-recipient-scroll-window1-original-dosbox.png)（初始索爾/亞雷斯/哈諾，僅下箭頭）、[`window2`](../figures/shop-equipment-recipient-scroll-window2-original-dosbox.png)（捲動1格後亞雷斯/哈諾/希莉亞，上下箭頭皆有）、[`window3`](../figures/shop-equipment-recipient-scroll-window3-original-dosbox.png)（清單底端希莉亞/鐡諾/貝克威，僅上箭頭）。項目仍為partial：no-recipient/full、sell/equip/transfer child panel與其他章節DOSBox E2仍缺。
- [x] **RE/UI-TOWN-SECRET-GATE**：Docker Capstone閉合`0x2cd16→0x4e4b9`與`0x2cde0..0x2cef7`：每章0x1f-byte town record `+1`必須等於目前五項selection，`+2`必須等於BIOS Shift/Ctrl/Alt-F1..F10 scan，才把selection寫5。新證據撤回「chord立即進店」：hub先重畫selection5 icon/label，後續Enter才由`0x2d093→0x2d28c`進variant5 shop。23筆已資料化為editable `native_secret_gate`並接runtime；modified F2/F3/F5/F9不再誤觸remake全域shortcut。撤回`found_secret_*`永久顯示第六項等同原版的斷言；ch02 E2已由後續項目閉合，其餘town仍待逐章驗收。
- [~] **UI-VIS-PREPARATION**：`0x318ad..0x321c8` 已修正
  `0x32004` 的輸入正規化，並證實選滿後先由 `0x320fc` 重排隊伍、再走
  `0x31d3c..0x31db4` 最終確認。外層 `0x2d093` 另證實先顯示 FDTXT
  `0x201`「要進入戰場嗎？」；可選記錄不超過15／19時完全略過 `0x318ad`，超過才進
  30個全零選取旗標。城鎮重製流程已改為出發確認→按名冊門檻略過或選人→最終
  確認，任一取消依可編輯 `cancel` 回城；另以 `0x2cad7` 分開無城鎮路徑的
  FDTXT `0x19a`「要記錄戰況嗎？」與可選存檔，拒絕時仍進選人。已刪除預先全選與小隊不足按Escape
  強行出發。正常序章→第1章哈諾加入→戰後同步五人→羅德鎮→整備回歸已通過，
  並補上後加入角色的持久快照。2026-07-29 更新：選人主畫面、角色狀態、
  待機週期及最終確認已接原版索引色正式路徑；`0x1f42d` 已更正為戰場進入
  演出，不是選人 slide。城鎮 FDTXT `0x201` 提示現保存實際 town frame，
  無城鎮 FDTXT `0x19a` 提示依 `0x2cc04` 使用黑色來源；兩者都接
  6＋4＋兩 tick 脈動＋4＋5＋還原，肯定存檔／轉場只在還原幀呈現後執行。
  2026-08-02 IDA／Capstone勘誤：`0x320fc` 的目的index從1開始，selection
  byte `i` 對應persistent record `i+1`，record0固定且不消耗quota；重製已改為
  固定1筆＋可選15／19筆，正常戰場上限為16／20。舊「最多只上場15／19人」
  行為已撤回，證據見[`fd2_preparation_fixed_record_ida.txt`](../data/ida/fd2_preparation_fixed_record_ida.txt)。
  保存 record 與 ch02 departure 生命週期證據圖。仍須晚期合法存檔、
  跨畫面初始相位與 DOSBox 同狀態實機差分，故維持部分完成。
  **2026-08-25 平行 harness（`prepE2`，`:199`，獨立於當時可能同時在跑的其他 instance）
  用機器上唯一真實存檔（`~/fd2-run/FD2.SAV` 4 槽，非 chapter-jump 合成）補測**：
  slot1（最新進度，raw chapter `0x1a`＝第27章「命運的交會點」，13 人真實名冊
  `[0,9,4,30,1,8,2,10,13,12,5,11,6]`）LOAD→軍營帳篷場景→`Right`×3 cycle到「出口」→
  Enter，完整重現 FDTXT `0x201`「要進入戰場嗎？」YES/NO 確認框（含 NPC 頭像）；
  選 YES 後**畫面直接跳進約10段戰前對白**（「這裡就是遺跡了嗎」…「一切的謎底就在
  眼前了！」，逐句與續四十五/續四十八舊記錄的對白內容完全吻合），**全程沒有出現
  任何選人核取方塊畫面，也沒有出現獨立的 `0x31d3c` 最終確認畫面**，對白結束後
  直接進入戰鬥地圖、13 人全隊已自動部署完畢（索爾 HP823/823，與舊記錄一致）。
  這與 production `acceptTownDeparturePrompt`（`remake/cmd/fd2/main.go:3066`）「
  `len(prepIDs) <= prepLimit` 時直接 `leavePreparation("confirm")`，完全跳過
  `prepSelecting`/`prepConfirm` 兩個階段」的既有邏輯逐步吻合。截圖：
  [`preparation-ch27-departure-original-dosbox.png`](../figures/preparation-ch27-departure-original-dosbox.png)
  （3 格：YES/NO確認→對白開場→部隊已部署的戰鬥地圖）。
  **重要限制、誠實記錄**：續九（2026-08-17）已用 Ghidra 靜態核對出一張逐章旗標表
  （`DAT_000523e7`，chapter-indexed）：只有第23、24、25、28、29、30、31章會顯示
  選人畫面，其餘（含這次測試的26/27章）全部是0（略過）。機器上僅有的4個真實存檔槽
  （ch27/7/8/9）**全部落在「略過」的章節區間**，且本作僅有13名可招募角色，正常
  單周目任何時間點的名冊人數都不會超過15／19門檻——換句話說，**用這台機器現有的
  合法存檔，結構上不可能走到選人核取方塊畫面或 `0x320fc` 重排隊伍那條路徑**；
  過去唯一真正操作過該畫面的續八～續十一（2026-08-17/18）用的是 ch23/ch24
  chapter-jump 合成存檔＋binary-patch 門檻，不符合本項「合法存檔」的驗收標準。
  故 `0x318ad` 選人核取／`0x320fc` 重排／`0x31d3c` 選滿後最終確認這三段，在「一般
  玩家合法存檔」前提下**目前沒有已知路徑可達**，仍待下一輪判斷是否改用「合法途中
  存檔＋真的打贏ch22前所有戰鬤推進到ch23」這種更高成本的方式，或修正驗收標準本身。
  同輪嘗試用 `fd2-preparation-oracle` 做同狀態 pixel diff，但這台機器**未安裝 Go
  工具鏈**（`go`/`golang` 全機找不到，需要下一輪先處理環境），故本輪僅完成
  逐格畫面的定性比對，未做位元組級差分。
  **2026-08-26 續輪（純靜態，未碰 DOSBox-X）：re-derive「19 vs 13」矛盾，結論是
  存檔進度缺口不是遊戲邏輯缺口**。先用 `ghidra_batch_probe.py` 對 doc56 UI-11
  引用的 `0x318ad/0x31e80/0x32004/0x320fc/0x31d3c/0x318c7/0x31a29/0x36d98` 八個
  位址逐一 `function_bounds`：**全部 `in_function:false`**，證實 writerfire「doc56
  整備 UI 位址也是舊版殘留」的猜測；嘗試用 `call_scan(0x10620)`（`0x32004` 已知
  行為特徵）重新定位，找到 `+0x190` 這個對 `0x32004→0x32194`／`0x318c7→0x31a57`
  兩點都成立的局部 delta，但套用到 facility 入口 `0x318ad` 本身、`0x320fc`、
  `0x31d3c` 都落在指令中段或 `end_of_code`，**這三個對回答部署上限最關鍵的位址
  本輪仍未精確定位**，細節與 bytes dump 見 `known_address_errata.json`。
  **關鍵發現**：這個「目標 15／19 vs 只有 13 人」矛盾其實已經在完全獨立的
  `58-remake-live-verification-log.md` 續九～續十一（2026-08-17/18，task #118，
  比 prepE2/writerfire 早約一週）被完整反組譯＋live 驗證過，且是直接對照
  **實際在跑的 509158-byte `FD2.EXE`**（本輪用 `PUSH 0x164` 序列在該檔案裡
  重新核對出 `0x2ff01` 對應唯一 file offset `0x55f15`，確認就是同一份「真檔案」，
  不是任何 Ghidra 專案的鏡像）做純檔案 byte-signature 搜尋，不是猜測：file
  offset `0x50f4e`＝目標人數立即值（15 預設／章節>26 時19，與本節逐章旗標表、
  doc56 `NativePreparationPartyLimit`、doc25 §9.1 三方獨立吻合，19 本身不是
  誤讀）；`0x510f7`＝`CMP EAX,EBP;JNZ`（選滿才能離開，沒有「選不滿也能確認」
  的隱藏路徑，L232 起記錄的續八～續十一原本只把這段當成「不符合法存檔驗收標準」
  略過，沒有進一步追問「19 這個數字本身為何存在」）；並用 live single-step
  證實游標移動寫死排除陣列最後一個 index（`roster_count-1`），13 人存檔時
  index 12 永遠無法到達，這正是「選人畫面卡死＋Escape 只會重置」的真正成因。
  獨立核對 `docs/data/chapter_beats/ch{NN}_post.json` 的 `"join"` op 數量：
  ch01-10 共 9 次、**ch11-22 共 13 次**（與續九引用的「背景 agent 查證 ch11-22
  間共13名角色加入」逐一吻合，兩個獨立資料來源給出同一個 13）、ch23-29 再 2
  次——代表一個真的照劇情打過來（不是章節跳躍合成）的存檔，抵達顯示選人畫面
  的章節（23-25/28-31）時隊伍規模粗估已在 20+ 人，遠超過 15／19，湊滿並不難。
  **也就是說「本作僅13名可招募角色，正常單周目名冊人數都不會超過15／19門檻」
  這句 L235-236 的既有結論需要修正**：13 這個數字對「機器上現有的4個存檔＋
  writerfire 用的 raw ch27 章節位元組合成捷徑存檔」成立，但不是遊戲本身的
  結構性上限——這些存檔全部繞過了 ch11-22 這段負責加人的劇情，不代表劇情
  正常推進時的名冊規模。**仍未解決、留給下一輪的具體問題**：續十一反組譯游標
  程式碼時另記錄「渲染迴圈固定只畫 `EBX=0xb..0`(12張portrait)，不論真實隊伍
  人數多少」——若這句話字面成立（渲染上限硬編碼12，不隨 `roster_count` 縮放），
  即使隊伍真有20+人，這個畫面仍可能永遠只能選12個，推翻上面的樂觀結論；但
  該輪唯一測過的存檔 `roster_count-1` 剛好也是12，兩個假說（動態上限恰好算出
  12；或硬編碼常數12）在單一資料點下無法區分，需要下一輪拿一個 `roster_count
  ≥15` 的存檔實測才能分出勝負。本輪判斷靜態證據已足夠支撐上述結論，未嘗試
  live DOSBox-X 驗證（時間/風險考量，留給下一輪視情況決定）。完整推導過程見
  `docs/knowledge-base/25-battle-event-system.md` §9.1 本輪新增段落。
- [~] **UI-VIS-LOAD**：合法 IDA 9.4 證實 `0x25F48` 載入 FDOTHER #13，
  `0x30437` 使用 entry16（310×86）於 `(5,112)`，不是 FDOTHER #5
  對話框。production 已改走 FDTXT #0／原版字型／palette 的 indexed
  compositor；空槽 320×200 與 DOSBox oracle 全幀 RGB 相同，並新增目前
  source 的 [`load-empty-remake.png`](../figures/load-empty-remake.png)。
  `/tmp` 修改存檔的 chapter1 有效槽與 production 也全幀 RGB 相同；這只
  關閉有效槽排版，成功 native restore、delete/overwrite 與 roster ABI
  仍待 E2。**2026-08-25 平行 harness（`loadE2`，`:199`，不干擾同時可能在跑的
  canonical/其他 instance）真機補測，一般玩家未修改存檔、非合成路徑**：
  - **native restore 與 roster ABI 已 E2 關閉**：標題 START/LOAD/CONTINUE
    確認全幀渲染後，↓ 選 LOAD，四槽畫面（`1)第二十七章…2)第七章…3)第
    八章…4)第九章…`）與機器既有 `~/fd2-run/FD2.SAV`（4 槽皆非空，
    slot0..3 raw chapter=`0x1a/0x06/0x07/0x08`）逐槽比對顯示章節=raw+1，
    與 `fdsave.py`/`docs/data/fd2_load_slots_ui_ida.txt` 記錄的公式一致；
    選 slot2（第七章）Enter 後畫面黑轉場、gameplay 實際恢復到章節7城鎮
    （酒店旁街道），非僅静態排版——[`load-slot2-restored-gameplay-original-dosbox.png`](../figures/load-slot2-restored-gameplay-original-dosbox.png)。
    進入酒店 NPC 對話後的 party roster widget（`NativeThreeRowWindow`
    同款兩欄×三列）完整捲動顯示全部 9 名成員，逐一比對
    `tools/fd2save.py` 對同一 `FD2.SAV` slot1（0-indexed，即畫面
    slot2）解出的 `roster_char_ids=[0,9,4,30,1,8,2,10,13]`
    （索爾/悠妮/亞雷斯/蓋亞/哈諾/希莉亞/鐵諾/瑪琳/貝克威，經
    `native_character_catalog.json` id→name 換算）：畫面兩欄×三列、
    row-major 讀序與此陣列逐一精確吻合（含捲動後第二頁）——
    [`load-slot2-roster-abi-crosscheck-original-dosbox.png`](../figures/load-slot2-roster-abi-crosscheck-original-dosbox.png)。
    Roster ABI（順序與身分）視為 E2 關閉。
  - **delete：靜態證據已排除、非「仍缺」**。`docs/data/fd2_load_slots_ui_ida.txt`
    明載 `0x30550` 四槽輸入迴圈契約僅 `slot 0..3、上下 bounded 不循環、
    Enter/Space 確認、Escape 取消`——沒有第五個「刪除」分支。本輪 live
    嘗試（數字鍵、額外方向鍵）在該畫面均無額外效果，與此靜態證據一致。
    原生 LOAD 四槽畫面不存在刪除功能，這是可關閉的結論，不是尚待驗證的
    缺口；remake（`native_load_slots_ui.go`）本來就沒有實作刪除，兩者
    現在確認是**行為一致（都沒有），不是 remake 的缺失**。
  - **save/overwrite：locate 到正確原生觸發點，但尚未在 live 環境親眼
    看到磁碟真的被覆寫，仍列 partial**。`docs/knowledge-base/25-battle-
    event-system.md` §9.1 記載 writer `0x30012` 只有兩個呼叫者，其一是
    `0x2ccb6`（城鎮 hub option2「要進入戰場嗎？」confirm 之後）。本輪
    在 town hub（非商店本身，是酒店/武器店/道具店/教會/**出口**五格可
    互相 wrap 切換的那層，`Left`/`Right` 有效、`Up`/`Down` 對它無效）
    找到「出口」格，Enter 後正確跳出 FDTXT `0x201`
    「要進入戰場嗎？」YES/NO confirm——[`town-hub-exit-battlefield-confirm-original-dosbox.png`](../figures/town-hub-exit-battlefield-confirm-original-dosbox.png)，
    與 doc25 §9.1 描述的存檔閘門文字完全一致。選 YES 後完整跑完章節8
    開場過場（約 20 次對話 Enter）直到真正進入戰鬥地圖，但期間全程用
    `md5sum`/`fd2save.py` 監控 harness 私有 `FD2.SAV`，checksum
    （`0x002777a7`）與四槽內容全程逐位元組未變、mtime 也未更新（同目錄
    `FD2.TMP` 則持續更新，證實 DOSBox 進程確實在正常寫檔，只是沒有寫
    `FD2.SAV`）。可能原因：這次是經新載入的 slot2 直接推進到下一章，
    存檔所需的某個前置狀態（例如「目前作用中槽位」指標）未被這條
    live 路徑滿足；也可能 hub「出口」實際觸發的是另一個外觀相同但非
    `0x2cad7` 分支的確認框。兩者都未證實，誠實列為**仍需下一輪對
    `0x2ccb6`/`0x2cad7` 做 live 斷點或 Ghidra 交叉確認**，不得倒推成
    「原版此路徑不存檔」。因此 overwrite 動作本身（selection 應該覆寫
    哪一槽、是否有覆寫前確認）**這輪未能實測到**。酒店 NPC 對話框
    右下角另有一組 4 icon（狀態／存讀／離開），對它的方向鍵/滑鼠輸入
    在本輪測試中始終無法可靠控制選中項（Left/Right/Up/Down/滑鼠點擊
    均未觀察到穩定的位置移動證據，且重複同一動作序列出現不一致結果），
    這個 icon row 的真實輸入 ABI 仍是未解問題，留給下一輪。
  - **2026-08-25 平行 harness（`tavernE2`，`:199`，與同時在跑的 `saveE2`
    互不干擾）續測，酒店 NPC 對話框 4-icon 輸入 ABI 之謎已完全解開，
    且順帶 live 驗證出一條目前唯一已知「確實會寫入 FD2.SAV」的路徑**：
    - **根因不是輸入不可靠，是這個 widget 完全沒有可見的選中游標渲染**。
      逐鍵窮舉（Left/Right/Up/Down/Tab/數字鍵/F1-F10/Insert/Home/End/
      PageUp/PageDown/KP_Left/KP_Right/KP_Up/KP_Down/滑鼠點擊，每次都
      在按鍵前後各截一張 320×200 全幀比對）證實：**Up/Down/Tab/數字鍵/
      滑鼠點擊對這個 icon row 完全是 no-op（AE=0，多次獨立測試零例外，
      不是偶發丟鍵，是這幾個鍵本來就沒接這個 widget）**；**Left/Right
      則是每按一下都確實把一個內部游標移動剛好 1 格，但游標移動本身
      在畫面上零像素變化（4 個 icon 方框完全不會高亮/變色/加框），純黑
      箱**，這正是上一輪判定「無法可靠控制選中項」的根本原因——上一輪
      是在等一個從未存在過的視覺回饋，不是方向鍵真的沒反應。用「先按
      N 下 Right，再按 Enter，觀察 Enter 實際打開哪個畫面」的間接探測法
      逐格驗證，確認游標是 **bounded 不 wrap 的 3 格**（index 0..2，即使
      畫面畫了 4 個 icon 方框，Right 按到第 3 下之後也還是停在 index 2，
      同一個「要離開戰場嗎？」畫面，第 4 個 icon 方框未觀察到可達成的
      獨立語意，維持未解）：
      - **index0（放大鏡+對話泡）＝狀態**：直接開啟既有已 E2 關閉的
        `NativeThreeRowWindow` 兩欄×三列 roster 總覽（與 loadE2 輪
        `roster_char_ids` 交叉驗證過的同一個 widget）。
      - **index1（磁片+左箭頭）＝存檔，本輪 live 寫入成功並完整驗證**：
        Right×1+Enter 開啟一個與標題畫面 LOAD 選單同排版的四槽清單
        （`1)第二十七章…2)第七章…3)第八章…4)第九章…`），對 slot1
        按 Enter 後畫面顯示「**記錄儲存完畢！**」，`FD2.SAV` md5
        由 `e6d9a35756cddfc2519969b10f039181`→`9f35a4488cc36e596561b02
        3bbebe15d`、mtime 同步更新；`tools/fd2save.py` 解出 slot0（對應
        清單「1)」）的 raw chapter 由原本的 `0x1a`（第二十七章）改寫成
        `0x06`，與這次 LOAD 進場用的 slot2（`0x06`，即「第七章」）目前
        session 的 roster_char_ids/currency（`[0,9,4,30,1,8,2,10,13]`／
        `0x0098b811`）逐位元組相同，證實這是把**目前 session 的即時進度
        真的寫進了選中槽位**，不是介面裝飾——[`tavern-inn-icon1-save-
        slot-list.png`](../figures/tavern-inn-icon1-save-slot-list.png)、
        [`tavern-inn-icon1-save-complete.png`](../figures/tavern-inn-
        icon1-save-complete.png)。這是目前整個 91 worklist 唯一一條
        **live 實測「按了之後 FD2.SAV 真的改變」的存檔路徑**，可以拿來
        跟同輪 `saveE2` 用 `LOGC` 追蹤過、確認**不會**寫入的 town-hub
        「出口」路徑對照，下一輪對這條 tavern-icon1 路徑跑同一套
        `LOGC` ground-truth 追蹤，應該就能直接定位真正的 writer 位址，
        不用再猜 `0x2cad7`/`0x2ccb6`/`0x30012` 是否適用。
      - **index2（磁片+右箭頭）＝離開，會整個結束 FD2.EXE 行程、不存檔**：
        Right×2+Enter 開啟「要離開戰場嗎？」YES/NO confirm（與 doc25
        §9.1 記載的 FDTXT 文字相同，但這裡的語意其實是「離開遊戲」，
        不是戰鬥相關）；選 YES 後畫面直接跳回 DOSBox-X 視窗內的
        `C:\>` DOS 提示字元（FD2.EXE 行程整個終止），`FD2.SAV`
        md5/mtime 全程未變——[`tavern-inn-icon2-leave-confirm.png`]
        (../figures/tavern-inn-icon2-leave-confirm.png)、[`tavern-inn-
        icon2-quit-to-dos.png`](../figures/tavern-inn-icon2-quit-to-dos.png)。
      - index3（`C:>_`圖示）：如上所述，Right 游標在 index2 就
        bounded，本輪未能觸及一個獨立於 index2 的第 4 個語意，誠實
        列為未解（可能是純裝飾/未接線，也可能需要目前未找到的另一種
        觸發手法）。
      - Escape 會從子畫面退回 icon row 一層（游標位置保留，不重置）；
        Delete 會直接整個退出對話框回到城鎮 hub 五格畫面（比 Escape
        更深一層的取消），過程中同樣未寫入 `FD2.SAV`。
    - **不是續五十四/續五十五記錄的 Enter/Space 選擇性掉鍵問題，是完全
      不同、而且更確定性的現象**：續五十四/五十五的症狀是 Enter/Space
      在戰鬥地圖移動確認時「時好時壞」，方向鍵不受影響；這裡剛好相反且
      無一例外——Enter/Space（以及 Insert/Home/End/PageUp/PageDown 等
      多個非方向鍵，經測試全部殊途同歸地等同「確認目前游標位置」）本輪
      **100% 可靠**（約 15 次獨立測試零失敗），真正沒有視覺回饋的是
      Left/Right 本身，且游標移動的邏輯生效是 100% 確定的（用後續
      Enter 的目的地間接驗證），不是隨機丟鍵。
    - 機器既有 `~/fd2-run/FD2.SAV` 全程只被讀取（harness `launch` 對
      `~/fd2-run-harness-tavernE2` 隔離複本），本輪造成的 SAVE 寫入只
      發生在這個隔離複本內，未影響機器上的既有進度或其他平行 instance。
  - **2026-08-25 平行 harness（`saveE2`，`:299`，與同時在跑的 `tavernE2`
    互不干擾）續測，用 ground-truth 指令追蹤（`tools/dosbox_exec_trace.sh`
    的 `LOGC`，見 `98-tooling-infrastructure.md`「Ground-truth 執行流程
    追蹤」節）取代純 file-polling，把上一輪「仍需下一輪對`0x2ccb6`/
    `0x2cad7`做live斷點或Ghidra交叉確認」的待辦徹底做掉**：先用
    `BP 0170:1B1F84`（`TXT`直譯器，296 呼叫點，doc35 §9.9 已驗證的通用
    對白函式）等三個斷點做初步嘗試，發現**斷點『registered 但從未命中』
    這個 doc48 §8.4 已知瑕疵這次也踩到**——即使在明顯持續有對白畫面渲染
    的情況下，三個斷點全程零命中，判斷 BP 在本輪環境不可信，改用
    `LOGC` 逐指令 ground-truth 追蹤（同一顆斷點失靈的函式`0x1B1F84`在
    `LOGC`追蹤裡確實有命中，交叉證實不是 delta 算錯，是 BP 機制本身的
    問題）。用同一存檔（LOAD→存檔位 1「第二十七章 命運的交會點」→軍營
    icon 選單`Right×3`→「出口」→「要進入戰場嗎？」YES）重跑三次，其中
    第三次做到最嚴謹的控制組：**先在 debugger console 記下這次 fresh
    boot（`cp -r`複製時刻）的 `FD2.SAV` 原始 mtime 當基準，武裝
    `LOGC`（3 億指令）後立刻按 YES，完整涵蓋「YES confirm → 這裡就是
    遺跡了嗎過場對白」這一段**，事後逐位元組核對：
    - `FD2.SAV` 的 mtime 與 checksum（`e6d9a35756cddfc2519969b10f039181`）
      **全程沒有變化**，與此次 fresh copy 的原始基準完全相同——**不是
      「內容相同所以誤判沒變」，是這次連 mtime 都乾淨比對過，物理上
      沒有任何 write syscall 打中這個檔案**。
    - 去重後的 3 億指令 unique `CS:EIP` 清單裡，**`0x30012`（writer）、
      `0x2ccb6`（doc25 §9.1 認定的唯一 town-flow caller）、`0x2cad7`
      （gate dispatcher 本身）、`0x2fd93`/`0x318ad`（另一條 caller／
      整備入口）全部零命中**，往外各擴 0x100 bytes 鄰域也是零——這不只
      是「writer 沒被呼叫」，是**整條 doc25 §9.1 描述的 gate dispatcher
      `0x2cad7` 本身這次都沒有被執行到**，同一份追蹤裡`TXT`直譯器
      （`0x1B1F84`）確實有命中，證實 delta／追蹤方法論本身無誤，問題
      不在量測工具。
    - 工作目錄逐檔案 mtime 稽核（`find -newermt`）確認整個 session 期間
      唯一被寫入的檔案只有 `FD2.TMP`（遊戲固有暫存檔）與本工具自己的
      `LOGCPU.TXT`/`trace_*.txt`——**排除「寫到別的存檔槽/別的檔名」
      這個候選假說**，也排除「DOSBox-X 掛載的檔案系統快取寫入、沒有
      即時 flush 到 host 磁碟」這個候選假說（不是 flush 延遲，是這次
      CPU 追蹤本身就沒有執行到會發出寫入的程式碼）。
    - **結論修正**：上一輪列的「可能原因」二選一（前置狀態未滿足 vs.
      出口觸發的是另一個非`0x2cad7`分支的確認框）現在有 live ground-
      truth 證據支持**第二種**——這次「出口」→YES 走的流程，連
      `0x2cad7` gate dispatcher 本身的位址都沒有被 CPU 碰過，文字內容
      雖然與 doc25 §9.1 描述的 FDTXT `0x201`「要進入戰場嗎？」一致，
      但背後呼叫鏈明顯不是 doc25 §9.1 記載的那一條。**doc25 §9.1 標記
      的`[驗]`需要下一輪重新檢視**——不是否定「原版只能在戰間兩個固定
      點存檔」這個大結論（沒有相反證據），而是「`0x2cad7`/`0x2ccb6`是
      這條 live 路徑的實際呼叫鏈」這個具體 claim 需要用 xref/資料驅動
      方式重新找過，目前唯一可信的是「這個特定存檔／這個特定觸發序列
      下，SAVE 這輪確實沒有被呼叫」。
    - 過程中意外驗證一個有實用價值的方法論教訓：**比較存檔『有沒有被
      寫入』不能只看 checksum**——如果测试用的存檔狀態本身就是先前
      某輪存檔操作留下的（例如再次載入同一章節、同一 roster），即使
      writer 真的被呼叫，寫出來的 bytes 也可能與磁碟上已有內容完全
      相同（idempotent write），此時 checksum 比對會呈假陰性；必須同時
      核對 mtime（本輪一度誤判 mtime「有變化」，後來發現是沒有記錄
      「這次 fresh boot 的原始 copy-time mtime」當基準，屬於比較基準
      缺失的方法論錯誤，非真的觀察到變化——修正後的第三輪补上了嚴謹
      基準，結論才站得住），最嚴謹的做法就是本輪最終採用的
      「CPU 指令級 ground-truth 追蹤」，直接排除「這段程式碼有沒有被
      執行到」的疑慮，不用依賴檔案系統層的間接證據。
    - screenshot：[`save-writer-logc-trace-no-hit-postyes-dialogue.png`](../figures/save-writer-logc-trace-no-hit-postyes-dialogue.png)
      （YES confirm 之後正常推進到「這裡就是遺跡了嗎？」過場對白，證實
      YES 分支確實有被正常處理、遊戲邏輯持續運作，只是這條路徑沒有
      呼叫到 SAVE 相關的任何已知位址）。
    - **仍待下一輪**：目前只證明「這條路徑沒有經過 doc25 §9.1 記載的
      呼叫鏈」，還沒找到它實際經過哪條呼叫鏈（如果真的有存檔會發生在
      更後面的整備畫面／戰鬥地圖，或者這個特定存檔狀態根本就不會觸發
      任何存檔）。建議方向：對已經证实會執行的鄰近位址（如
      `0x1B1F84`附近上游）做 `D SS:ESP` 讀 call stack，或直接對這次
      追蹤到的 9000+ 個 unique 位址跑 `ghidra_batch_probe.py`
      `function_bounds`，找出「confirm YES 之後真正進入的第一個新
      function」是誰，才能建立起這條 live 路徑的真實呼叫鏈。
  - **2026-08-25 平行 harness（`savewriter`，`:299`，同時有 sibling
    instance `prepE2`在跑但互不干擾）續測，把上一輪「下一輪對 tavern-
    icon1 路徑跑同一套 `LOGC` ground-truth 追蹤，應該就能直接定位真正
    的 writer 位址」的待辦做掉，真正的存檔 writer 已定位並完整靜態驗證**：
    LOAD 存檔位1（第二十七章）→軍營帳篷場景（游標預設在酒店）→Enter
    進酒店→NPC對話框「有什麼事嗎？」直接顯示4-icon列（不需要額外
    Enter推對白）→在此武裝`LOGC`（6億指令）→Right×1選index1（磁片+
    左箭頭）→Enter開四槽清單→對slot1按Enter→畫面顯示「記錄儲存
    完畢！」——`FD2.SAV`的`stat` mtime從harness fresh-copy的
    `Birth`(20:54:07)前進到`Modify`(21:00:08)，確認真的有write
    syscall（checksum因為這次是「LOAD slot0→原地立即重存同slot0」的
    idempotent write維持不變，屬於`98-tooling-infrastructure.md`已記載
    的「不能只看checksum」陷阱的再一次實例，不是沒寫入）。
    去重後9960個唯一位址（`tools/dosbox_exec_trace_analyze.py`交叉
    `ghidra_batch_probe.py`）：doc25§9.1舊鏈`0x30012`/`0x2ccb6`/
    `0x2cad7`/`0x2fd93`/`0x318ad`（含`0x30012`所在完整函式`0x2ff01`與
    其內部呼叫目標`0x2d80d`）**全部零命中**，與同日稍早`saveE2`輪對
    town-hub-exit路徑的結論相互獨立印證。**真正的writer是`0x2968d`**
    （`FUN_0002968d`）：對trace命中的177個候選function/cluster起點做
    批次disasm，逐一找`INT`指令，鎖定3個真正的`MOV AH,0x40 / INT 21h`
    （DOS寫檔syscall）位址（`0x3d12a`/`0x3d470`/`0x46da2`，逐位元組
    `bytes`批次掃描確認opcode`b4 40`，排除decompile呼叫引數不可靠的
    已知盲點）；沿呼叫鏈往上（`xref_to`）追出`0x46da2`所在函式被
    `0x2968d`透過`0x377a3→0x3de66→0x46d53`呼叫，`0x2968d`本身
    push `0x59cb`（=**22987十進位，與harness`FD2.SAV`實際檔案大小
    逐位元組相同**）並對`0x50254`/`0x5025f`（byte dump確認皆為
    `"FD2.SAV\0"`）分別以`0x50251`=`"rb\0"`、`0x5025c`=`"wb\0"`兩種
    模式呼叫`fopen`，先讀入既有存檔到buffer、迴圈依`FUN_00029bcb()`
    使用者輸入patch選定槽位的metadata（`buf+slot*0xa28+0xa00..+0xa09`，
    呼應doc25既有的「metadata+0..+9」欄位語意但是獨立實作）、再開
    `"wb"`寫回checksum(`buf+0x59c7`)+完整`0x59cb`bytes。呼叫者鏈
    `0x2670e`（酒店NPC對話框/4-icon列本體）→`0x29300`（反編譯後是
    清楚的三分支icon dispatcher：`index0→0x29620`狀態／`index1→
    0x2968d`存檔／`index2→0x2986f`離開，與本輪tavernE2 live觀察的
    icon語意逐項精確對應）→`0x2968d`，整條鏈的每個位址都在本輪9960
    個trace命中位址裡被直接確認執行過，不是靜態推論。截圖：
    [`tavern-icon1-save-writer-logc-trace-confirmed.png`](../figures/tavern-icon1-save-writer-logc-trace-confirmed.png)。
    **誠實限制**：這條鏈只證實tavern icon1這一條路徑的writer，**不是**
    否定`0x30012`/`FUN_0002ff01`的存在或作用——它是否仍是整備/軍營
    出口流程（`0x2fd93`/`0x2cad7`分支）真正會用到的writer、或本身也是
    死碼，本輪未觸及，需要另一輪針對整備分支單獨live trace才能回答。
    doc25§9.1已同步更新此修正。
  - 機器既有 `~/fd2-run/FD2.SAV`（`md5sum e6d9a35756cddfc2519969b10f039181`）
    全程只被讀取（harness `launch` 對 `~/fd2-run-harness-loadE2` 的
    隔離複本），本輪結束前重新核對 md5 與 mtime 均未變，其他驗證回合
    依賴的既有進度未受影響。
  - **2026-08-25 平行 harness（`camproute`），把上一輪留下的「`0x30012`
    是否仍是整備/軍營出口流程真正的writer、或本身也是死碼」待辦做掉，
    結論：不是死碼，但也尚未被live直接命中過**。先用
    `ghidra_batch_probe.py` 重新核對doc25§9.1標題引用的`0x2cad7`/
    `0x2ccb6`/`0x2fd93`三個位址，發現**這三個位址在目前`FD2Analysis3`
    project裡本身就是錯的**：`0x2cad7`/`0x2ccb6`都不落在任何已知function
    邊界內（`function_bounds`回傳`in_function:false`，硬解出來的disasm是
    垃圾位元組）；`0x2fd93`落在一個完全無關的函式`FUN_0002fb2c`
    （0x2fb2c..0x2fe13，戰鬥前party動畫/montage迴圈）。也就是說本輪之前
    `saveE2`/`savewriter`兩輪對這三個位址做LOGC追蹤得到的「零命中」，
    其實是在追蹤跟存檔閘門無關的位址，沒有真正回答問題（零命中本身沒錯，
    只是測錯了對象——很可能是舊EXE版本殘留的位址，沒有隨EXE rebaseline
    重新核對過，呼應既有memory `fd2-re-old-new-exe-address-instability`）。
    改用`xref_to`+`call_scan`兩種獨立方法交叉確認writer
    `FUN_0002ff01`（entry`0x2ff01`，doc25稱的`0x30012`是其內部呼叫
    `0x2d80d`那行，位於函式中段偏移`0x111`）在目前build的**真正**呼叫者：
    只有兩個，`0x15400`（在`FUN_00015311`，依`DAT_00053c2f`/
    `DAT_00053af9`門檻分流，本身由per-unit狀態機`FUN_00013a9f`與章節
    門檻函式`FUN_00014ef0`呼叫）與`0x1d43c`（在`FUN_0001cff0`，依
    `local_20[DAT_00053c57]`值域`<9||==0x18||>0x1b`才呼叫writer否則走
    `DAT_00051d01`跳表，本身由迴圈`FUN_00018d8c`呼叫，`FUN_00018d8c`
    由`FUN_00018890`呼叫）。這兩條鏈結構上對應doc25標題原本描述的「兩個
    互斥存檔閘門」概念，只是位址全部要換成這輪修正後的。
    **live覆核**：用`saveE2`/`savewriter`輪同一張存檔位1（raw chapter
    `0x1a`=26，顯示第二十七章，屬於doc25分類的「城鎮流程」而非「整備
    限定流程」），走完全相同的「LOAD→軍營帳篷場景→icon選單`Right×3`→
    「出口」→「要進入戰場嗎？」YES」路徑，用`camproute`自己重新武裝的
    `LOGC`（10.7億指令，涵蓋YES confirm到完整過場對白到真正進入戰鬥
    地圖部署畫面全程，去重後14,924個唯一位址）交叉比對修正後位址：
    `0x18890`→`0x18d8c`→`0x1cff0`三個位址**全部命中**（證實這條live
    路徑真的會執行到修正後的真正閘門鏈，不是猜測）；但`0x2ff01`/
    `0x2d80d`（writer本體）與另一條閘門鏈（`0x15311`/`0x15400`/
    `0x13a9f`/`0x14ef0`）**全部零命中**。對照`FUN_0001cff0`的分支條件，
    這條路徑走的是「不呼叫writer」的跳表那一臂——與doc25「城鎮流程走
    跳表、只有raw chapter 22-24/27-29的整備限定流程才走writer」的既有
    結構性主張完全自洽（測的存檔本來就是城鎮流程章節，不是整備限定），
    這輪等於用正確位址第一次乾淨印證了這個既有主張，而不是推翻它。
    **誠實結論**：`0x30012`/`FUN_0002ff01`不是死碼——它的兩條真正呼叫鏈
    都是live追蹤直接證實會執行到的真實UI分派程式碼（`0x1cff0`這條本輪
    剛實測命中），不是從未接進任何狀態機的孤立函式；但也尚未被live
    直接命中——本輪與之前所有輪次一致地顯示，凡是測過的存檔/路徑走的都
    是這兩個閘門的「跳過writer」那一臂。要徹底補齊還需要一張raw chapter
    22-24或27-29的存檔（harness目前4個存檔位raw chapter分別是
    0x1a/0x06/0x07/0x08，都不在這個範圍），這需要真的推進到那幾章（或
    另尋捷徑構造測試存檔）才能補齊，不在本輪合理工作量內完成，留給
    下一輪。doc25§9.1已同步更新此修正。截圖：
    [`camproute-town-hub-exit-confirm-dialog.png`](../figures/camproute-town-hub-exit-confirm-dialog.png)、
    [`camproute-battle-map-after-yes-confirm-ch27.png`](../figures/camproute-battle-map-after-yes-confirm-ch27.png)。
  - **2026-08-25 平行 harness（`writerfire`），終於補上 raw chapter 27（落在
    22-24/27-29「整備限定流程」範圍內）的合成存檔測試，但writer依然零命中，
    且發現doc56整備UI位址集本身也是舊版殘留**：用`fd2save.py`把harness私有
    `FD2.SAV` slot0章節byte由`0x1a`(26)改成`0x1b`(27)（round-trip自檢通過），
    LOAD後畫面顯示「第二十八章」（=raw+1），**選中後直接跳過城鎮hub，顯示
    FDTXT`0x19a`「要記錄戰況嗎？」**——首次用真的落在該範圍內的存檔live印證
    doc25§9.1「整備限定流程跳過城鎮hub」這個結構性主張（先前所有輪次測的
    章節都在範圍外）。武裝`LOGC`(10億指令)後按Enter接受，進入一個外觀與
    `56-fd2-remake-sdd.md`描述的`0x318ad`選人畫面一致的介面（HP/MP狀態欄＋
    出戰/剩餘人數計數器＋角色icon網格，Enter對目前游標角色toggle選取＋
    前進一格）。`xref_to`重新核對`FUN_0002ff01`全EXE依然只有`camproute`
    找到的兩個caller（`0x1d43c`/`0x15400`），沒有第三個；涵蓋「YES確認→
    選人畫面反覆互動」全程的LOGC追蹤對writer本體、兩個caller、及其外層
    dispatcher（`0x18890`/`0x18d8c`、`0x13a9f`/`0x14ef0`）**全部零命中**
    ——比`camproute`更弱（`camproute`至少命中了`0x18890→0x18d8c→0x1cff0`
    這條dispatcher，只是內部走跳過writer那臂；這輪連dispatcher本身都沒
    進去過）。方法論已交叉驗證無誤（追蹤最熱位址native`0x10620`精確命中
    Ghidra真實函式`FUN_00010620`，與doc56「`0x32004`輪詢`0x10620`」的描述
    吻合）。**同時發現doc56對這個選人UI本身引用的位址（`0x318ad`/`0x31e80`/
    `0x32004`/`0x320fc`/`0x31d3c`/`0x318c7`）全部`function_bounds`回傳
    `in_function:false`**——與本節先前修正`0x2cad7`/`0x2ccb6`/`0x2fd93`
    同一類錯誤（舊版/舊IDA session殘留，未隨EXE rebaseline重新核對），
    `56-fd2-remake-sdd.md`整備UI章節需要下一輪比照doc25§9.1重新定位。
    **結構性卡點**：選人畫面出戰上限19（`[0x53c03]>0x1a`分支），但全遊戲
    可招募角色僅13人（與`prepE2`既有結論一致），選滿12名可用角色後
    `Escape`/`Delete`（doc56 raw scancode分析選出的兩個候選確認鍵）都只會
    把選取重置回全空，不會前進到`0x320fc`/`0x31d3c`——這條路徑在鍵盤操作
    範圍內從未能真正推進到選人畫面之後。曾嘗試把roster_count從13硬改成19
    （複製record0填補空位）求選滿，但改完後遊戲在YES確認後直接靜默彈回
    標題LOAD選單（重跑一次同樣發生），判斷是roster完整性檢查失敗，
    **不是**安全的合成測試手法，不建議下一輪重複。**誠實結論**：本輪沒有
    證實或推翻writer在整備限定流程真的會被呼叫；反而讓doc25§9.1「Yes才呼
    `0x30012(0)`」這個沿用自舊文件的具體宣稱本身變得可疑——更可能的結構是
    writer（如果這條路徑真的會呼叫它）是在選人UI**完成**（而非剛進入）
    之後才被呼叫，需要下一輪先用LOGC ground-truth方法重新定位doc56選人UI
    目前build的真實位址才能繼續往下追。doc25§9.1已同步更新此修正。截圖：
    [`writerfire-fdtxt-0x19a-record-battle-confirm.png`](../figures/writerfire-fdtxt-0x19a-record-battle-confirm.png)、
    [`writerfire-selection-ui-all-selected-remaining07.png`](../figures/writerfire-selection-ui-all-selected-remaining07.png)、
    [`writerfire-selection-ui-delete-resets-to-empty.png`](../figures/writerfire-selection-ui-delete-resets-to-empty.png)。
- [ ] **UI-VIS-DIFF-HARNESS**：固定同一FD2.SAV／roster／camera／cursor／tick，輸出DOSBox與remake 320×200 pair及pixel diff；現有ch01兩張角色狀態不同，只證明compositor slice。
- [ ] **ENGINE-REPOSITORY-EXTRACTION-GATE**：待 FD2 忠實模式的核心垂直
  路徑穩定後，建立獨立 GitHub 引擎倉庫。抽離範圍只包含可由第二個真實
  戰役消費的網格、回合排程、事件虛擬機、索引色渲染、輸入、存檔介面與
  跨平台層；FDFIELD／FD2.SAV、handler ABI、原版戰役、位址證據與
  FD2 專屬相容規則留在本倉庫。驗收門檻為：第二個可編輯戰役不含
  `fd2` product branch 即可啟動、遊玩、存讀檔及建置，兩倉 CI 均可由
  Docker 重生。另需先決定引擎程式碼授權、貢獻規範與版本相依方式。

## 文件狀態入口（更新至 2026-07-28）

目前統計：`[x]=493`、`[~]=98`、`[ ]=68`；只計算實際 checklist 行，且僅代表工程項目數，不是原版完成百分比。

- [x] 根目錄 `README.md` 改為「資產／RE／引擎切片／原版差距」四欄狀態表，加入已驗證成果圖片；不再宣稱全 30 章 parity。
- [x] `remake/README.md` 改為垂直切片與 fail-closed 差距說明；`00-index.md` 指定 README → `56` SDD → `42` gap audit → 本 worklist 的閱讀順序。
- [x] `20`／`22` 的「所有必要能力已完成／只剩工程整合」過強斷言降級為「資料與工具證明可行，runtime integration 尚待」；`90`／`51` 明確標成歷史計畫／試玩快照。
- [~] 專題 RE 文件仍保留各自證據與歷史修正；不直接合併成單一長文，避免丟失 address-level provenance。若內容與 README 狀態衝突，以 `56`、`42`、本表最新勘誤為準。
- [x] 2026-07-27 README/KB review：README 改正「跨平台已完成」「EXE 全部表已閉合」「SDL2 第二條 runtime」等過強敘述，補上原版／重製對話圖與可驗證差距說明；`00-index` 明列 README→56→57→42→91 裁決順序；`08` 修正兩個圖片相對路徑。`90`、`30`、`51`、`SESSION-HANDOFF-*` 不合併，保留 address-level/historical provenance，避免把舊快照當現況。
- [x] 2026-07-27 stale dialogue-operand assertion cleanup：`09`、`01`、`18` 不再把控制碼第二 word 一律稱為固定肖像/DATO ID；依 `0x15f84→0x12c60` 分開 identity lookup、runtime unit `+7` 與 direct-DATO fallback，並將 `FFFA/FFFB` 統一修正為遞迴名稱／數值插入碼，不是特效。
- [x] 2026-07-27 second-pass dialogue wording audit：`14` §4 的組合說明與 `-17/-18` 讀取步驟仍殘留「直接肖像 ID」舊斷言，已改成 identity lookup／record `+7`／direct-DATO fallback 三路 provenance；未修改任何未證實的 story operand。
- [x] 2026-07-27 expansion-doc assertion audit：`17-scenario-expansion-evaluation.md` 原稱「原版評分式 AI 已還原、可照搬」已撤回，改以 `11` 的 raw dispatcher/candidate/score slices 與完整 runtime 未閉合為準；`50` 的 persistence 句也限定為 remake 自有 JSON projection，不冒稱 `FD2.SAV` byte identity。
- [x] **DOC-EVENT-DSL-ASSERTION-AUDIT-20260728**：將`29-remake-extensible-event-system.md`明確降級為歷史設計草案；刪除「handler只管勝負／動作全在FDFIELD」「record +5 bit0全域等同存活」「第一章主角含妮雅」「示例已完整重現30關」等會污染忠實模式的斷言。同步將第3/6/7/8輪的「核心全完成／通用1:1／像素級收官／魔法SFX補完」標題限定為當時codec或fixture範圍；SDD視覺估計統一為doc57的40–45%，shop recipient production接線明列為E1而非DOSBox lifecycle parity，並刪除已被後續closure取代的ch29 cleanup重複待辦。
- [x] **DOC-REPO-WIDE-ASSERTION-AUDIT-20260728**：擴大審核歷史專題文件並修正會被當成規格的現行矛盾：`00/28/53`不再把攻略稱為handler ground truth；`19/29/30`把自動campaign與Registry降為尚未閉合的scaffold／設計提案；`25`保留raw byte5 caller predicate；`35`刪除BG=TAI台座與`0x53ec8`=縮放X；`39`區分AFM resource decode與caller schedule；`44`撤回「序章無單位移動」「group10/11全遊戲死資料」及過時兩行直進戰鬥live-state；`47/50`撤回所有章NPC永遠dir0；`50`的campaign graph test不再冒稱全戰役原版route E2；`99`的資產全解改為當時base-codec範圍。
- [x] **AGENT-MEMORY-AND-DOCKER-HYGIENE-20260729**：新增根目錄
  `AGENTS.md`，統一專案目標、文件權威順序、E0–E3、known corrections、
  fail-closed、Docker-only Capstone、subagent review與重大更新才commit/push等
  跨session規則；`CLAUDE.md`改為指向單一操作契約。另建立
  `~/.codex/AGENTS.md`共用Docker鐵則。實際停止四個已跑21小時的
  `fd2-go-test-local` containers，確認沒有FD2 container殘留，並刪除已被
  authorized workflow取代、repo無引用的3.6GB `fd2-ida-local` image；保留目前
  cap/go-test/dosbox/authorized-IDA各一份可重現image。
- [x] **RE-POSTBATTLE-HUB-ROUTE-2D093**：依合法 IDA Pro 9.4／Capstone 的
  `0x2CAD7/0x2D093` 與 `0x526B9` raw table，新增
  `fdother.ResolveNativePostbattleRoute`；保存 preparation-first gate、
  hub selector→raw callee mapping、invalid fail-closed。IDA 再閉合
  `0x2CAD7` 回傳值：子流程 raw 0 會內部重複；直接整備／option2 的非零
  結果使 gate 回傳0，其餘 option 的非零結果使 gate 回傳1。
  `ResolveNativePostbattleOutcome` 只保存這個 raw 契約，不把 option 或
  raw 1 自動命名成酒店／商店／教會／結局，也不直接呼叫 scene。
- [x] **RE-TOWN-SHOP-SERVICE-2E341**：Docker Capstone 固定 resource與selector後續已完成callee dataflow：`0→0x2f0b0` purchase、`1→0x2f642` sell、`2→0x2f883` equip、`3→0x2f8ea` inventory transfer。命名依insert/remove/equip/gold writer與FDTXT，不依icon猜測；`ResolveNativeShopServiceRoute`現保存typed kind但仍不呼叫scene。
- [x] **RE-TOWN-HOTEL-SERVICE-2FC85**：Docker Capstone 固定 `0x2fc85` raw resource `13`、selector `0/1/2→0x2ffa5/0x30012/0x301f4`，selector3→`0x19953→0x197e5`；新增 `fdother.ResolveNativeHotelServiceRoute` raw plan/regression。只保存 address-level order，不命名服務、不執行 scene。
- [x] **RE-PREPARATION-CAP-318AD**：Docker Capstone 重核 `0x318ad`：`[0x53c03] <= 0x1a` 時 cap=15，`>0x1a` 時 cap=19；新增 `fdother.NativePreparationPartyLimit` 與 boundary regression。明確以 native index 為輸入，不把 late cap 猜成顯示章號或直接改寫 JOIN roster。
- [x] **RE-PREPARATION-PREVIEW-31E80**：Docker Capstone 完整 trace 固定 `0x31e80` 讀 caller-owned 30-byte selection table、以 `0x320ce` 計數，依 flag 分支 `0x4deda/0x4de56` 做 indexed preview；body 未寫 selection table／persistent roster。撤回把它當 Enter/toggle mutation，remake 保持 `partyDeploy` mutation 與 renderer boundary 分離。
- [x] **PROGRESS-AUDIT-E0-TO-E2**：重新檢視近期對話、commit 與權威文件，確認停滯主因是 E0 raw slice 沒有同步 runtime consumer／UI input trace／E2 screenshot、`main.go` 仍是 monolithic scene owner，以及 30 章 postbattle graph 未逐章驗收；新增停止孤立 offset 擴張的門檻，下一里程碑改為 title→dialog→battle→postbattle hub→preparation/town 垂直鏈。
- [x] **UI-01-TITLE-TRACE**：新增純 `TitleMenuState`／`TitleSlotState`，保存原版主選單三項 wrap、24-tick confirm flash、load branch 與 `0x30550` 四槽 bounded/no-wrap/cancel contract；`titleUpdate` 的 Ebiten input 已改走同一 state transition，Docker/Xvfb regression 可重播 selection/action trace。仍不宣稱原版逐幀 visual parity 或 FD2.SAV 相容。
- [x] **UI-07-08-CAMPAIGN-MENU-TRACE**：新增 `campaign.MenuState`，將 `choice/town` hub 的 bounded cursor、空選項 fail-closed 與 confirm→`optN` transition 抽成純 state contract；`campInput` 已共用該 contract，internal/campaign 與 Docker/Xvfb focused regression 通過。未命名 town service、未跳過 handler，逐章 route/E2 仍是 partial。
- [x] **UI-08-TOWN-HUB-SOURCE-SCREENSHOT**：用目前 source 在 `fd2-go-test-local` 內重新 build（不使用舊 `fd2-linux`），以 `FD2_CAMP_NODE=town_ch02`、frame 30 產生 [`town-hub-remake.png`](../figures/town-hub-remake.png) 並加入 README；這是 remake current artifact，不是原版 visual parity。
- [x] **UI-08-TOWN-HUB-CH02-E2-SLICE**：在隔離 `/tmp` game sandbox 只以 route patch 跳過戰鬥勝負判定，原版 postbattle handler／campaign gate／town resources 均照常執行；走完20次戰後對話確認，第21次取得 ch02 town。初次 diff 抓到 `BlitNativeGlyph` 把 `0x4ea2a` 的 shadow 誤寫同列左側；修正為下一列左下／正下後，selection0/pulse2 與 Left→selection1/pulse2 的320×200 raw RGB MD5分別整幀相同。這不證明 route patch 是原版玩法，也不解除其他 variant/input 的 E2 gate。
- [x] **RE-FDTXT-GLYPH-SHADOW-4EA2A**：Docker Capstone 指令級確認 foreground→`edi`、shadow→`edi+(stride-1)`／`edi+stride`；撤回同列`edi-1` shadow 的錯誤 ABI 與兩個保護錯誤位址的 roster/class tests。共用 `BlitNativeGlyph`、相鄰筆畫 regression 與 consumer tests 已修；town selection0/1 E2 整幀 hash 是直接 visual oracle。
- [x] **UI-08-TOWN-DETERMINISTIC-SHOT-STATE**：新增 screenshot-only `FD2_SHOT_TOWN_STATE=selection,pulse`，只接受 native town 的 selection0..5／pulse0..3，非法值 fail closed；正常 input 不讀此 hook。`0x2ce7a/0x2ceac/0x2cef7` 無 `[0x54133]` writer，故方向鍵／secret reveal 不再猜測性 reset pulse。
- [x] **UI-08-TOWN-VARIANT0-SIX-SELECTION-E2**：以新 `waittown0:key,delay,max` 背景簽章同步避免固定 Return 次數過按，原版依 input 到達0酒店、1武器店、2出口、3道具店、4教會、5「???」；六幀各自與 deterministic remake pulse 做320×200 raw RGB全幀hash相同。另實測Right 0→4、Left 4→0、Shift+F1 0→5；secret reveal production helper有pulse/clock continuity regression。`waittown0`只辨識variant0，不冒稱可同步variant1/2。
- [x] **UI-09-CH02-SECRET-SHOP-SERVICE0-E2**：由同一原版 sandbox 走 `Shift+F1→selection5→Enter`，捕捉 variant5/resource63/DATO#0x84 秘密商店。新增 strict screenshot-only `FD2_SHOT_SHOP_STATE=service,pulse,gold`；E2 抓出 production service phase 被 caller 與 compositor 雙重 `/2`、導致 selected sprite 永不出現，已只修正該 service-menu call site並補 consumer regression。gold0 時原版/rebuild phase0、phase2 raw RGB MD5 分別 `12fad3c03096aae48098c8f9074370c7`、`e5654e8ed03d1e4fd30b2c76106bb7a1`，兩組皆整幀 AE=0。
- [x] **UI-09-CH02-SECRET-SHOP-FOUR-SERVICES-RETURN-E2**：原版實際 Right `0→1→2→3→0`、Left `0→3` 六幀各與同service remake pulse全幀AE=0；Escape closing後回town hidden selection5，亦與town pulse1全幀AE=0。E2抓出`leaveShop→enterNode`把selection誤重設0；production現只對已證實native variant1/3/5恢復同值，custom shop仍預設0，並有boundary regression。新增[兩列對照圖](../figures/secret-shop-ch02-services-return-original-vs-remake.png)。
- [x] **UI-09-CH02-SHOP-VARIANTS-1-3-5-E2**：由同一原版town分別以selection1進weapon variant1、selection3進item variant3；各取10個steady樣本，variant1全部、variant3除首張transition外九張均在phase0/2交替並與production全幀AE=0。selected phase raw RGB MD5為variant1 `69003be54f47c221916c1ed89cf1d26f`、variant3 `dd5d80bb761cc87980dff066773f6763`、variant5 `e5654e8ed03d1e4fd30b2c76106bb7a1`，原版/remake成對相同。新增[三變體對照圖](../figures/shop-variants-1-3-5-original-vs-remake.png)；主選單variant gate關閉，child panels仍待。
- [x] **UI-09-CH02-WEAPON-PURCHASE-LIST-E2**：新增 strict screenshot-only `FD2_SHOT_SHOP_PURCHASE_STATE=selection,start,gold`，只接受production已claim的native purchase mode、合法goods selection與正規化偶數window start，其他狀態fail closed。原版service0 Enter後實測Right `0→1`、Down `1→3`、Left `3→2`；延長等待排除進場最初2像素與portrait animation transient後，四個stable 320×200幀均與production全幀AE=0。raw RGB MD5為selection0 `1589cee3c068936f0beb6058cfd63991`、1 `7480dbb0284b033b4e9ad8c8c7a8b78e`、2 `48d6182e261ebce574b08c4778b8a072`、3 `3c0a2c935260b8ca80432b25b3600111`；新增[兩列對照圖](../figures/shop-purchase-ch02-selections-original-vs-remake.png)。這只關閉購買清單steady/input，不推廣到確認、收件者或交易結果。
- [x] **UI-09-CH02-WEAPON-PURCHASE-CONFIRM-E2**：新增 strict screenshot-only `FD2_SHOT_SHOP_CONFIRM_STATE=good,choice,pulse,gold`；只接受production已claim且shared assets完整的native shop、真實editable good、choice0/1、pulse0..3與合法gold，其他狀態fail closed。原版由good0 Enter開「布衣／50元／要不要啊？」、Right到No、Left回Yes；高頻取樣的可見selected Yes/No raw RGB MD5分別`7a07b1c064ca2c431bc97c798dcfd51e`／`56f6ffb003e87cbc63d7a915ac4b5dd0`，normal frame `b8cce25df13447e73e1750a8b2edaf0f`，三者均與production全幀AE=0。新增[兩列對照圖](../figures/shop-purchase-confirm-ch02-original-vs-remake.png)；只關閉confirmation steady/input，不推廣到recipient或transaction result。
- [x] **UI-09-CH02-WEAPON-PURCHASE-INSUFFICIENT-E2**：新增 strict screenshot-only `FD2_SHOT_SHOP_INSUFFICIENT_STATE=good,gold`；只接受production已claim且shared assets完整的native shop、真實editable good及`gold<price`，不扣金、不改recipient，final compositor失敗即原子回復。原版gold0對good0選Yes後顯示「錢不夠！」及等待標記。最初誤用第四個inward choice frame造成整幀AE=563；Docker Capstone重核證實原版`0x197e5`四次present後由`0x19913..0x1994c`恢復310×86 question region，`0x16c57(1)`再以FDOTHER#5 cell18/19畫等待標記。remake目前以ch02限定的deterministic recomposition取得相同pixels，尚非generic saved-buffer restore owner；原版／production raw RGB MD5皆為`6babcedfe2017a7457924c4df65ba7dc`、整幀AE=0。新增[左右對照圖](../figures/shop-purchase-insufficient-ch02-original-vs-remake.png)。不外推到recipient/no-recipient/full/success。
- [x] **UI-09-CH02-EQUIPMENT-RECIPIENT-E2**：`FD2_CAMP_NODE=shop_ch02_weapon`本身不建立persistent party，故新增screenshot-only `FD2_SHOT_PARTY_BINDING`：只接受compile無issue、同時提供`PartyScenario+PartyOrder`的LOADCH binding，依該binding記錄的order materialize typed roster並要求identity/selector/race/class/byte6/raw inventory/equipment-base provenance；hook不獨立重證JOIN來源位址，姓名與順序也不硬編。`FD2_SHOT_SHOP_EQUIPMENT_RECIPIENT_STATE=good,selection,start,cycle,gold`再嚴格驗證商品、價格、三列window與FDICON cycle。E2抓出ch01 party遺漏DX projection；2/2/1/2由可見HIT/EV與已知equipment rows交叉約束，不是直接raw `+0x3e` dump。另修正HIT/EV整組相對AP/DP右移3px及arrow Y anchor；修正後good0/selection0/start0/cycle1/gold1000原版與production raw RGB MD5皆`28258fb3ce5bc42eb1c701a7792d193b`、整幀AE=0。新增[左右對照圖](../figures/shop-equipment-recipient-ch02-original-vs-remake.png)；此bridge不代表正常campaign persistence，亦不外推到input/scroll、FD2.SAV相容、no-recipient/full/success。
- [x] **UI-VERTICAL-CH02-TOWN-PREPARATION**：將 `Game.stepCampaignMenu` 接到 `campInput`，新增 `TestCampaignTownPreparationInputTrace`，以 `down,down,enter(opt2)` 驗證 `town_ch02→preparation_ch02→story_ch02_pre→battle_ch02`；保存可編輯 trace [`town-preparation-ch02.json`](../data/ui-traces/town-preparation-ch02.json) 與目前 source rebuild 的 [`preparation-current-remake.png`](../figures/preparation-current-remake.png)。這是第一個 campaign/UI state vertical closure，仍不等於逐章原版 parity。
- [x] **UI-VERTICAL-CH02-TOWN-SHOP-RETURN**：新增 `Game.leaveShop` 與 `TestCampaignTownShopPurchaseReturnTrace`，驗證 `town_ch02→shop_ch02_weapon`、reserve 不先扣金、finalize 後回 town；保存 [`town-shop-ch02.json`](../data/ui-traces/town-shop-ch02.json) 與 source rebuild 的 [`shop-current-remake.png`](../figures/shop-current-remake.png)。這只閉合 remake shop/campaign boundary，不命名 native shop callee 或宣稱原版 parity。

- [x] **UI-VERTICAL-CH02-TOWN-CHURCH-REVIVE**：新增 `Game.reviveChurchUnit`／`Game.leaveChurch` 與 `TestCampaignTownChurchReviveReturnTrace`，驗證 `town_ch02→church_ch02→revive(level3,class1,fee7)→town_ch02`，gold 100→79、HP restore、OnField restore；保存 [`town-church-revive-ch02.json`](../data/ui-traces/town-church-revive-ch02.json) 與 source rebuild 的 [`church-current-remake.png`](../figures/church-current-remake.png)。未命名未知 church callee，不宣稱原版 service/E2 parity。
- [x] **UI-VERTICAL-CH02-TOWN-CHURCH-CLASS-CHANGE**：`Game.applyChurchClassChange` 與 `TestCampaignTownChurchClassChangeReturnTrace` 驗證悠妮（native identity/portrait09）依 special override 解析唯一 portrait34/class21、Yes 確認、MV 5→7、Exp reset、消耗 item `0x5a`，並可 Escape 回 `town_ch02`；保存 [`town-church-class-change-ch02.json`](../data/ui-traces/town-church-class-change-ch02.json)。舊「可編輯三分支」斷言已撤回。
- [x] **UI-VERTICAL-CH02-SAVE-LOAD-BOUNDARY**：新增 `TestCampaignSaveLoadRestoresTownBoundaryAndParty`，驗證 town 節點 F5 存檔→清除 transient runtime→F9 讀檔後恢復 campaign cursor、gold、items、party roster/deploy/join order/chapter，並由 `enterNode` 清除 battle/shop/church state；保存 [`save-town-boundary-ch02.json`](../data/ui-traces/save-town-boundary-ch02.json)。這是 remake JSON boundary，不是 native `FD2.SAV` 相容性。
- [x] **UI-VERTICAL-CH02-TOWN-HOTEL-RAW-RETURN**：新增 `hotel` campaign node、`Game.applyHotelServiceSelection`／`Game.leaveHotel` 與 `TestCampaignTownHotelRawRouteReturnTrace`，驗證 `town_ch02→hotel_ch02→town_ch02`，selector 0/1/2/3 保留 raw resource13 與 `0x2ffa5/0x30012/0x301f4/0x19953→0x197e5` order；未命名服務、不做 party/gold mutation，未知 selector fail-closed。保存 [`town-hotel-raw-return-ch02.json`](../data/ui-traces/town-hotel-raw-return-ch02.json)。
- [x] **POSTBATTLE-UNBOUND-FAIL-CLOSED**：`Game.enterNode` 對沒有 active handler 的 `postbattle_*` cutscene 拒絕空 beats auto-advance，新增 `TestUnboundPostbattleCutsceneFailsClosed`；流程停在原 node、保留 `loadErr/msg`，避免未完成 persistence/reward handler 被誤當成直接回 town。
- [x] **POSTBATTLE-SAVE-FAIL-CLOSED**：`saveGameToSlot` 對所有 `postbattle_*` 節點拒絕 F5，新增 `TestSaveRejectsUnboundPostbattleBoundary`；未完成 persistence handler 不會產生假 save。
- [x] **POSTBATTLE-BINDING-GATE-AUDIT**：新增唯讀 `tools/audit_postbattle_binding_gates.py`，逐一依 handler source address 檢查 generated binding 的 `loadch/pan/dialog/act/layout` 覆蓋；目前 18 節點仍 blocked，ch09/ch10/ch12/ch18 已通過 compiler regression 並提升為 active handler，ch09 resource37 由 Docker exporter 解碼，其餘 skeleton 禁止自動啟用。

## 第 1 輪 ✅
- [x] 素材盤點(`FD2.EXE` + 12 `.DAT` + 音效驅動)
- [x] 破解 `.DAT` 容器格式 + 寫 `tools/unpack_dat.py`
- [x] 辨識圖像/調色盤/文本/地形表 header
- [x] 攻略萃取成知識庫
- [x] 建知識庫骨架 + RE 計畫 + 反思 + README + git push

## 第 2 輪 ✅
- [x] **當年開發工具考證**(Watcom C/C++32 + DOS/4GW + Miles AIL v3 / XMIDI + AFM 動畫工具/作者 Lo Yuan Tsung)→ `04-original-toolchain.md`
- [x] 建立本 worklist
- [x] **EXE 資料表 dump**:`tools/dump_exe_tables.py`,9 表全對齊「舊版」offset,5 表 dump 並自驗全通過 → `docs/data/exe_tables/`、`03-…`
- [x] **圖像解壓**:破解 RLE(c≥0x80 literal / c<0x80 run),`tools/decode_image.py` 渲染標題+背景驗證 → `05-image-compression-format.md`
- [x] **音樂解析**:確認 XMIDI,`tools/xmi2mid.py` 轉 15 首標準 MIDI(note 平衡、tempo 直通)→ `07-music-xmidi-format.md`
- [x] **動畫機制結構**:AFM 容器 + FIGANI 幀封裝(幀數自描述 + offset 表)→ `06-animation-format.md`

## 第 3 輪（歷史素材／codec round；勾選不代表核心引擎或 AI 全完成）
- [x] **文本解碼**:破解 FDTXT(uint16 glyph 索引 + 控制碼 + 0xFFFF)+ 找到自製字型(FDOTHER_004,16×16 1bpp,1824 字模),**還原可讀中文** → `08-text-and-font-format.md`、`tools/decode_text.py`
- [x] **動畫逐幀拆解**:✅ **完整破解**!反組譯參數化解碼器 0x4F43D + 解出 13-byte 幀標頭(realW/H 在 +9/+11)+
      4 模式 RLE → `tools/decode_figani.py` 把 **264 動畫 2118 幀**全部解出(騎士揮劍動畫視覺驗證)← 使用者明確要求,完成
- [x] **持久素材抽取**:`tools/extract_all.py` → 本機 `extracted/`(raw/images/animations/music/fonts);**不入版控**
- [x] **劇情/對話結構解出**:[控制碼][說話者肖像ID][『][對白][』];全 35 章渲染成可讀 PNG(`extracted/story/`)→ `09-…`
- [x] **序章(FDTXT_001)逐章轉錄完成**(`extracted/story/序章_transcript.md`,本機)
- [x] **敵/我方動畫機制文件**:解碼器變體家族(全彩/remap調色/silhouette/dither)+ 陣營/面向 → `10-…`
- [~] **敵人/NPC 戰場 AI** 反組譯文件：舊 `0x15140/0x15356` 位址已撤回；
  真正的物理候選評分入口 `0x14237` 與法術 `0x15AD8→0x15B77` 已分離，
  仍需閉合候選格順序、raw helper 語意、turn/camp 與 runtime execution → `11-…`
  ——本輪(2026-08-20)推進:`doc11`新增完整回合主鏈反組譯,候選格順序/raw camp定義(+6=0/1/2)/
  turn-camp與runtime execution已由`0x1A30B`交織順序(own regen→友軍`0x1D80B`掃描→敵軍`0x1D8BA`掃描→
  `[0x53BEF]`回合計數遞增)與三個end-turn入口(`0x13565`自動判定、`0x16F55`選單「全軍前進」/「結束回合」)
  補齊,完成度大幅提升;仍缺:`0x14818`各caller-specific mode是否有額外LOS判定、`0x1728C`子選單(selector2)語意。
  ——本輪(2026-08-20續輪,`doc11`,回應L145尾巴)窮盡收尾:**`0x14818` LOS缺口視為已閉合**——完整
  反組譯整個480-byte函式本體(`0x14818..0x149f7`)後確認,除既有已知的Manhattan(`mode<0x10`,含可選內圈
  排除)/十字(`mode>=0x10`)距離規則,以及僅`mode<0x10`才有的flood-fill佔用阻擋(`0x4e8a5`/`0x4e390`,
  doc13已閉合)之外,函式本體不呼叫任何額外視線/阻擋子函式;`mode>=0x10`十字分支甚至完全沒有阻擋判斷,
  純幾何直線比較。**`0x1728C`子選單機制層已閉合,但玩法語意層仍未閉合,誠實保留fail-closed**——4項旗標
  切換環的完整結構(`[0x51e61]`/`[0x51e62]`/`[0x53af9]`/`[0x51aab]`)、對應存檔metadata `+6..+9`欄位
  (與doc23既有記錄互相印證)、切換時顯示的8個FDTXT人名標籤(米亞斯多德/蜜蒂/羅德曼/莎拉/約拿/卡里斯/
  羅蘭/希爾法,與doc49角色ID17-24對應)、確認鍵動作(純翻轉旗標,撤回先前「音量呼叫」臆測)皆已反組譯
  查證;但這四個旗標實際控制遊戲裡什麼行為(是否為recruit/上場二選一或純UI選項)仍未閉合,doc23原本
  「玩法名稱仍不猜」的立場未被推翻。**L145兩個尾巴缺口不再是開放問題,但checkbox本身涵蓋的turn/camp
  與runtime execution全貌已在本行閉合,不因0x1728C語意未知而降級整項狀態**。
- [x] **RE-AI-CALLER-15AD8**：Docker Capstone 閉合 `0x15A1E..0x15B76` 的 bounded candidate→`0x14818` target builder→`0x15B77` score→best-score/tie-break/write globals 邊界；`0x15B77` 的 command `<0x0d`、recovery `0x0d..0x10`、raw flag `0x14..0x16` branches 已寫入 `11`，不把它升格成完整 AI turn。
- [x] **RE-AI-DISPATCH-14EF0**：Docker Capstone 找到 `0x14EF0` 的六個 direct callers 與 `0x14237→0x1598A→0x1567E` 後續分派至 `0x1548E/0x15311/0x15055`；已記為 candidate dispatch boundary，不命名 turn/camp 或宣稱完整 AI parity。
- [x] **RE-REFERENCE-FILE-HASHES**：固定目前反組譯版本的 `FD2.EXE` 大小
  `357074`、MD5 `b97caf2239a27a896069d03549d96e1e` 與 SHA-256，另為
  12 個實際解析資產建立可重算清單
  [`fd2-reference-files.json`](../data/fd2-reference-files.json)；
  `disasm_le.py` 每次執行會在標準錯誤輸出顯示來源指紋。不同雜湊不得沿用位址。
- [~] **RE-BATTLE-AI-SPECIAL-TOPIC**：已把 `0x1A4EB/0x1A58F→0x1D80B/0x1D8BA
  →0x13A9F→0x14EF0` 整理為可信拓撲，並分開 `0x14237` 物理評分與
  `0x15AD8→0x15B77` 法術評分。`0x1548E` 已更正為選擇結果執行，不是
  pathfinder；`0x145CD→0x4E040→0x146D1→0x14B16` 已閉合 raw 落點產生與
  row-major 順序，`0x14B78→0x4E1A6→0x13488` 已閉合路徑方向與實際落點
  排序；無 action 的一般 mode 0 備援已定位到 `0x14121→0x13E9C`，舊
  `0x15192` 假說撤回。2026-07-29 又固定 `0x1D80B` 的 raw `+6==1`
  單遍，以及 `0x1D8BA` 對 raw `+6==0` 的「分數門檻預選＋無門檻第二遍」；
  每筆均依序走結構已閉合的 90 筆全域事件表、30 筆章節戰場事件 handler 表與
  `[0x53ECC]` pending 碼，round counter 在第二掃描返回後才增加。既有
  constructor＋`0x14818` 消費證據已固定 raw camp code 敵0／友1／己2，
  故前者是友軍單遍、後者是敵軍兩遍；具型別
  `PlanNativePhaseUnitScans` 已分開三遍、保留 signed threshold 與缺 score
  fail-closed regression；`ExecuteNativePhaseUnitScans` 另保存每遍動態
  重判、兩張表順序與 pending 提前退出。`0x1598A→53C23` 命令遮罩候選、`0x1567E→53C33`
  item-command 候選與 `0x13512` bit7 已串成「高價值優先遍後排除雙動」。
  尚未接 production `NextAIPlan`。下一步以固定存檔 trace 驗證實際選中
  command／目標與畫面順序；不得重複把陣營碼、兩張表或 pending 碼降回未知。
  ——**2026-08-25 固定存檔 live trace（DOSBox-X harness instance `aiE2`，ch08
  「王城前的戰鬥」存檔）**：LOAD 存檔位3→軍營走出口→YES 進戰場→約20+次
  Enter 推進戰前對白，成功進入互動戰鬥（`MAP·08 TURN·001`，
  `ENEMY·22 FRIEND·11 NPC·00`，勝利條件「敵全滅」、失敗條件「索爾死亡」）。
  全員待機＋系統選單環（上=系統選單/戰況總覽、左=行軍、右=設定、下=END）
  →END→YES 確認，成功觸發「ENEMY PHASE」演出（鏡頭依序掃過營寨守衛×2、
  橋上守衛×3、開戰全景等多個定點鏡頭），驗證 doc58 記載的 End Turn 操作
  序列在 ch08 同樣可重現。主動移動索爾（滿血 HP802/MP790）北上至十字路口
  誘敵，其後連續三個 ENEMY PHASE（turn1→2→3→4）觀察同一隻銀甲守衛
  （138HP）：turn1→2 時，它從路口北側移動到與索爾正上方緊鄰的格子
  （Manhattan距離1），但**沒有攻擊**，索爾 HP 全程 802/802 無變化——這與
  doc11「mode dispatcher 先評 `0x14EF0`（含攻擊候選），失敗才走純移動
  fallback，同一次行動不會移動後再重評攻擊」的靜態結論吻合。但 turn2→3、
  turn3→4 時，守衛已連續與索爾緊鄰卻**仍然沒有攻擊**，位置、HP皆不變；
  反向驗證：主動選取索爾開指令環，「攻擊」圖示對這隻鄰接守衛顯示為
  **可選（橘框高亮，非灰階/紅框disabled）**，證明範圍/鄰接判定本身合法，
  不是座標誤判。**誠實結論（部分閉合，非完整 E2 confirm）**：第一輪
  「移動而不攻擊」直接支持既有靜態結論；但「已連續多回合鄰接仍不攻擊」
  是 doc11 沒有明確記載過的現象，本輪只用畫面觀察，未讀 EXE record
  記憶體，所以無法排除／證實最可能的解釋（doc11 2026-08-14 記載 ch01
  開場8個敵人 `inventory_slots[0]` 全部是空 item ID、導致 `0x14237`
  早退回傳無候選的同一模式，若套用在這隻守衛身上可完整解釋此現象，但
  未經 live record 驗證，仍是推論）。全程沒有一次真正的攻擊發生，因此
  本輪也**無法**觀察/比對「選中結果的畫面呈現順序」（游標/攻擊動畫演出）
  這個原始子題目標。下一步（真正閉合需要）：對此守衛的 raw record
  （`+0xb` 起 inventory slots、`+6` camp、`+0x34` mode nibble）做一次
  live 記憶體讀取確認是否為空武器欄位；若確認，執行順序子題可視為驗證
  通過，畫面呈現子題則需換一個「確定會出手」的存檔/敵人才能觀察。截圖：
  `docs/figures/re-battle-ai-e2-ch08-enemy-phase-banner.png`、
  `re-battle-ai-e2-ch08-enemy-approaches-adjacent.png`、
  `re-battle-ai-e2-ch08-enemy-adjacent-turn4-still-138hp.png`、
  `re-battle-ai-e2-ch08-sol-attack-valid-vs-adjacent-enemy.png`、
  `re-battle-ai-e2-ch08-battle-status-turn4.png`。
  ——**2026-08-25 續：live record 讀取關閉「是否為 empty-weapon」子題（DOSBox-X
  harness instance `aiattack`，同一 ch08 存檔，`tools/dosbox_harness.sh`
  獨立第二輪）**：沿用上一輪確立的 LOAD 存檔位3→軍營走出口→YES→約20+次
  Enter 推進戰前對白流程，成功重現互動戰鬥；主動誘敵索爾北上兩回合，
  連續與 3 隻敵方單位鄰接（2 隻`人類 法師`＋1 隻`人類 戰士`／`鎧甲武士`）。
  進 debugger 用 `[0x53a45]`→delta`0x19C000`→`0x1EFA45` 讀出這次開機的
  陣列基底`0x26C484`（`[0x53beb]`→`0x1EFBEB`讀出總數33），逐筆`D`讀出
  索爾（slot0）與鄰接戰士（slot11，位址`0x26C7F4`）完整`0x50`-byte raw
  record。**結果：戰士`+0x0A`＝`0x40`（bit7未設＝非空）、`+0x0B`＝`0x03`
  （武器item id），武器欄位確認非空**，與角色資訊畫面顯示的「巨劍」
  逐位元組吻合——**直接推翻這個個案的 empty-weapon fail-closed 假說**。
  真正原因改用 doc11 既有 `0x14237` 第5步公式重新核對：`actor AP(戰士
  73,record`+0x48`)− target DP(索爾711,record`+0x48/+0x4A`＝
  `922`/`711`，與畫面 UI 逐位元組吻合)`＝`−638`，遠低於文件既記載的
  `<=2`拒絕門檻——**這隻戰士對索爾完全沒有合法物理攻擊候選，是命中
  已有靜態反組譯的AP−DP評分拒絕分支，不是武器欄位問題**。旁證：兩隻鄰接
  法師同回合 MP 從`011/011`降到`009/011`（吻合`火炎術 -MP02`），索爾HP
  `802→705`（-97），證實**至少一隻法師確實出手攻擊**（走的是法術評分
  `0x1598A`路徑，不受這條物理AP−DP門檻限制）——同一場戰鬥裡「有武器
  但物理评分被拒絕的戰士」與「真的出手的法師」形成直接對照組。**結論
  （比原訂目標更精確、已達 record 位元組級驗證）**：doc91上一輪138HP
  守衛的「可能是empty-weapon」假說，對**這次調查到的這隻不同敵方個體**
  被證偽；真因是`0x14237`公式本身既有的score`<=2`拒絕分支對「高DP目標
  vs 低AP敵人」這種組合的正常設計行為，不是資料缺陷或未知邏輯。因為
  索爾在兩輪都是同一個高DP(711)角色，且此門檻是通用評分公式（非特例），
  原138HP守衛極可能命中同一條門檻，但138HP那隻本體這輪未在已初始化的
  33筆陣列中定位到（疑似屬後續增援波，未展開追查），該個體本身仍未逐
  位元組驗證，留待下一輪視需要補上。詳細位元組證據與交叉驗證見doc11
  「物理攻擊候選：`0x14237`」小節2026-08-25補充。截圖：
  `docs/figures/re-battle-ai-e2-ch08-armed-warrior-mode2-no-attack-2026-08-25.png`。
- [x] **RE-AI-PATH-FALLBACK-14B78**：Docker Capstone 閉合 `0x4E1A6`
  mode 0/1/2、方向碼、成本與 `0x40/0x80` gate；`0x14B78` 依
  Manhattan→軸差→逐列順序選落點，`0x13E9C` 才是最後的 Manhattan
  最近 opposite-group 座標備援。新增 raw-only path／blocked-coordinate／
  destination ranking／nearest-coordinate adapters 與決定性測試。
- [x] **RE-AI-PHYSICAL-SCORE-14237**：Docker Capstone 閉合候選格×目標枚舉、
  actor/target `+0x48/+0x4A` 地形百分比修正、差值`<=2`拒絕、嚴格
  `score>target +0x40`時×2/priority18、`0x1DEBE`及raw `+8`調整，以及
  priority→score→先出現者同分規則。新增 raw-only
  `ScoreNativePhysicalAttackCandidate`／`SelectNativePhysicalAttackCandidate`
  與門檻、嚴格HP比較、priority及穩定同分測試；合法 IDA 9.4 另交叉確認
  函式邊界、三個 callers 與 `0x1DEBE` 唯一 caller。不接 normalized planner。
- [x] **RE-AI-PHYSICAL-EXECUTION-1548E**：Docker Capstone 證實唯一 callers
  `0x13E39/0x14F9B`；callee 消費 `0x53C43/47/4B`，經 `0x14B78` 後依
  `0x53AF9` 選地圖呈現或 `0x28A6C(actor,target)`，收尾固定回1。沒有
  `0x4EE40/0x4F355` call，故撤回「pathfinder／移動決策入口」斷言。
  合法 IDA 9.4 已交叉確認函式邊界與兩個 callers。
- [x] **RE-AI-UNIT-DISPATCH-13A9F**：Docker Capstone 閉合 `0x13A9F` 的 unit `0x50`-byte record、raw `+5 & 0x05` gate、`record+0x34 & 0x0f` command nibble 與 `0x14EF0/0x1598A/0x15311/0x1548E` 分支；保留 nibble 語意未命名。
- [x] **RE-AI-UNIT-SCANS-1D80B**：Docker Capstone 閉合 `0x1D80B/0x1D8BA/0x1D988` 三段 `[0x3BEB]` record scans、raw `+6/+5/+0x26` gates、`0x13A9F`／`0x1598A→0x1567E` 呼叫與 `[0x51A8F]/[0x53C03]` table dispatch；保留 raw table/loop semantic 未命名。
- [x] **RE-AI-PHASE-CALLBACK-ORDER**：合法 IDA Pro 9.4 優先確認
  `0x51B91` 為 90 筆、`0x51B19` 為 30 筆，並固定逐筆順序為
  可選全域事件→無條件章節 handler→pending 檢查；不合格 record 仍走尾段，
  第二遍則重新讀取第一遍可能改寫的 `record+5 bit7`。
  `fdother.ExecuteNativePhaseUnitScans` 保存動態重判、表界與提前退出的 E0
  契約；未知 handler 效果仍由呼叫端提供，不接正式 `NextAIPlan`。
  `[0x53ECC]` 碼 1 只證實固定 `0x22E5C` 資源 #79 呈現，碼 2 只證實
  章節戰後表→`0x2CAD7` gate；舊「世界地圖／中場／勝利」通用名稱已撤回。
- [x] **RE-AI-PHASE-CALLS-1A4EB**：Docker Capstone 固定 `0x1A4EB` 的 `0x1A813(1)→0x1A866(1)→0x1A7BD→0x1D80B→0x1A7F1` 與 `0x1A58F` 的 selector-0 對應鏈；只記 phase-specific raw callsites，不命名回合開始／結束。
- [x] **RE-AI-COMMAND-ENUM-1567E**：Docker Capstone 閉合 `0x1567E` 的 `record+0x0B+2*slot` item ID→row `+0x10` command、`command<=0x0F→0x14818`、`command>0x0F→0x149F8(command-0x10)`、`0x15880` score 與 `0x53C33/37/3B/3F` best writes；`0x53C3F` 是 inventory slot，執行端再由 `0x1B722` 解 item。撤回混用 `0x15B77` 與 command-list 的說法。
- [x] **RE-AI-SCORE-15880**：Docker Capstone 閉合 `0x15880` 的 item row `+0x0D/+0x0E` type/word 分支：type5/0x0D 的 current HP `<=max/3→8`、`<=max/2→3`、其餘0，raw `+0x34 bit7` ×3；type0x14/0x15 經 `0x4E516`、type0x18 直用 row word，target HP `<=threshold→0x12`、其餘8。`ScoreNativeAIItemCommandTargets` 已接並驗證邊界；不命名效果或 status。
- [x] **RE-AI-ITEM-PRODUCER-1567E**：保存帶雜湊的 `0x14818/0x149F8/0x14B16` 指令窗口，閉合 count-sized slot scan、row-major destinations、低 command area targets、高 command actor→destination cardinal targets、strict best 與 `[0x53C3F]=raw slot`。`ScoreNativeAI1567E` 已接；map0＋tracked item79 fixture 固定 score8／`(19,15)`／slot0。這是 E0 交叉 fixture，不宣稱一般玩家 map0 持有 item79。
- [x] **RE-AI-CANDIDATE-149F8**：Docker Capstone 閉合 `0x149F8` 的 cardinal ±X/±Y cursor steps、map bounds、`0x12C0D` unit lookup、raw `+6` selector gate、supplied byte-buffer writes 與 cursor restore；明確標為 candidate scanner，不命名 damage/hit/LOS/spell effect。
- [x] **RE-AI-MODE-SOURCE-10FB6**：Docker Capstone 閉合 FDFIELD 名冊 `b17/b18/b19` → runtime `+0x34/+0x35/+0x36`，33 圖 1887 筆低四位分布已保存為 `docs/data/fdfield_native_ai_modes.json`，資料管線與 `Unit` 保留原始來源；高四位不誤命名成 mode。
- [x] **RE-AI-MODE-WRITER-3419C**：閉合 `0x3419C` inclusive range writer 的保留高四位規則，以及 `0x13D20`／章節處理器的 whole-byte writes；新增 fail-closed materializer 與 writer regression。
- [x] **RE-AI-MODE2/11-BRANCHES**：Docker Capstone 與合法 IDA 閉合 mode 2 為 `0x14EF0` 失敗後 `0x14237→0x13FD4`，不走 `0x13E9C`；mode 11 依 `[0x53C23]`／`[0x53C4F]` 兩個獨立 signed `>=6` gate，第一段後仍評估物理第二段。新增 raw call-plan regression。
- [x] **RE-AI-IDLE-RECOVERY-13FD4**：`0x13FD4` 只在 currentHP≠maxHP 且 raw `+0x25/+0x26==0` 時回復 `floor(maxHP/5)` 並封頂；新增 state-only adapter，玩家休息正式路徑同步刪除錯誤的最少回復 1 並接 raw transient gates。
- [x] **RE-AI-MODE11-WRITER-35F92**：`[0x53AD5]+0x10==4` 時，`0x36078→0x3419C(20,20,11)` 改寫單位 20 低四位；它是全域 90-entry 表的 event 82，不是第二張 30-entry 表的 entry 22。一般玩家觸發尚未閉合，且 33 張格子事件表沒有 event 82，不猜章節或人物。
- [~] **REMAKE-AI-MODE-RUNTIME**：模式 2/11 raw planner 與 `0x13FD4` mutation 已閉合，但其餘模式玩法名稱、event 82 觸發、完整回合 orchestration 及 `NextAIPlan` production 接線仍未完成。`set_ai:berserk` 仍只是 inert 事件標記。——本輪(2026-08-20)推進:`doc11`「回合orchestration」子項已閉合(見上`0x1A30B`交織順序);「event82觸發」子項在`doc25`2026-08-19全EXE writer稽核已窮盡(§6.3附記);仍缺:「剩餘模式玩法名稱」——此為刻意fail-closed立場(不替模式命名),非遺漏,待可靠玩家可見語意證據(攻略對照/DOSBox E2)才補上。
- [x] **RE-FIELD-EVENT-13A44**：閉合地圖 event-word low5 的 1-based slot、FDSHAP `0x20/0x40` 寶箱 gate、FDFIELD 控制段 16×2 `(event_id,selector)` 與 `0xFF` gate；33 張地圖已同步為可編輯資料並有失敗即關閉查詢。
- [~] **REMAKE-GLOBAL-EVENT-DISPATCH**：全域 `0x51B91` 已由錯誤的 58 entries 更正為 90 entries；回合事件使用 0..57，格子事件只覆蓋另一子集合。58..89 handler 的高階語意與各 dispatcher 的 selector 生產路徑仍須逐一閉合，未知 handler 不接正式流程。——本輪(2026-08-20)推進:`doc25`§10對58..89剩餘26個handler做第一輪嘗試,58/59/60/61/63/82(既有)+67/69/76/78/84(乾淨反組譯)+65/74/75(局部片段)=90個entry中13個現有位址佐證的高階語意描述;仍缺:62/68/70/71/72/73/77/79/80/81/83/85..89共16個handler因函式邊界猜測失敗未取得可信結果(下一步應改用`extract_event_id_groups.py`已驗證的basic-block walk方式,而非位址差猜邊界)。
      ——本輪(2026-08-20續輪,`doc25`§10.4,回應L212剩餘16個handler)**部分推進，未完全解決**:改用
      `getInstructionAt`+`.getNext()`手動basic-block walk配合逐byte hex dump逐一定位這16個。結果——
      **9個(68/70/71/81/85/86/87/88/89)證實([驗])落在鄰居handler(多為event67/84)內部指令中段的
      ModRM/位移/立即值operand byte，無獨立語意，不是真正進入點**；**6個(62/72/73/79/80/83)取得可引用
      位址的具體行為描述([推])，多延伸既有event58(五選一寶物)/event72·84(回合重排程)/event73·74·75
      (給予item 0x1B/0x23家族)/event78·79(條件繪圖)家族**；**1個(77)確認非獨立進入點(落在一個先前未
      記錄的「給予item type 7」多階段handler尾端)，但該外層handler真正入口本輪60-byte視窗不足以定位，
      仍未解**。**90個entry中有具體行為描述者由14升至20**(先前14個58/59/60/61/63/65/67/69/74/75/76/
      78/82/84 + 本輪新增62/72/73/79/80/83)；另9個證實為共用鄰居代碼無獨立語意；1個(77)落點性質已知但
      外層handler未定位；64/66兩個entry在先前範圍界定中被遺漏，不屬本輪範圍。**checkbox維持`[~]`**：
      仍有77的外層handler、62/72/73/79/80/83升級為[驗]的交叉驗證、64/66兩個遺漏entry，以及各
      dispatcher的selector生產路徑尚未逐一閉合。
      ——本輪(2026-08-24,doc25§11,收尾58..89全範圍)**58..89全部32個handler首次取得明確狀態**:
      event64([驗]確認落入event62函式`jmp 0x358e9`位移中，第10個table artifact)、event65(補完整
      乾淨函式`0x35997..0x359ca`，由局部片段升級為完整)、event66([驗]落點在event65 `RET`前3
      byte，字面解碼出的3-byte垃圾指令恰好順流落入獨立姊妹函式`0x359cb`)、event77(外層handler
      `0x35e5b..0x35ebc`完整重建，其table slot對應該handler tail-call `jmp`的位移欄位，字面執行會
      解出無效opcode)均已閉合。順帶修正`0x35B78`語意——原判斷「給予道具」，實為
      「spawn_group+兩段調色盤淡出+戰場重繪」，影響event73/74/75/77呼叫點的讀法。**新發現的疑慮**：
      系統性回頭核對指令邊界後，發現既有標「[驗]乾淨」的event76／event78、以及event58本身登記位址
      `0x354fe`，其table位址同樣疑似偏移了幾個byte、落在鄰近函式指令中段(先前的「乾淨反組譯」可能是
      湊巧resync誤判)——**證據強但未經獨立管道完全釘死，本輪未直接改寫這3項既有結論，留待專門
      re-verify**。32個entry最終統計：22個有具體行為描述、10個確認為table artifact無獨立語意。
      **checkbox仍維持`[~]`**：剩event58/76/78的re-verify、各dispatcher selector生產路徑未逐一閉合。
      ——本輪(2026-08-24續輪,`doc25`§11.7,definitively收斂58/76/78)**re-verify完成**:找到§11.5當時
      缺的第二條獨立管道——不靠反組譯，直接讀`0x51b91`跳表原始4-byte值，用4個既驗錨點
      (event0=`0x341db`/event59=`0x35641`/event77=`0x35ebe`/event82=`0x35f92`)校準出一致的LE
      relocation偏移`0x356`(4/4錨點命中,零反例)，逐byte確認event58/76/78三個table槽位的原始值
      **precisely等於**既有登記位址`0x354fe`/`0x35d60`/`0x35ed2`——不是誤讀，也排除了§11.5回溯找到
      的「更早疑似真入口」(`0x35854`/`0x35d5d`/`0x35ec1`)是table實際編碼值的可能性。交叉指令邊界
      回溯(58新補、76/78重驗)確認三者皆落在鄰居handler中段：58→event57自己handler(`0x354dd`)的
      `PUSH 0xcd`立即值中段(15-byte巧合resync)、76/78→§11.5已找到的獨立乾淨函式`0x35d5d`/`0x35ec1`
      的PUSH/CMP運算元中段。**三者definitively確認為table artifact，無獨立語意**——與64/66/77/68/70/
      71/81/85..89同款,不是「未經獨立管道完全釘死」的存疑狀態。58..89最終統計更正為**18個具體行為
      描述、14個table artifact**(原22/10統計本身加總亦有誤，一併更正)。額外發現：doc25§6.3「event
      58:map25五選一寶物」的入口位址`0x354FE`與「透過event_id58觸發」歸因需撤回——邏輯描述本身
      (`0x1B8A6`/`0x5274E`/`0x1BB8C`/FDTXT`0x1E0`)不受影響仍為[驗]，但其真正所在函式`0x35854`
      目前查無任何已知靜態呼叫者，map25寶物slot在原版runtime真正的觸發路徑變成新的未解問題(見
      doc25§11.7.5，也牽動已標`[x]`的**REMAKE-TREASURE-EVENT58**——該項的遊戲規則描述本身未受
      影響，僅其RE位址佐證`0x354FE`已知有誤，見該行附註)。**本項(58..89 handler高階語意)可視為
      definitively收斂完成**；checkbox維持`[~]`僅因「各dispatcher selector生產路徑」子項仍未逐一
      閉合，與本輪解決的範圍無關。
- [x] **RE-POST-RESOLUTION-1AA1D**：閉合 `{kind:u8,payload:u16le}`，kind0/1 為物品／金錢、kind2 dispatch 全域事件、kind3 為另一呈現分支；建構器只採 FDFIELD b22+b23..24，撤回 b23..25 24-bit payload。
- [x] **REMAKE-NATIVE-TREASURE-ASSETS**：33 圖 composition+FDSHAP 寶物格及 16 槽控制列已選擇性同步；type0/1 可執行，其他型態保存 event/native_type 並失敗即關閉，不再誤給一般物品。
- [x] **RE-EVENT82-REACHABILITY**：turn、field、treasure、unit effect 與四個 EXE 硬編碼後處理列均無 payload82；目前無已知資料 producer。仍須稽核 runtime `+0x31..+0x33` 的其他 writer，未證實 dead code。——已解:`doc25`(2026-08-19)全EXE指令級xref掃描,僅4個真正writer(2個寫死0xFF常數、2個被`kind<2`硬gate擋掉),**證實dead code**。殘留2個低機率不確定性(暫存器算位移寫入、未反組譯區域)如實記錄未升格為絕對結論。
- [x] **REMAKE-TREASURE-EVENT58**：閉合 map25 slots0..4 共用 event58；空欄時依 slot 給 `[1D,2B,33,3D,47]` 並共同關閉五槽，滿八格不改狀態。規則已綁定 EXE 雜湊、匯出成 editable JSON 並接正式 ClaimTreasure。——**RE位址附註(2026-08-24,doc25§11.7)**：本項描述的遊戲規則本身未受影響，但其原先引用的 RE handler 位址 `0x354FE` 已確認是 `0x51b91` 跳表 event58 槽位的 table artifact(落在 event57 handler 中段，不含這段邏輯)；真正的邏輯本體在 `0x35854`，且該函式目前查無已知靜態呼叫者，原版 runtime 如何從 map25 資料的 `value:58` 呼到這段程式碼仍未查明。若 `native_treasure_event_rules.json` 或相關 regression 有依賴 `0x354FE` 這個位址值本身(而非規則的行為結果)，建議之後核對更新；不影響本項 checkbox 狀態。
- [x] **RE-PHASE-RESOURCE-1A7BD**：Docker Capstone 固定 `0x1A7BD` 是 `[0x53AF9]` gate 下的 `0x111BA(0x1A4D,0,0x40)` resource-handle setup，`0x1A7F1` 釋放 `[0x53B0F]`；已從 transient selector／campaign phase 語意中分離。
- [x] **音樂播放與場景切換**機制(AIL XMIDI 序列)→ `12-…`
- [x] **戰場選單與行動系統**(行動狀態機/選單游標/Get_EasyMagic)→ `13-…`
- [x] README 知識庫總索引(可點選分類)
- [x] **glyph→Unicode 對照表完成(1824/1824,100%)** → `docs/data/glyph_map.json`(含數字/英文/漢字/標點/機器人雙字元代號)
- [x] **全 35 章劇情轉錄完成**:自動解碼成含說話者的 UTF-8 → 本機 `extracted/story/full_story_auto.md`(1450 句);序章~第3章另有人工精校
- [x] **按鍵綁定**(Enter/Space 確認、ESC 取消、方向鍵)反組譯 → `13-…`
- [x] **Get_EasyMagic** 法術面板反組譯(0x18ED0)→ `13-…`
- [x] **場景→曲號對映**:play_bgm(0x26777)+ 32 處呼叫 track 反組譯 → `12-…`
- [x] **LE fixup xref 工具**(`tools/le_xref.py`)解開 DOS4GW 重定位,可做 data xref
- [x] **控制碼語意還原**(反組譯文本渲染器 0x16D00-0x17200):FFEF/EE/ED/EC=開對話框(FFEF 帶 DATO 頭像)、
      FFFE=換行、FFFD=翻頁等鍵、FFFF=結束 → `09`;副產物確認 **DATO.DAT=人物頭像**
- [x] **劇情校對**:解碼自驗 + 上下文揪出 14 處形近字模誤判並修正
      (脅/實/黨/費/鍛/輩/辭/摸/牢/樁/紮/襲/態/責)
- [x] **陣營/狀態 remap 配色**:確認 LUT 來源=FDOTHER 資源#3(LMI1,23張256-byte LUT),dump 並套用展示(LUT0灰=已行動…)→ `10`;BB→LUT索引精確對應待續
- [x] **DATO 頭像全解**(136×4嘴型幀)→ `01`§7;**Unicode→glyph 反向表+編碼器**(round-trip 100%)→ `tools/encode_text.py`
- [x] 各 track 呼叫端對應確切遊戲狀態名(片頭/世界圖/城鎮/戰鬥/劇情)→ doc12「場景切換時的換曲」已列 5 狀態對映(2026-07-05 核實)
- [x] **FDSHAP 圖塊庫解碼**:標頭 count + u32 offset 表 + native 24×24 four-mode RLE；2026-07-26 直接掃 FDSHAP_000 的 288 tiles，mode `[0,2,3]` 全部完整解碼，撤回「僅不透明 bg-RLE」錯誤。`render_map.py` 依 `0x4deda` ABI 保留 transparent spans 為 index0；多層 foreground composition 仍不得由單張 export 推論。→ `01`§8
- [x] **全 33 張戰場地圖抽取**:FDFIELD×FDSHAP(配對 map N→FDSHAP[2N],索引驗證全通過)→ 本機 `extracted/maps/`;`tools/extract_maps.py`、`render_map.py`
- [x] **FDICON.B24** = 1680 個 24×24 **地圖單位 Q版小人 sprite**（four-mode RLE；撤回「與 FDSHAP 為不同 bg-RLE codec」，兩者共享 ABI、renderer branch 不同；每角色組12=4方向×3幀）→ `31`
- [x] **TAI.DAT** = WxH 圖像(sprite-RLE,如 155×42);多為 UI/特殊圖
- [x] 寫一篇總覽:「1995 年怎麼做出炎龍騎士團2」→ `15`
- [x] 寫一篇總覽:「1995 年台灣怎麼做遊戲 — 炎龍騎士團2 技術全紀錄」→ `docs/knowledge-base/15-how-fd2-was-made-1995.md`(2026-07-05 核實存在)

- [x] **FDFIELD 三段完整解析**:構成(地形)/控制(出場數/回合事件/寶箱/敵我roster)/出場位置;全33圖 metadata → 本機 `extracted/maps/maps_metadata.json`;`tools/parse_field.py`

## 第 4 輪以後(暫定)
- [x] 地圖格式完整解析(FDFIELD 三段)+ 渲染全 33 圖(見上)
- [~] 反組譯戰鬥/命中/傷害/AI 演算法(Ghidra)，與攻略公式交叉驗證——大部分收口:`doc27 §5`(2026-08-19)20項三方一致性盤點,15項三方一致(物理/劍技/法術/恢復/命中/暴擊/AI評分);仍缺:經驗值公式攻守等級因子、武器命中特殊效果(0x2f7b6內cVar4分支)、6種傳送/魔刃等經驗公式、法術命中逐ID核對——本輪(2026-08-19續輪,`doc27`§5.1)推進:武器命中特殊效果`cVar4`分支來源鏈與全部15個觸發武器id解出(→完全閉合)；6種傳送/魔刃/魔鎧/風行/麻痺/毒擊/解毒/祛麻/行動術經驗公式全部找到並反組譯(→完全閉合)；職業等級上限特例封閉列舉(`0x1e292`只比對portrait是否為0x1e/0x1f，非職業，無第三分支→完全閉合)；經驗值攻守等級因子靠第二個獨立實作`0x1ecc7`佐證既有假設(仍為部分開放，未100%排除歧義)。仍缺:法術/道具命中率逐ID核對(`0x1c7ed`的`record[+2]`未逐一dump比對`spell.json`)——這是四項剩餘工作中唯一完全未觸碰的子項。
- [~] **物品系統反組譯**(M1 用)→ `32`:已確認物品表23B結構、roster 8裝備欄與 AP/DP raw temporary leads；舊 `0x15356` 傷害公式地址未由 canonical scan 證實。裝備加成精確累加點（夾攻擊大函式、表 base-relative）與使用效果碼待續。——本輪(2026-08-19續輪,`doc32`§4.2)大幅收口:裝備加成精確累加點早在§3.5已閉合(四條公式對截圖逐位吻合)；使用效果碼把`0x20c6f`的`cVar1`(row`+0xd`)dispatch從「部分覆蓋清單」補成0–24全25個值窮舉(20個有callee、5個是no-op)，武器on-hit特殊效果(`cVar4`)也解出來源鏈與全部15個觸發武器id。剩餘缺口只剩:type3旗標(僅1個道具id71)的下游消費者、幾個marker/狀態的玩家可見名稱。
- [~] **轉職系統反組譯**(M4):轉職觸發(教會/道具)、職業數值替換、能力繼承、轉職後成長表切換 → 攻略道具表(勇者徽章→英雄…)交叉驗——機制已解:`doc32 §6`(2026-08-19),教會Lv≥20→查0x526a7道具→0x1e529五組growth累加(Lv保留EXP歸零HP/MP回滿),成長表切換證實=同一張68列表後半段(idx32-67);13/18道具吻合攻略。caveat:部分函式位址來自遺失舊版EXE,新版待重定位;class_change_targets.json portrait11/12/13疑輪轉錯位待查——本輪(2026-08-19續輪,`doc32`§6.6)推進:對第二個舊版位址`0x31793`在新版EXE做spot-check,確認該位址現在是無關的UI程式碼(呼叫`0x11eb0`/`0x11d40`/`0x2eb9f`,與轉職候選判定完全無關),強化(非首次證明)「同位址探測法已窮盡」的結論；portrait11-13輪轉錯位問題本身仍未解決,要解開需要全檔byte-signature重新定位轉職相關函式,超出可負擔的探測量,維持D(可續但需大量前置工程)。
- [~] **角色名對應**:補全 portrait→角色名 → `49`。核實後「12 個」已過期,實際已定案 38 組
      (0-31 共 32 + 48/66/68/96/97 共 5 + 本輪新增 126=ASR-06);其餘約 97 組多為泛用怪物/路人,
      對話走場景相依 `-19/-20`(見 `40`),**無法只靠對話反推**,需逐圖解 FDFIELD roster 才能繼續補
      ——本輪(2026-08-19續輪,`doc32`§7)複核:狀態不變,未展開新地圖解碼;`doc49`(2026-08-19)已誠實列為待辦,
      每張地圖都要逐一解FDFIELD roster `byte[+7]`,工程量遠大於單輪範圍。
- [x] `FDICON.B24`=1680個24×24地圖單位sprite(sprite-RLE,見 `31`);`TAI.DAT`=WxH圖像(sprite-RLE)
- [~] `FD2.SAV` 存檔：Docker static trace 已固定 `rb/wb FD2.SAV`、全檔 `0x59cb`、四槽 record `+0x312b+i*0xa28`（`0x28` metadata + `0xa00` persistent roster）；真實 sandbox decode 與 `tools/fd2save.py` round-trip/tamper regression 已固定 `0x4dbd8` rolling-XOR、`0x4dbb9` byte-sum checksum。合法 IDA 9.4 閉合 reader `0x2602c..0x26098`、writer `0x30012` 及兩個戰間 caller；兩端對稱處理 roster 與 metadata `+0..+9`。production `FD2_NATIVE_SAVE` 已從 indexed selector 正式接到 `BuildNativeChapterSlotRestorePlan`：依雜湊綁定的 `0x526b9` table，把 raw chapter 1..29 原子還原為 fresh campaign flags、gold、typed persistent party 與 town／preparation node；ch21/ch27 的 postbattle inventory gate 不重播，錯誤不部分套用或誤轉 JSON loader。四槽 LOAD 仍不是 `0x10010` CONTINUE；尚缺一般玩家有效槽 E2、metadata `+10..+39` 其他可能 consumer、delete/overwrite 及 current-battle restore。不得再稱「強加密／無結構」；重製自有存檔仍為另一格式。
  `0x112A5→0x1145A→0x17FC0` 的 writer／consumer 已再由合法 IDA 固定
  item cells、command mask、race/class/level、transient、base AP/DP、
  MV/EXP、DX、HP/MP 與衍生 AP/DP/HIT/EV offsets；新增
  `PersistentRecord.View` 唯讀投影及 signed-word regression。下一步是
  證據化 name/class/resource resolver，再接 normalized party；不可直接
  把 raw `+7/+8` 都當 portrait／character id。
- [x] **RE-SAVE-ENVELOPE-ADAPTER**：新增 `remake/internal/fdsave` typed raw adapter，依 `0x4dbd8/0x4dbb9` 保存 rolling-XOR、u32 byte-sum、四槽 bounds 與 writer／reader 已證實的 metadata `+0..+9`；`+10..+39` 與未投影 roster bytes 保持 opaque，Go Docker round-trip/tamper/bounds regression 通過。
- [x] **RE-SAVE-WRITE-SLOT-30012**：官方 IDA 9.4 閉合 `0x30012` confirmed-slot write order：2560-byte roster→`record+0`、metadata `+0..+9` globals→record、checksum over `0x59c7` bytes、rolling-XOR、完整 `0x59cb` write。新增 `fdsave.WriteSlot` opaque replacement adapter/regression；仍不宣稱 native roster/opaque metadata 已接入 remake campaign。
- [x] **NATIVE-CHAPTER-SLOT-RESTORE**：官方 IDA 9.4 固定 `0x30012` 只由 `0x2ccb6/0x2fd93` 戰間流程呼叫；新增雜湊綁定的 `native_intermission_gate.json`、side-effect-free restore plan 與 production title owner。完整 `campaign_full` raw chapter 1..29 均驗證落到既有 town／preparation；合成有效槽驗證 typed party、gold、raw option bytes 保存及錯誤無部分 mutation。這是 E1，不取代一般玩家有效槽 E2，也不接 CONTINUE。
- [x] **音色合成評估+MT-32實證**(SoundFont/MT-32/版本切換,munt渲染15首)→ `16`
- [x] **擴充劇本/玩法可行性評估**(戰場/對話/商店/機制)→ `17`
- [~] SoundFont/MT-32 → 見 `16`(MT-32 已渲染);SoundFont 試聽 + TIMB 配器對映待補
- [x] 選定首個重製技術棧做「讀真資料 → 畫面」垂直切片——2026-08-19稽核確認：本檔第277行「重製MVP垂直切片」與289-294行「M0引擎骨架✅」已證實Go/Ebiten技術棧選定與垂直切片皆已完成，僅本行未同步。
- [x] 反組譯完整性盤點——`doc27 §5`(2026-08-19)戰鬥演算法20項三方一致性盤點表(攻略公式=反組譯位址=remake實作),明確標出15項一致+剩餘缺口清單

## 重製前置(規劃/實作)
- [x] **音樂預錄 OGG**(MT-32 音源):15 首 → 本機 `extracted/music_ogg/`;`tools/export_music_ogg.sh`
- [x] **字型現代化規劃**(UTF-8 + TTF render)→ `18`(計畫:文字資料化 + TTF + 雙字型模式)
- [x] **劇本/關卡腳本系統設計**(可分支節點圖/敗北路線/商店/旗標)→ `19` + `docs/data/campaign_sample.json`
- [ ] 實作:`decode_story_text.py --script-json`(35 章 → UTF-8 script);重製文字層 TTF render
- [ ] 實作:從原版資料自動生成「線性 campaign.json」(parse_field + 劇情 + 商店)→ 原版模式
- [x] 實作:引擎 ScenarioRunner 狀態機(節點/轉場/旗標)——已解:`doc19`(2026-08-19)逐一核對後確認:猜測的`handler_script.go`(postbattle/cutscene handler beat編譯schema)／`menu_state.go`(泛用選單游標)不是主要實作，但ScenarioRunner本身確實已在`remake/internal/campaign/campaign.go`(`Node`/`Campaign`/`Runner`，729行)＋`main.go`的`enterNode`/`campInput`實作，且超出原始設計新增`preparation`/`town`/`cutscene`/`inventory_gate`/`inventory_recipe`等節點型別，`Campaign.Flags`+`Node.SetFlags`對應旗標系統，`Runner.Advance(outcome)`對應轉場解析。**注意**:本篇原始設計的「勝利/失敗條件」組合式詞彙(`survive_turns`/`protect`/`turn_limit`等)仍完全未實作(見上方`winCondition`/`checkVictory`/`advanceTurn`純未實作項)，屬另一獨立技術債，不影響本項「節點/轉場/旗標」三部分狀態機本身已完成的判定。
- [x] **第一性原理可行性確認** → `20`(9 項必要能力全具備,降為工程整合)
- [x] **Go/Ebiten 重製架構規劃** → `21`(桌面/Web/手機)
- [x] **重製 MVP 垂直切片**:Ebiten 載入序章地圖+渲染+游標(方向鍵/WASD/觸控)→ `remake/`
- [x] **技術驗證報告** → `22`(桌面 ELF 10.8MB + WASM 10.5MB + 資產管線,三項全通)

---

# 重製 worklist(Go/Ebiten,本機優先;依序執行)

> **詳細工作拆解(WP/輸入/產出/驗收/衝刺)見 `30-remake-work-breakdown.md`**。本表為里程碑總覽。

> 策略:**先把本機桌面執行檔做成能完整玩,再回頭處理網頁/手機打包**(`22` 已證三平台都可建)。
> 每個里程碑 = 一個可執行、可驗收的切片。完成才往下一個。架構見 `21`,可行性見 `20`。

## M0 — 引擎骨架 ✅(已完成)
- [x] Ebiten 專案 + Docker 建置流程(`remake/`,`go.mod`/`go.sum`)
- [x] 載入地圖渲染(tileset.png + map.json,offset 表定位無漂移)
- [x] 游標移動 + 相機跟隨(方向鍵 / WASD / 觸控)
- [x] hi-res 畫布(640×400,CJK 拉畫布不縮字)
- [x] **本機桌面執行檔建成(Linux ELF)** + WASM 編譯成功 → `22`

## M1 — 戰棋核心(下一個,讓它「能玩一場戰鬥」)
> 驗收:能部署我方、選單下指令、移動(flood-fill 範圍)、攻擊結算傷害、敵方 AI 回合、判定勝敗。
- [x] 資料模型:Unit(HP/攻防/移動力/陣營/位置/alive/acted)、BattleState(回合/單位) → `remake/internal/battle/model.go`
- [x] 單位資料管線 `tools/export_units.py`(roster+座標+EXE數值→units.json)+ 引擎載入並渲染(陣營色塊+HP bar+選中資訊)+ headless test 全綠
- [x] 移動:flood-fill 可達範圍 + 高亮 + 選取/移動/待機(`move.go`);地形成本待接
- [x] **地圖單位 sprite=FDICON Q版小人**(24×24 待機動畫)→ `31`(取代誤用的 FIGANI 全身)
- [ ] 戰場選單狀態機(移動/攻擊/待機/道具/結束),對齊 `13`(游標/Enter/ESC)
- [x] 攻擊結算:套**青衫公式**(物理/劍技/法術/恢復+命中+暴擊+經驗,doc 02 §4 = 實作依據)+ EXE 數值表(`03`)——2026-08-19稽核確認：`docs/knowledge-base/27-combat-rules-and-validation-checklist.md`§5三方一致性表(物理/地形/命中/法術傷害/恢復/AI評分)均已標記remake實作並✓一致，僅本行未同步。
- [~] 敵方 AI 回合：normalized flood-fill/評分與 raw evidence 對照；舊 `0x15140` 地址已由 canonical recheck 撤回。`0x13A9F/0x14EF0/0x15B77` 的 dispatcher/candidate/score slices 已各自有 evidence/adapter，但完整權重、turn/camp、target selection 與 runtime execution 仍待 RE。`0x1598A` 使用 `0x14818`、`0x1567E` 的 item-command spell branch 才使用 `0x149F8`；raw `+0x22..+0x27` 不命名 AP/DP/HIT/status。——本輪(2026-08-20)推進:物理/法術/道具三條評分公式與`0x14EF0`三分數tie-break早已個別關閉;`doc11`本輪新補「兩遍敵軍掃描為何存在」的觸發時機面——`0x1D8BA`在`0x1A30B`內只會被呼叫一次且是selector0那次,與selector1的`0x1D80B`友軍單遍不是同一次呼叫,現確定是同一個`0x1A30B`裡先友後敵、緊接遞增回合數的固定順序。target selection完整權重公式面維持既有結論;「為何需要預選與第二遍」這個玩法設計層問題仍待。
- [~] 敵方 AI 雙預選 bridge：`BuildNativeAIPhaseDiagnosticPlan` 已依
  `0x1D8BA` 原序將 `0x1598A→0x15B77→[0x53C23]` 與
  `0x1567E→0x15880→[0x53C33]` 兩個具型別 producer 接入
  `PlanNativePhaseUnitScans` 的 signed `>=6` 門檻；每個合格 selector-zero
  單位都要求明確成本列，缺漏／重複／額外輸入失敗即關閉。map0 修改狀態的
  E0 交叉夾具固定96／8並保留第二遍，且驗證輸入記錄不變。它不執行
  `0x13A9F`、回呼表或 pending code；尚缺同一原版 runtime 動態 trace，
  故仍不接正式 `NextAIPlan`。
- [x] **RE-AI-COMPOSITION-EVENT-BYTES-ALL-MAPS**：修正同步工具漏掉
  FDFIELD 構成格 `+2` 的管線缺口，同時撤回把它直接命名成完整 target
  flags 的錯誤斷言。33 張 map 現均同步
  `native_composition_event_bytes`；`0x4DBFC` 的 low5 基底與
  `0x145CD→0x14625/0x146A7` 的 caller-specific `0x40/0x80` writer 已分層。
  合法 IDA Pro 9.4 已優先確認函式邊界與交叉參照，Capstone 再覆核
  直接指令；`0x4E040` 只建立搜尋狀態，實際旗標消費端是 `0x4E16E`。
  證據保存於
  [`fd2_field_composition_lifecycle_disasm.txt`](../data/fd2_field_composition_lifecycle_disasm.txt)。
  map19 1600格中7格非零，真實 unit55 的兩個 producer 均為零分且不創造
  勝者。`0x145CD` 直接呼叫者的短生命週期執行期旗標（live flags）仍維持
  明確傳入。
- [x] **RE-COMMAND-FLAG-LIFETIME**：合法 IDA Pro 9.4 優先確認
  `0x1598A/0x1567E/0x1CFF0/0x1BBDC` 的候選生命週期，Capstone 再覆核每次
  `0x4E040/0x14818` 後都呼叫 `0x4DBFC`，且這些函式沒有呼叫 `0x145CD`。
  `State.NativeTargetFlags` 已刪除；正式命令改由
  `NativeCompositionEventBytes` 每次重建獨立低五位切片（low5 slice），測試鎖定跨呼叫
  不共享 mutation，缺來源仍失敗即關閉。直接證據見
  [`fd2_ai_composition_flag_lifetime_disasm.txt`](../data/fd2_ai_composition_flag_lifetime_disasm.txt)。
- [x] **RE-AI-RAW-RECORD-1598A**：`NativeAIScoringRecords` 以完整來源建立分離的 `0x50` runtime 快照，補齊 presentation、`+5/+6/+34..+36/+42/+46` 並拒絕不完整 roster；map0 與 map19 真實資產錨點通過。
- [x] **RE-AI-CANDIDATES-1598A**：`NativeAIScoredCommandCandidateGroups` 已以 command `+3/+4`、原版 cost row、exact grid flags 與 raw `+5/+6` 建立 row-major destination/target-index groups；selector target-code transform 與空 target skip 已保存，map0 identity103→ally `(23,14)` 真實資產 regression 通過。群組、單位級最大分數與三遍門檻均已接入唯讀診斷；下一步是原版同狀態動態 trace。
- [x] **RE-AI-SCORE-GROUPS-15B77**：`ScoreNativeAIScoredCommandGroups` 已依完整 ID 家族分派攻擊、恢復、旗標與原始零分支；map0 command0 的四個友軍目標各得24、群組合計96。IDs10..12 缺 `0x1F183` caller gate 時拒絕執行。`[0x53C23]` 的數值最大值可由零開始比較，但零分時的命令字區域變數初值仍未知，尚不可聲稱已閉合勝者。
- [x] **RE-AI-UNIT-SCORE-1598A**：`ScoreNativeAI1598A` 已串接命令可用性→候選幾何→群組評分→正分 strict winner，並交叉驗證 actor mask／MP 與 runtime record；map0 command0 固定最大分96與 `(23,14)`，全零分不創造勝者。純數值結果已接到三遍 phase planner 的 `[0x53C23]` 證據欄；正式動作執行、逐單位回呼與 pending early-exit 仍未接。
- [x] **RE-AI-MAP-ASSET-INPUTS**：撤回「地圖已有初始命令遮罩」的錯誤前提；同步前 33 張圖共 1887 個單位全數缺欄位。現在已由 FDFIELD b13..b16 補齊，並依 `0x10d7f..0x1100c` 同步 constructor `word42/word46`；1885 筆具有完整 MP 來源，map32 兩筆未覆蓋 selector 保持缺值。現有 263 筆非零遮罩中，261 筆通過原始 MP gate。
- [x] **RE-AI-SPELL-SCORE-15B77**：Docker Capstone/Hex-Rays 釘死 `0x15b77` 的 attack IDs0..12 score（HP `<` spell value→24，否則8；record `+0x08==0` 時乘 1.5 並 toward-zero）與 recovery IDs13..16 score（HP `<` max/3→8、否則 `<` max/2→3、否則0；`+0x34 bit0` 再×2）；新增 raw-only `ScoreNativeAISpellAttack`／`ScoreNativeAISpellRecovery`，ID10..12 嚴格要求 caller-supplied `0x1f183` gate。未接 AI runtime、command inventory、target UI 或效果名稱。
- [x] **RE-AI-SPELL-FLAGS-15B77**：Hex-Rays 釘死 ID20/21→raw `+0x25/+0x26` nonzero flag score，每筆各加6；ID26/27→同兩 offsets zero flag score，每筆各加4；新增 `ScoreNativeAISpellFlag`／`ScoreNativeAISpellZeroFlag`，不清除、不命名 flag，也不接施法 runtime。
- [x] **RE-AI-SPELL-MODIFIERS-15B77**：Hex-Rays 釘死 ID17/18/19→raw `+0x22/+0x23/+0x24` zero flag score，每筆各加3；`ScoreNativeAISpellZeroFlag` 保存該 raw helper，未命名 transient 欄位或接 AI runtime。
- [x] **RE-AI-DISPATCH-1598A**：合法 Hex-Rays pseudocode 釘死 `0x1598a` 的 caller order：`+0x27==0` gate→`0x1c269` command bytes→record `+5 <= unit+0x44` MP gate→target resolver→`0x15b77` score；最高 score 勝，平手比較 command record `+0`，再保存 raw `(x,y,command)`。新增 `SelectNativeAISpellCandidate`，只做 score/tie-break，不接 MP、target、UI 或施法執行。
- [x] **RE-AI-DISPATCH-GATE-1598A**：`NativeAvailableAICommandIDs` 將 `0x1598a` 的 raw `+0x27==0` gate 加在既有 bounded command scan 前；unknown physical IDs36..39 仍 fail-closed，不接 target resolver 或 runtime action。
- [x] **RE-AI-SPELL-ID22-15B77**：`0x15d30` 先 gate raw `+0x27==0`，再呼 `0x1c269(unit,nil)` 掃 `+0x1a..+0x1e` 五 bytes；任一 bit set 即累加6。新增 `ScoreNativeAISpell22`，不命名欄位、不接 ID22 effect/status runtime。
- [ ] 勝敗判定 + **回合推進(回合無上限;上限只由劇本事件 turn>=N 設定,見 `27`§1)**
- [ ] headless 確定性回歸:固定種子打一場 → 結果可重現(驗演算法,不靠手玩)

## M2 — 文字 / 對話層
> 驗收:對話框能顯示 UTF-8 劇情、帶頭像、翻頁;字用 TTF render(不再靠點陣字模)。
- [ ] 工具:`decode_story_text.py --script-json`(35 章 → UTF-8 `script.json`,控制碼→結構)
- [x] 引擎 TTF 文字渲染(接 `18` 字型現代化:資料化 + TTF + 雙字型模式)——2026-08-19稽核確認：`remake/cmd/fd2/font.go`已用`golang.org/x/image/font/opentype`實作CJK TTF渲染，並由`main.go`多處`loadFont()`接入正式畫面，僅本行未同步。
- [x] 對話框 UI ✅(debd52d):原版框素材(LMI1 #21 310×99)+ orig 佈局(下框(5,112)@320/上框鏡射)+
      大側臉頭像(我方左面右/對方右鏡像面左,對映 0x4E8AF/0x4E8E1)+ 白字『』框內換行(≤3行);
      翻頁=campaign story 逐句 Enter。LMI1 #20=單位詳細狀態面板(待用)
- [~] DATO 頭像接入：已新增 `internal/dato.MouthState`，以 native `0x16D00` 的每 2 frame tick、開嘴 1 tick、閉嘴 `rand()%30+2` cadence 驅動 m0/m3；完整 DATO frame/grid、speaker layout 與 runtime dialogue parity 仍未閉合。

## M3 — 音訊層
> 驗收:戰鬥/城鎮/劇情切場景時 BGM 正確切換,用預錄 OGG(MT-32 音源)。
- [x] OGG 串流播放(15 首,來源 `extracted/music_ogg/`)——2026-08-19稽核確認：`remake/cmd/fd2/audio.go`的`playBGM`已用`vorbis.DecodeWithSampleRate`+`audio.NewInfiniteLoop`完整實作OGG串流播放，僅本行未同步。
- [x] 場景→曲號對映(對齊 `12`,play_bgm 邏輯)——2026-08-19稽核確認：`main.go`多處場景轉場點已呼叫`playBGM`並帶入正確track(如`title.go` FDMUS_018／`0x025db5`)，wiring已落地，僅本行未同步。
- [ ] (選配)SoundFont/MT-32 版本切換開關 → `16`
- [ ] 音效(SFX)接入

## M4 — 腳本系統 / 流程串接
> 驗收:序章→商店→分支→下一關 能一條龍跑完;戰敗走不同路線而非 game over。
- [ ] 工具:原版資料自動生成「線性 campaign.json」(parse_field + 劇情 + 商店)→ 原版模式
- [ ] 引擎 ScenarioRunner 狀態機(節點/轉場/旗標),對齊 `19` + `campaign_sample.json`
- [~] 商店節點：目前可編輯 `item.json`／shops fixture 保存 215 個 numeric item ID（0..214）與價格；較早「337 筆商品」說法無現行 fixture 支持，已撤回。祕密商店與 town 回返已接、`ClassID`／item type／class equip 白名單、指定收件者與兩階段裝備 prompt 已接；賣出 UI 已接成「Tab→角色→欄位」，`SellSlot` 鎖定原價 75 折並同步移除 equipped flag；`0x1145a/0x1c142` RE 已接入 base+flag 重算與 `<0x80`/`>=0x80` 同類替換；raw `inventory_slots` 保留 source 8 bytes，Load/PartyUnits 依 `0x10f06..0x10f31` materialize 成 runtime 8 slots，內部空槽不再錯移。runtime `0x602ad` item table 的完整邊界／215 rows 對應仍未閉合，故不把它當作 attack UI 的真相；`0x14237→0x14818` 僅鎖定 caller-specific geometry 用途；待：完整 item multiplier/效果碼與原版 UI 對照。——已解(L366/L1354):`doc32`§1.1(2026-08-19)修正舊版file offset provenance bug後,證實table真正邊界為精確215 rows(ID 0..214)、stride`0x17`(23B)，row215與已知class-change`0x615FE`表零gap銜接，不再是「已知前綴」；`+0x9/+0xa`(武器命中特效selector/強度)、`+0xd`(效果dispatch code全25值窮舉)、`+0x10/+0x12/+0x15`(target mode/code)亦於`doc32`§4.1/§4.2收斂命名，只剩`+0xb/+0xc`(caller-specific幾何)與結構性冗餘`+0x16`未強行命名。L368(`+0x22/+0x23/+0x24`)查明與本表無關，是另一結構(command17/18/19暫態buff持續時間byte)，已在`doc13`(2026-08-19)閉合。
- [~] 戰後 town/整備流程：campaign_full 的 postbattle→town、連戰 preparation 路線與 shop/rumor return 已盤點；城鎮 `0x2d093` 是進戰場確認／小名冊略過選人／取消回城，無城鎮 `0x2cad7` 則是記錄詢問後必進選人；兩路共用 `0x318ad` 的30-byte全零勾選表、一般cap15／late cap19。重製已接分流及 `partyDeploy`，永久 JOIN roster 不被改寫；選人面板仍是重製殼層，尚非原版介面。church `0x3072f` 已證實四個 raw index→address dispatch（不是四個已命名服務）；`0x2d7bd` 只接受左右鍵並在四項循環。revive fee table、原子 `ReviveUnit`、church selector 與 class-change 候選→唯一 target→確認 mutation 已接；尚待 indexed renderer 與原版數值對照（無免費一般治療）。
- [~] 戰後 town/整備流程：preparation 與 church selector UI 已接；`docs/figures/church-selector.png` 為 xvfb 實機畫面。revive 與 class-change 單一 target mutation 已可保存 roster/gold；尚待完整 xvfb 轉職操作。原「`+0x22/+0x23/+0x24` DX/race/multiplier欄位資料化」敘述已勘誤(2026-08-24)：這三個offset根本不是DX/race/multiplier，是指令17/18/19(魔刃/魔鎧/風行術)的暫時buff持續時間byte，write→decrement→recompute全鏈(`0x22721`/`0x22866`/`0x22997`→`0x1A866`→`0x1B750`)早於2026-08-19即逐指令反組譯完成(doc13/doc27§8)，statically在任何地圖資產都是0(純runtime state非角色靜態屬性)；remake已有`ApplyNativeCommandModifier`/`ApplyNativeRuntimeEquipmentRecalc`/`TickNativeTransientsRaw`三個對應primitive，缺的只是接成`ExecuteNativeCommand17_19`的工程接線，非RE缺口。
- [~] class-change church：已鎖定 `0x3151a..0x3152d` portrait→item gate、`0x31860` inventory 掃描、`0x1b8e7` item 移除與 `0x31571..0x3157a` class/portrait 寫回；`0x526a7` mapping、`0x2a2e8` 成長重算與 editable target resolution 已接，待 raw race/multiplier 欄位與實機回歸。
- [~] class-change church：`class_change_targets.json` 已校正為兩層可編輯資料：current portrait 0..0x11→default target 與 optional/special override inputs（`0x526a7` 以 current portrait 索引，raw `0xff` 不啟用 optional override），以及 target portrait 0x20..0x41→class/mobility increment (`0x615fe`)；portrait 9 持 item 0x5a 時覆寫為 target 0x34。這些不是玩家同時可選的分支。
- [~] class-change church：核心 `campaign.ApplyClassChange` 已依 `0x31602` 實作可重現 RNG（row `[min,max)`）、將新職 AP/DP/DX/MaxHP/MaxMP growth **累加**既有值、MV(+0x3b) 累加、保留 Lv、清 EXP、HP/MP 回滿與轉職道具移除；persistent party 已同步保存 MV。自動 target 解析與左右 Yes/No confirmation 已接，仍需原版實機數值回歸。
- [~] campaign town/shop 外部交叉盤點：攻略頁明列第4、7、9、14、16、18、19、21章的武器店／道具店／教會／神秘店（來源連結已記入 handoff）；不能由攻略頁推論戰後立即順序，仍以 EXE table 與 `campaign_full.json` 的 postbattle→town/preparation 節點為準，後續測試不得把勝利直接串成下一戰。
- [x] ch02/ch03 story handler slices：ch02_pre/ch02_post 依 count-aligned scene line 範圍播放；ch03_post 接已證實的 ch04 scene3 lines0–3；ch03_pre 已由 jump-table/loadch/FDTXT_004 direct evidence 完成 binding，idx0→scene0 lines0–3、idx1→scene1 lines0–4，`story_ch04` 不再只播兩句 generic fallback。
- [x] ch04/ch05 pre-handler slice：`ch04_pre` 的 FDTXT_005 idx0/1/2 已接 `ch05.json` scene0/1（3+3+9句），map4 50-slot、pan、acting22/21 皆有 binding；`story_ch05` 已由空 cutscene 接回可編輯 handler。
- [x] ch05/ch06 pre-handler：新增 `HandlerDialog.Segments[]` 跨-scene adapter，依 FDTXT_006 #0 的 scene0→1→2→3 targets 展開 18 句；`ch05_pre` 完整 binding，`story_ch06` 已接回可編輯 handler。
- [x] ch06/ch07 pre-handler：FDTXT_007 index0/1（2+6句）與 map6/acting28/29 已接 binding，`story_ch07` 已接回 editable handler。
- [x] ch07/ch08 pre-handler：FDTXT_008 index0/1（跨 scene 15句+2句）與 map7/acting31/32 已接 binding，`story_ch08` 已接回 editable handler。
- [x] ch08/ch09 pre-handler：FDTXT_009 index0/1（2+5句）與 map8/acting35 已接 binding，`story_ch09` 已接回 editable handler。
- [x] ch09/ch10 pre-handler：FDTXT_010 index0 跨 scene0/1（6+6句）與 map9/60-slot 已接 binding，`story_ch10` 已接回 editable handler。
- [x] ch10/ch11 pre-handler：FDTXT_011 index0 跨 scene0/1/2（4+6+2句）、index1/2 scene2 延續，map10/acting38/39 已接 binding，`story_ch11` 已接回 editable handler。
- [x] ch11/ch12 pre-handler：FDTXT_012 index0 跨 scene0/1（2+9句）與 map11/acting40/41 已接 binding，`story_ch12` 已接回 editable handler。
- [x] ch12/ch13 pre-handler：FDTXT_013 index0（6句）與 map12/70-slot 已接 binding，`story_ch13` 已接回 editable handler。
- [x] ch13/ch14 pre-handler：FDTXT_014 index0（4句）與 map13/70-slot、pan 20,20 已接 binding，`story_ch14` 已接回 editable handler。
- [x] ch14/ch15 handler：Docker Capstone 已證實 pre `0x334f3..0x334f7` 的 `roster_has(12)`→FDTXT_015「有 12：0/1/2；無：3/4/5」，以及 raw `ch14_post` `0x239d1..0x239d3` 的「有：12；無：13」。主迴圈與前三戰既有測試證實玩家戰鬥 N 對應 raw `ch(N-1)_post`；因此 `postbattle_ch14_persist` 應使用 `ch13_post`，`postbattle_ch15_persist` 才使用 `ch14_post`（JOIN15→set_chapter15→town_ch16）。pre binding 含 map14/80-slot、pan、acting48；runtime 只讀 permanent party roster，缺此資料 fail-closed。——2026-08-19稽核確認：此主張已由緊接的下一項「ch14/ch15 postbattle campaign index correction」驗證並回歸完成，僅本行未同步。
- [x] **ch14/ch15 postbattle campaign index correction**：撤回「同號 postbattle node 對同號 raw post handler」的錯誤斷言；目前已驗證並回歸 `postbattle_ch14_persist→ch13_post→town_ch15`、`postbattle_ch15_persist→ch14_post→town_ch16`。其他仍採同號 binding 的章節必須逐一用直接指令複核，不能機械式整批平移。
- [x] **既有 postbattle 索引錯接稽核**：稽核工具現將 active binding 與已證實的 `battle N→raw ch(N-1)_post` 關係逐筆比較，不再把「欄位非空」當成 active 正確。原有13個同號錯接已清除；IDA 直接指令再閉合 raw ch25→玩家ch26、raw ch27→玩家ch28、raw ch05→玩家ch06、raw ch06→玩家ch07、raw ch07→玩家ch08、raw ch09→玩家ch10、raw ch12→玩家ch13與raw ch19→玩家ch20。目前稽核為17 active／7 blocked，沒有 `active_index_mismatch`、`unbound_mapping_complete` 或 `unbound_inline_beats`。——本輪(2026-08-19續輪,`doc25`§批次盤點,L1139)更新:`tools/audit_postbattle_binding_gates.py`現況已是24節點、**19 active／5 blocked**(blocked:`ch17/ch22/ch23/ch24/ch29`)，與本行「17 active／7 blocked」的文字有落差，已過期；**`ch16`已於2026-08-18(`doc26`§7.3/§7.4)轉為active**(`postbattle_ch16_persist`現有`handler_binding:"assets/cutscenes/bindings/ch15_post.json"`)，本行「17/7」的舊數字未同步。
- [x] **玩家第 8 戰 raw ch07 post 垂直切片（E1）**：撤回 `ch08.json` 把 groups 1／8／9／10 預先 materialize 的舊設定。`0x1088D` 只建立 party＋group0（10＋19＝29 slots），event27 回合2..7才逐組追加兩筆，合法戰後 frontiers為29..41的奇數。address-keyed binding 已接 slot28 raw JOIN5身分、layout、ACTING33／34、FDTXT_008 index3／4、精確全黑與 framebuffer clear，再走JOIN5／sync／chapter8進 `town_ch09`；負向測試拒絕其他 `0x11D40` call site／參數。event28 slots10..27 raw `+0x34 &= 0x80` 的正式回合接線及 DOSBox E2仍待完成。證據見 [`fd2_ch07_post_ida.txt`](../data/ida/fd2_ch07_post_ida.txt)。
- [x] **玩家第 10 戰 raw ch09 post 垂直切片（E1）**：IDA Pro 9.4 與 Docker Capstone 固定 `0x235F9..0x23790`。正式 binding 保留有／無凱麗造成的60／61兩種強推論 frontier，依位址執行 delta 0→63 共64次 DAC 淡出、只寫明列 offset 的 sparse record/view patch、delta 64→0 共65次 DAC 淡入、FDTXT_010 index4／5、ACTING37、JOIN11／6、sync與chapter10，最後進 `town_ch11`。執行期對非法值、缺 raw provenance 或 frontier 不足會在任何寫入前原子拒絕；尚缺未修改 DOSBox 一般玩家逐幀 E2。證據見 [`fd2_ch09_post_ida.txt`](../data/ida/fd2_ch09_post_ida.txt)。
- [x] **ch00 `0x3241f` 原生淡入閉合**：追查 map32 runtime roster 的 raw FDICON key producer，讓 title/story indexed compositor 不再依賴 `Fig==key` 假設。——本輪(2026-08-19續輪,`doc50`)推進:Ghidra headless反組譯`0x3241f`所在呼叫序列(`0x323b0..0x3251a`)證實這整段是純對白/演出交錯，不含任何FDICON查表，排除了`0x1f525`(PALFADE)本身內含key邏輯的可能，把搜尋範圍縮小到`0x32975`/`0x32999`一帶。——2026-08-24收尾(doc50):用`call_scan`窮舉`FUN_00010c50`(FDFIELD-scripted key producer)在全binary的呼叫者，全binary僅一處(`0x10bee`，在`SPAWN`即`0x10b4e`內)，排除`0x32975`/`0x32999`。反編譯`FUN_0001088d`(LOADCH的`0x205da`呼叫對象)證實它每次都無條件tail-call `SPAWN(0)`——這解釋了ch00 21-unit map32 roster(king/queen/Sol×2/Ares/16 guards)為何在LOADCH後立即成形而handler transcript看不到顯式spawn呼叫。完整producer鏈已閉合:`0x205da→0x1088d`(無條件`SPAWN(0)` tail-call)`→0x10b4e→0x10c50→0x11019`，寫入`unit+2`，餵給既有`slot×12+dir×3+cycle`公式對`FDICON.B24`指標表。此為RE問題結案，remake ch00渲染路徑是否已改接為獨立的工程接線工作。
- [x] **raw ch15 postbattle layout audit（玩家第 16 戰）**：Docker Capstone 與合法 IDA Pro 9.4 固定 `0x23a0a→0x233c6` 的 slots `0..15`、special raw slot65=`(28,30,pose2)`、camera raw `(22,25)`，X=`[28,27,28,29,30,25,26,27,26,29,30,31,25,26,30,31]`、Y=`[28,27,27,27,27,28,28,28,27,28,28,28,29,29,29,29]`、constant pose0；acting resource49 只有 slot65 pose0/5 beats。IDA 另證實 `sub_3453E(index)` 讀 `runtime[index*0x50+5]&1`，故 handler 的 `0x42..0x49` 確為 slots66..73。`sub_1088D` 直接指令與 map15 資料固定入口為16個 persistent slots加60個 group0 rows，即76 slots——**四條分支已在下方項目解出**(`doc26 §7`,2026-08-18,見下一行);唯一剩缺口(battle_ch16一般玩家原版runtime capture)如實維持unbound fail-closed。**注意**:2026-08-19稽核發現`sub_3453E`實為stale label,真實呼叫目標是`0x34894`(doc26 §7.1.1/doc40已訂正),不影響本項76-slot入口結論。
- [x] **native inactive-count condition primitive**：新增 `native_inactive_count_gt` editable condition，compiler 僅接受明確 slots、非負 threshold 並保留 raw byte5 bit0；runtime 對缺 slot／缺 raw provenance 直接 fail-closed，測試覆蓋 count 5/4 與缺 raw。這只提供 ch15 branch 所需的一個純條件 primitive，未替 `[0x53bef] >18` 或 record `+0x42 >=0x140`。
- [x] **ch15 raw round/word provenance**：Docker Capstone 確認 `[0x53bef]` writer=`0x1a5b9`、ch15 gate 嚴格 `>0x12`，以及 `[0x53a45]+0x42` raw u16 gate `>=0x140`；新增 `NativeRoundCounter`、`NativeRecordWord42` 與 `native_round_gt`／`native_record_word_gte` strict compiler/runtime regression，不再把 raw word 直接命名成 normalized MaxHP。
- [x] **raw ch15 runtime roster producer**：合法 IDA Pro 9.4 直接指令證實 `sub_320FC` 只重排完整 persistent records、不改總數；`sub_1088D` 先逐筆複製 persistent roster，再以 `sub_10B4E(0)` 逐列附加 raw group0，沒有 fig15 的略過、替換或提升分支。raw ch15 的擁有者是玩家第16戰，故應對照 map15：16個 persistent slots加60筆 group0，入口恰為76 slots；撤回較早以 map14 推導74／78的假說。
- [x] **ch15 +0x42/+0x46 constructor producer/export**：Docker Capstone 固定 constructor 的 HP／MP 公式與 `+0x40/+0x42`、`+0x44/+0x46` 寫入；新增 `native_record_word42/46` 投影並同步 33 張地圖。具備來源的列以原始值初始化 HP/MP，舊列沿用正規化數值；格式錯誤或未覆蓋 selector 維持缺值與失敗即關閉。
- [x] **ch15 compound predicate primitive**：新增受限 `native_any_of`，只接受已驗證的 raw round／inactive-count 子條件；任一子條件可證實為真才通過，全部缺 provenance 仍 fail-closed。尚未改寫 immutable `ch15_post.json` 或解除 campaign binding。
- [x] **ch15 +0x42 persistence bridge**：`syncPartyFromBattle` snapshot 與 `applyPersistentStats` 現保留 `NativeRecordWord42/HasNativeRecordWord42`，測試覆蓋 raw word `0x140`；不由 normalized HP 推導，units source 缺 constructor provenance 時仍 fail-closed。
- [x] **ch15 candidate editable CFG**：新增 `handlers/candidates/ch15_post_cfg.json`，保留 raw source addresses 與 nested OR/else branch。2026-08-02 IDA 重核修正 JOIN18 錯置：`0x23b1f` 跳到章節尾端，JOIN18 只屬於 `else word42>=0x140` arm。candidate binding 已改用直接 producer 證實的76-slot入口；production scenario 未接此建構，候選也不列入production handlers或campaign node。
- [x] 執行 raw ch15 四條 branch trace，補 JOIN18 當下的 typed persistent record、`battle_ch16→postbattle_ch16→town_ch17` 與 save regression；在一般玩家原版 runtime capture 前保持 unbound fail-closed。——已解:`doc26 §7`(2026-08-18)。四分支邏輯/JOIN18讀寫路徑/ch16→ch17鏈路皆已反組譯確認;save regression本身可靠,唯一剩缺口(battle_ch16原版runtime capture)如實維持unbound fail-closed，待未來活體驗證。注意:此內容實際位於`ch16_post.json`(off-by-one改名後),非`ch15_post.json`(後者是另一個已解完的簡單案例),容易搞混。
- [x] ch16/ch17 pre-handler：`0x335bb` 的 `roster_has(18)` 接 `test/jne 0x3344d`；有角色18直接進 shared tail，沒有才 `spawn(group 1)`。已轉為 editable `if roster_has`，map16/60-slot/FDTXT_017 binding 接入 `story_ch17`。compiler branch 現繼承前置 LOADCH slot frontier，但 merge 後不假設分支新增 slots。
- [x] ch17 battle initial-group correction：原版 ch16 pre 只在 char18 缺席時 append group1，group3 是 ch16 post 才 spawn；`ch17.json` 不再把 1/3 固定 initial。Scenario 加入可編輯 `initial_groups_if_party_absent`，只控制戰前 `OnField` visibility；它不宣稱已還原 native append-slot identity，post handler 仍 fail-closed。
- [x] ch17/ch18 pre-handler：FDTXT_018 index0/1/2（7+4+13句）與 map17/70-slot、acting54/55 已接 binding，`story_ch18` 已接回 editable handler。
- [x] ch18/ch19 pre-handler：`ch18_pre` 實際 index0（8句）與 map18/70-slot 已接 binding，`story_ch19` 已接回 editable handler；未把未呼叫的 FDTXT_019 其他 strings 硬播。
- [x] ch19/ch20 pre-handler：FDTXT_020 index0（17句）與 map19/70-slot 已接 binding，`story_ch20` 已接回 editable handler。
- [x] **玩家第20戰 raw ch19 post 垂直切片（E1）**：IDA Pro 9.4與Docker Capstone固定`0x23E74..0x240FA`；四張table精確寫slots0..15、52..60與view `(26,31)`。固定record0＋選15人、map19 group0共67筆，形成83-slot入口；round15執行group1→84、ACTING60–62、index14–16與JOIN28，round16依`0x24005 jg`全部略過；JOIN25、index13、chapter20為共同路徑。舊scenario預載70筆再加16人的86-slot拓撲已撤回，改用runtime append只建立group0。正式binding已接`postbattle_ch20_persist→town_ch21`，兩條分支、persistent JOIN與城鎮銜接回歸通過。稽核現為17 active／7 blocked；尚缺未修改一般玩家DOSBox E2。證據見[`fd2_ch19_post_ida.txt`](../data/ida/fd2_ch19_post_ida.txt)。
- [x] ch20/ch21 pre-handler：FDTXT_021 index0（17句）與 map20/80-slot 已接 binding，`story_ch21` 已接回 editable handler。
- [~] class-change data/UI bridge：`LoadClassChangeTable`、`NativeClassChangeTarget`、`LoadClassChangeGrowth` 已接；church 先在三列視窗選角色，再依 special>optional>default 自動解析唯一 target，最後以左右 Yes/No confirmation 決定 mutation。`0x31019` row、FDOTHER#14 entry16 panel、`0x1974c` 六幀 opening，以及 `0x19953/0x197e5` 動態名字＋FDOTHER#2 Yes/No normal/pulse＋四幀 choice open/close 均已成 fail-closed indexed compositor。official IDA 重核補正完整順序：候選清單先以 `0x2d31b` 五幀關閉＋source restore；確認結束再跑 choice close 4 幀、dialogue close 5 幀＋source restore，才執行 mutation／返回。每幀都由 Draw acknowledgement 推進。`0x19953` BIOS delta>=2 時 counter mod4 前進、選中 variant=counter/2。已重生 [`native-class-list-indexed.png`](../figures/native-class-list-indexed.png)／[`native-class-confirm-indexed.png`](../figures/native-class-confirm-indexed.png)，兩者現在包含原版教會 scene source；raw service0 status/command renderer、HIT/EV/DX 實機數值差分仍待。
- [~] class-change synthesis：`0x31602` 五組 `0x1e529` 先把新職成長加到 raw AP/DP/DX/MaxHP/MaxMP，隨後呼叫 `0x1b750`；該 routine 讀 raw `+0x37/+0x39/+0x3e`、item table 23-byte row 的 `+1/+3/+5/+7`，寫 derived AP/DP/HIT/EV `+0x48/+0x4a/+0x4c/+0x4e`。`RecomputeAfterClassChange` 已恢復並防止既有裝備重複計算；`+0x22/+0x23/+0x24` 是 constructor 清零後由其他 transient/effect writer 使用的旗標，class path 本身不寫入，不能臆測成 class modifiers。
- [~] headless class-change fixture：`FD2_CAMP_CLASS_FIXTURE=1` 現正確注入 native identity/portrait9 的悠妮（先前誤寫索爾已修正）＋item0x58/0x5a，供 xvfb 驗證「教會→轉職→角色→自動解析 special target0x34→Yes/No」；正常遊戲不改變。舊 `church-class-targets.png` 是 remake 自創三分支選單，已撤回並刪除。
- [~] 分支與敗北路線：campaign runner 已有 on_lose→retreat 非 game-over 路徑與測試；battle Node 新增可編輯 `protect` 目標（空值沿用索爾），main 不再硬編碼唯一保護角色；待逐關核對原版保護目標與 retreat 後整備語意。
- [~] 存檔/讀檔(自有格式,非破解原版 `FD2.SAV`)：節點／旗標／金幣／道具／persistent party 已保存；2026-07-20 新增同目錄暫存檔+rename 原子寫入與清理測試，避免 town/shop/preparation 存檔被截斷。仍待完整 GUI/Xvfb 讀檔回歸。

## M5 — 內容完整化(原版可破關)
> 驗收:從序章玩到結局,全 33 戰場 + 全劇情 + 商店,正常玩法可達(無 debug hook)。
- [ ] 匯出全 33 戰場為引擎資產 + 全單位/數值表接入(對齊 EXE 表 `03`)
- [ ] 全劇情/對話接入(35 章)
- [ ] 完整性盤點:對照原版,缺漏列冊(`83` 完整性 > 投報)
- [ ] 正常玩法可達性驗證(連通/可破關鏈,參考 skill 踩雷)

## M6 — 跨平台打包(回頭做網頁/手機)
> 驗收:Windows/macOS/Linux 桌面包 + 網頁 + Android APK。
- [ ] 桌面交叉編譯 + 打包(Windows `.exe` / macOS `.app` / Linux AppImage)
- [ ] WASM 上網頁(資產載入 + `index.html` 完整化)
- [ ] Android:`ebitenmobile bind` → `.aar` → Gradle APK(觸控已支援)
- [ ] 玩家向 README(圖文並茂,突顯貢獻)+ 工程文件分離

## 擴充(M4 之後,擺脫原版固定 33 路線)
- [x] **可擴展事件系統規劃** → `29`:trigger/when/do DSL + 文本事件控制碼 `{{}}`;條件/動作 Registry 可註冊;原版 30 關可表達+自創戰役
- [ ] 實作 EventSystem(ConditionRegistry/ActionRegistry)+ DialoguePlayer 解析 `{{}}`
- [ ] 自創戰場 + 自訂劇本(用 `19`+`29` 系統)
- [ ] 多分支劇情線 / 多結局
- [ ] 編碼器回寫中文(`encode_text.py`)做在地化/二創

## 第 5 輪 ✅(開場流程反組譯 — 使用者指定)
- [x] **建反組譯器** `tools/disasm_le.py`(capstone 解 DOS4GW LE,docker)+ 確認 entry/main/狀態機
- [x] **頂層狀態機反組譯**:真 main=0x25bf4(雙層迴圈),核心狀態變數 `[0x53c03]`=章節,兩張章節跳表(0x51d71 戰前劇情 / 0x51de9 戰後)→ `23`
- [x] **標題序列**:角色立繪 5 幀(FDOTHER #0x45-0x49,320×147)垂直捲動(非旋轉)+ FLAME DRAGON logo(#7 sub0)+ 主選單;**解碼器當 oracle 解圖視覺驗證** → `23`
- [~] **主選單機制**:輸入迴圈/scancode dispatch(↑0x48/↓0x50/Enter/Space)/游標 wrap、return `0=新遊戲`、`1=0x30550` 四槽 selector 已由 Docker Capstone 重跑；第三 return branch 直進 `0x10010`。2026-08-02 合法 IDA 重核已撤回「`0x4E031` 是戰鬥驅動器」：它只複製 BIOS 鍵盤緩衝 word；第三分支返回0後由 main `0x25DCE` 呼叫並循環重入真正的共享控制器 `0x117E7`。remake 也已刪除 selection2 誤讀 JSON slot0 的高風險行為，正式 native transaction 完成前留在 title。四槽 LOAD 已接 checksum-valid selector→typed party→town/preparation production owner；真正未接的是未修改一般玩家有效槽 E2、delete/overwrite 與 CONTINUE 的 pending-group／`Game` handoff，故仍不能稱完整 native LOAD/CONTINUE 相容 → `23`、`56`、`57`
- [x] **新遊戲→開場對話→自動進戰場**:[0x53c03] 章節驅動,cutscene 0x3231b(與前代主角對話)→ 戰場地圖=章節*3+2(自動串接)→ `23`
- [x] **call-graph 遞迴反組譯工具** `tools/callgraph_le.py`(可達集/callers/rpath/funcof/jtab)→ `24`
- [x] **cutscene→戰場控制流勘誤**：`0x10010` 真 caller 仍是 `0x1a251/0x26130`，但展開 `0x25ebb` 證實 `0x26130` 只屬第三主選單分支；新遊戲與四槽讀檔各自跑 pre-handler 後從 `0x25ebb` 返回，main `0x25dce` 才呼叫 `0x117e7`。舊「handler ret 後在同 driver 線性落入 `0x10010`」已撤回；callgraph 工具排除 `0x1b051/0x26f30` 偽命中的成果仍有效 → `23`、`24`
- [x] **[0x53ecc] 戰後/事件狀態機**：章節 handler 的 raw code 由戰役迴圈消費；`0x205be` 另有直接閉合的 0/1/2 roster 規則。不得再把 `0x205c9–0x20c64` 寫成單一事件解譯器，或把所有 code1/2 writer 先統稱同一玩法語意 → `24`§6
- [x] **挖完事件 handler 原語** → `25`：第三張章節跳表 `0x51b19`（30章／18個特殊 handler），FD2 事件是每章 C handler 而非 byte-code；`0x3453e` 查 raw bit，`0x205be` 是三值結果規則，`0x205da` 才是重設／章節載入入口。
- [x] **RE-BATTLE-RESULT-205B4-BOUNDARY**：Docker Capstone 與合法 IDA 9.4 交叉確認完整函式起點 `0x205b4`、共享 direct-call 入口 `0x205be`，以及 code2→camp0 active code0→record0 bit0 code1 覆寫順序；`0x205d5→0x2067e` 跳過相鄰 `0x205da`。新增 `NativeBattleResultCode205B4`、map0 真實 roster 錨點與失敗即關閉測試；撤回舊「`0x205be` 清碼並呼 `0x1088d`」混線斷言。
- [x] **逐關挖 18 特殊 handler** → `26` + `tools/event_handler_dump.py` + `docs/data/battle_events.json`(30章條件→動作,供 remake 去 hardcoding)
- [x] **補完 battle-event raw predicates（2026-07-27 勘誤）**：`0x3453e(idx)` 只閉合為 `[0x53a45]+idx*0x50+5 & 1`；remake 的 `unit_inactive` 是 caller-specific projection，不是全域死亡／存活欄位。`0x33499`=roster_has（查 `[0x53bf7]` 我方名冊）。`battle_events.json` skeleton 未記錄 action_fns，不代表 postbattle/cutscene handler 無動作；舊 bit0 高階命名已撤回。
- [~] **handler raw-byte5 runtime bridge**：`0x3453e` raw adapter、constructor、已知 damage/death writer、revive writer 與 `deactivate_unit` 已有 raw propagation/regression；完整 raw roster 時 `cmd/fd2` 的 `any_unit_inactive` 已 strict 讀 raw bit0，只有舊／混合 JSON 才使用 `OnField/Alive` 相容 projection。需補 zero-HP 初始 record／所有 LOADCH 分支並讓 strict binding 缺 raw 時 fail-closed，才可把 ch01/ch02 handler 全面升為 E0。
- [~] **persistent raw-byte5 bridge**：`syncPartyFromBattle`／`applyPersistentStats` 已保存 `NativeRecordByte5/6`，並在 raw bit0 有 provenance 時依 native branch 決定 HP refill；缺 raw 仍保留 E1 projection。需完成 LOADCH raw record materialization 才能移除 fallback。
- [x] **反思日誌補第 7-10 輪** → `99`
- [x] **挖完 `[0x53bf7]` 表語意**:不是 tile,是**我方隊伍名冊**(32槽×0x50B);`0x33499(id)=roster_has(id)` 查 byte[+8]==角色ID(章16 用)→ `25`/`26` 回填;兩單位陣列釐清([0x53a45]96槽全場 / [0x53bf7]32槽名冊)
- [x] **回合計數釐清**:`[0x53bef]`=回合/進度 counter（開始1/inc/cmp N），`[0x53ec8]`=累積計數（非回合）；**修正前輪把 [0x53ec8] 當回合**。byte+5 bit0 的歷史高階命名已撤回，僅保留 raw mask。
- [x] **戰鬥規則來源盤點 + 動態驗證清單** → `27`:青衫公式=remake 實作依據+交叉驗證;列出 10 項需 DOSBox 實機驗證(核心 #1-4=戰鬥狀態機旗標/計數語意);新增「回合無上限」需求
- [x] **動態驗證清單更新** → `27`§3：byte+5 bit0／bit7 的 caller-specific raw tests 已列出；回合/換邊完成條件仍未由完整 state-machine 關閉。7-8 用青衫攻略；9-10 對 normalized projection 可簡化，但 raw persistence/handler 仍需 `0x50B` slot 與 `+8` provenance；3(`[0x53ec8]`)低優先。舊「bit0=1 是存活」使用者記憶已撤回。
- [x] **撤回 `[0x53ad5]`=opened-treasure／unit-pointer 斷言**：`0x10322` 初始化時複製 0x20 bytes 到 `[0x53ad5]` 指向的 buffer，`0x13d00` 以 event index 寫其 byte；ch25 post `0x24f30/0x24fb1` 讀 entry #12 來選 FDTXT index（base+5/base+8）。它是 battle-local state table，但高階 event 意義未命名；`OpenedTreasure` 保留 remake-owned state，不再聲稱原版位址。
- [x] **state table entry12 writer closure**：`0x356bc..0x35821` 先 gate table[12]，成功臂以 actor class 查 item `0xd0`、`0x1b8e7` 消耗它、完成 presentation 後才設 table[12]=1，接 `spawn(1)→JOIN(31)→FDTXT #4`。因此 ch25 post 的 table[12] base+5/+8 有直接來源；尚未完成兩臂 runtime 資產，不能以 treasure／party condition 取代。
- [x] **entry12 dispatch-scope audit（FDFIELD 勘誤）**：IDA 的八個 generic indirect xrefs 本身無法定位章節，但 map25 FDFIELD field slot2 已直接證實 selector1、座標 `(1,46)` → event61/`0x356B7`。舊「沒有 map25-local caller」斷言撤回；item D0、entry12、spawn1、JOIN31 與 text2/3/4 已資料化。59 幀呈現與 selector 時機的後續接線狀態以 `REMAKE-FIELD-EVENT61-SELECTOR1` 項為準。
- [x] **RE-FIELD-EVENT59/60**：map25 y36/y22 selector0 邊界及 trigger record byte6 非零 gate 已閉合；分別把 ranges39..44、23..24+53..56 低四位模式設0，規則已嵌入 editable map asset。
- [x] **REMAKE-FIELD-EVENT59/60-SELECTOR0**：合法 IDA 9.4 與 Docker Capstone 固定 `0x13488` 只有 path byte1 進 `0x1300D`，七拍提交 `x-1` 後以新座標呼叫 selector0；重製已在每個向左格步驟相同提交點執行 event59/60，向右反例與第1..6拍不觸發測試通過。
- [~] **REMAKE-FIELD-EVENT61-SELECTOR1**：event61 handler 已解碼並資料化；selector1 位於 AI `0x13E77` 收尾及玩家 `0x18890→0x18D8C` 三個 action handler 成功返回臂，不可簡化成任意 walk completion。FDTXT_026 63 句與 `ch26.json` 全量對齊；presentation 保存 archive/resource/frame/base/stride/transparent/delay。共同成功閘門現已接入待命、攻擊、一般法術、原始指令、三種已閉合物品交易與 AI；攻擊及攻擊型法術延至全螢幕演出結束，取消、目標不合法與 executor 錯誤不觸發。正式路徑完成 FDTXT2／3／4、59 幀兩 tick cadence、native compact remove D0、entry12、append group1 與 persistent JOIN31，缺 D0 不突變。ch25 pre-handler `PAN(9,39)→FOCUS_UNIT(0)`、ch26 slot0 `(15,46)` 及原版 cursor state machine 又推得 event 格 runtime view `(camera 0,39; cursor 1,46; visible 1,7)`，`battle_ch26` 已資料化初始 view/HUD，真實資產 regression 不再手工注入。剩餘門檻是同 roster/event/tick 的未修改 DOSBox 一般玩家比較；production 已達 E1，未達 E2。
- [x] **NATIVE-MAP-RENDERER-INPUTS-ALL-MAPS**：稽核證實舊資產只有 map0 帶 composition byte+3 與 FDSHAP terrain control，map1–32 全缺，這會讓後期所有 indexed map frame 在資料入口失敗。新增 `sync_native_map_renderer_inputs.py`，先驗證 FDFIELD.DAT／FDSHAP.DAT 大小、MD5、SHA-256，再只同步 `native_tile_blit_modes/native_terrain_control`、保留既有寶物／事件／手改欄位；33 圖 `--check` 與 Go loader regression 通過。這關閉 E0 input completeness，不代表 ch02+ view/HUD runtime 或畫面 E2。
- [x] **撤回 ch27 `0x24618`=acting 的暗示**：official IDA 定義 `sub_24618=0x24618..0x24754`（含 post-handler `0x33af1/0x33c9d` callers）；Docker Capstone 證實它是 13×8 offscreen terrain + 固定 9-pass strip composite + 0..62 palette 收束的地圖轉場。四個參數是 tile/strip geometry/progression，不能降成 actor `act`、pan 或任意 fade；strict indexed runtime adapter 已於 2026-07-28 接通。
- [x] **全 30 關卡目標表(攻略 ground truth)** → `28`:每關勝利/失敗/加入條件;**失敗條件=護衛目標**證實 unit_state 機制;加入=roster_has;ch30 魔神連鎖=回合事件;remake 關卡規格直接可用
- [x] **撤回章17 alive 誤讀**：依 caller-specific raw bit0 branch 重新解讀；舊「指定單位存活→設碼」已撤回 → `25`/`26` 回填
- [~] 單位 0x50B 結構：`+5` raw bit0/bit7 predicates、`+8`角色ID、`+0/+1/+2/+6/+0x31` 已解；完整逐欄佈局 [阻]（remake 用自有 struct，不需）
- [x] (補)更新 doc 12:修正「main=0x10000」、補章節→BGM 表 0x51e63 精確曲號——已解:真main=`0x25bf4`;30-entry表逐位元組複核無誤;開場BGM=FDMUS_018(取代猜測FDMUS_004)

## 第 6 輪（歷史單一戰鬥演出 fixture 對照；不代表通用戰鬥 renderer 1:1）
> 目標:remake 戰鬥攻擊演出(orig_05)像素級對齊原版。方法=**密集網格疊圖 oracle**(見記憶 pixel-align)+ 反組譯確認機制,**無 dosbox debugger**(0.74 vanilla 不能 dump)。
- [x] **完整 RE 戰鬥演出繪圖機制** → `35`:演出主函式 0x28a6c、blit 0x4e63d(無縮放/無翻轉,尺寸朝向燒進素材)、固定錨點(164,157)、phase [0x540ff]、BG 多層(0x52381=BG.DAT)、戰場→BG 表 0x52363
- [x] **figure 幀/姿態**:我方亞雷斯=攻擊動作1 `FIGANI_013_f01`(組×3+1,人眼確認);幀序播放;守方不翻轉(FIGANI_288 原圖面右)
- [x] **白斬擊弧 = FIGANI 攻擊幀自帶**(燒 sprite),移除程式 vector 補弧
- [x] **[設計鐵則] 我方=背影+腳下台座 / 敵方=正面**(使用者確認,與攻守無關純陣營)→ `35`§3.2.5
- [x] **figure 位置對齊**(密集網格+程式量土台中心):我方土台中心 x≈238、敵方腳 y≈135(@320)
- [x] **狀態欄對齊**:名字放大(16px視覺)、血條加長(緊接標籤到數字)、bevel 立體框、HP/MP淺藍標籤、暗槽色暗版、上下欄位置/間隔(我方離頂、敵方離150線空隙)
- [x] **z-order RE**:演出順序狀態欄(0x28ce7/0x28d62)先、figure(0x28e76/9a/ee0)後 → figure 蓋住狀態欄;remake 改 BG→狀態欄→figure → `35`§4.-1
- [x] **狀態欄機制 RE**(agent):真繪製器 0x18c6d(非 0x29164);框=素材sprite、HP=逐欄cell(len=curHP×101/maxHP)、名=16×16點陣字、數值=6px digit cell → `35`§4
- [x] **清除錯誤斷言**:土台正名 FIGANI自帶→**TAI.DAT 台座**(0x29164 載 0x28c46);figure-X=word[unit+0x40] 誤讀;對話框開框碼 0x16F40
- [x] **① TAI.DAT 台座解碼 + remake 貼上** ✅(v23):TAI_004=154×42 綠草橢圓台座(decode_sprite 解 body[4:],index0透明17%);remake 載 tai_004.png 貼我方腳下(z:狀態欄<台座<figure);對齊 orig 取代偏灰 dither。確切 entry↔職業/地形對映待後續
- [x] **② 複查 `+0x40`／figure displacement**：**`+0x40=當前HP`**（`0x18c98` 血條 `word[+0x40]×101/word[+0x42]`=HP%）與 `+0x44/+0x46=current/max MP` 已閉合，舊「戰場格 X」已清。`0x29f72` 是 derived AP/DP/HIT/EV、HP、item、terrain/RNG 的 hit/crit/damage resolver，**不是** lunge；`+0x48/+0x4a` 亦是 derived AP/DP。`0x2935b` 直接以 `frameIndex*4+8` descriptor pointer 讀 header `u16 X/Y` 再交 `0x4e63d`，故逐幀 figure displacement 已閉合為 frame metadata；caller schedule／攻守配對仍另列待辦。
  - [x] runtime export guard：`cmd/fd2` regression 對 `meta.json` 全部 22 個 FIGANI resource、每一 frame 的 `(X,Y)` 與 player archive `FIGANI.DAT` header 比對；不再只憑 exporter 意圖宣稱 runtime 位置資料正確。
- [x] **③ 狀態欄框/HP 用真素材** ✅(v25-26):破解 FDOTHER#5 LMI1 sub-sprite codec(反組譯 0x4e916:c≤0xC0 literal/c>0xC0 run,新 codec,`tools/decode_lmi.py`);框=#22(149×42 含bevel+標籤+槽)貼 panel.png、血條 cell=#27-30;修 HP靠左(槽 x21-123)/提亮/數字對位。doc35 §4.2.5。盜賊 y 軸對齊(276→296,頭頂偏上一排)
- [x] **④ BG 草地延伸到 figure 腳下** ✅(2026-07-05 使用者確認 `docs/figures/battle_restore_grid.png` 網格對照:左原版/右 remake 兩邊草地都延伸到 figure 腳下、台座疊綠草非黑底,一致)

## 第 7 輪（歷史戰鬥演出資料化 round；「像素級」只限當時 fixture）
> 從「手調對齊」進化到「原版資料驅動」;README 對外展示;全部 push(commit 至 a42ee4a+)。
- [x] **[重大] FIGANI 幀標頭 +0/+2 = 每幀絕對螢幕座標 (dx,dy)@320**(修 doc06 錯誤標註「boundW/boundH」):
      f01=(141,3)/盜賊=(16,41) 與模板匹配 orig 落點完全一致 → 走位/伸擊/突刺全在資料,引擎照貼即可
- [x] **戰鬥演出資料驅動重寫**:meta.json(22 個 FIGANI 全幀 dx,dy)+ loadFigMeta;刪 lunge/錨點手調;
      FIGANI_013 15幀=f01-f10旋轉蓄力/f11黃劈擊/f12-14突刺;盜賊 4 幀待機呼吸
- [x] **打擊感**:命中=全紅剪影交替閃(redSilhouette,orig=VGA色盤閃紅)+ HP 命中窗快抽;5 階段對照 orig 全對上
- [x] **通用化**:newAtkAnim 建構器(所有角色同管線:攻=組×3+1/守=組×3;演出長度隨幀數;命中幀=倒數第4幀通用推定)
- [x] **播放速度接口**:FD2_BATTLE_FPT 環境變數(tick/幀,預設3)+ atkAnim.fpt
- [x] **像素級對齊(模板匹配法)**:三 figure+台座+狀態欄框+三處數字 全部 err=0 且 dx=dy=0;
      狀態欄=原生 149×42 blit(敵(0,154)/我(171,4))、數字=LMI1 #31-40 素材(#42-51綠/#119-128黃=滿血變色)、
      LMI1 混雙 codec(框 0x4e916/小cell 4-mode)、VGA 6-bit palette ×4(decode_lmi 修正)
- [x] **README 對外展示**:battle_restore.gif(orig|remake 同步+網格)、battle_storyboard.png(5階段分鏡)、
      battle_restore_grid.png(網格驗證);新增「戰鬥演出:像素級 1:1 還原」節
- [x] **FD2_SHOT_SERIES 逐幀截圖鉤子**(GIF/分鏡素材管線)
- [x] 名字=TTF 28px+深藍描邊(~85%,既定決策:只有狀態欄數字用點陣素材,其他文字 TTF)

## 第 8 輪（歷史玩法盤點 round；魔法／SFX／campaign 目前仍是 partial）
> 使用者指示:檢視腳本系統一路到移動/觸發戰鬥/魔法,盤點缺口逐項補。
- [x] 盤點完成(見下缺口清單)
- [x] **腳本系統 campaign(M4 骨架)** ✅(74bf386):internal/campaign(節點圖 Runner:story/battle/
      choice/event/ending + 旗標 + 敗北路線 + choice 條件選項;單測3條);引擎接線(FD2_CAMPAIGN=1、
      enterNode/campInput/drawCampaignUI、勝敗 Enter 轉場、resetBattle 重試);campaign.json 第一章示範
      (敗北→撤退設旗標→再戰)。待續:商店節點、存檔、原版 33 關自動生成 campaign
- [x] **移動動畫** ✅(74bf386):battle.Path(BFS 路徑)+ walkAnim 沿路徑逐格走(方向幀+OffX/Y 內插,
      ~4-5 tick/格,走完進攻擊/待命,期間鎖輸入);AI 移動沿用瞬移(待接同管線)
- [x] internal/battle 測試失敗已修 ✅(e09c68c):部署格斷言=舊設計殘留,對齊現行(部署格屬 spawn_party)
- [~] **魔法系統** (第7-8輪完成資料與部分 runtime,commit 3c618c4/74366fa:暫定四向 action UI+法術+MP+青衫公式;code: ringInput/castSp/spells.json)——`0x18d8c` 已證實方向 result order，但 `0x1cff0` command table、完整 native 演出仍待；——本輪(2026-08-19續輪,`doc13`)未新增證據，維持既有D判定：「`0x1cff0` command table」部分已由其他項與doc56閉合，但「完整native演出」子句仍未解。
      不存在獨立 spell-id→FIGANI 特效索引（doc37）；僅已證實施法者自身 FIGANI 組動畫，其他 spell runtime 保持 partial
- [x] **音樂** ✅(e09c68c):audio.go(ebiten/audio+vorbis;忠實 play_bgm 0x26777:同曲不重播/換曲釋放/
      無限迴圈);campaign 節點 bgm 驅動;FD2_MUTE 靜默。待:非 campaign 模式場景→曲號自動對映(doc12 表)
- [x] **音效 SFX** ✅(第8-11輪完成,cmd/fd2/audio.go;commit e09c68c 音樂+SFX 收線)。資料位置 RE(doc36):`FDOTHER.DAT` 資源 #31(巢狀 `LLLLLL` 容器,14 個 8-bit
      unsigned mono raw PCM 子樣本)+ 戰鬥音效動態 index(同檔案,依攻擊資料決定 index);播放走
      `AIL_init/set_sample_address/set_sample_loop_count/start_sample`(0x26896/0x26945)。
      待:14 子樣本→UI事件對照、戰鬥動態 index 表還原、remake 端接入(SDL_mixer/ebiten audio)
- [~] **native action overlay／現行四向 approximation**：官方 IDA 9.4 `0x18d8c` 已釘死 `↑0=攻擊/←1=法術/→2=物品/↓3=待機`，而 `0x1741c` 已證實為 FDOTHER#2 四張 indexed asset 的十字 slide；battle wrapper 的 directionState 固定 `[0,1,2,3]`，因此 raw cell index=`3*availabilityWord+2*directionState` 的 enabled cells 是 `[0,2,4,6]`、disabled 是 `[3,5,7,9]`。先前誤把 `0x1728c` 巢狀 menu 的可切換 `0x12…` states 當作 battle gate 已撤回。visible cursor `column/row` framebuffer byte-address=`+0x8088+0x18*column+(0x18*0x1c8)*row` 亦已閉合；`fdother.BattleActionOverlayState`／`ActionOverlayOrigin`／`BlitActionOverlayFrame` 已把 ABI、open／close 各四幀 offset 與 index-0 transparency 接成 unit-tested primitive。runtime 已改成 caller-owned opening0..3／closing0..3 lifecycle，動畫期間鎖輸入，第四個 close present 後才提交 child menu 或 action；native loop 沒有 delay call，所以只保存順序與 present count，不冒稱原版時長。Docker/Xvfb 用 read-only 玩家 FDOTHER 實跑的 [8-frame artifact](../figures/action-overlay-open-close-remake.png) 逐幀互異。adapter 已採用 `0x1b83d` equipped/ID `<0x80` 前提和 raw command-mask 非零 gate（legacy scripts 才回退 Spells），但仍非 native gate 全等價。command22 是 `unit+0x27` 的已知 writer；仍待狀態名稱／其他 writer、72×72 indexed backup/restore、DOSBox visual diff、attack target geometry、`0x1b8a6` 後 item selector/effect、圖示 provenance、攻防預覽。
- [x] **RE-ATTACK-EQUIPPED-PREDICATE-1B83D**：官方 IDA 9.4 閉合 `0x1b83d(unit,a2)`：八格依序檢查 `flag&0x40`，`a2==0` 僅接受 item `<0x80`，`a2!=0` 僅接受 item `>=0x80`，回第一個 raw slot／`-1`。新增 `battle.NativeEquippedInventorySlot` regression，action overlay 在 constructor raw flags 存在時採用此 predicate；target geometry、damage/effect、renderer 仍 partial。
- [x] **RE-ITEM-AVAILABILITY-GATE-1B8A6**：`0x1b8a6` 的 raw occupied count 已有 record adapter；新增 Unit-facing `NativeInventoryAvailableCount`，overlay 在八格 constructor flags 存在時以 bit7-clear count 決定 item disabled，`len(Inventory)` 僅是 legacy fallback。

- [x] **native command target flag/runtime-grid bridge**：`0x14818→0x4e040` 的 raw target resolver 已有純資料層與 runtime producer（camp predicates、cross、cardinal flood-fill）。修正舊斷言：bit40 block；bit80 是扣 terrain cost 後強制 remaining budget=0 的可達終點，不是 zero-cost chain。FDFIELD composition event word low byte（entry+2）只是不可變來源；每次 command caller 先取 low5 基底、使用 byte+3 grid，結束即依`0x4df4c`重建（2026-08-20訂正：原記錄的`0x4dbfc`是位址標籤錯誤，真正位址不是合法entry point，見下方`0x122dc mode6`項與doc58續三十/三十一）。缺 exact event bytes/grid 仍 fail-closed。
- [x] **native command MP transaction**：官方 IDA `0x21227→0x1CA89` 已證實 generic command 在 candidate array 建立後、逐 target effect 前以 record `byte+5` 從 actor runtime `+0x44` 扣 MP，前段 selector 已 gate `currentMP >= cost`。`SpendNativeCommandMP` 以 raw 0..255 cost 實作該成功交易並在 invalid/MP不足時不變更；刻意不接受 normalized `Spell`、不搶接 legacy cast/UI。
- [x] **generic native command two-stage data contract**：`NativeCommandEffectTargets` 固定 `0x1cff0` generic path：actor/`record+3` candidate list → confirmed candidate → confirmed cell/`record+4` final-effect list；non-candidate confirmation 拒絕。它不涵蓋 `0x17/0x1e` special branches、MP/effect/renderer，且尚未接 UI。
- [x] **native command record loader**：`NativeCommandRecord` 明確表示 verified IDs 0..35 的 raw `+3/+4/+5/+6` 為 selection/effect mode、MP cost、target code；從現有 physical `spells.json` 讀取時逐 row 重解 `raw` 七 bytes，欄位不符、缺洞或非 36 rows 均拒絕，避免 normalized Spell 名稱／效果編輯污染 native ABI。
- [x] **SDD native command family matrix**：`56` 現以 IDs 0..35 的 dataflow、strict engine slice、UI/renderer gate 三欄固定已證實 family 與 fail-closed 邊界；不得以 label、raw record 或 generic dispatch 把未知 ID 借接 legacy `CastArea`。ID24 已更正為玩家 `2A6BD→276EC→1C81F` 的 derived-stat special route；AI table 的 `funcs_1541f[24]=22153` 是另一分派，不能誤接為 ID16 heal。
- [x] **commands 0..8 direct compositor + numeric route**：`0x1cff0` 對 IDs0..8 直入 `0x2a6bd`，確實不是 handler table 的 `0x21227/0x213b7` wrappers；但 direct `0x2a6bd` 的 `sub_2b659` MP event 和 final-target loop `1C75E(targetSlot, commandID)` 已重新逐行確認。故 ID0 executor／target UI 恢復為 bounded state slice，renderer/post-resolution 仍未宣稱完成。
  - [x] generic renderer schedule：`funcs_2ac25[0]=0x26152`；`0x2a6bd` 以 handler mode0 取 step count，再逐 step 走 mode2→`0x11eb0` 320×200 present→`0x17aa9(1)` tick→mode1，收尾另走 mode4/double-buffer path。`0x2b9a1` 依 descriptor frame byte+6 delay 推進 `0x540fc/0x540fd` subframe counters。這是 schedule ABI，不為 handler 視覺命名。
  - [x] generic BG selector boundary：`0x2a6bd→0x2b5e1(finalCount, finalTargetArray)` 倒序 target scan，經 `0x12e38`／`0x1f183`，只有 gate 不通或累積 selector=0 才以 control byte+2 取代 selector，再載 `BG.DAT`。`NativeCommandBackgroundSelector` unit regression 固定這條 raw ABI；command ID 只先選 generic/special presentation branch，不直接選 BG resource。selector semantic 保持 raw。
  - [x] BG archive input：`BG.DAT` #0/#1/#2 為 320×100 的 `0x4e63d` four-mode single-frame payload，新增 `fdother.DecodeArchiveSingleFrame` 與 player-archive decode regression；它只提供 indexed frame，layer selection／schedule 仍由 native caller evidence 決定。
- [x] **shared native damage route IDs0..12**：IDs0..8 經 `2A6BD→2B659/1C75E`，ID9 direct `1CA89→1C75E`；IDs10..12 的 `0x21548` 專用 compositor 尾端也直接 `1CA89→per-target 1C75E`。同樣扣 MP、逐 target numeric writer、success-only raw completion writer；engine bounded support 0..12，UI 仍僅 ID0。不得從 numeric 共用推論 visual equivalence。
- [~] **native command IDs13..16 healing route**：IDA `0x21AD9/0x21B99/0x2211C/0x22153→0x21B18` 已閉合 generic final target array、`0x1CA89(actor,id)` MP debit、`0x1C8ED→0x1C916` per-target HP restore 及 `+0x42` cap；其 amount 公式同 `9/10 + rand%100/1000`。`ExecuteNativeCommandHeal` 已接 strict non-UI engine slice（own record target/MP/restore/cap/raw completion writer，family boundary fail-closed）。專用 indexed animation、UI、SFX、message 未接，禁止誤用 IDs0..9 damage executor。——本輪(2026-08-19續輪,`doc13`)未觸碰，狀態不變，維持D。
- [~] **native command ID24 player special route**：玩家 confirm 的 `0x1CFF0` 對 `0x18` 直入 `0x2A6BD→0x276EC`；`0x276EC→0x2B659` 以 `0x1CA89(actor,0x18)` 扣 record24 MP，並以 `trunc(actor derived +0x48 × 15/10) - target derived +0x4a` 呼叫 `0x1C81F`。原版為多段演出暫時復原 HP 後等份遞減，`ExecuteNativeCommand24` 已接相同 final delta 的 strict non-UI slice。`funcs_1541F[24]` 雖為 `0x22153`，但只在 AI／自動 `0x15311` dispatcher 使用，且傳 ID16 給 heal tail，不能拿來推導玩家 ID24。multi-hit／presentation/SFX/UI 未接。**⚠位址勘誤(2026-08-19,`doc13`§6/`doc27`§6.3獨立交叉印證)**:`0x2A6BD`與`0x276EC`在目前Ghidra project裡都不是有效指令邊界(分別落在無關函式`FUN_0002a694`/`FUN_000275e6`中段)；真正的dispatcher是`0x2ff01`(`0x1cff0`對id<9或==0x18或>0x1b時的直接呼叫目標)，ID24分支的真正宿主函式是`0x2CF30`(mult=15，公式與數值結論不變，只有位址標籤需要修正)。**遊戲內名稱本輪新解出:「破龍擊」**(`command_labels.json`)。倍率15(damage multiplier，非EXP係數)。
- [~] **native commands28/29/31 derived-strike siblings**：同一 `0x276EC` 對玩家 ID28／29／31 分別選 20／12／18 倍率，並經 `0x2B659→0x1CA89(actor,id)` 與同一 final HP delta path；其 ordinary record geometry 可走 `NativeCommandEffectTargets`，`ExecuteNativeCommandDerivedStrike` 已接 strict state-only slice。ID30 的 special route 亦已收斂：`0x1CFF0` 先確認 record+3 candidate，`0x149F8` 從 saved pre-confirm cursor 朝 confirmed cursor 走 `record+3-0x10`（record30=4）格；X-first，僅 X 相同走 Y，selector=1 只收 enemy，然後 `0x2A6BD→0x276EC` default倍率18。`ExecuteNativeCommand30` 已接顯式 cursor state slice；不將其隱藏接入 current UI，cursor lifecycle／multi-hit／SFX／indexed renderer 仍待。32..35 走 `0x27FC9`。**⚠位址勘誤(2026-08-19,`doc13`§6/`doc27`§6.3)**:`0x276EC`不是有效指令邊界，ID28/29/31的真正宿主函式是`0x2CF30`(`0x2ff01`內`commandId==0x18||commandId>0x1b`分支的跳轉目標，倍率20/12/18數值不變)。**遊戲內名稱本輪新解出**:28=淒煌斬、29=熾炎刀、30=音速刃(special cursor route)、31=(FDTXT字串472為空字串，非解碼失敗，資源本身該slot沒有文字)。`0x2A6BD`同樣勘誤，ID30 default分支的真正目標同為`0x2CF30`。
- [x] **RE-COMPOUND-PLAN-27FC9**：Docker Capstone 重新固定唯一 caller `0x2A7CE`（`0x2A6BD` selector `>=0x20`），並把 ID32/33/34/35 的 raw helper 順序、ID33 direct clear offsets `+0x25/+0x26/+0x27`、固定 amount `0x320` 資料化為 `battle.NativeCompoundCommandPlan`；此為 editable evidence-only plan，`Callee==0` 明確代表 inline byte clear，不執行 transaction/MP/target/UI。
- [x] **native commands 17..19 transient modifiers**：ID17/18/19 handlers 已直接定位 `+0x22/+0x23/+0x24` nonzero gate 與 writer：17 對 derived `+0x48`、18 對 `+0x4a` 做 `__CHP(value*0.15+1)` **toward-zero** increase 並設 2..5 duration，19 對 `+0x4c/+0x4e` 各加 15 並設 duration。`0x377A4` 暫存 control word、設 RC=11b、`frndint` 後 restore，故撤回 FPU-rounded／未知 round-mode 說法。ID17/18 的 wrappers 都以 `0x1CA89(actor,0x12)` debit，且 records17/18 的 raw 7 bytes 相同；因此禁止泛化成「每 handler 必傳自身 ID」。這撤回 doc35 將 `+0x48..+0x4e` 稱作 screen coordinates 的衝突斷言；status labels、duration decrement、UI、engine integration 尚未閉合。——已解:`doc13`(2026-08-19)。三效果=魔刃術/魔鎧術/風行術(FDTXT_000印證);duration歸零呼叫`0x1B750`重算derived stat(非對稱減法);UI=到期/中毒扣血文字popup(非持續圖示);engine integration兩條路徑並存(legacy已上線可玩簡化版、native raw ABI三primitive已RE完整但未串成可執行command)。
- [x] **RE-COMMAND17-19-RAW-DISPATCH**：新增 `battle.ApplyNativeCommandModifier`，嚴格映射 ID17→`0x22721`、ID18→`0x22866`、ID19→`0x22997`，回傳 branch-specific raw result/RNG/accumulator；不接 MP、target、presentation 或 stat 名稱，unsupported ID fail-closed。
- [~] **native commands 20..21 flag-clear/restore route**：`0x22A85/0x22BC6→0x22AA8→0x22AF6` 分別對 `+0x25/+0x26` 做 nonzero gate；成功時以 command record 10 呼 `0x1C916` HP writer 後清 flag，零 flag 只顯示失敗。MP debit 仍以 command20/21 record。`ExecuteNativeCommandClearRestore` 已接 strict non-UI core（record10 amount、raw clear、cap-aware restore、empty gate仍 successful completion）。兩個 status 名稱與 UI 未閉合；ID22 的 `+0x27` application route 不可混入。——本輪(2026-08-19續輪,`doc13`)推進:**遊戲內名稱**已由`command_labels.json`解出——20=解毒術、21=社麻術(疑「解痲術」字模誤判)；逐指令反組譯確認`0x22A85`/`0x22BC6`是共用同一份機器碼的wrapper尾跳(只差flag offset與command ID兩個立即數)；EXP累加`[0x53EC8]+=classAdjustedLevel×4`(此為doc27§5.1清單外的新發現，doc02攻略文字的`Σ(40×9/受法者總HP)`HP加權項在程式碼裡找不到，只有簡單常數倍率)。UI/engine integration仍未接。
- [~] **native command 22 application route**：`0x22BE1→0x22CDA→0x22D1B` 在 `+0x27==0`、class `+0x20∉{0x19,0x1a}` 且 `rand()%100<50` 時，固定以 `0x1C81F(target,10)` 扣 10 HP，寫 `rand()%4+2` 至 `+0x27`；其他路徑僅失敗顯示。它已接入 `ExecuteNativeCommandApplication` 的 strict raw core；status name/tick、UI、expiry recompute integration 未閉合。——本輪(2026-08-19續輪,`doc13`)推進:**遊戲內名稱**已解出——22=封咒術(`+0x27`綁定確認，無對應清除指令)；逐指令反組譯確認`0x22BE1`/`0x22CBF`/`0x22E41`(22/26/27)共用同一份機器碼(只差flag offset與command ID)，class exclusion(`+0x20∈{0x19,0x1a}`跳失敗)確認泛化到三個command共用，非ID22專屬；EXP累加`[0x53EC8]+=classAdjustedLevel×8`(doc02攻略未列封咒術這一類別，程式碼是簡單×8常數而非含HP項公式)。
- [~] **transient command duration lifecycle**：official IDA/Capstone 固定 `0x1A866` gate 為 `record+6 == selector` 且 `(record+5 & 1)==0`，direct callers 已觀察 `0x1a4d1→push1`、`0x1a55e→push0`、`0x1a797→push2`；另有 `0x1a30b` 內部 `record+6==2` sweep，不能混成同一 phase。通過 raw gate 後，六個 bytes `+0x22..+0x27` 才逐一 decrement，歸零才發 expiry feedback 並 `0x1B750` 重算 derived stats。remake 現以 `NativeRecordByte5/6` 保存 provenance，`TickNativeTransientsRaw` fail-closed；舊 `TickNativeTransients(camp)` 不再猜測映射。selector→campaign phase、expiry equipment recompute、UI/status icon 或 native command executor 仍未接，故不可稱 gameplay 完成。
- [~] **native command 23 special relocation**：`0x2218A→0x22253` 已確認
  先把 selected unit `+0/+1` 寫 `0xff/0xff` 作離場演出，再直接寫 selector
  cursor globals `0x51CF9/0x51CFD` 進場；這是 direct coordinate
  relocation，非 path movement。mode6 legality 已釘為 other-active-unit
  occupancy gate 與 target-dependent terrain code20；camera/render/UI integration
  尚未完成。——本輪(2026-08-19續輪,`doc13`)推進:**遊戲內名稱**已解出——23=傳送術；逐指令反組譯
  完整確認`0x2218A`呼叫序列(`0x12D7B`數值popup→MP debit→class-adjusted level×10累加進
  `[0x53EC8]`→兩次`0x22253`呼叫)與doc56舊敘述逐指令吻合；EXP係數×10精確吻合doc02攻略
  「傳送術=10×(受法者等級/施法者等級)」，三重印證(名稱+機制+EXP係數)。legality/camera/render/UI
  仍未接。
- [x] **RE-RAW-BYTE6-FDFIELD-CONSTRUCTOR**：`parse_field.py` 保存 FDFIELD roster b0 的 `native_record_byte6`，`export_units.py` 將其寫入 units JSON；`battle.Load`／`Scenario.PartyUnits` materialize raw `+6`（own party=2，map selector key 亦保留 direct provenance）。這只閉合 constructor source，不替 `+6` 命名 camp 或 phase 語意。
- [~] **native commands 25..27 closure**：ID25 `0x22C04` 以 record25
  MP debit，僅在 target `+5 bit0x80` 已設時清 raw bit；
  `ExecuteNativeCommand25` 已接 strict non-UI slice。ID26/27 復用
  `0x22d1b` 到 `+0x25/+0x26`；舊「固定10 HP／兩 RNG」已修正為
  gate RNG→damage RNG（base10 實際9 HP）→duration RNG 三 draws。
  `ExecuteNativeCommandApplication` 已同步修正。UI/status labels 與其餘
  engine integration 待。——本輪(2026-08-19續輪,`doc13`)推進:**遊戲內名稱**已解出——25=行動術(清
  `record+5` bit0x80/acted flag，與機制+EXP係數三重印證)、26=毒擊術(`+0x25`施加)、27=麻庫術
  (疑「麻痺術」字模誤判，`+0x26`施加)。ID25獨立handler `0x22C04`本身也有一份`class-adjusted
  level<<3`(×8)累加，不經過`0x22d1b`共用core——這是doc27§5.1六格EXP清單原本遺漏的第三個
  寫入點(數值同為×8但位址不同)，本輪(`doc13`§7)補上。EXP×8精確吻合doc02「行動術=8×」；
  22/26/27透過共用`0x22d1b`核心同為×8，但doc02只列麻痹/毒擊、未列封咒。
- [~] **native command IDs10..12 compositor family**：ID10 `0x21527`、ID11 `0x2185F`、ID12 `0x21A9E` 都會進 `0x21548` 的 320×200/640-stride indexed presentation；**修正舊斷言**：其尾端已直接定位 `1CA89→per-target 1C75E`，故 numeric state core 已由 `ExecuteNativeCommandDamage` 支援。`0x2189A/219AD` scroll/composite、專用演出/SFX/UI 仍待，不可從數值共用推論 visual equivalence。
- [x] **scenario native command-mask bridge**：`PartyMember.initial_command_mask` 已接 exact four-byte source，loader 對 malformed length fail-closed；`gen_campaign.py` 從 EXE `character_defaults.json` 依角色 index 合併至 ch01..ch30 而不覆寫既有手工 scenario 欄位。戰後 persistent snapshot 也保留完整五-byte runtime mask，level-up OR 不會跨 town/preparation 消失。ch01 悠妮 `[1,0,0,0]` 有 per-scenario materialization regression；不可由 normalized `Spells` 反造 raw bytes。待：逐章真機 availability 對照、未知 command effect／frame renderer。
- [~] **魔法系統**（資料表與基礎 Cast 已接，native command/effect 尚未閉合）:magic.go(spells.json=EXE dump 36條+normalized spell names;InCastRange/Cast
      固定表值傷害/治療capMax);悠妮火炎/電擊/治療;法術選單→射程紫高亮→施放接戰鬥演出+扣MP。
      待:AoE(range>0)、命中率、輔助系(魔刃/風行…)效果。
      ✅ 法術特效對映已 RE 定論(f8fffba 後,doc37):**不存在獨立法術id→FIGANI對映**——施法演出=施法者
      自己的組×3/×3+1(火花燒在 sprite 幀,`0x28784` 不讀 spell_id)。這僅閉合 FIGANI 手勢選擇；
      `0x2a6bd` command-specific presentation、SFX、命中與多段畫面仍待，現行角色攻擊動畫只是局部 adapter，
      不得稱完整原版一致。
      ——本輪(2026-08-19續輪,`doc27`§6,回應L555/L557/L572)推進:**L557命中率**——即時反編譯
      `FUN_0001c75e`二次核實，確認法術/道具命中率(`rng%100<record[+2]`)與物理攻擊HIT-EV公式
      (`0x2f7b6`)完全獨立，結論穩定(逐ID數值核對仍缺)。**L557 AoE**——在`FUN_0002ff01`內找到
      真正的多目標套用迴圈(對`param_4`陣列每個target各呼叫一次`0x1c75e`，id 0-8適用)，但上游
      「range如何決定填入陣列的目標清單」仍未追完，部分推進未關閉。
      ——本輪(2026-08-20續輪,`doc27`§6.4,回應L557 AoE殘留缺口)**上游生成器完整追出，L557 AoE子項視為已關閉**:
      逐指令反組譯`0x1cff0`確認`0x2ff01`的`param_3`(目標數)/`param_4`(目標陣列)來自呼叫`FUN_00014818`兩次——
      第一次以spell/item record`[+3]`(選取階段/游標可達範圍)取候選、經`FUN_000115b6`互動確認迴圈；第二次以
      `[+4]`(實際生效/AoE展開範圍)產生最終`targetCount`(commandId==0x1e特例改用`FUN_000149f8`直線步進)。
      `FUN_00014818`本體確認`rangeByte<0x10`時呼叫`FUN_0004e390`+`FUN_0004e42c`遞迴四方向flood
      fill塗地圖緩衝區(圓形/範圍型)，`>=0x10`時走列/欄門檻掃描(直線型)，最後統一掃描全部unit依緩衝區命中+
      `[+6]`陣營篩選器收集roster index，直接餵給`0x2ff01`的`param_3/param_4`。**鏈路已用位址級反組譯完整
      釘死，doc27原文結論為「完成度:已關閉」**；僅剩葉節點`FUN_0004e4be`(flood fill寫入原語)/`FUN_0004e8a5`
      (回傳陣列用途)資料表細節未展開，不影響機制結論。**L557命中率、輔助系效果、SFX/renderer/UI整合仍未
      閉合**，故本compound bullet整體checkbox維持`[~]`，僅AoE子項可視為done。**L572位址勘誤(本輪最主要
      產出)**:`0x2a6bd`在Ghidra project裡不是有效指令邊界(落在無關的451-byte調色盤特效函式
      `FUN_0002a694`中段)，真正的command-specific presentation dispatcher是`0x2ff01`(3876
      bytes)，其分支結構(id 0-8走AoE迴圈、id 24/28-31走`0x2cf30`、id≥32走`0x2d80d`)首次有
      反組譯佐證；`0x276ec`同樣不是有效邊界。doc37「spell id不選FIGANI」結論不受影響仍成立；
      SFX與逐command完整presentation contract仍未展開。**L555**:`0x2ff01`逐目標迴圈證實了
      scroll/composite的原生結構(`0x11eb0`/`0x2eb9f`/`0x311e5`等step呼叫)，但renderer/SFX/UI
      仍未接進remake，部分推進未關閉。
      ——本輪(2026-08-24,doc27§6.5,`0x2cf30`/`0x2d80d`完整反組譯)**兩個分支首次完整解出**:
      `0x2cf30`(ID24/28-31 derived-strike,2269 bytes)倍率表`id24→15、id28→20、id29→12、
      其餘(id30音速刃/id31)→18`，另有獨立per-target hit-event replay迴圈(資料源
      `FUN_000314de()`)驅動`play_sfx_a`(`0x25a96`)與HP遞減動畫，id28(淒煌斬)步數8/其餘1步且多一次
      draw call。`0x2d80d`(ID32-35「四大絕招」,1780 bytes)全部對映完成:
      id32熾天使→`0x2111a`固定威力relay；id33風妖精→清`+0x25..+0x27`後固定800傷害經`0x211a4`；
      id34破壞神→三重buff(`0x22721`/`0x22866`/`0x22997`=魔刃/魔鎧/風行)；id35暗邪鬼→三重異常經
      `0x22d1b`作用`+0x25/+0x27/+0x26`(毒/封咒/麻痺)——四者皆與`command_labels.json`及doc02攻略
      文字三重印證。SFX第二階段來源也一併解出:全域`DAT_00052668`4-byte=`5b 5c 5d 5e`
      (91-94號)，緊接已知#82-90音效池，已用`export_sfx.py --res`驗證四者皆為合法容器。
      **剩餘缺口**:`0x2cf30`hit-event陣列葉節點細節、`0x2d80d`兩個調色盤全域變數(餵`FUN_0002df01`)、
      第一階段FDOTHER資源65-68型別、逐command命中率數值核對、remake尚未接線任一分支的
      presentation/SFX——checkbox仍維持`[~]`。
- [~] **商店+祕密商店**: 69個shop節點已用`native_hub_variant` 1/3/5啟用indexed production owner；四項service與23筆secret chord gate已接。`found_secret_ch*`／legacy `SecretIf`只保留editable擴充，不再當原版gate。sell高階adapter仍會canonicalize ignored stale tail，不宣稱FD2.SAV byte parity。後續E2已閉合ch02三種主選單、secret chord/return與weapon purchase list；剩餘為purchase後續、sell/equip/transfer、town variant1/2及其他章節。
- [x] 存檔/讀檔 ✅(e09c68c):save.go 自有 JSON(節點/旗標/金幣/道具),F5/F9,節點邊界語意

## 第 9 輪 ✅(3-subagent 成本分工;haiku=資料/sonnet=RE·套件/旗艦=架構·驗收)
> 策略(rulebook/45):簡單工作派便宜模型,旗艦只做架構與把關;每件交付先抽驗再 commit。
- [x] **商店品項表**(haiku): `docs/data/shops.json`保存攻略來源的69家／23祕密商店品項與進入提示，campaign已資料化；這是外部攻略／editable authored資料，不是EXE gate真值。原版modifier/key→selection5仍列E0缺口。
- [x] **SFX 破案**(sonnet):FDOTHER#31=14×8bit PCM+AIL 鏈 → doc36;WAV 導出(export_sfx.py,11025Hz 負向證據);
      **index0=游標音確認**(5處方向鍵分支);戰鬥音效=另一獨立池([0x5411f])待導出
- [~] **法術 FIGANI 手勢邊界**：`0x28784` 不讀 spell id，沒有另一段 FIGANI 由 spell id 選擇（火花在角色幀）→ doc37；
      但 `0x2a6bd` command-specific presentation／SFX／命中分支未閉合，remake 角色動畫不可稱完整原版施法演出，
      不結案。
- [~] **歷史 legacy magic snapshot（不可作 native completion claim）**：舊條目所稱「魔法完整版」僅指
      `CastArea` AoE/命中擲骰與 normalized 輔助法術；2026-07-26 已由 SDD56/UI-03 取代為逐 command
      E0 matrix。native target/effect/transaction/presentation 未閉合者維持 fail-closed。
      (魔刃/魔鎧/風行 doc02 明文值)/毒麻封咒行動術/combo;13 單測;引擎:Buff 進 Attack、TickStatus、
      AoE 指空地、FD2_SEED。缺口列冊:風妖精 dmg=0 矛盾、劍技倍率表、傳送 UI
- [x] **全 33 戰場匯出**(haiku):remake/assets/maps/map1-32(96 檔,抽驗 3 圖合法);
      旗艦接線 loadMap(dir)+campaign battle.map 欄位(map3 實測換圖)
- [x] **AI 行走+敵攻我演出**(旗艦):NextAIPlan 決策執行分離+aiStep;atkOwn 欄位按陣營
- [x] **SFX 引擎接入**(旗艦):loadSFX/playSFX+游標/確認/命中掛點(命中暫代,待戰鬥池)
- [~] 戰鬥音效池([0x5411f] 動態子容器)導出+逐招對照——本輪(2026-08-19第12輪,`doc36`)推進:改用Ghidra
  headless取代已知有誤判風險的`disasm_le.py`，發現第10/11輪記錄的入口`0x027fc9`是誤判(實際落在無關
  選單迴圈`FUN_00027f4a`內)；真正的攻擊/招式總派送函式是`0x2ff01`(與doc27§6.2/doc13發現的command
  presentation dispatcher同一函式)。找到真正的SFX index來源:資料段全域表linear`0x0526bc`，完整解出
  action_id 0-9→`FDOTHER.DAT`#82-90對照，25個WAV已用`export_sfx.py --actionid`匯出並逐一驗證為合法
  PCM容器。仍缺:action_id↔招式中文名稱、池內sub-index觸發時機、id 12-21/25-27資源型態、id≥0x20分支
  (`FUN_0002d80d`)自己的index來源；remake `atkAnim`現有SFX hook仍用第10輪未證實候選池，未接上本輪
  驗證過的真實家族。「導出」部分關閉，「逐招對照」核心仍未完全關閉。
- [x] 非 map0 角色 sprite 組匯出(換圖後 fallback 色塊)——2026-08-19稽核確認：本檔第10輪(593-594行)「sprite/頭像滿覆蓋(haiku):96組×12幀sprite(全33圖需求);map3實測全真sprite」已完成此項，僅本行未同步。
- [x] 33 關 campaign 自動生成(parse_field+劇情+商店串鏈,M4 工具)——2026-08-19稽核確認：本檔第10輪(590-592行)「全30章campaign生成器」與第11輪(608-611行)「ch2-30 scenario stub…全30章一條龍可玩」合計完成此項，僅本行未同步。
- [ ] UI 音效 index 2-0xb 語意畫面實測

## 第 10 輪（歷史快照；不代表目前 parity）
- [x] **全 30 章 campaign 生成器**(sonnet):gen_campaign.py→campaign_full.json(183 節點,
      雙重驗證 python+真 campaign.Load;章→map 順序對應依據誠實);旗艦修 resetBattle fallback
      (scenario 空不再錯載 ch01 → roster 全員登場);ch02/map1 實測 33 單位 ✓
- [x] **sprite/頭像滿覆蓋**(haiku):96 組×12 幀 sprite(全 33 圖需求);旗艦補 5 敵方頭像→384 全滿;
      map3 實測全真 sprite
- [x] **戰鬥音效池 RE**(sonnet):FDOTHER #48-53/64/78/88 九候選 42 WAV(七池 sub0 相同=共用
      揮擊音,md5 抽驗 ✓);[0x5411f] 載入點 0x028110(index=招式id→byte陣列動態);
      **位址勘誤:doc36 全篇 0x11fba→0x111ba**(對齊 doc35)
- [x] **全域文字銳利化**(旗艦):font.go per-尺寸 face 快取,所有 Draw 呼叫自動銳利(糊字根因=非整數縮放)
- [x] **BGM 修正(使用者實聽 oracle)**:FDMUS_018=商店(推翻 doc12「戰鬥」推定);戰鬥曲撤下待聽辨
- [x] **派工 SOP 入 rule**:rulebook/45 新節(haiku=資料/sonnet=RE·套件/旗艦=架構·把關;prompt 要素;把關不可省)
- [x] **每章 scenario stub**(ch2-30「能玩」關鍵):party 延續+deploy_cells+initial_groups 全開——2026-08-19稽核確認：本檔第11輪(608-611行)「ch2-30 scenario stub(sonnet):29個chNN.json(party延續/deploy_cells/initial_groups全開)」已完成此項，僅本行未同步。
      (gen_campaign 擴充,回合增援事件之後疊)← 下輪首位
- [ ] 戰鬥曲號聽辨(使用者)+ 各 track 逐曲實聽修正 doc12
- [~] 戰鬥 SFX:index 陣列填值上游、#48-64 逐招對照、remake 接入(atkAnim 命中掛 battle 池)——本輪
  (2026-08-19第12輪,`doc36`)推進:「index陣列填值上游」對action_id 0-9已完整解出(全域表`0x0526bc`，
  見上一行)；`#48-64`候選池(第10輪PCM特徵掃描)與本輪動態追出的真實家族`#82-90`是兩個不同、相鄰的
  資源家族，僅`#88`重疊，`#48-64`維持「候選、未證實載入點」狀態不因本輪升級。remake接入仍未做——
  atkAnim現有hook用的是候選池，非本輪驗證過的真實家族。
- [ ] UI 音效 index 2-0xb 語意畫面實測

## 第 11 輪（歷史快照；「全 30 章一條龍」斷言已由後續誠實揭露降級）
- [x] **ch2-30 scenario stub**(sonnet):29 個 chNN.json(party 4 人/deploy=own_deploy 真資料
      (9 章資源瑕疵 spiral fallback)/groups 全開排除 group==255 padding);campaign_full 30/30
      掛 scenario(含修 ch01 campaign 模式沒主角隊的壞點);三層驗證+3 章實跑
      → **全 30 章一條龍可玩**(FD2_CAMPAIGN=assets/scenarios/campaign_full.json)
- [x] **戰鬥命中音接真素材**(旗艦):battle 池共用揮擊音(#48 sub0)接命中幀;loadWav/playRaw
- [x] **SFX index2 追蹤**(sonnet,部分解出誠實標記):真路徑=0x01cff0
      `[esp+計數+0xd0]`（填值待追）;
      **意外收穫:0x1c269 從 unit+0x1a 起掃描 5 bytes/40 bits 並輸出 byte index；欄位語意尚未定案**；`+0x22..+0x24` 是另一路 raw transient/modifier bytes;
      battle_sfx_map.json 骨架。依「夠用就停」:+0xd0 續追降低優先(共用音已可用)
- [x] 聽辨清單(extracted/music_ogg/聽辨清單.md,待使用者逐曲填)
- [ ] 戰鬥曲/勝利曲聽辨(使用者)
- [x] party 數值成長/招募(doc28 加入條件)、回合增援事件疊到 stub——2026-08-19稽核確認：本檔第12輪(625行)「gen_campaign v3招募累積+成長」與第13輪(665行)「gen v4增援疊入:18章35筆spawn_group」合計完成本項兩子句，僅本行未同步。
- [x] ch10 等圖少數 tile 雜色查因——查無異常:`doc05`(2026-08-18)複核,FDSHAP RLE解碼0邊界異常,視覺比對只是原版手繪高對比dither,非bug,維持07-03non-bug結論
- [x] unit+0x1a vs +0x22 offset：constructor trace 已定案為 initial command mask vs raw transient/modifier bytes（舊稱 `magic_raw` 已撤回）
- [~] +0xd0 陣列填值(逐招音效對照,低優先)——本輪(2026-08-19第12輪,`doc36`)推進:第11輪猜測的
  `[esp+計數+0xd0]`填值來源本輪查明並非該stack offset，真正的index來源是資料段全域表
  `0x0526bc`(見上兩行的action_id 0-9→FDOTHER#82-90對照)；action_id 12-21/25-27範圍逐一驗證
  對應資源不是SFX(非LLLLLL容器)，型態未鑑定；action_id 10/11/22/23落在表的未初始化缺口，
  語意不明。逐招音效對照本身仍未完全解出(缺招式中文名稱與sub-index觸發時機)。

## 第 12 輪 ✅(招募成長/劇情文本/編輯器規劃/政策更新)
- [x] **gen_campaign v3**(sonnet):26 角色 21 章招募累積(ch30 全 30 人)+ 成長(HP 真表值,
      AP/DP 近似明標);**增援誠實跳過**(battle_events.json 實為勝負 metadata；此處的
      「event_id→group 未反組譯 0x22e5c」是本輪歷史快照，已由第 13 輪的 `0x1a813`／`0x51b91`
      證據取代，不得再當現況)→
      docs/data/turn_events.json 真資料 dump + doc26 防誤用註記
- [x] **story 管線**(sonnet):story_to_script.py,ch01-03 精校文本 156 句(speaker 對映 78-85%);
      引擎 story script 載入(旗艦:Node.Script+loadStoryScript,無檔 fallback)
- [x] **著作權政策更新(使用者 2026-07-03)**:FD2 版權過期,**對白文本開放入庫**
      (assets/story/ 例外;ch01.json 恢復原文);圖像/音樂/binary 仍本機
- [x] **tile 雜色結案**(sonnet):非 bug——map9 黑塊紫紋=原版地底裂谷美術;
      全 33 圖 index 零越界、匯出 vs oracle 逐像素 0 差異
- [x] **編輯器規劃**(sonnet)→ `38`:選型=獨立網頁單檔編輯器(File System Access API;
      不做 Ebiten 內建=避免編輯器複雜度混入引擎/不外包 Tiled=劇情事件無對應工具);
      MVP=戰場編輯(產物零轉換直接引擎載入);地基發現:MoveCost 未接地形、
      event.go 實作僅 doc29 願景子集(表單以實作為準+--dump-registry 同步)
- [ ] **戰場編輯器 MVP**:網頁單檔 HTML/JS,tile 繪製+單位擺放+部署格;FSA API 讀寫 assets/maps;
      驗收=引擎零轉換載入(細節 `38`)
- [ ] 劇情編輯器:對白+事件表單+商店(下拉=event.go 現行能力,`38` §3.3)
- [ ] 編輯器能力清單同步:Go --dump-registry
- [ ] campaign 節點圖編輯器(拖線/旗標/敗北路線可視化)
- [x] **地形屬性接線**:地形控制表 per-tile 確認(300~400 格不等,非固定 300;
      `tools/dump_terrain_table.py` → `docs/data/exe_tables/terrain.json`,33 tileset 全 dump)。
      移動代碼(byte1,0-5)語意用 references/text/notes.md 玩家攻略「地形移動力/攻防影響」表
      交叉驗證 AP/DP 數值全吻合(森林 code2/3 = -5%/+10%、沼澤 code4 = -5%/-5%)。
      `tools/export_engine_assets.py` 換算 per-tile 步行成本寫入 map.json `"cost"[]`;
      `battle.State.Cost` + `MoveCost` 查表(`remake/internal/battle/move.go`),`Load()` 自動讀
      units.json 同目錄 map.json 接上(main.go 未改動)。全 33 圖 + 頂層 map0 重新匯出。
      新增 6 個測試(`move_test.go`)。**限制**:僅步行成本,騎兵/飛行差異(notes.md 另有數字)
      待 Unit 加兵種欄位才能接;地形 AP/DP 戰鬥加成本輪未接。
- [x] **0x22e5c 語意更正**：已確認它是固定載入 `FDOTHER.DAT` #79
      並呈現的路徑，不讀章節索引，也不是 `turn_events.event_id→group` 消費點；
      真正增援消費鏈為 `0x1a813`（turn/camp filter）→`0x51b91`（全域 90-entry 表中的 FDFIELD 子集合 0..57）→spawn 原語。
      舊「待反組譯 0x22e5c→接增援」與「章1專屬中場」名稱已撤回，詳見
      `25` §6.1；玩家可見場景名稱仍須原版執行期證據。
- [ ] ch04-33 劇情文本精校(30 章,PNG 人眼轉錄;對白已可入庫)
- [x] 視窗縮放 filter 查證(可能 linear 暈染,tile-debug 提醒)——已解:`doc57`(2026-08-19)。查證確認猜測成立:視窗可被`WindowResizingModeEnabled`拖曳成任意非整數倍率，專案沒有(也無法用目前Ebiten v2 API)覆寫最終畫面→視窗這一層的縮放濾波(v1的`SetScreenFilterEnabled(false)`語意在v2已不存在)，非整數視窗大小下像素藝術邊緣確實會被Ebiten內建平滑濾波模糊。`main.go:9696`引用的`run.go SetScreenFilterEnabled`是過期/不存在的說明(該檔案不存在，全repo也無此呼叫)。可行改善方向(本輪未實作):限制`WindowResizingMode`只接受整數倍率、或在`defaultWindowSize`/resize handler裡把實際視窗尺寸捨入到最近整數倍——此為後續實作工程，不影響本項「查證」已完成的判定。

## 第 13 輪 ✅(增援打通/地形/開場實機裁決/文本流水線)
- [x] **回合增援機制全解**(sonnet):0x51b91 全域 90-entry 跳表中的 FDFIELD 子集合 0..57(0x22e5c 排除);map0 4/4 ground truth;
      extract_event_id_groups.py;turn_events.json 補 groups
- [x] **gen v4 增援疊入**(sonnet):18 章 35 筆 spawn_group(turn 精確比對=原版語意);
      \$turn_counter 展開(3 圖核對);6 筆 \$reg_or_mem 列冊待解;ch08 T0/T4 實跑增援登場 ✓
- [x] **地形接線**(sonnet):FDSHAP 2N/2N+1 配對地形表(4B:寶箱/移動代碼/**戰鬥背景編號**
      =doc35 地形→BG 對應解!);MoveCost 查表+6 測試;main.go 零改動。騎兵/飛行差異待兵種欄位
- [x] **ch04-08 文本**(sonnet):177 句入庫;speaker 編碼文獻化(0-9,A-V→face_portrait)
- [x] **dosbox 開場實機裁決**(sonnet):logo=縮放進場(使用者記憶證實,推翻 doc23 [驗]);
      開場實為 32.3 秒多幕過場(疑 ANI.DAT 驅動,新缺口);選單座標/硬切閃光轉場
- [x] **title 修正**(旗艦):logozoom phase(紅閃→縮入→白閃)+選單實拍座標
- [x] **ANI.DAT 完整 AFM 格式 RE**(sonnet):9 資源=10-opcode 增量繪圖 VM(palette 4 op+
      framebuffer 6 op,直寫 VGA 0xA0000);173B 標頭+8B 幀記錄,289 幀全解無例外(位元組自洽);
      `tools/decode_ani.py`;9 資源逐一視覺比對 doc23 §2.4③ 分鏡全數命中(守護者/索爾/拔劍/
      騎馬夜行/明月/合照/金鎖);**「2」logo 縮放亦由 ANI.DAT(資源#1)驅動**,更正 doc23 猜測。
      見 doc39。待補:⑥浮空城/⑨惡魔臉未逐幀窮舉、轉場閃光呼叫端排程。
- [ ] 開場配樂曲號實聽驗證(容器 nosound 無法驗;使用者聽辨)
- [x] ch21/22 \$reg_or_mem 增援 eax 來源 RE(6 筆)——已解:`doc25 §6.1.1` [驗],event_id 47/49 同構公式 `group_id = turn_counter DIV 2`,6/6 對照 map roster 全部吻合
- [x] ch09-33 文本(批次進行中:09-13 執行中)——2026-08-19稽核確認：本檔697行「全33章劇情文本完成(sonnet流水線6批):ch01-33共1452句」已涵蓋ch09-33轉錄，僅本行未同步（接線入遊戲是另一獨立仍開放議題，見707-721「誠實揭露」段落）。

## 第 14 輪 ✅(AFM 完全破解+開場過場端到端+文本過半)
- [x] **AFM 格式完全破解**(sonnet):10-opcode 增量繪圖 VM(Lo Yuan Tsung 1993);
      派發 0x36c9e/跳表 0x5276a/framebuffer=VGA 0xA0000;289 幀(9 資源)逐位元組驗證;
      decode_ani.py;視覺全命中 dosbox 分鏡(屠龍/logo/金鎖…)→ doc39
- [x] **Go AFM VM 移植+開場接入**(旗艦):internal/afm(容器+VM);執行期解玩家 ANI.DAT
      (不夾帶版權幀);title cutscene 9 幕串接進選單;afm_test 驗幀數 96/51/35;
      無 ANI.DAT 退回 FDOTHER 捲動 fallback
- [x] **AFM 播放器排程 RE**(sonnet):play_afm(index,delayMs,skippable);毫秒校準 0x3dc9f;
      5 呼叫點釘死(開場 3/4/5/6/7/8/0/1,delay 90-15ms;idx0/2=章節過場非開場);
      title.go 換真值排程(拿掉月亮 idx2、各幕 delay、skippable 旗標)
- [x] **ch14-18 文本**(sonnet):229 句;ch01-18 累計 747 句;ch18 永久劇情死亡標記
- [x] **0x1f73f FDOTHER 靜態幕 RE**(sonnet):開場 2 幕靜態=①守護者(#100+pal#99,esi=0x1c2)
      +⑥滿月浮空城(#75+pal#76,esi=0x0a,dosbox frame168-173 逐像素吻合);機制 memset黑→
      載調色盤→blit→淡入→BIOS tick 忙等(修正原 KB「BGM/SFX」誤判);⑨惡魔臉排除是 0x1f73f(待下輪)
- [x] **開場過場插 2 靜態幕**(旗艦):cutScript AFM+static 交錯腳本;frame165 守護者/frame645 浮空城驗證
- [x] **全 33 章劇情文本完成**(sonnet 流水線 6 批):ch01-33 共 1452 句;
      speaker 場景本地表現象文獻化;身世真相(悠妮=ASR-07/大魔王=ASR-06)
- [x] **speaker→頭像機制 RE**(sonnet):0xFFEF operand→0x12C60 查[0x53A45]/[0x53BF7] byte[+7]=DATO;
      三推論裁決(①部分成立=陣列重填+雙定址②怪物表不成立③字母碼是 render_story.py operand 洩漏 bug);
      **story JSON 零修改**(現行最忠實);修 render_story.py operand-skip;doc14 修正
- [x] **開場配樂曲號 RE**(bgm-title 執行中):play_bgm 開場鏈曲號→FDMUS 檔(取代猜測 FDMUS_004)——已解:`doc12`,FDMUS_018,`0x25db1-0x25db5`唯一play_bgm(0x12,0)呼叫
- [x] 開場分鏡⑨惡魔臉來源 RE(疑另一機制或 ANI.DAT)——已解:`doc39 §10.9`,是`title_seq`(0x1f894)捲到esi==0時露出立繪緩衝區頂端(FDOTHER #0x45/#0x46),非獨立機制;doc23§2.4⑦07-03已用肉眼比對解出,本輪Ghidra逐指令複驗控制流補強
- [x] ch21/22 \$reg_or_mem 增援 eax 來源 RE(6 筆)——重複項,已解見上方 `doc25 §6.1.1`(`group=turn/2`)
- [x] 待展開(位址已釘):0x3453E 額外檢查、tag==0x27 sentinel、[0x53BF7] 表用途——已解:`doc40`/`doc26`(2026-08-19)。0x3453E=stale label(真實呼叫0x34894=NativeRecordByte5Bit0);tag==0x27全EXE唯一處0x161a2(推翻doc40「下框變體」說);[0x53BF7]=持久隊伍roster(非原猜的scene actor table,已訂正)。「為何是編號39」屬asset層,靜態無法答

## ⚠ 誠實揭露:全 33 章劇情文本「大部分轉錄完成但尚未接進遊戲」(2026-07-27 重查)

**症狀**:尚未接 script 的 remake story 節點仍會使用短佔位文字；已接的節點則會載入對應劇本。
**查證**:目前實際 `campaign_full.json` 有 **121 個 story/cutscene 節點：9 個有 direct `script`、33 個有 `handler_binding`**；
其餘 79 個沒有 script/handler，仍依 node lines/default fallback，不能把 33 章轉錄宣稱成已接入。
`assets/story/ch01~33.json` 的 33 章 1452 句轉錄存在，但不等於每個 story node 都有正確 scene/line 對映。
**根因**:各自完成、接線沒人做——
- 「全 33 章文本完成」(story 流水線 6 批)✓ 真的轉錄好了
- 「全 30 章 campaign 節點生成」✓ 節點圖生成了，但不代表 story 對映完成
- **部分節點接 script、其餘仍依 placeholder/default fallback** → 兩者尚未完全連起來 ✗
**教訓**:子系統各自報「完成」不等於整合完成;跨模組「接線」要獨立驗(truth-in-code,
配 rulebook/63)。使用者實玩才揭露——沒實玩/沒查,文件會一直顯示「完成」。
**目前修法狀態**：9個節點有 direct script、44個由 handler binding 供應過場資料；另外30個 retreat、23個 rumor 是刻意的短 authored node，10個 unbound postbattle 與5個 generic story fallback 才是待 mapping/handler 的缺口。24個 postbattle 有 generated binding skeleton（其中14個已由 authored binding 啟用），未經 override/compile gate 仍不算 active handler，不能把同一章 script 盲目灌入其餘節點。
下一步要依原版 handler／FDTXT scene label 逐節建立 mapping，完成後才可宣稱接通。
- [x] **story-script coverage audit tool**：`tools/audit_story_script_coverage.py` 以唯讀方式列出 story/cutscene、coverage role、script、scene、handler、generated skeleton 與 next。2026-08-02 實測為121個 story/cutscene、9個 direct script、44個 handler-bound、68個 fallback；fallback 再分為30個 retreat、23個 rumor、10個 unbound postbattle與5個 generic。24個 postbattle skeleton 中14個已啟用、10個未綁定；postbattle skeleton 依主迴圈證實的零起算關係定位。數字變動時必須以工具輸出與對應回歸一起更新，不可只改文件。
- [x] **raw ch03 post binding（玩家第4戰）**：handler `0x231bc` 只有 FDTXT_004 dialog `0x231e5`、persistent sync `0x231ed` 與 `set_chapter4` `0x231f2`，無 unknown 或 runtime layout 需求；由既有 generated mapping 提升為 authored binding，接入 `postbattle_ch04_persist→town_ch05` 並納入全章 owner regression。
- [x] **raw ch04 post binding（玩家第5戰）**：Docker Capstone 證實 `0x2324c→0x233c6` 的 X/Y/pose 陣列（各 7 bytes）、slots0–6、special slot41 `(12,8,pose0)`、camera raw `(6,4)`；map4 raw roster frontier=50，FDTXT_005 index9 count-aligned 為 scene5 lines0–16 加 scene6 lines0–1。authored binding 現接 `postbattle_ch05_persist→town_ch06`；未宣稱 renderer parity。
- [x] **raw ch05 post binding（玩家第6戰，E1）**：Docker acting exporter 解碼 resource27 為3 beats、slot34/pose2；raw map5 `enemy_ally_total=40` 且 group3僅一筆，handler `0x10b4e(3)` 因而保存 `spawn_groups[3]=1`。`0x232b8` pan `(5,14)` 依既有 tile ABI materialize `(120,336)`，FDTXT_006 index6 對 ch06 scene6 lines0–18。IDA Pro 9.4 直接確認 table index5=`0x23296`，並沿 `0x232e3→0x231df` 真實共享尾段固定 JOIN13→spawn3→pan→ACT27→dialog→sync→chapter6順序；authored binding 已接 `postbattle_ch06_persist→town_ch07` 並有 compiler／campaign regression。`0x2cad7` 原版戰間 outcome與一般玩家畫面仍未達E2。
- [x] **raw ch12 post binding（玩家第13戰，E1）**：IDA Pro 9.4 與 table bytes 確認 index12=`0x2389f`，即使 IDA 導覽把它併在 `sub_237D5` 內也不可改寫真實入口。FDTXT_013 index9 經 address context 依序展開 ch13 scene3 lines0..5、scene4 lines0..5，再由 `0x238d0` sync、`0x238d7→0x237c8` JOIN3、`0x237d0→0x231f2` chapter13；authored binding 已接 `postbattle_ch13_persist→town_ch14`，跨 scene與尾段順序均有永久回歸。`0x2cad7` outcome及一般玩家畫面仍未達E2。
- [x] **raw ch08 post binding（玩家第9戰）**：Docker acting exporter 解碼 resource36 為 5 beats、slot47/pose0；raw map8 `enemy_ally_total=60` 且 group4 僅一筆，handler `0x10b4e(4)` 保存 `spawn_groups[4]=1`。`0x235d8` pan `(6,1)` materialize `(144,24)`，FDTXT_009 index4 對 ch09 scene4 lines0–4；authored binding 現接 `postbattle_ch09_persist→town_ch10`，未宣稱 renderer parity。
- [x] **raw ch11 post binding（玩家第12戰）**：Docker Capstone 證實三個 14-byte arrays、slots0–13，special slot2 最終覆寫 `(10,4,pose0)`，camera raw `(14,0)`→`(336,0)`；map11 60-slot frontier。Docker acting exporter 解碼 resource45 的 slot8 special frames（0 與 6 beats），FDTXT_012 index3/4 對 ch12 scene3 lines0–2、scene3 lines3–9；authored binding 現接 `postbattle_ch12_persist→town_ch13`，未宣稱 renderer parity。
- [x] **raw ch13 post binding（玩家第14戰）**：Docker Capstone 證實三個 16-byte arrays、slots0–15，special slot0 最終覆寫 `(0,0,pose0)`，camera raw `(12,10)`→`(288,240)`；map13 70-slot frontier、group1 僅一筆。Docker acting exporter 解碼 resource47 為 4 beats、slot67/pose2，FDTXT_014 index2/3 對 ch14 scene0 lines8–17、scene1 lines0–6；authored binding 現接 `postbattle_ch14_persist→town_ch15`，未宣稱 renderer parity。
- [x] **raw ch24 post binding（玩家第25戰）**：Docker Capstone 證實 handler `0x24df2` 的 FDTXT_025 index6/7、PAN raw `(4,16)`→`(96,384)`、spawn group2=1、ACT resource75；Docker acting exporter 解碼為 4 beats、slot70/pose2，map24 raw frontier=70。FDTXT_025 index6/7 對應 scene2 lines0–17；authored binding 現接 `postbattle_ch25_persist→town_ch26`，未宣稱 renderer parity。
- [x] **raw ch25 post binding（玩家第26戰，E1）**：Docker Capstone 證實 `0x24e80` 的 `0x233c6` caller 以16 slots、camera raw `(9,5)`→`(216,120)` 寫入 map25；Docker acting exporter 解碼 resource77(slot1/pose2)、78(slot2 pose2→1→special pose0)、79(slot0/special pose2)、80(slot0 pose3→2→slot2 pose2)。FDTXT_026 string5–11 已由 raw glyph/control stream 對到 ch26 scene2 lines0–14、scene3 lines0–17、scene4 lines0–7；IDA Pro 9.4 又固定主表 index25=`0x24e80`、event state entry12 的兩個分支及共同 sync/chapter26 尾段。authored binding 已接正確 owner `postbattle_ch26_persist→town_ch27` 並有編譯與 campaign regression；2026-07-29 的63/63 count-aligned勘誤仍有效，未宣稱 renderer parity或一般玩家 E2。
- [x] **raw ch06 event26→event25→post conditional frontier（玩家第7戰，E1）**：IDA Pro 9.4 固定 map6 六格 selector0 event26=`0x3499B`：觸發單位 raw `+6 != 0` 才以 `0x3419C(9,27,0)` 清 slots9..27 的 `+0x34` 低四位並寫 state16=1。enemy turn10 event25=`0x34924` 先要求 state16==1，才依序 spawn group2→pan `(16,10)`→ACTING30→FDTXT_007 index2→寫 state17=1；未踏格反例不增援。ACTING30 直接引用 slots34..43。先前「slot43 是96-slot空白 record」已撤回：runtime 是 party9＋group1 25=34，再 append group2 10=44。authored scenario 現保存完整 gate／事件順序，已追蹤的 ch06 post handler 亦由錯誤線性稿修成雙層 CFG：state17==1 精確細化為44 slots，再讀 slot43 raw byte5 bit0；active 才 layout→index4→JOIN12，否則 index5。`postbattle_ch07_persist` 已接 binding 並回歸至 `town_ch08`，JOIN12 同拍建立唯一 persistent raw record；尚缺一般玩家 DOSBox E2。證據見 [`fd2_ch06_post_event25_ida.txt`](../data/ida/fd2_ch06_post_event25_ida.txt)。
- [x] ch01 開場三幕(王城父子/草地悠妮蓋亞/遇海盜)手動接線+轉錄 FDTXT_033/032(intro-scenes)
- [x] **ch01 開場三幕背景圖 RE+接線**(使用者實測發現對白疊在戰場地圖上,非王座廳/草地,2026-07-04):
      RE 修正 doc23 §4 誤記(「FDTXT 序幕『影像』資源」不存在,FDTXT 純文字)——真正背景是
      **暫借章節 32 時 `0x1088d` 順帶載的 FDFIELD 組32(資源96/97/98)= 18×51 複合地圖**(王座廳→長廊→
      草地),與戰場同一 tile 渲染器;已渲染驗證(`extracted/maps/map32.png`)逐像素對齊 dosbox 參考圖
      + 使用者原版錄影。序幕尾端 `[0x53c03]=0` 還原真章節,「遇海盜」對白疊在**真戰場地圖 map0**(非另一
      張圖)。remake 加 `campaign.Node.Map/CamX/CamY`(story 節點固定鏡頭背景圖)+ `main.go` `storyBG` 模式
      (鏡頭不跟游標、不畫單位/游標/HUD);`campaign_full.json` 三節點接線(palace/meadow→map32,
      pirate→map0)。截圖驗證王城幕=雙王座紅毯廳(對照 orig_02_dialog_02_king.png)。
      **教訓**:另一 agent 曾提案「背景已在 BG_BG_\*.png,只需配對」,經抽樣檢視(320×100 全景走廊,
      無王座/紅毯任何痕跡)證偽——套用前先驗證,不可盲信「已抽出」的斷言(rulebook 62)。
      另踩雷:`~/.local/share/fd2_re/assets/`(玩家/測試用資產覆蓋目錄,`assetPath()` 優先讀它)有舊版
      campaign_full.json 快取(缺 ch00_palace/meadow 分幕),測試前先同步 repo 最新版才看得到真結果
      (使用者已驗收+ commit;team-lead 另修 play.sh 每次啟動先清 XDG scenarios/story 影子,一勞永逸)。
- [x] **王座廳 NPC 擺位**(使用者驗收背景後指出「王座是空的、索爾沒出現」,2026-07-04):RE 出 FDFIELD 組32
      出場位置段(資源98)直帶場景 NPC 座標+肖像,同戰場單位 roster 格式;**國王 portrait48@(7,5)+
      王后 portrait66@(10,5)** 頭像圖核對(`DATO_048/066_m0.png`=戴冠鬍鬚男/紫髮女)完全對上
      `f_006.png` 左王/右后。索爾在該格出場位置表無對應項(原版走 0x3231b 內 `push1/3/5;call 0x10b4e`
      另一條登場路徑,未逐一 RE),故索爾位置(fig0 @(8,8) dir2)是目視 f_006 定位、非 FDFIELD 直讀,
      已在 doc23/campaign_full.json 誠實標記。remake 加 `campaign.Actor{Fig,X,Y,Dir}`+`Node.Actors`
      (story+Map 節點靜態擺位,複用 battle.Unit/drawUnitSprite 畫法、無戰鬥邏輯),`story_ch01_palace`
      接 3 actor。截圖對照 f_006 吻合(國王/王后坐正確王座、索爾紅毯中央背對鏡頭)。
      **順帶發現**(未實作,留給 ch02-33 接線時參考):同一出場位置表在草地段(row42/46/47)另有
      portrait0×2(索爾+疑似另一己方角色)+portrait4(亞雷斯)+16 個 portrait68/69 走廊守衛,
      可比照本次做法補草地/走廊 NPC。
- [x] **ch01 開戰隊形 deploy_cells 核對**(使用者指出「索爾隊伍站位都是錯的」,2026-07-04):
      格子座標本身(FDFIELD `own_deploy` 直讀)已驗證正確,問題出在**逐人分配順序**——用 fig sprite
      外觀(fig4=藍盔=亞雷斯/fig9=紅髮=悠妮/fig30=機甲=蓋亞)逐一核對 `orig_03_battle_start.png`/
      `f_029.png`,發現影片是「索爾+亞雷斯緊鄰、悠妮稍右、蓋亞最右」,但 `ch01.json` 原
      `deploy_cells` 陣列順序配上 `party` 順序會把亞雷斯/悠妮的格子配反。交換
      `deploy_cells[1]`/`[2]` 修正,隔離 Xvfb + xdotool 送 Enter 清對白後截圖(before/after 對照)
      確認吻合。**除錯插曲**:FD2_SHOT_CUR 測試一度看似「怎麼設都沒用」,查出是地圖只有 24 格高
      (576px)但視窗 400px,camY clamp 上限只有 176,導致 curY=20/21.5/23 全部 clamp 到同一個畫面
      (誤判無效);換更小的 curY(如 15)才看出真的有作用——clamp 邊界會讓「看似無效的截圖測試」
      其實只是撞到同一個 clamp 上限,不是機制真的沒用,下次遇到「怎麼測都一樣」先檢查 clamp 範圍。
      → doc44 §2.5 定案(信心分級:格子=FDFIELD 直讀高信心,逐人配對=影片外觀反推中高信心非鐵證)。
- [ ] ch02-33 全章 story 節點接 script(gen_campaign 修+重生成)— 等 ch01 落地後做
- [~] ch02-33 全章 story fallback：runtime 對精確 `story_chNN` generic node 自動掛 `assets/story/chNN.json`，讓已匯出的可編輯完整劇本取代節點短 fallback lines；named/pre/post cutscene 不套用此 heuristic，避免重播整章。ch02/03 handler 仍待逐段 beats 接線。
- 🟡 **ch01 開場 Phase 2 實作(doc46 D1-D6,2026-07-04,待使用者驗收才打勾)**:使用者三輪回報後
      team-lead 先做「原版開場逐幕時間軸」(doc46)才動手,這輪照時間軸把 D1-D6 全部實作:
      **D1/D2 背景重構**:`story_ch01_palace` 拆成 `story_ch01_palace_throne`(map32 王座廳)+
      `story_ch01_palace_path`(map32 草地小徑,原「meadow」節點誤用棚)兩幕,`story_ch01_meadow`
      **改名為 `story_ch01_forest_duel`+`story_ch01_forest_discover`,背景從 map32 改指 map31 密林**
      (先前張冠李戴的核心 bug);map31 actor 用 FDFIELD roster 直讀(索爾19,46/亞雷斯19,47/
      蓋亞5,43/悠妮5,44);`portrait75` 是商店店員 NPC，不在 00-41 可入隊角色範圍，**未擺放**。
      **D4 行軍蒙太奇**:新增 `story_ch01_march`(map0,無對白,`auto_advance`
      180 幀自動轉場,索爾走位代表隊伍,簡化版,doc 誠實標「近似非逐幀重現」)。
      **D5 分段播放(核心)**:`campaign.Node` 加 `Scene` 欄(只取 Script 檔 `scenes[]` 裡 label
      對映的那一段,不再攤平全部劇本);改「每段一個 story 節點」而非 Node 內 sub-scenes,
      保留 `FD2_CAMP_NODE` 可跳任一幕驗證。**D6 走位動畫**:`campaign.Actor` 加
      `FromX/FromY/WalkFrames`(進場走位,重用 `battle.Unit.OffX/OffY` 插值)、`Node.ExitWalk`
      (退場走位,索爾沿紅毯走下場~1.5s);新增泛用**淡出/淡入轉場**(`storyFade`,0.6s/次,
      story 節點間一律套用,不再硬切)。**除錯插曲**:forest_duel 一度以為亞雷斯(fig4)沒畫出來,
      加 debug 座標印字才確認兩個 actor 都在正確位置、只是 FDFIELD 給的座標剛好只差 1 格(y46/47)
      造成兩張 24×24 sprite 緊貼——不是 bug,是資料本身就這麼緊,已移除 debug 印字。
      驗證:每幕獨立截圖 + 相鄰幕轉場(throne→path 含退場走位+淡出淡入全程截圖)+
      discover 幕走位動畫三階段截圖(進場遠/中/抵達)+ march 幕靜默→自動轉場→抵達海島全程截圖,
      build+test 綠、gofmt 乾淨。**D8(戰前 MAP/TURN 資訊畫面+行軍確認 UI)不在本輪範圍,已登記獨立項**。
      → doc25 §7.5.1 已修正範圍(戰場進場直接定位仍成立;cutscene 幕內走位是另一機制,已推翻舊結論)。
- [~] **D8:戰前 UI**(doc46 附帶發現):Docker/Capstone 已釘 `0x1a30b` battle-entry choreography：
      `0x1f1cc(0x52)`→20ms→`0x1f30a(0x52)`、64000-byte indexed surface；`0x1f42d` 已釘為
      LMI1 entry #0x52 的雙側五幀 slide-in/restore（x=85−offset、165+offset；offset=100..0）、
      後續 `0x1a813/0x1a866` dispatch；`0x15f0e` frame ABI 亦已釘為 offset-table + RLE
      decode + stride blit；`[0x53a81]` 已由既有 loader trace 對位為 `FDOTHER.DAT#5`
      的 `LMI1`，remake `fdother.ParseLMI1`／`LMI1Entry.BlitAt`（透明 preserve + mirror）
      與 player-asset regression 已補（#0x52=72×14；directory offset 不是 RLE 結尾）。
      證實不是 `resetBattle` 直接跳過的空白階段。仍待釘死
      MAP/TURN/ENEMY/FRIEND/NPC 欄位與 YES/NO input 的資源／字串 ABI，再做 remake shell 與截圖，
      不把 resource `0x52` 或 `0x51e81` 猜成畫面名稱。
- [x] **D8 scope correction / raw entry step**：重新檢查官方 `0x1a30b`，確認本體沒有 `0x15f84` 文字呼叫；只對 selector/gate 通過的 raw record 做 `+0x40 += +0x42/5`、上限 clamp 與 indexed redraw，之後才呼叫 `0x1f1cc/#0x52`。新增 `NativeBattleEntryStep` regression；MAP/TURN/ENEMY/FRIEND/NPC 資源與 YES/NO input 仍未證實，不能由 `0x52` 命名。
- [x] **0x1a30b shared-caller correction**：Docker Capstone xrefs 固定 callers=`0x135c5/0x17154/0x17272`；`0x1716f/0x17241` 旁有 FDTXT_000 `0x19c/0x1a4` 互動訊息，`0x1728c` 處理 selector flags。故 `NativeBattleEntryStep` 保持 reusable raw record primitive，不接成 D8-only preparation action。
- [x] **UI-11 remake shell screenshot artifact**：Docker `fd2-go-test-local` + Xvfb 實跑 `FD2_CAMP_NODE=preparation_ch02 FD2_SHOT_FRAME=30`，產生 [`preparation-remake.png`](../figures/preparation-remake.png)（640×400，2× 320×200）；只證明 editable preparation node 與地圖背景/overlay 可呈現，不取代原版 DOSBox 差分，也不關閉 MAP/TURN/YES-NO evidence gate。
- [x] **native raw action-bit writer**：Docker Capstone 固定 `0x13512(index)` 設 `record[index*0x50+5] |= 0x80`、`0x13536` 全表清 bit7；新增 `battle.SetNativeRecordBit7`／`ClearNativeRecordBit7All` 與 bounds/other-bit regression，保留 raw offset，不把 bit7 強行命名成回合狀態。
- [x] **post-resolution inventory occupied-count ABI**：Docker Capstone 固定 `0x1b8a6(unit)` 掃 `record+0x0a+2*i` 八個 cell；bit7 clear 只增加 occupied count，函式不驗證 compact prefix。caller 再以 count 作 slots `0..count-1` 上界；洞會讓 stale item byte 進入掃描。bit7 set 是 `0x1bb8c` 使用的 reserved 空格。已更正 free-slot／prefix 斷言並以 `battle.NativeInventoryOccupiedCount` 保存 exact count。
- [x] **post-resolution inventory reservation writer**：Docker Capstone 固定 `0x1bb8c(unit,item)` 取第一個 flag bit7 cell、清 flag、寫入 item byte、回傳 1/-1；新增 `battle.AssignNativeReservedItem` 與 first-cell/none regression，保持 raw item/category opaque。

## 待辦:實測回饋(使用者 playtest,2026-07-03)
- [x] **開場過場節奏 3x 太快 RE**(dragon-fx2 DOS 對比發現,doc39 §10.8):原版魔王立繪捲動——已解:`doc39 §10.10`(2026-08-19)。原版535步×30ms、被6觸發點切7段、段間阻塞,總16.05s;remake把7段併成單一220-tick(3.67s)且搬到演出後,漏掉中間12.75s穿插等待。給了拆7段+各段tick對齊建議
      (esi535→0)貫穿全開場、與各 AFM 幕交錯(暫停播幕→續捲),貢獻 ~16s 延遲;remake 把捲動
      搬到最後單播→開場 5s vs 原版 14.7s。修需先補 0x11eb0/0x1f894 逐指令(捲動如何在 AFM
      直寫 framebuffer 後接回)。使用者已 OK 開頭閃光(#9),此為獨立節奏落差,低優先
- [x] **序章劇本 staging 機制 RE**(使用者指出 #3=劇本機制沒 RE 完整,2026-07-03 反組譯+dosbox 220+ 張連拍
      複驗收尾)→ **定論:主角隊直接定位,原版無行軍動畫**。0x3231b 使用直接 spawn(`0x10b4e`)、
      攝影機平移（`0x13185`/`0x135dd`）與新增群組索引轉場（`0x32999`）；這些都不是單位行走。DOSBox 全程重跑序章開場
      未見任何單位行走動畫或世界地圖段落;玩家記憶「走到地圖中央」疑與攝影機平移視覺效果混淆。
      remake 現行 focusOnParty(純鏡頭對準)+ spawn_party(直接定位)已忠實,#3 非 bug,不需補行軍動畫。
      → `docs/knowledge-base/25-battle-event-system.md` §7.5.1
- [~] **playtest 8 項修正**(playfix agent 執行中,#7=我 kill 誤殺非 bug 已排除):
      #1 方向鍵按住持續移動、#2 預設沒開場動畫、#4 移動後 ESC 取消退回、
      #5 action overlay／command grid 的原版 side-by-side 視覺對照、#6 地圖狀態欄還原原版、#8 單位走完轉回正面朝向
      → **batch1 已 commit(0f32d25)**;#7 非 bug(kill 誤殺);#3 部分(鏡頭對準部隊)
- [ ] **#9 法術特效時序**(待使用者釐清):playfix 靜態審查=攻擊系法術路徑乾淨無殘留;
      真根因疑「治療系法術 target=1 無全螢幕演出(只文字)」→ 打治療咒後緊接敵方攻擊演出,
      被誤認成法術效果延遲出現。修法需先 RE 原版治療咒視覺(閃光/數字浮現/僅改血條),
      或使用者釐清實際現象,不瞎編視覺
- [x] **序章場景轉換打通**(2026-07-04,使用者驗收 OK,commit 2c5adda):王座廳/草地/遇海盜改用
      真 tile 地圖背景(map32/map0)+ 固定鏡頭,非戰鬥圖。RE 定論:0x3231b 暫借章節32 載 FDFIELD
      組32(紅毯雙王座→長廊→草地縱向拼接),與戰場共用 tile 渲染器。story.Node 加 Map+CamX/CamY,
      main.go 加 storyBG 鎖鏡頭/擋游標。→ `23-boot-title-and-scenario-flow.md` §4
- [x] **援軍 stale-cache bug 根因修復**(2026-07-04,使用者報「援軍不該一開始出現在地圖上」):
      根因非 code bug——`~/.local/share/fd2_re/assets/scenarios/ch01.json` 是舊版 `initial_groups=[1,2,10,11]`,
      XDG 快取層優先蓋掉 repo 已修正的 `[1,2]` → group 10/11 開場即 OnField=true 出現。**治本**:XDG 是給
      版權衍生素材(sprites/maps/music)+ 玩家編輯版覆蓋用,scenarios/story 是原創內容不該進 XDG;已刪 XDG
      scenarios/story 影子 + play.sh 每次啟動先清,dev 一律以 repo 為真相。→ 記憶 `fd2-intro-cutscene-bg-and-userdata-cache`
- [x] **過場腳本機制第一性原理解答(doc47)**(2026-07-04,使用者問「RE 為何沒還原 staging」,旗艦親做):
      方案 b 證偽=FDTXT 純對話碼無 staging;方案 a=序章 handler 0x3231b 逐 beat 全轉錄。
      原語翻新:0x135dd=平滑鏡頭平移、0x15f84=對白播放器(doc23 舊判「逐格貼圖」誤)、
      0x1366a=演出(acting)播放器（direct bank 格式與 106 筆資源已解出；normal=逐格搬移、
      special=原地 pose，zero-special 保留三 tick 時序）、0x112a5=入隊(0/9/4/30)。
      重大:王城→草地=同 map32 鏡頭平移轉場非淡出換景;對白與演出逐條交錯;海島幕 3 個平移點。
      → remake 修正指示 doc47 §4；尚待逐章把 direct acting 資源接入可編輯 cutscene 節點，
      並以實機截圖核對 renderer/presentation 差異（不猜測性補 handler 語意）。
- [x] **王座廳 NPC 擺位**(cutscene-bg 執行中):國王/王后坐王座 + 索爾站紅毯中央,對照 f_006.png;
      story 節點加 actor 擺位欄。RE 查 FDFIELD 組32 是否帶 NPC roster(sprite id/cell 直接來自原版)——2026-08-19稽核確認：此項與本檔746-753行「王座廳 NPC 擺位」(2026-07-04)逐字重複，該項已用FDFIELD組32出場位置段解出國王/王后座標並接入`campaign.Actor{Fig,X,Y,Dir}`+`Node.Actors`、截圖核對f_006.png吻合，僅本行為舊重複提問未同步刪除。
- [x] **ch21/ch22 pre-handler**：FDTXT_022 index0（11句）與 map21/70-slot、pan(16,28)、acting67 已接 editable binding；`story_ch22` 已接回原版 pre-handler，compiler/campaign/battle regression 通過。
- [x] **外部資源／城鎮流程交叉盤點**：公開資料確認 `FDFIELD.DAT` 是可替換的外部場景層，且章節間存在 preparation、商店、教會、存讀檔流程；後續以 DAT provider + battle→town/prep graph 實作，未將網路資料當 binary 格式硬證據。
- [~] **社群行為 oracle 對照**：逐項把 FD2.EXE 修改表中的入隊、隨時存檔、等級上限、寶箱持久化轉成可編輯規則與 regression；先挑 save/chest 兩項和目前 persistent flow 最相關者。——save/chest已解:`doc25 §9`(2026-08-19)。存檔writer 0x30012只有2個戰間邊界呼叫者(戰鬥中不可存);寶箱旗標[0x53AD5]每戰重置不進存檔。對照出remake 2處缺regression(save未擋battle節點、treasure不變式)。入隊/等級上限留待後續
  ——本輪(2026-08-19續輪,`doc25`§9.3跨文件盤點)推進:**入隊(JOIN)機制本身已完整閉合**——`0x112a5(join_id)`
  JOIN constructor已由`native_join_constructor.go`+`native_join_constructor.json`(32-row，含MD5/SHA256驗證)
  做成通過回歸測試的可編輯規則；仍未閉合的是「哪一章、哪個handler呼叫哪個join_id」逐章ID/條件表，這不是
  單一位址能收斂的規則，而是隨每章postbattle/pre-battle handler解碼逐步累積，不建議另開獨立項目追蹤。
  **等級上限機制核心已由`doc27`§5(worklist245/266)反組譯**:`0x1e292`的`cVar1(actor+7)==0x1e/0x1f→99上限`
  否則`40上限`——`doc27`§5.1(本輪，見上方L245附註)已進一步確認這是封閉列舉(比對portrait非職業，函式內無
  第三分支)，class→cap對應本身已完全閉合；仍缺remake端的執行接線(`growth.go`目前門檻只有「100經驗一級」，
  沒有class-specific cap／達上限經驗歸零)。可編輯規則草案:`LevelCapFor(classByte)=99 if classByte in
  {0x1e,0x1f} else 40`；`if level>=cap: exp=0`。
- [~] **ch22_pre control-flow**：固定 16-slot deactivate loop、`0x11df2` immediate `palette_update` 已 lower 並通過 regression；共用 `0x24618` 9-pass indexed adapter 已完成，但本 handler 的 exact binding／進入時 raw roster-camera context 尚待閉合，不能僅因 renderer 存在就接 `story_ch23`。——本輪(2026-08-19續輪,`doc56`)複核:直接讀當前`campaign_full.json`，`story_ch23`(`type:"story"`，僅`lines`/`bgm`/`next`)確實沒有`handler_binding`欄位，現況未變，本輪只做直接讀檔核對，未新增反組譯。
- [x] **ch23/ch24 pre-handler**：FDTXT_024 index0/index1（14句）與 map23/70-slot、spawn group1、四段鏡頭已接 binding；`story_ch24` 已接回原版 pre-handler，compiler/campaign/battle regression 通過。
- [~] **ch23 post mapping boundary**：Docker Capstone 補齊初始 dialog `0x24c4c`→FDTXT_024 index2（scene0 line14、scene1 lines0–1），並固定 `0x24d22` latch/copy loop 的 raw 邊界；generated binding 已 mapping-complete，但 `0x11d40` palette、`0x24d22` indexed copy 與其他 renderer calls 仍 fail-closed，未接 `postbattle_ch23_persist`。——本輪(2026-08-19續輪,`doc56`)複核:直接讀當前`campaign_full.json`，`postbattle_ch23_persist`(`type:"cutscene"`，僅`next:"preparation_ch24"`)確實沒有`handler_binding`欄位，仍是無binding的空placeholder，實質缺口未變。
- [~] **ch24/ch25 pre-handler**：`0x24b4d` 四段 transition count 已 lower 為 `transition_reveal`（20/20/20/60、20ms/frame），FDOTHER#88 sub1 四次 SFX、index=-1 stop、handle release 已接，FDTXT_025 跨 scene 對白已接 `story_ch25`；尚待 indexed double-buffer visual adapter。——本輪(2026-08-19,`doc31`§9.6)查證:仍開放，且與doc31本節主題
  (`0x22253`)是不同的native位址(`0x24b4d` alternating-buffer present，非`0x22046`/`0x22253`)；
  `cmd/fd2/main.go`的`"transition_reveal"`case目前只建立`transitionRevealJob{remaining,delay,then}`，純計時
  骨架，沒有任何真實indexed緩衝區交替寫入。本輪未觸碰此項，如實維持D。
- [~] **ch25/ch26 pre-handler**：FDTXT_026 string0 已以 direct scene0 12-line mapping 接 binding（map25/70-slot、pan、acting76），`story_ch26` 已接回 handler。2026-07-29 已修正未加引號訊息計數，FDTXT_026 全量 63/63 count-aligned；這只關閉文字索引，不自動證明每個條件分支或 event61 玩家路徑。
- [~] **ch26/ch27 pre-handler**：FDTXT_027 idx0/3/4/5/6/7 已高信心對到 ch27 scene0 全部 21 句，新增六組 editable direct overrides 並接 `story_ch27`；共用 `0x24618` renderer 已完成。IDA／Capstone 又閉合 ch26_pre 返回時的 view `(camera 9,49; cursor 14,54; visible 5,5)` 與 selector0，`battle_ch27` 已資料化並由正式 runtime 消費。HUD 持續擁有者亦已閉合為 save-persistent gate A、process-persistent anchor 與 controller entry gate B=1，`battle_ch27` 已改用 `native_map_hud_inherited`，不猜章節常數；仍缺未修改一般玩家／CONTINUE 的同狀態 E2，以及 `0x24b14` item `0x64` branch 的其餘視覺行為，故不能視為完整章節流程完成。
- [x] **raw ch27 post／玩家第28戰流程（E1）**：FDTXT_028 string7 已精確對到 ch28 scene1 lines11–15。IDA Pro 9.4 直接確認主表 index27=`0x25464`，該入口準備對話參數後跳到 `0x231df` 共用尾段，依序執行 dialog／sync_party／set_chapter28；低位址來源是真實共享程式碼，不是 exporter 污染。authored binding 已接 `postbattle_ch28_persist→preparation_ch29`；舊接在玩家第27戰天空之鑰成功分支的 owner 已撤回，該分支只保留 raw ch26 已證實的 sync_party／set_chapter27。未宣稱 renderer parity或一般玩家 E2。
- [x] **ch28/ch29 pre-handler**：Docker 隔離 Capstone 與 IDA Pro 9.4 證實 `0x35822` 的 pan→spawn→300ms→`0x11DF2(0,255,255)` 全白→200ms→`0x11DF2(0,255,0)` 基準恢復（baseline restore）→redraw；舊稱「兩次無作用（no-op）調色盤更新」已撤回。2026-08-02 更正來源 `PUSH` 順序為 `(group,y,x)`，並以非對稱 ch27/ch28 呼叫回歸鎖定 group 與 x。FDTXT_029 idx7/idx8、map27/pan/acting86 binding 通過回歸，`story_ch28` 已接回可編輯 handler。
- [~] **ch26 post item-gate branch**：`0x25186→0x24b14(0x64)` 是前 16 個 runtime slots 的 exact inventory search，無 camp/activity filter；成功臂無 `0x1b8e7`，天空之鑰不消耗，之後才 sync→chapter increment→persistent cleanup。FDTXT_027 idx8–12 / idx13–16 對應兩臂；仍需把 visual/effect calls 與缺匙 editable branch 資料化，不能只保留 generic ending。
- [x] **ch26 success palette-ramp lowering**：Docker Capstone 定義 `0x25052(start,delay)` 為 inclusive `delta=start..0` 的 `0x11df2(0,255,delta)`＋每步 delay；compiler 已 lower immediate start 0..63。synthetic descending/zero/invalid 與真實 `ch26_post.json` 六個 5/4/3/2、80ms calls 均有 regression。這是 palette ramp，不是 generic fade；`0x24618` 已有專用 adapter，其餘 renderer effects仍各自 fail-closed。
- [x] **撤回 `0x1f882`=vsync/sync helper**：Docker Capstone 展開 `ebx=0..63`、每次 `0x11d40(0,255,ebx)`＋2ms wait，故是 64-step native palette fade-out。compiler 現保留 exact `native_palette_fade_out(0..63,2ms)` payload；它與 `0x25052/0x11df2` 的 delta ramp 不同，runtime 在 indexed DAC adapter 未完成前有 regression-protected fail-closed。
- [x] **native palette pulse (`0x35e5a`)**：Docker Capstone 完整 body 固定 `0x11df2(0,255,delta)` 的 inclusive 0→63（8ms/step）、400ms hold、再 62→0（8ms/step）。compiler 以 exact editable `native_palette_pulse` payload 保存不對稱端點，並拒絕帶參數變體；runtime 在 indexed DAC adapter 未完成前 regression-protected fail-closed，不以 story fade／delay 偽造。官方 IDA xref export 亦已納入此 helper 與 `0x33f78` staging wrapper。
- [x] **ch29 staging wrapper (`0x33f78`)**：Capstone stack trace 與官方 IDA function/xref 共同固定 raw push-order `[y,x,slot]`→`0x12cea(slot,x)`→`0x22253(slot,x,y,x,y)`；compiler 將七個 ch29 pre call-sites 保存成 `native_staging_present`，含 source regression。因 `0x22253` 的 indexed 11+6+10 presentation adapter 未完成，runtime 明確 fail-closed，禁止誤 lower 成 spawn／position／pan。
- [~] **ch29 post staged mapping**：四組對白已精確接到 ch29/ch30 authored lines；`0x12cea` focus、`0x25089` persistent cleanup、`0x17aa9` tick、dynamic palette loop、terminal `loadch` 與 `0x24618` indexed transition 均已有 runtime adapter/regression。`0x2bce5` 仍是未閉合的專用 ending renderer，因此整支 terminal handler 仍不接 campaign runtime。——本輪
  (2026-08-20,`doc35`§9,回應L862-867/899/1017-1020 cluster)誠實負面結論:窮盡三種獨立靜態方法(DWORD表掃描/
  CALL-JMP flow掃描/逐byte反組譯核對)均證實`0x2bce5`/`0x2c172`/`0x2c405`/`0x2c439`/`0x2c469`/`0x2c548`/
  `0x2c5e3`/`0x2c773`在目前`FD2Analysis3` project裡都不是有效指令邊界或已知資料/呼叫目標，blocker本身
  **未解除**。過程中意外發現一個結構相似但實為戰鬥指令選單party carousel的無關子系統(`FUN_0002ff01`
  @`0x2ff01`，與doc27§6.2/doc13發現的command presentation dispatcher是同一函式)，已排除是ending
  renderer。這是有價值的負面結果(避免下一輪重複走死路)，不構成renderer解封。
- [~] **ch29 post focus lowering**：`0x12cea` 已安全 lower 成 tile-step pan(22,23) 並通過 regression；cleanup與`0x24618`已接，仍待ending renderer。
- [~] **ch29 post persistent cleanup**：`0x25089` 已 lower 為 editable `reset_persistent_roster_state`，並以 runtime/campaign regression 鎖定清 transient、回填 MaxHP/MaxMP；本 handler 的主要剩餘 renderer gate 是 `0x2bce5` ending。——本輪(2026-08-20,`doc35`§9)同cluster誠實負面
  結論:blocker未解除，見上方「ch29 post staged mapping」項附註。
- [~] **ch29 post tick wait**：`0x17aa9(1)` 已 lower 成一個 editable delay tick 並通過 compiler regression；`0x24618` 已接，仍待 `0x2bce5` ending renderer。——本輪(2026-08-20,`doc35`§9)同cluster誠實負面結論:
  blocker未解除，見上方「ch29 post staged mapping」項附註。
- [~] **ch29 post dynamic palette loop**：`0x11df2(EBX,255,0)` 已依 direct 0x3e→0 loop materialize 成 63 組 palette/delay beats 並通過 regression；`0x1088d` 的舊文字-only 說法已由完整 `loadch` 取代。`0x24618` 已接，仍待專用 ending renderer。——本輪(2026-08-20,`doc35`§9)同cluster誠實負面結論:blocker未
  解除，見上方「ch29 post staged mapping」項附註。
- [~] **ch29 post terminal handler**：`0x25870 → 0x1088d` 不是純文字載入：它會載 FDTXT/FDFIELD、重建 unit buffer、從 persistent roster 複製 records、寫 map29 deployment 並 spawn groups。現已 lower 為完整 editable `loadch`（chapter30/map29/roster70/ch30 story+scenario），而非文字-only operation；`0x112a5` 已證實 persistent records 依 JOIN 呼叫 append，因此正常遊戲 slot order 可用 `partyJoinOrder` 表示。layout、動態 pan與`0x24618` indexed adapter已完成；`0x2bce5` renderer仍未完成，故整支handler維持fail-closed。`0x25970 → 0x31529` 返回後是 self-loop，這是 internal ch29／map29 最終戰的終局路徑，**不是** map28 戰後可接 `preparation_ch30` 的 handler。〔**2026-08-25 勘誤**：原文此處字面寫的是「`0x25970 → 0x2bce5`」，已用兩輪獨立 `ghidra_batch_probe.py`（`doc35`§9.11/§9.12）逐 byte 核對出 `0x25970` 的 CALL 指令目標其實是 `0x31529`（`call_scan(0x2bce5)` 全 exe 窮舉 0 筆，`0x2bce5` 從未被任何位置直接 CALL 過），self-loop 本身的觀察不變。詳見 `known_address_errata.json`。〕現行 final battle→generic ending 暫略過它；完成後以 terminal node 接入。——本輪(2026-08-20,`doc35`§9,
  此為cluster master item)誠實負面結論:窮盡三種獨立靜態方法均證實`0x2bce5`等位址不是有效指令邊界，
  blocker未解除；意外發現的`FUN_0002ff01`戰鬥選單party carousel子系統已排除是ending renderer，另留給
  「native command presentation」相關項目參考。〔**2026-08-25(`doc35`§9.14)逐項核對收尾**：對
  §9.2/§9.13的10個handler重測`function_bounds`(全數`in_function:false`，`-readOnly`分析未持久化，
  已知限制)；補測剩餘4個cluster位址(`0x2c405/0x2c439/0x2c469/0x2c5e3`)，其中`0x2c439`給出乾淨
  `RET`邊界、字面對上idx4 handler已記錄的終點`0x2c440`，`0x2c469`重新對齊後正是idx5 handler的
  `unit+6`mirror判斷式，`0x2c405`同樣重新對齊成合理除法慣用法，僅`0x2c5e3`反組譯不出結果；再把
  §9.2系統內容對11個項目逐項列出的具體訴求(FDOTHER#0x36/54、320×200 buffer、0→63/4ms、2000ms、
  FDOTHER#56/DATO、dialogue-frame grid 49次呼叫、input-skip)逐一比對，7項裡6項完全不符、僅
  mirror-flag判斷式`[0x53a45]+slot×0x50+6`慣例相同(不同段程式碼)。**高信心確認§9.2系統=章節結局
  montage這個假說可排除**，但**明確不撤回**`91-worklist.md`既有party montage記錄本身(來源獨立於
  §9.2/Ghidra，是官方IDA+玩家檔案regression)——最可能的解釋是L1592-1610那批記錄依據的IDA/Capstone
  session分析的是不同EXE build或誤記live記憶體位址為靜態linear位址(呼應
  `feedback_fd2_old_new_exe_address_instability`與本文件§9.5.4的既有發現)，不是內容本身造假。詳見
  `doc35`§9.14，含11項逐一unrelated/partial判定與下一輪建議(用byte-pattern重新定位而非信任字面
  hex數字)。〕
- [x] **ch29 post layout data**：`0x257b4 → 0x233c6` 的 20 slots X/Y/pose 與 camera `(16,18)` 已存入 editable binding，並有 compiler regression；`0x112a5` 已補證 persistent ordinal=JOIN chronology。整支終局 handler 尚未接 campaign（ending renderer仍fail-closed），不表示終局已可播放。
- [x] **ch29 post final pan**：`0x25937 → 0x135dd(11,12)` 已依 X-first/Y-second native ABI lower 為 tile-step `(264,288)`，compiler regression 通過；終局`0x24618`已接，仍待ending renderer。
- [x] **0x24618 indexed transition runtime closure**：editable schema與compiler保存tile/radial-radius、9-pass LUT `9..1`、5ms/500ms/4ms schedule及32-step `0x11df2` DAC ramp。Docker重讀證實`0x11df2`每次從immutable `[0x53a65]`取RGB再加delta／upper-clamp63，非對current DAC累積。runtime現在all-or-nothing preflight原始field、tile-aligned camera、actor provenance、selector cache、FDOTHER#3 LUT與FDOTHER#0 768-byte baseline DAC；`ComposeNativeTransitionFrame`逐pass執行terrain→first LUT→unit/foreground→second LUT→rect LUT→312×192 present。每個pass與baseline-derived DAC step皆需真實Draw acknowledgement，500ms tail固定30 ticks；拒絕時不改既有work/VGA。60Hz host無法重現5/4ms每次寫入的原始wall-clock，故只宣稱完整狀態／順序，不宣稱DOS timing parity。ch29 terminal仍由後續`0x2bce5` gate阻擋。
- [x] **RE-22046-INDEXED-PASS-SEQUENCE**：Docker Capstone 重讀 `0x22046`，新增 `fdother.ApplyIndexedTransitionPass` 保存第一 radial LUT→`0x127a9` middle redraw→第二 radial LUT→centered rectangle LUT 的不可省略順序；三段 geometry 先完整 preflight，缺 redraw/invalid second pass 不修改 buffer。LUT bank、double-buffer與Ebiten presentation已由strict runtime adapter消費。
- [x] **ch29 final 0x24618 arguments**：依 layout→focus 的 native scroll-offset writes，`0x25848` dynamic args 已定案為 tile `(6,6)`、radial radius `(10,step8)`，已寫入 binding/compiler regression並由runtime adapter消費；terminal handler仍因`0x2bce5`維持fail-closed。
- [x] **0x24618 pass-range/runtime boundary**：`0x22046` 的固定最後兩參數是 row range `[start_y,end_y)=[0,0xc0)`，不是 source_y 或 blit width；clip `0x138×0xc0`、radial step、`0x53a6d` LUT bank、`0x219ad` row clip均已接入strict indexed adapter。
- [~] **ch29 pre native unit presentation**：舊「6×(render+present+10ms)+2 ticks」結論已撤回。完整 `0x22253` trace 是前段 `0x22470` 11 次 LMI present/tick、中央 `0x22547` 6 次 10ms remap present+2 ticks、後段 `0x22656` 10 次 remap present/tick，合計 27 次 present；既有 `unit_present` metadata 不完整，維持 fail-closed。——本輪(2026-08-19,`doc31`§9.2/9.4)
  已找出精確根因:`HandlerUnitPresent`舊「六幀」schema對不上真實11+6+10鏈路，已被`NativeStagingPresent`
  新schema取代，但兩者在runtime端都被硬性擋下(`handler_compile.go`刻意讓舊schema編譯失敗，`main.go`對
  兩個op都fail-closed，`beatrunner_test.go`已將此固定成回歸測試——刻意設計，非遺漏)。也補上三個已知caller
  的視覺語意推論(ch29 staging=鏡頭跟拍+就地演出；戰鬥道具ID101瞬移=離場+進場；ch29終局handler=slot1淡出
  轉場)。但fail-closed本身**未解除**——沒有寫任何新的Ebiten job driver代碼(本輪任務範圍是反組譯記錄，
  非引擎實作)。worklist仍應維持D/未關閉。
- [x] **`0x22253` machine-readable schedule boundary**：`fdother.NativeUnitPresentSchedule` 現嚴格保存三段 11+6+10 的 27 個 present：FDOTHER#6 entries `0x72..0x7c`（各1 tick）、FDOTHER#3 entries `5..0`（各10ms，最後才2 ticks）、#3 entries `0..9`（各1 tick）。regression 拒絕舊 six-frame shortcut 或把兩 ticks 移位；這仍不是 geometry/buffer/Ebiten renderer adapter。
- [x] **`0x22470` first-phase destination ABI**：direct arithmetic 已保存為 `NativeUnitPresentByteOrigin(x,y,camX,camY)=0x8088+24*(x-camX)+24*456*(y-camY)+456`。它是 456-stride indexed work-buffer byte offset，最後 `+456` 不可漏；raw helper 保留 offscreen signed result，clip 仍屬 caller/renderer boundary。LMI decoder／unit-layer/present adapter 尚待組合。
- [x] **`0x22470→0x4e85b` LMI write primitive**：`0x4e85b` 逐像素透過 `0x4e916` decode，僅非零寫 destination，等同既有 `LMI1Entry.BlitAt` 的 preserve-zero 規則。`BlitNativeUnitPresentLMI` 已將 #6 cell 與 verified byte origin 組合，對 offscreen origin fail-closed；其後 unit redraw/present/tick 與其餘 phase 仍待 adapter。
- [x] **`0x22470` eleven-pass intro executor**：`RunNativeUnitPresentLMIIntro` 固定走 #6 entries `0x72..0x7c`，每一 entry blit 後強制要求 caller 執行一次 redraw/present/tick callback；不得折疊為一張最終畫面。short table／nil callback 均 fail-closed。尚未接 GUI renderer。
- [x] **`0x22547` LUT geometry correction**：重做 `0x22046` argument
  mapping，撤回舊「dynamic radius」斷言。radius其實固定11、scale固定16；
  dynamic值是`startY=trunc((24*raw53ABD+15)/5)*lutIndex`。新增
  `NativeUnitPresentContractStartY`、`NativeUnitPresentLUTPass`與完整
  6+10 `NativeUnitPresentLUTFrames`，保存兩radial及中間rectangle的
  split-row geometry；raw globals仍不猜玩法名。
- [x] **`0x22547/0x22656` BUFFER-TRANSACTION**：
  `RunNativeUnitPresentLUTFrame`嚴格要求完整`0x25680` work/snapshot與
  256-byte LUT；每frame先restore snapshot，再執行first radial、
  mandatory full-buffer object redraw、second radial、rectangle及present。
  防止錯誤累積16次LUT或略過中間sprite mutation；Ebiten snapshot producer
  與present scheduler仍待。
- [x] **`0x22253` INDEXED-FRAME-COMPOSERS**：新增exact
  `0x25680` terrain-only snapshot、atomic object-only `0x127a9/0x129ec`
  redraw、source`+0x8088` stride456→destination stride320的312×192
  viewport copy，以及`0x22470` intro／`0x22547/0x22656` LUT frame
  composers。剩餘runtime gate縮小為Unit raw pose/motion、cycle globals與
  phase-specific snapshots，不再籠統寫成「沒有indexed buffer」。
- [~] **ch29 post BIOS tick wait**：`0x17aa9` 已證實讀 DOS BIOS tick（約54.9ms），lower 為每 tick 3 個 remake frames 並通過 compiler regression；若要逐毫秒重現，需在 runtime 加 BIOS-tick clock adapter。
- [~] **native `0x22253` renderer adapter**：已釘死 `0x22547→0x22046` indexed off-screen blit 呼叫鏈。2026-07-26 stack-slot recheck：FDOTHER #81 的 nested `LLLLLL` allocation 只存 local、尾端 free，未傳 renderer callees，故不再叫它 frame/pixel source；`0x11eee` 只做背景/tile redraw。真正已見資料是 boot `0x111ba(FDOTHER,#3)`→descriptor base `0x53a6d`（`0x22547` 倒序 entries 5→0）與 FDOTHER#6 `LMI1` bank：230 entries，`0x22470` entries 0x72..0x7c（12×21、九個20×22、24×23），`+0x1f6`=entry0x7c。**修正舊斷言**：`0x22046` 有六個靜態 caller，不是 unit-present 專屬；它只**兩次**呼 `0x219ad`，後者逐 row 用 `sqrt(radius²-dy²)*scale/10` 求 clip span，再以 remap LUT in-place map pixels，之後 `0x22046` 自己對另一矩形範圍作同 LUT remap。`__CHP` 已釘死為 toward-zero；`fdother.ApplyRadialLUTRemap` 與 `ApplyCenteredRectLUTRemap` 都有 boundary／clip／256-byte LUT regression。**原本的中間 redraw 已證實會 mutation**：`0x127a9→0x127e0` 依 camera-relative object sprites 經 `0x4deda/0x4de56` 寫 `0x53a49`，不可合併兩 radial passes 或省略。個別 caller 視覺語意、descriptor/buffer adapter、Ebiten adapter 仍缺，`unit_present` 暫維持 fail-closed。
  ——本輪(2026-08-19,`doc31`§9.3/9.6)修正:確認§9.3列出的幾何/緩衝區交易(`fdother`/`indexedmap`兩package)
  **已完整存在且有30個回歸測試**，唯一缺的是Ebiten job driver這一層(仿`nativeIndexedTransitionJob`寫一個
  27-present state machine)，已用同性質的`0x24618`/`nativeIndexedTransitionJob`做出精確對照。**「可能已
  部分由`ComposeNativeTransitionFrame`覆蓋」的舊猜測已被本輪修正為錯誤**——`ComposeNativeTransitionFrame`
  服務的是`0x24618`(明確是不同native位址)，不覆蓋`0x22253`；兩者只是共用`ApplyIndexedTransitionPass`/
  `0x22046`幾何原語，不能因此判定898部分關閉。仍應維持D。
- [~] **chapter ending renderer (`0x2bce5`)**：已釘死 FDOTHER `#0x36`（十進位54）、320×200 雙 buffer、palette 0→63/4ms、2000ms hold、chapter26/29 分支文字與 fade-out；仍缺 ANI/FDOTHER compositing adapter，禁止把它吞成 generic ending。——本輪(2026-08-20,`doc35`§9,L899)
  同cluster誠實負面結論:無新進展。§9.2的phase-table/master-engine架構(param_2 event dispatch、per-slot
  tween、LUT轉場)如果日後証實ending renderer用的是同一種設計模式(不同位址、不同呼叫者)，可作為
  「這類native演出大致長怎樣」的參考藍圖，但目前不能當成同一份程式碼直接套用。

- [x] **shared object redraw compositor**：`0x127a9` 的 `0x127e0` 不是單純 loop bookkeeping：active roster entry 以 camera-relative placement 選 24×24 descriptor，走 `0x4deda` raw indexed-RLE 或 `0x4de56` palette-band-RLE 寫 `0x53a49`；尾端 `0x129ec` 又在同 buffer 疊 map/object layer。`+5 bit7` clear→raw、set→band 已由 direct branch 關閉。`BlitNativeUnitLayer` 現以 raw slot／pose／movement／base-frame／active gate、camera bounds、cycles 及 pixel shift 完整表達 steady unit layer，且 preflight 失敗不寫半張 frame；它不接 GUI。`0x53a61` 是 global raw-key cache 的 pointer blocks，runtime index 是回傳 `slot×12 + pose×3 + cycle`，而非角色 group。仍待將 terrain→range→unit→foreground→HUD→viewport copy 組成 caller adapter；在此之前不得把 `0x22046` passes 或 `unit_present` 接成 native UI。——2026-08-19稽核確認：`remake/internal/indexedmap/frame.go`的`ComposeFrame`(約476行起)已強制此 terrain→range→unit→foreground→HUD→viewport copy 順序並經本檔914行「steady native indexed map-frame scheduler」`[x]`收錄，caller adapter缺口已補上，僅本行未同步。
- [x] **`0x11cac` range-layer provenance**：Docker Capstone 釘住 redraw order 為 `0x11eee terrain → 0x122dc range overlay/mutation → 0x127a9 unit+foreground → 0x1acf3 HUD → 0x11eb0 viewport copy`。修正舊斷言：只有 modes1..5 展開固定 calls 到 `0x126f7`；mode6直接清 selected cell byte+3，7+直接return。`0x126f7` camera-bound 後以 `0x4deda` 寫 `buffer+0x8088`。
- [x] **`0x122dc` range call-table／asset closure**：Docker Capstone 完整直讀 modes 1..5，`fdother.NativeRangeOverlayPlacements` 保留原始 call order 的 1/1/5/13/21 個 `(x,y,descriptor)`；特別固定 mode3 centre=`#14`、mode5 的重複座標／不同 descriptor，禁止圖形化 normalize。`0x25c7d..0x25c92` 已證明 `FDOTHER#1→0x53a4d`；實檔 header 是 20-entry 24×24 four-mode-RLE bank，`0x126f7` 以 `base+6+4*descriptor` 選 #0..18 後 `0x4deda`。`DecodeNativeRangeOverlayBank`／`BlitNativeRangeOverlay` 以真實 resource regression 固定 456 stride、0x8088、camera clip 和 preflight。mode6 不呼 `0x126f7`，而是算 `4*(x+y*raw53ac1)+7` 後清 `[0x53a51]` 指向資料的一個 byte；drawable API 明確拒絕 mode6。native buffer/grid lifetime已接；mode6 production caller仍待。
- [x] **RE-RANGE-MODE-ZERO-NOOP**：官方 IDA 9.4 重讀 `0x122dc`
  證實 switch default不draw；Capstone另固定bootstrap `0x10483`
  先寫`[0x51a83]=0`再呼`0x11cac(1)`。故raw mode0是transient opening frame，
  不是persistent steady state。`BlitNativeRangeOverlay`現以byte-for-byte
  regression接受0為exact no-op；pure modes1..5 placement API仍拒絕0，
  mode6仍只走獨立field mutation。
- [x] **`0x122dc` mode6 raw-field／scheduler closure**：`0x108f0..0x10932` 載 FDFIELD composition 至 `0x53a51`、讀 signed `u16 width/height`；`0x4df4c`（2026-08-20訂正：原記錄的`0x4dbfc`是位址標籤錯誤——`0x4dbfc`落在無關的Watcom long-shift runtime helper`FUN_0004dbe7`中段、零xref、不是合法entry point；真正位址`0x4df4c`由loader`FUN_0001088d`在`0x1097a`以`PUSH [0x53a51]`/`CALL 0x4df4c`呼叫，與ch23_post beat34`0x24a92`呼叫同一函式、同一參數,詳見doc58續三十一）由 header 後的 4-byte cells 逐筆將 byte+3 初始化為`0xff`，再對 byte+2 mask `0x1f`。所以 mode6 的 `4*(x+y*width)+7` 正是 selected cell byte+3（event-high／raw blit-mode byte），不是 overlay sprite或抽象grid。`ComposeFrame`現按原順序在terrain後清selected cell、再畫unit/foreground，且只有full-frame成功才commit caller field；bounds/HUD failure regression保證atomic。這只閉合compositor primitive，尚未把未證實的global-selector6 owner接進production。
- [x] **`[0x51a83]` full-domain correction**：合法 IDA 9.4 完整 data xrefs 已保存於 [`fd2_51a83_xrefs.txt`](../data/ida/fd2_51a83_xrefs.txt)。撤回把它限制為`0..5`或稱「戰鬥訊息索引」：`0x15140/0x153b1/0x1bd14/0x1d188` 都是 zero-extended record byte `+2`；原 spell table 的 range 5/7/9 會產生7/9/11。`0x122dc`對>6不畫圖，但`0x115b6`仍以selector-1進`0x14742` target legality。battle raw state現保留writer可達的`0..0x101`；campaign JSON只允許有直接入口證據的 selector 0／1：ch26_pre 返回 battle_ch27 時為0，CONTINUE／post-bootstrap `0x1060c` 為1，避免靜態資料冒充其他互動writer。
- [x] **RE-INTERACTIVE-SELECTOR-LIFECYCLE**：Docker Capstone固定setup `0x10483=0→0x11cac(1)→0x105eb:0x11cac(0)→0x1060c=1`，並固定`0x1cff0` target entry寫`record+4+2`、cancel/effect期間暫寫0、exit恢復1。remake campaign/production frame現以selector1和FDOTHER#1 descriptor0呈現原生steady cursor，移除白框 approximation；target modal亦直接呈現完整call-table已閉合的selectors2–5，regression要求每一 selector 實際改變indexed VGA frame。selector6 mutation、7+ no-draw target visual、flash與indexed effect仍維持partial。
- [x] **`0x115b6→0x14742` cursor-confirm closure**：Capstone證實`0x14742`唯一caller為`0x1175f`。code5先拒絕；cell byte+3=`0xff`也在code4前拒絕；非`0xff`的code4接受；codes0..3以`[0x51a83]`（>1才減1）作strict Manhattan `< radius` roster count，count非零才確認。code6維持獨立relocation branch。新增`NativeCursorConfirmationAllowed` fail-closed raw-roster regression。同步撤回target code2=`camp!=1`舊斷言；direct branches是`camp==1`，即只選友軍。
- [x] **steady native indexed map-frame scheduler**：新增 `internal/indexedmap.ComposeFrame`，強制順序 `0x11eee terrain → 0x122dc range → 0x127a9 unit → 0x129ec foreground → HUD callback → 0x11eb0`。**更正舊 320×192 斷言**：direct `0x11d12..0x11d36` 是 width312、height192、dst `A0504`／stride320，即 VGA `(4,4)` 四邊留4px；compositor/regression已照此修正。HUD callback 缺失即拒絕，private work clone 讓任一 layer/HUD 失敗不污染 caller 的 work/VGA。
- [x] **native map HUD panel subpass**：`indexedmap.BlitNativeMapHUDPanel` 直接接 `0x1acf3` 已證實的雙 raw gate、FDOTHER#5 LMI1 #130（69×34）、`stride*157+anchorX`；entry geometry 不符即拒絕且不寫 destination。**撤回**把它當一般 LMI1 cell 的實作：#130/#0x83/#0x84 必走 `ParseLMI1FrameEntry→0x4e63d` four-mode `Frame`，`DecodeNativeMapHUDFrames` 已以真實 FDOTHER regression 固定。它只畫 panel，terrain/unit icon 與 AP/DP/HP digit paths 仍分離，不能把完整 HUD 標成完成。
- [x] **native HUD signed-number selector**：`indexedmap.BlitNativeMapHUDSignedNumber` 固定 `0x1aeb1` 的 raw LMI #0x83（非負 6×7）／#0x84（負值 6×5）選擇、absolute value、`origin+8` digit callback。callback 必填且 failure atomic，不把 sign 留半張；font、table value、AP/DP/HP來源與語意仍未命名。
- [x] **native HUD two-digit renderer**：`0x1aeb1→0x187d6` call-site 固定 glyph base #0x1f、width=2；`%0.5d` 被 patch 成 `%0.2d`，每位以 six-pixel advance 走 `0x16886→0x4e63d` Frame。`BlitNativeMapHUDTwoDigitNumber` 接上完整 #0x1f..#0x28（實檔 #0x20=5×8、其餘6×8）與 sign selector，超過99 fail-closed，不讓 native truncation變成可編輯資料的隱性行為。數值來源／AP/DP/HP語意仍不命名。
- [x] **native HUD terrain-icon subpass**：`0x1acf3` 在 panel 後以 `0x12e38` local word0（masked terrain descriptor）直接選 selected FDSHAP bank descriptor，`0x4deda` raw blit 到 panel `+6`。`BlitNativeMapHUDTerrainIcon` 固定此 10-bit selector／anchor並拒絕 bank 外資料；不以 PNG preview 或 terrain 名稱代替原始 source。
- [x] **native HUD unit-icon subpass**：`0x12c0d` 成功後，`0x1acf3` 以 unit+2 selector-cache slot、raw global state（3→1 alias）選 cached FDICON 12-frame block，raw blit 至 panel `stride*5+6`。`BlitNativeMapHUDUnitIcon` 有 cache/state/bounds regression；slot 不命名為角色或 portrait。
- [x] **native HUD terrain AP/DP subpass**：resolver raw control byte+1 經 `0x51a12/0x51a2a` 固定 0→(+5,0)、1/5→(0,0)、2/3→(-5,+10)、4→(-5,-5)。`NativeMapHUDTerrainAPDP`／`BlitNativeMapHUDTerrainAPDP` 用 exact AP/DP layout origin、sign和兩位 glyph renderer，invalid code／render失敗 atomic；不替 control byte 命名。
- [x] **native HUD persistent anchor branch**：Docker Capstone 實讀 `0x1ad2a..0x1ad5f`：raw `0x53abd>5 && 0x53ab9<3` 才寫 anchor `0xf2`，`0x53abd>5 && 0x53ab9>9` 才寫 `1`，其餘座標保留既有 `0x51a0c`；`indexedmap.AdvanceNativeMapHUDAnchor` 覆蓋兩臨界值與 retention，不把 globals 命名為未證實 UI 語意。
- [x] **native HUD HP subpass**：`0x1ae8e→0x1875d→0x187d6` 的 incoming stack 已逐項驗：unit unsigned `+0x40/+0x42` 傳 current/max 和 mode3；current==max 選 glyph base #0x1f，否則 #0x2a，畫 current 三位、每位 advance6；current>999 改畫 base+10。真實 #5 #0x29/#0x34 均18×8，兩 digit bank 僅 digit1=5×8。`BlitNativeMapHUDHP` 覆蓋 equal/unequal／overflow和 invalid-resource atomic，未將 unequal 命名成 damage。
- [x] **native full HUD assembly**：Docker Capstone `0x1ad72..0x1aea9` 確認順序 panel→terrain→AP→DP→optional icon→optional HP；`BlitNativeMapHUD` 以 `NativeMapHUDInput` 將所有已證實 subpass atomic 組裝。`OptionalUnit=nil` 嚴格代表 `0x12c0d` 或後續 raw unit-byte gate 的 skip，helper 不猜測 gate 角色語意；display gates 關閉時 no-op 且不要求資源。
- [x] **native HUD optional-unit gate**：`0x1ae2a..0x1ae47` 已直接固定：raw `unit+7==0x79` skip；否則僅 raw `unit+0x1f==0x0a && unit+6==1` skip。`NativeMapHUDOptionalUnitEligible` 覆蓋兩 skip 與兩放行，供 caller 正確產生 `OptionalUnit=nil`；三 byte 不命名。
- [x] **strict native indexed-frame entrypoint**：`ComposeNativeFrame` 把 `FrameInput` 與 `NativeMapHUDInput`/frame/terrain/unit/cache 綁為單一 `NativeFrameInput`，直接以 `BlitNativeMapHUD` 填滿 `0x11cac` 的 HUD slot，不再把完整 native frame 交給任意 callback。regression 驗 HUD bytes 進 work buffer 及 `0x11eb0` viewport copy；PNG/Ebiten presentation 仍是下一個獨立 asset/palette bridge。
- [x] **FDSHAP archive sprite-bank bridge**：`fdother.DecodeSpriteBankResource` 以 LLLLLL `ReadResource→fdicon.Parse` 解 FDSHAP even image resource，不混入相鄰 terrain-control resource；player-provided FDSHAP#0 regression 固定 288 個24×24 four-mode frames。這提供 native HUD terrain icon／indexed compositor 的真實 archive input，但 map↔resource pairing仍由上層明示。
- [x] **FDSHAP map resource pairing**：`DecodeMapTerrainResources(mapIndex)` 只讀已證 map N→image #`2N`、control #`2N+1`，並驗 bank frame count 不超 control-record count；FDSHAP map0 真實 regression=288 frame/1200 control bytes。明確拒絕從 tile count/cost 猜 map 資源。
- [x] **exported map-path binding**：`MapIndexFromAssetPath` 僅接受 legacy `assets`=map0 或 basename 精確 `mapN`，拒絕 suffix/負數/任意目錄；runtime 將用此 explicit N 餵 FDSHAP pair loader，不以檔名近似猜配。
- [x] **production native-map asset gate**：`Game.loadMap` 載入 HUD FDOTHER frames、FDOTHER #1 range bank、明示 FDSHAP pair、FDICON.B24、FDOTHER #3 LUTs與VGA palette為all-or-nothing `nativeMapAssets`；任一缺失/解碼失敗保持既有PNG renderer。bundle regression明確拒絕缺range bank；indexed-to-Ebiten presentation仍待camera/global-state bridge。
- [x] **indexed→Ebiten native HUD strict bridge**：撤回舊hardcode
  `gateA=true/gateB=true/anchor=1` partial presentation；`0x10010`證實
  gateA由native save plaintext `0x30d2`恢復。`drawNativeMapHUD`現只在
  `NativeMapHUDRuntimeState`、selector/cache cycle、unit+7/race/+6、
  raw maxHP全部有provenance時，一次畫panel/terrain/AP/DP +
  optional unit/HP；缺任一在draw前回legacy。`battle_ch01`、`battle_ch26`、
  `battle_ch27` 已用可編輯 view 與 `native_map_hud_inherited` 接上
  save-persistent gate A、process-persistent anchor 及 controller gate B=1；
  其他章仍須逐章 view 來源，且角色 raw record 不完整時照舊失敗即關閉，
  故此項是 strict bridge 而非全戰役畫面已 native。
- [x] **HUD unit-gate constructor provenance**：Docker Capstone `0x10d7f..0x10efc` 固定 runtime `+6=FDFIELD b0`、`+7/+8=FDFIELD b1`，與 editable `map_selector_key`/`battle_fig` 對齊；`+0x1f` 改由 portrait/resource branch 寫入，不能拿 portrait/class 直接代替。缺少該 resource byte 時 optional icon/HP 繼續 fail-closed。

- [x] **FDICON indexed asset primitive**：`internal/fdicon` 現直接 decode `FDICON.B24` header/offset table/24×24 four-mode RLE，保留透明與 dither spans；`Sprite.BlitAt` 是 raw `0x4deda`，`BlitPaletteBand` 是 `0x4de56` 的 `(index&7)+0x18`。**撤回 256-byte LUT 對應說法**（那是其他 renderer path）；fixture 與 player-provided 原始 1680-sprite regression 通過；仍未替代 roster/frame/timing/layer adapter。

- [x] **FDICON native selector primitive**：`Bank.SpriteFor(key,pose,cycle)` 嚴格表達已解析 B24 raw key 的 `key×12 + pose×3 + cycle` lookup（pose 0..3、cycle 0..2）並 regression；`0x127e0` 則先取 runtime `unit+2` cache slot 選對應 12-pointer block。它與 `0x287b5..0x2884c` 的 battle `unit+7 × 3` FIGANI selector 是不同 raw field；現有 exported visual id 的相等只在已驗證 roster 記錄成立，不能當 ABI alias。`NativeFrameIndex` 依 +4 movement offset 選 `0x3C0B/0x3C07`，將 global cycle 3 正規化為 1，`+0x26` 則強制 0；撤回「runtime +4 frame」說法，故沒有把它隱式接入 GUI。
  - [~] battle selector bridge：`battle_fig`→`Unit.BattleFig`→全螢幕 `newAtkAnim` 已可承載 split ABI，loader regression 固定它可與 legacy map `fig` 不同；constructor `0x10d7f..0x10efc` 已閉合 FDFIELD `b1→unit+7`，正式 exporter 已寫入該欄、舊 JSON 才 fallback。`fig` 不宣稱原版 field。
  - [~] map selector provenance audit：`0x10c50→0x11019` 是 global raw-key FDICON cache path；完整 constructor 已釘 FDFIELD `b0`（亦寫 native camp `+6`）。`0x11019` 只比對全域 key table，僅新 key 使用 caller archive pointer 建 block；player `0x10a25` 與 scripted `0x10b69` 都開啟 `FDICON.B24`。parser/exporter 現輸出 raw `map_selector_key=b0`；map0 30筆實跑為 keys `[0,1,2]` 並逐筆等於 camp raw code。`tools/sync_native_selector_fields.py --check` 現驗證全部 33 份版本化 map assets 的 `map_selector_key`／`battle_fig`／raw `native_record_byte8`；舊 scripted `native_identity` 已移除，避免把 FDFIELD `b1→runtime +8` 錯稱角色身分，且不覆寫其他人工校正數值。Scenario 現在以 party-first／group-order batch materialize，battle draw 只在整場成功時 slot→key；malformed editable input 會保留 legacy append 並禁用全場 native selector。撤回把角色表/DATO/素材 index 的相等值當成全域 mapping。下一步是 native indexed buffer/palette/layer composition，不得把目前 PNG/Ebiten selector adapter 寫成完整原版 renderer。
    - [x] player-party source split：`0x1088d→0x10a77` 先 copy persistent `[0x53bf7]` 0x50-byte record，再用 copied `+7` 作 `0x11019` key，回傳 slot 寫 `unit+2`。它不是 FDFIELD `b0` 路徑；slot allocation 順序必須保留這條 roster loop 的順序。
      Official IDA 9.4 address-only xref report再確認 `0x10a77` 屬於 `sub_1088d`，而 `sub_1088d` 的 callers 是 `0x205ff`、`0x25870`、`0x2c437`；不得將 selector initialization 當成只有一般 battle setup 才會做的步驟。
      `JOIN` constructor `0x112a5(join_id)` 直接寫 persistent `+7=join_id` 且 `+8=join_id`；`0x33499` 已閉合 `+8` character-ID lookup。因此 fresh player 的 map raw key=character ID，但只限這個 writer；不得回推 FDFIELD/NPC/general `fig` identity。另 `0x314a7..0x3157a` class-change flow 對 live roster `+7` 寫 UI-selected raw target，故 equality 不是 immutable；`0x11506` 的 full 0x50 runtime→persistent copy 會在任何 `sync_party` caller 保存它，唯 class-change 是否立即進這條 flow 待追。
    `fdicon.NativeSelectorCache` 已以 first-seen key→slot regression 表達 cache 部分；resource/key decoder 尚未接入 runtime。
    `KeyForSlot`／`SpriteForNativeSlot` 已閉合 slot→raw B24 key→`key×12+pose×3+cycle` 的 pointer-block lookup；runtime materialization 仍待。
    - [x] explicit raw-key materializer：`map_selector_key` 與 `battle.MaterializeNativeMapSelectorSlots` 現可按 caller supplied native order 建 first-seen slots；preflight 要求每筆有 0..255 key，missing/invalid 不改 unit/cache，絕不從 `Fig` fallback。`spawn_party` 已先物化玩家隊伍，後續 `AppendGroup` 共用同一 cache，正式 scenario 已保留 party-first→scripted order；不完整 batch 會禁用全場 native selector，story/direct-start/retry 不在此 E1 範圍。
    - [x] player JOIN/class-change split persistence：fresh `PartyMember.Fig` 僅在 verified JOIN initialization 種入 `BattleFig`／raw key；`ApplyClassChange` 依 `0x3157a` 更新後兩者、清舊 slot，保留 stable `Fig`（native `+8` identity），跨關 persistent overlay 完整帶回 split fields。battle/campaign/cmd regression 通過；renderer 仍不由 legacy `Fig` fallback。
    - [x] state atomic construction-order seam：`State.AppendNativeMapSelectorBatch` 持有單一 global raw-key cache，只有整批 explicit key preflight 成功才 materialize+append；regression 固定 party `[9,4]`→scripted `[0,2,0]` slots `[0,1,2,3,2]` 和 failure 不污染 state/cache。33 份 map asset 已有 raw keys；Scenario 已於 `spawn_party`／`AppendGroup` 接上 mixed construction order，缺 key 時保留 legacy append 但整場 native selector 失敗即關閉。
    - [x] persistent overlay boundary：`syncPartyFromBattle`／`applyPersistentStats` 保存 raw `+0x42` 與 `+0x46`，且不由正規化 HP／MP 反推。`MapSelectorSlot` 是每戰由 `0x11019` 重建的 battle-local cache result，不得由 persistent snapshot 覆蓋；回歸以既有 slot 7 證明 overlay 不修改它。
    - [x] **JOIN-112A5-PERSISTENT-RECORD-MATERIALIZATION**：IDA Pro 9.4 主判讀與 Docker Capstone 覆核固定 fresh JOIN 的 default/growth table 公式；`sync_native_join_constructor.py` 現從 32×0x18 defaults、32×0x0B growth 與 `fd2-reference-files.json` 產生雜湊綁定的 `native_join_constructor.json`。Go loader 驗證 EXE identity、row order、file offsets、raw strides；正常 JOIN→LOADCH 與 `scenario join_party` 共用 materializer，建立 identity／raw key、race/class、level/MV、command mask 及 `+0x42/+0x46`。凱麗 id12 初始 `+0x42=151`，event63 fixture 不再手填，也不從 ch27 近似 `hp=90` 反推。另修正友軍尚未轉為 Own 時被錯誤 camp gate 阻止建 persistent record 的舊缺陷。
    - [x] **JOIN-1145A-EQUIPMENT-RECOMPUTATION**：撤回「`sub_1145A` 尚未閉合」的舊斷言；raw helper、八格 `0x40` gate、item row `+1/+5/+3/+7`、signed/wrapping destinations 早已具直接證據。本輪把它接入正常 `JOIN 0x112A5` materializer：局部 0x50-byte transaction 先寫 raw inventory、base AP／DP／DX、HP／MP，再原子重算 typed AP／DP／HIT／EV；缺 item row 失敗即關閉。凱麗 fresh JOIN regression 固定 base `80/69/10`、items `0x3E/0xAC` 與 derived `100/79/110/15`。同輪修正 native save restore 遺漏 `+0x42/+0x46` provenance，以及商店 current stats 把 signed words 誤讀成 unsigned。這不宣稱保留原版 record 的未觸及 bytes，也不是 ch27 一般玩家時點 E2。
- [x] **FDICON native placement primitive**：`NativePlacementOffset` 逐指令重現 `0x127e0` 的 456-byte buffer stride、`0x75d8` origin、24-pixel tile 與 `unit+4 × {+0x720,-4,-0x720,+4}` direction offset；`+0x26` 才加入 native 0/1 pixel shift。它回傳 framebuffer byte offset，不把未證實的 framebuffer origin/layer/UI 自動轉成 remake screen coordinate。
- [x] **native foreground-terrain occlusion layer**：Docker trace 已把 `0x129ec` 定為 unit-sprite 後的前景補畫，但修正「每個可見 unit」的簡化說法：它先跳過 `0x1f183(slot)` true 的 raw gate（`unit+7==0x1c` 放行；其他 `unit+7` 的 class `0x13` 或 race `4/5` 跳過），再跳過 `0x3453e` inactive slot。**撤回**剛才將 `unit+7` 稱為 group 的錯誤：map sprite group 是 `unit+2`。`fdicon.NativeForegroundRedrawEligible` 以 regression 固定兩 gate，`NativeForegroundRedrawCells` 保留 eligible slot 的精確 `(x,y)`、`(x,y-1)`、移動 pose-neighbour 順序。`BlitNativeForegroundLayer` 現以 raw roster inputs 接上 steady `0x129ec→0x12ac6`：camera interval、bit7／bit8 descriptor、`index+1`、`0x8088` offset、raw/LUT-transparent branch 全部 byte-level regression；只在 supplied map 外的座標 fail-closed skip，不讀 unchecked native memory。Official IDA 9.4 再證明 `0x1366a` 的 scripted-step redraw 也做 `0x11eee` terrain→per-slot `0x127e0`→`0x129ec`，並在 `0x129ec` 後才進 `0x11eb0`／present；故不可只把 occlusion 掛在 steady `0x127a9`。range/HUD/VGA/Ebiten adapter 尚待。——2026-08-19稽核確認：`remake/internal/indexedmap/frame.go`之`ComposeFrame`已直接呼叫`ForegroundBank.BlitNativeForegroundLayerAt`並與range(`0x122dc`,見902-910行)、HUD(見914-925行)、viewport copy(`0x11eb0`,965行)同納入單一schedule，range/HUD/VGA/Ebiten adapter缺口已補上，僅本行未同步。
- [x] **FDSHAP raw-transparency / LUT branch boundary**：four-mode decoder 保留 opacity mask，`export_engine_assets.py` 以它輸出 raw `0x4deda` preview 的 RGBA tileset（map0 alpha `(0,255)`，opaque palette index0 不被猜透明）。**撤回**「mode3 一律等價 alpha」：`0x11eee` 的 entry `+3!=0xff` 走 `0x4dcc6`，其 mode3 對既有 destination 做 LUT remap，不是 skip。exporter 已保留 event high byte `native_tile_blit_modes`，供未來 indexed adapter；完整 palette/LUT compositor 與 `0x129ec` schedule 仍 fail-closed。——2026-08-19稽核確認：`0x129ec`已由`ComposeFrame`排入schedule(見901/959行)，`0x4dcc6` LUT primitive與terrain compositor亦已由本檔961-965行`[x]`收錄，僅本行未同步。
- [x] **native terrain frame selector**：`0x11eee` 對 visible FDFIELD cell 取 10-bit tile ID、讀 FDSHAP terrain-control byte；priority 為 bit8→`+2*flip(0x53a40)`，否則 bit10→`+trunc(0x3c0b/2)`，否則 bit4→`+flip`，其餘 base tile，隨後才選 `0x4deda/0x4dcc6`。`fdicon.NativeTerrainFrameIndex` strict regression 覆蓋 priority/negative truncation/bounds。這是 raw animation ABI，不替 bit 命名；GUI frame scheduler 尚未接。
- [x] **native `0x4dcc6` LUT primitive**：`fdicon.Sprite.BlitLUT` 精確保留 source write→`lut[source]`、mode3→`lut[existing destination]`、mode1 dither holes 不改寫三種行為，short LUT fail-closed 並 regression。它不選 LUT／不管 map camera/layer，避免把原始 pure blitter 誤接成完整 terrain renderer。
- [x] **native single-cell terrain compositor**：`Bank.BlitNativeTerrainCell` 組合 exact frame selector 與 FDFIELD `entry+3==0xff` raw／否則 LUT branch，regression 覆蓋兩支及 mode3 destination remap。camera-visible loop、LUT phase、foreground `0x129ec` 不在此 pure adapter 範圍。
- [x] **native visible terrain pass**：`Bank.BlitNativeTerrainRegion` 以 raw FDFIELD cell、FDSHAP 4-byte control records、map origin／explicit LUT 做 `0x11eee` row-major visible region，bounds fail-closed、regression 覆蓋 raw/LUT cell order。正常 `0x11cac` ABI 已釘為 `(buffer+0x8088,456,13,8,camX,camY)`，其後 range→unit→foreground passes 仍分離。
- [x] **native indexed viewport copy**：official IDA/Capstone 關閉 `0x11eb0` 為逐列 `memmove`；`0x11cac` 明確以 source `buffer+0x8088`／stride456、width312、height192 複製到 VGA `0xA0504`／stride320。regression 覆蓋 row stride、source/destination offset、4px border 與 fail-closed bounds；ch01 已接 Ebiten production presentation。
- [~] **native terrain/unit map HUD (`0x1acf3`)**：它在 `0x11cac` 的 terrain/range/unit+foreground 後、viewport copy 前執行，且須 raw gates `0x51aab`、`0x51aac` 都非零。`BlitNativeMapHUD→ComposeNativeFrame→drawNativeMapFrame` 已把 panel、terrain、AP/DP、optional FDICON unit與HP依原順序接入ch01 production frame；#130、hex #0x83/#0x84、digit/overflow banks、persistent anchor與raw cycle均有resource/runtime regression。FDOTHER#5 full-screen #22只在native admission失敗時作playable fallback，不再代表ch01現況。ch26 event61 所需 view/HUD 已另達 E1；此項仍為partial，因其餘 ch02+ 缺逐章view/gates/anchor來源、`0x12c0d` exact raw lookup predicate/order尚未閉合，且沒有原版DOSBox 320×200 HUD pixel oracle；高階global與resource artwork名稱仍不猜。——本輪(2026-08-19,`doc10`)推進:**`0x12c0d` exact raw lookup predicate/order已閉合**——完整反組譯確認由index0起遞增線性掃描`[0x53a45]`，逐筆比對`record+0==[0x53ab1]`(X)→`record+1==[0x53ab5]`(Y)→共用predicate`0x34894`(=byte[idx*0x50+5]&1)三條件AND短路序，第一筆命中勝出；並澄清`[0x53ab1]/[0x53ab5]`(camera-pan目標)與持久anchor游標對`[0x53ab9]/[0x53abd]`是不同全域。**「ch02+缺逐章view/gates/anchor來源」子項推進**:對全部`0x51aab`/`0x51aac` gate讀寫點做靜態呼叫鏈稽核，證實所有gate writer都是共用引擎函式(battle-turn wrapper+戰役主迴圈)，沒有任何一個逐章各自的caller——**通用機制已確認存在，非逐章特判程式碼**；殘留範圍縮小為純資料層的逐章初值(camera/cursor/anchor)來源盤點，已核對ch01/ch26/ch27三章，其餘27章仍待，但不再需要逐章反組譯新code path。DOSBox 320×200 HUD pixel oracle仍缺，不受本輪影響。
  - [x] HUD runtime provenance：data初值anchor=1、gateA/gateB=1；
    load `0x10010`由plaintext `0x30d2`覆寫gateA。anchor只由visible
    cursor row/column `[0x53abd]/[0x53ab9]`兩條branch改0xf2/1；doc14
    舊「框寬高」斷言已刪。`NativeMapHUDRuntimeState`保存raw bytes與
    persistent anchor，未materialize時不畫native HUD。
  - [x] camera/cursor runtime provenance：`0x11b48..0x11cac`四個direct
    helpers證實absolute cursor、camera及visible cursor identity。
    上/左在visible `<2`且camera非零時捲動；下在visible `>5`且未達
    `height-8`時捲動；右在visible `>10`且未達`width-13`時捲動。
    `NativeMapViewState`與keyboard/touch bridge保存原版13×8 window，
    並拒絕broken identity或diagonal raw move。
  - [x] inherited HUD state vertical slice：`battle_ch01` campaign 節點保存
    真實 FD2.SAV 的 camera `(1,13)`、cursor `(8,17)`、visible `(7,4)`；
    ch26／ch27 各自使用 pre-handler 閉合的 view。三者都由
    `native_map_hud_inherited` 取得 save-persistent gate A、process-persistent
    anchor 與 controller gate B=1；loader 要求 HUD 必須有 view，且原子拒絕
    不合法 raw bounds。固定 `(1,1,1)` 只保留給明確的存檔 fixture，不再冒充
    所有戰鬥入口初值。
  - [x] codec boundary：#130／hex #0x83／#0x84 不走 `ParseLMI1` 的 `0x4e916` cell codec；native `0x1aeb1` 有 literal `mov ebx,0x83/0x84`，明確走 four-mode `0x4e63d`。`ParseLMI1FrameEntry`／`DecodeLMI1FrameResource` regression 驗證 geometry 69×34、6×7、6×5 及 transparent decode。撤回剛才將 hex immediate 誤改成 decimal #83/#84（44×12／45×12）的錯誤斷言。
  - [x] optional unit selector：`0x1ae4d` 以 raw `unit+2*12 + state` 選 FDICON，state=3 alias 1，並在 panel `stride*5+6` raw blit；HP `+0x40/+0x42` 經 `0x1875d` 畫至 `stride*21+9`（mode3）。`NativeMapHUDUnitFrameIndex` regression 保留 selector，不替 state 命名。
  - [x] strict compositor layout／production bridge：`NativeMapHUDLayoutFor(anchor,456)` 固定 frame／terrain／AP／DP／unit／HP 的六個 byte destinations，拒絕非 native stride 與 69-pixel frame 出 320-pixel viewport 的 anchor；`BlitNativeMapHUD`已由`ComposeNativeFrame`接入Ebiten production full frame。此項不證明其他章節的raw runtime來源或DOSBox visual parity。
  - [x] HUD viewport-base／原版位置 oracle：Docker Capstone固定
    `0x11cfa`將`[0x53a49]+0x8088`與stride456傳入`0x1acf3`；舊adapter
    錯把HUD offsets套在allocation base，測試也固定了錯位。`ComposeNativeFrame`
    現改傳`work[0x8088:]`，HUD panel由同一source經`0x11eb0`落到VGA
    `(anchor+4,161)`，並保留full-frame atomic failure。
    `extract_fd2_video_frame.sh`先裁錄影的1408×880 centered viewport再回復
    320×200，撤回直接縮整張1440×1080影片的失真oracle。原版434.5秒與
    remake現對齊camera `(1,13)`、absolute/visible cursor `(8,15)/(7,2)`、
    tree terrain與`A -05/D +10`；screenshot hook也改走native cursor/camera/
    HUD anchor state machine。roster/event仍不同，完整pixel diff仍待。
  - [x] pre-handler→battle runtime roster handoff：原版`ch00_pre`
    `LOADCH(map0)`後由ACT0將party slots0..3從部署Y
    （scenario UI順序`0,4,9,30`為`[20,22,21,23]`）先依JOIN順序
    `0,9,4,30`重排成`[20,21,22,23]`，再上移六格成`[14,15,16,17]`，
    並於同一runtime array
    append initial groups；舊`resetBattle`卻清掉全部`storyActors`並重播
    `on_battle_start`，是原版錄影與remake可見roster不一致的根因。
    現僅在handler roster／party-scenario paths與battle node完全相等時
    carry已ACT/SPAWN的array、重建native selector slots、保留pending roster
    並consume已完成opening；direct start／retry／mismatch仍走部署重建。
    regression同時鎖定carry與direct兩條座標。新增完整runtime regression
    實際compile並跑完`ch00_pre`至`battle_ch01`：frontier精確為12
    （party4 + group1四筆 + group2四筆），party座標為
    `0:(7,14),9:(10,15),4:(8,16),30:(11,17)`；slot9的raw `+5`
    whole-byte writer結果為1，pending groups 3..7仍保留。
- [x] **native terrain renderer export bridge**：`export_engine_assets.py` 在帶 FDSHAP terrain resource 時輸出完整 `native_terrain_control` raw bytes 加既有 per-cell `native_tile_blit_modes`。map0 實測為 576 cell modes、1200 control bytes；因此 region adapter 不必把 normalized `cost` 當 native renderer input。
- [x] **native terrain renderer runtime bridge**：`battle.Load` 以 serialized `native_tile_blit_modes` 驗證 exact map provenance，但依`0x4df4c`（2026-08-20訂正，原記錄`0x4dbfc`是位址標籤錯誤，見1193行同項訂正說明）將 live `State.NativeTileBlitModes`全填`0xff`；`native_terrain_control`維持原始資料。dimensions/cell count/control alignment/tile bounds任一失敗即fail-closed。舊版把archive zeroes直接當live renderer state、造成整張圖走LUT的斷言已撤回。
- [x] **FDOTHER#3 LUT bank loader**：`fdother.ParseLUTBank`／`DecodeLUTResource` 嚴格解析 LMI1 directory 的 23×256-byte remap tables（非 UI LMI cell），fixture 與 player-provided archive regression 通過。現可把確證 LUT 交給 `BlitLUT`；map selector、palette timing、renderer layer 仍不猜接。
- [x] **native terrain LUT phase selector**：EXE `0x51A97` 的 20 bytes 直接讀得 `0..10..1` 往返序列；`NativeTerrainLUTIndex(0..19)` 並 regression。`0x11eee` 預設取此 phase 對 FDOTHER#3 LUT；explicit override state仍只保留 raw，不命名效果。
- [~] **indexed ending compositor core**：`internal/ending.IndexedCompositor` 現提供原版尺寸的 VGA/offscreen/work buffers、透明 `fdother` in-place blit、64000B copy、baseline-derived DAC、ANI、frame12..108、40/200-pass schedule與Ebiten獨立preview。timeline仍 fail-closed的理由已不是「沒有schedule executor」：現可跑到`0x2c548`，缺的是其後party montage dedicated indexed renderer與campaign terminal接線。——本輪
  (2026-08-20,`doc35`§9,回應原始行號1017-1020的montage解碼鏈)誠實負面結論:`0x2c548`/`0x2c5e3`等位址在
  本輪窮盡三種獨立靜態方法後驗證為不可達，montage renderer仍未解；意外發現的資源載入序列(BG.DAT→
  TAI.DAT→FIGANI.DAT×2→FDOTHER.DAT×2→per-角色資源)結構上與`native_2c548.json`描述的資產組合高度相似，
  值得下一輪重新獨立核對舊位址後比對是否為同一函式在不同EXE版本的位移結果，但本輪未能證實，不可當結論
  使用。
- [~] **ending compositor asset preflight**：正確圖源是 `FDOTHER_054.bin`（263655B、111-frame table），不是 `FDOTHER_036.bin`（408×138 的無關資源）；ANI #2 已可由 `internal/afm` 解出 26×320×200 frames。`internal/fdother` 已有 fail-closed raw table parser、原版透明 RLE in-place blitter，及 player-provided `FDOTHER.DAT` 的 `#0x36` archive loader；後者有與 raw #054 byte-for-byte 的 regression。schedule/branch adapter與phase0 preview均已接，下一個資產／renderer gate是`native_2c548.json`描述的FDOTHER#56、TAI#3、FIGANI/DATO party montage。——本輪(2026-08-20,`doc35`§9)同cluster誠實負面結論:無新進展，見上方「indexed ending compositor core」項附註。
- [~] **ending `#0x36` frame decoder contract**：`0x2935b` 以 `base+8+frame*4` offset table取 descriptor；`+0/+2` 是內嵌目的地 dx/dy，`+9/+11` 是 real w/h，payload 自 `+9` 以 transparent `-1` RLE blit。玩家素材 regression 現對 #054 全111幀逐一做 320×200 in-place decode。`0x2bce5` 的 frame0、frame9、frame12..108、兩段 frame-pair composite與palette/delay loop均已有runtime；`0x2c39b`已定案為DATO portrait ID＋current FDTXT string index並接兩段preview dialogue。舊「文字args尚無語意／缺完整prefix bridge」斷言已撤回；剩餘gate是`0x2c548` montage。——本輪(2026-08-20,
  `doc35`§9)同cluster誠實負面結論:無新進展，見上方「indexed ending compositor core」項附註。
- [~] **editable ending prefix timeline**：新增 `assets/endings/native_2bce5.json`，把已證實的 #054 blit、copy、delay、palette ramps、兩段 native composite loops 存成可編輯 IR。`0x2c39b` 第二 arg 已依 `0x15f84` direct ABI 定案為 current-FDTXT string index：final route idx2..7 → `ch30.json` scene1 lines0..13；chapter26 bad ending idx17..20 → `ch27.json` appendix scene lines1..4（原始 FDTXT_027 逐 string decode 實證）。第一 arg 已依 `0x1956b → 0x111ba(0x51a70)` 與 doc14 定案為 `DATO.DAT` portrait ID，timeline 改用 `portrait_id`。`internal/ending` 仍只接受 `recovered_prefix_only_fail_closed`，絕不將它視為可播放 ending；buffer/palette helpers、ANI/戰鬥段落 bridge 仍是明確 gate。
- [x] **天空之鑰缺失對話分支**：新增 `ch27.json` 分支 scene（FDTXT_027 idx13–16 共17句）並接 `inventory_gate_ch27_sky_key → story_ch27_post_sky_key_missing → ending_ch27_no_sky_key`；視覺效果仍待 direct RE，對話本身已可編輯且有 campaign regression。
- [x] **戰後 town/shop/preparation 外部交叉盤點（2026-07-20）**：subagent 查得公開攻略逐章列出羅德鎮、塞拉村、普里茲港等戰間商店／教會／整備，並有「第2章戰後獎勵」與「第6章戰後貝克威加入」等 persistent event 證據；只作流程旁證，不取代 EXE branch 證據。後續保持 battle→postbattle→town/shop/preparation→next battle 可編輯節點，禁止把 postbattle 直接接下一場戰鬥當完成。
- [x] **戰後 town/rest 反例盤點（2026-07-20）**：GameFAQs 明載第14章途中小鎮休息，且第22章至第26章前沒有 rest/buy/sell；因此 campaign 需保留 battle→town/rest 的可編輯節點，也要允許 ch23–25 連戰區間不插 town/shop。攻略只作外部旁證，仍須以 EXE/資產驗證觸發時機。

## 對話框 / 過場打磨(2026-07-05,使用者實玩逐項校正)
- [x] **對話框文字不覆蓋頭像**:上框(頭像在右)文字右緣止於頭像左緣前(commit 57c0e30)→ doc09
- [x] **對話框上下移入畫面**:下框上移(底邊可見)、上框下移(頂邊可見)、頭像置中框內(dc5ebb1)→ doc09
- [x] **框內底色=頭像底色漸層**:框內疊 40,69,138→56,85,154 漸層消接縫色差(dc5ebb1)→ doc09
- [x] **長對白分頁不截斷**:>3 行分頁,Enter 先翻頁翻完才換句;dlgWrap/dlgPageCount/dlgAdvance + dlgPage;
      Go 測試 dlg_test.go 驗全文保全(b81268d)→ doc09
- [x] **進場走位面向修正**:走完面向 actor 目標 dir(亞雷斯走到索爾旁面向他),storyWalkJob.finalDir(aaf5020)→ doc47 §11
- [x] **對話分頁捲動動畫**(2026-07-20)：原版確認有文字往上捲；remake 已實作 10 幀上捲（舊頁上移、新頁由底部進入、框內 clip），Enter 於動畫期間不跳頁，並有 dlg regression。GUI 實機截圖待補圖形依賴容器。
      目前翻頁是「瞬間切換」;要改成**平滑往上捲動**——按 Enter 翻頁時,當前內容往上捲出、下一頁從底部捲入。
      **使用者明示:不用依賴原版機制,自己寫平滑捲動即可**(原版有此效果,但捲動速度/幀數自訂,非 RE 值)。
      實作方向:翻頁時啟一個 `dlgScrollT` 計時器(數幀),繪製時把文字整體 y 偏移從 0 平滑插到 -行高×3、
      同時畫「當前頁下移出 + 下一頁自底部進」,期間 clip 在框內矩形;捲完才定位到新頁。
      動 `cmd/fd2/main.go` 對話繪製區 + `dlgAdvance`(翻頁時觸發捲動而非瞬間 dlgPage++)。
- [ ] **⬜ 自動結束回合**(使用者要求 2026-07-05,不急)：目前 remake 要手動按 Tab 才換回合；
      native end-turn 的完整 caller／team predicate／AI completion timing 尚未閉合。`+5 bit7` 只能作 raw
      set/test mutation，不在此 work item 命名 acted/turn，也不能直接宣稱「全員完畢→換邊」。需補 native
      state-machine evidence 後，才決定是否自動 endTurn、是否保留 Tab 提前結束。
      ——本輪(2026-08-20)推進:靜態RE前提已閉合(`doc11`)——三個入口(`0x13565`自動判定、`0x16F55`
      selector1「全軍前進」、selector3「結束回合」)與`0x1A30B`本體(own regen→友軍掃描→敵軍掃描→
      回合計數)完整回答caller/team predicate/AI completion timing三個子問題；仍缺:`0x1728C`(selector2
      子選單)本體語意，以及remake端尚未把這三個手動入口與`0x13565`自動判定接成統一Go實作(此為工程接線，
      非新RE缺口)——checkbox本身描述的仍是後者，故維持`[ ]`。
- [~] **handler 後半段 beats 解碼**(sonnet subagent 執行中 acb94c2):庭院/森林段走位/對話/fade 編排,
      供重建 palace_path/forest 節點(Ares 進場對話框位置、逐段走位轉向、索爾練劍、領頭跟隨、fade 換場)
      ——本輪(2026-08-19續輪,`doc44`/`doc53`§G,L1042)複核:`docs/knowledge-base/scene-decode/`目錄目前只有
      `ch1-meadow.md`(庭院段)與`ch1-throne.md`(王座廳段)，**沒有`ch1-forest.md`或同等的密林段
      scene-decode文件**——確認密林段(campaign節點`forest_duel`/`forest_discover`)仍是partial狀態，尚未
      有其他doc補齊。本輪未新增反組譯，僅確認狀態未變:handler層級的完整呼叫序列本身已是E0/E1(已由直接
      反組譯保存)，缺口是remake端`forest_duel`/`forest_discover`兩個campaign節點的beat排列尚未依此序列
      重排(現況用walk beat近似)，且act(0x5e-61)的acting_decoded幀資料尚未接上；下一輪若要關閉，工作範圍
      是remake端排程重寫，不是新的Ghidra反組譯。
      ——本輪(2026-08-20,`doc44`/`doc53`,回應L1042)新增`docs/knowledge-base/scene-decode/ch1-forest.md`，
      補齊上述缺口的解碼半部:FDTXT_032森林段對白全11條字串(40段)已完整解碼、acting id
      `0x5a..0x62`(90..98)共9個direct資源全解碼(raw frames+依doc50規則推算走位座標)、FDFIELD map31
      精確slot對照(索爾=slot0/亞雷斯=slot1/蓋亞=slot3/悠妮=slot4，另查出一個無對白的slot2佔位單位，疑為
      悠妮甦醒前倒地圖，與`0x32975(2)`隱藏時機吻合)。**仍未關閉，維持`[~]`**:座標推算僅套用doc50既有規則，
      沒有dosbox斷點交叉驗證(non-live)；`forest_duel`/`forest_discover`兩個campaign節點本身尚未依此重排
      beats(remake端排程仍是先前的walk beat近似，程式碼未動)。順帶修好`tools/export_acting_resources.py`
      對新版FD2.EXE(2026-08-14換基準後)完全跑不動的offset失準問題(signature search反查新offset，經106筆
      既有資料驗證)。

## 完成定義(反組譯研究)
全部資產格式可解(解包+解壓+轉現代格式)、核心數值表全 dump 並驗證、
主要遊戲規則演算法(戰鬥/移動/升級/AI)有反組譯依據、地圖可渲染、文本可讀可改。

## 2026-07-25 SDD gate（使用者要求先重審反組譯與 UI）

- [x] **可重現 UI/core regression container**：`fd2-go-test-local` 在 Docker build 時取得 Go modules、在 runtime 使用 `--network=none`；已實跑 `go test ./cmd/fd2 ./internal/... -count=1` exit 0。image 內含 Ebiten 所需 ALSA/X11/GL headers；這只驗 source build/test，並非原版 UI 畫面對照。
- [x] **UI-01 original title screenshot oracle**：新增隔離 `fd2-dosbox-screenshot-local` runner（SVGA/Xvfb/xdotool，原始 FLAME2 不掛載、只用 `/tmp` sandbox），連續 Escape 跳過 opening 後得到 320×200 `docs/figures/title-original-dosbox.png`。畫面證實 START／LOAD／CONTINUE 及初始 cursor；title input/save semantics 仍未關閉。
- [x] **UI-12 LOAD selector contract**：原版 DOSBox screenshot 與合法
  IDA 9.4 已固定四槽、slots `0..3`、↑↓ bounded（不 wrap）、
  Enter/Space confirm、Esc cancel；IDA 並固定 FDOTHER #13 entry16、
  FDTXT 索引、row/座標與 selected/normal 色碼。production 空槽已與
  DOSBox 全幀 RGB 相同；修改存檔 chapter1 有效槽排版亦全幀相同。
  native save boundary=`0x59cb`、
  record=`+0x312b+i*0xa28`（metadata=`0x28`、roster=`0xa00`）及
  rolling-XOR/checksum已有 adapter；JSON 仍是自有格式，尚未實作
  native 有效槽 restore／完整 roster 相容。——2026-08-19稽核確認：`docs/knowledge-base/57-ui-evidence-matrix.md` UI-12 row 與 `remake/internal/campaign/native_chapter_slot_restore.go` 的 `BuildNativeChapterSlotRestorePlan` 已證實 native 有效槽 restore 邏輯確已實作，僅本行未同步。
- [x] **UI-05 ch01 dialogue screenshot oracle**：START 分支得到 320×200 `docs/figures/ch01-dialogue-original-dosbox.png`，鎖住一種 lower/left DATO portrait、藍框、兩行文字與 page indicator；upper/right/control code/pagination 尚未由這張圖宣稱完成。
- [x] **UI-04 native command-grid remake oracle**：Docker/Xvfb 以 player-provided FDOTHER.DAT、ch01 materialized 悠妮 `initial_command_mask=[1,0,0,0]` 捕捉 [`native-command-grid-remake.png`](../figures/native-command-grid-remake.png)。畫面確證 command0 label「火炎術」與 selected-unit HUD 同時存在，故 raw mask→grid cell `(18,103)`→editable label→palette/font renderer 已接通；這是 remake runtime smoke，**不是**原版 DOSBox visual diff、full command gate 或 effect/UI 完成證明。
- [x] **FD2 remake SDD**：新增 `56-fd2-remake-sdd.md`，定義 UI contracts、battle→postbattle→town/shop/church/preparation flow、persistent party/save、native indexed renderer、E0–E3 證據分級與 milestone gates。
- [~] **SDD-1 UI evidence matrix**：以 Ghidra/IDA + Docker Capstone 重審 title/menu/action/target/HUD/dialog input dispatch；矩陣與 Capstone E0 已建立。2026-07-26 使用者合法 IDA Docker image 已實跑 `idat -A`／Hex-Rays，輸出 address-only [`fd2_xrefs.json`](../data/ida/fd2_xrefs.json)；script 已修正 IDA 9.4 移除的 xref-type API。分析 database 與 IDAPython config 均留 `/tmp`，repo 不含 license／binary／database，也絕不用 `kg_patch`。report 只補 call graph，未有資料流或 E2 不解除語意 gate。——本輪(2026-08-19續輪,`doc25`§批次盤點,L1065)複核:
  doc57「現有runtime evidence」表12行**全部**仍是`partial`，沒有任何一行升級成`verified`/`closed`。逐行殘留
  缺口性質分兩類:一類需要DOSBox-X即時比對(本任務範圍排除)，一類是可續靜態RE/remake接線工程；沒有發現
  任何一行的partial判定本身是過期的。此項本身是持續性靜態IDA/Capstone稽核工作，非單輪可關閉項目。
- [x] **SDD-1 baseline matrix**：新增 `57-ui-evidence-matrix.md`，以目前 runtime 行號把 UI-01…UI-12 的 partial/missing 與下一個 E0/E1/E2 問題固定下來；這不是原版 verified。
- [x] **UI-03 action caller recheck**：Docker Capstone 重審 `0x18890`，確認它呼叫 `0x18d8c` 取得 action result 並串接 `0x13488` path-walk／`0x13a44` target path；撤回「只是繪圖」類推，`0x18d8c` 本體仍是下一個 RE gate。
- [x] **UI-03 action switch closure**：Docker Capstone 完成 `0x18d8c`：`↑0=攻擊、←1=法術、→2=物品、↓3=待機／格子互動`；同步修正 `main.go` ring mapping 與 13/14/57 文件，撤回舊 screenshot-derived mapping。
- [~] **UI-03 native command ABI**：Docker Capstone 完成 `0x1c269→0x1cff0→0x4e516`：unit `+0x1a..+0x1e` 的
      五個 bitmask 逐 bit 展開為 command ID `0..39`，再索引 `0x619fd + 7*id` 的靜態 record。現行四格 ring
      只是 partial interaction；`0x159fa` 再證實 record `+5 <= unit+0x44`（current MP）的 availability gate。
      `0x10f7f/0x11399` construction 各 copy source 的 4 bytes 到 `+0x1a..+0x1d` 並清 `+0x1e`，
      `0x1d7fb` 可按 commandID/8 OR 回 runtime bit，故 40-bit ABI 初始為 32-bit source、可動態擴充。
      官方 IDA 再釘 confirm dispatch：IDs `0..8/0x18/>=0x1c` 走 `0x2a6bd` generic pipeline，
      `0x09..0x17/0x19..0x1b` 才經 `0x1d6c8` palette flicker→`funcs_1541f[id]`；這不把 command 0
      升格成 legacy spell effect。ID0 的 `0x2a6bd` entry 也只閉合 compositor（`funcs_2ac25[0]=0x26152`），
      尚未定位 HP/status writer。`0x1b6b7→0x1aa1d` 已排除為該 writer：前者只收集符合 post-resolution
      條件的 runtime record 三-byte資料，後者處理其後續訊息／掉落／互動。
      `0x1c75e→0x1c81f` 現已釘 command0 hit/damage：record `u16+0`×target class-ID（unit`+0x20`）multiplier/10，
      `rand()%100 < record+2`，命中後以 90..99.9% base 扣 `unit+0x40` 並 clamp0（`+0x42` 是 HP cap）。
      multiplier table 已與 file `0x51d96` 的職業魔抗 `resist_raw` 對齊（base=`dmg*raw/10`）；完整 target family
      仍待，尚不可直接替換為 legacy magic formula。
      selector `0x1d51d` 已鎖每欄四列的 variable-column grid：↑/↓ linear wrap、←/→ ±4、Enter/Space 重查
      MP gate、Esc cancel；`0x1ceed` 再鎖 x/y formula 與 label index=`0x1b9+commandID`。常駐 table
      已對齊 FDTXT_000，40 個 physical label slots 已由 `tools/export_command_labels.py` 匯出為
      `docs/data/command_labels.json`；label 不等於可達／有 gameplay effect。待 command producer、完整
      renderer/effect stack 後才可重製原版 menu。2026-07-25 再釘 `0x18d8c` wrapper 的 item-side raw
      preconditions：`0x1b83d` 找八格 inventory 中 equipped(bit0x40) 且 ID<0x80 的項目，失敗寫 output+0；
      `0x1b8a6==0`（八格全 empty bit0x80）寫 output+8。它們對應哪個圖示仍未有 callee/E2，禁止猜接 UI。
      2026-07-26 再以完整 `0x18d8c` dataflow 固定四個 disabled words 的順序為 attack/native-command/item/wait，
      `0x173e7/0x177fc` 僅選值 0；`0x1c269==0` 或 `unit+0x27!=0` 都寫 native-command `+4=1`。
      remake 已以 `NativeTransient[5]` gate raw command；撤回任何「`+0x27` 就是 legacy `Sealed`」的斷言。command22
      已知寫入此 duration；status 名稱與其他 writer 仍未知。
      confirm input 同步拒絕任何 nonzero disabled word，避免僅 render 灰 cell 卻仍執行該 action。
      action chooser 本體亦已完成 E0：availability=0 才可用 ↑/←/→/↓ 選 action 0/1/2/3，Enter/Space 確認、
      Esc 取消；四張 indexed asset 自中心做 4-frame 十字 slide，72×72 backup 每幀 restore。尚缺 resource
      anchor 與畫面 oracle，故仍不可將現有文字/ring UI 當成 original renderer。resource provenance 已補：
      `[0x53a89]` = `FDOTHER.DAT#2` 的 78-cell raw offset bank，`0x4e9e4` 直接貼 index pixels（0 preserve）；
      strict decoder/regression 已加入，仍未接 runtime renderer。
- [x] **UI-03 command-record/table identity**：`0x4e516` 的 IDs 0..35 與 EXE spell table 7-byte rows
      byte-for-byte 相同，故 record `+3/+4/+5/+6` 可安全正名為 `dist/range/mp/target`；全 FDFIELD 和
      character-default initial masks 的已見 ID 範圍為 0..30。36..39 僅是 pointer 可達的相鄰 data、label
      為空／系統訊息，未被升格為 spell。
- [x] **UI-03 level-up command producer**：`0x1e292→0x1d79c` 已釘為升級習得 command；growth row 的
      `learn_idx` 經 `0x4e4a2` 查 20×12-byte、最多六組 `(required_level,command_id)` 表，命中即 OR bit
      並顯示 FDTXT_000 #587「學會了！」。已導出 `command_learn.json`，保留 FF/FF sentinel；portrait→growth
      row 是 `0x4e4d1(unit+7)=0x620a1+unit[+7]*11` direct ABI；constructor 已證實 FDFIELD `b1→unit+7`，
      `State.GainExp` 已以 injectable table 接線，
      runtime asset `assets/data/command_learn.json` 已在每個新 battle state bind，不能用 legacy `Spells`
      偽造結果。
- [x] **UI-03 raw command-mask pipeline**：FDFIELD roster `b13..b16` 已由 parser/exporter 保留為
      `initial_command_mask`；battle runtime materialize 為可持久的 5-byte `NativeCommandMask`，並有原版
      order 的 ID expansion／`0x1d7fb` bounded-OR regression。舊 `Spells` 是 normalized approximation，
      不再冒充 raw source；尚未將未知 command effect 接入。
- [x] **UI-03 command availability gate**：新增 `battle.NativeCommandAvailable`／`NativeAvailableCommandIDs`，只接受 raw command bit、完整 0..35 `0x4e516` record 與 `record+5 <= unit.MP`（`0x159fa`）；36..39 physical bits、malformed book 與負 cost fail-closed。未併入 `+0x27` action-direction gate、target geometry 或 command/status 語意。
- [x] **UI-04 target-candidate provenance**：Docker Capstone 延伸 `0x1cff0→0x149f8`，確認 local command record `+3/+4/+6`、`command=0x1e` 傳 selector14、`0x149f8` 沿格步進並輸出符合 selector 的 unit index，另有 `0x17` special geometry 與 `0x2a6bd/0x1d6c8` effect paths；不再把 `0x149f8` 誤稱成傷害／完整 spell priority。
- [~] **UI-03 native target/effect state dispatch**：battle command grid confirm 現以 verified two-stage target contract 開啟原始 target cursor，並只白名單已有 state executor 的 IDs `0,13–16,20–22,24–29,31`；`main.go` 的 cursor highlight/confirm 共用 selected raw command ID 的 record `+3/+4/+6`，target entry materialize `record+4+2` selector，Enter 另以selected cell byte+3／selector／target code／完整raw roster執行 exact cursor-confirm gate，cancel與成功exit恢復selector1。未知 IDs、ID30 special cursor、缺 raw flags/record/resistance 仍 fail-closed。這接通 state/UI boundary，不宣稱 indexed effect renderer、SFX、完整 target visual 或所有 command semantics。
- [~] **UI-04 range geometry**：Docker/Capstone 已直讀 `0x14818`：它以固定 `0x61646` record 0 和原始 `(x,y,mode)`
      呼叫 `0x4e040`，mode 作 seed grid byte 並經 terrain cost gate 建立／更新 target grid；後續再有
      `|x-cx|+|y-cy| < caller radius` 的 marker 層、unit active flag／
      camp selector 輸出 slot；mode>=`0x10` 有另一路十字 clear。這只證實其中的曼哈頓幾何，
      另一 caller `0x14344` 證實同 helper 會以 unit `+0x20`（fallback 0x13）的 record 和 terrain table
      作格點 gate，故 SDD 必須保留 table+terrain+marker，而不能以單一 diamond 實作。
      `0x1cff0` stack-dataflow 亦已固定參數為 `(x,y,out,mode,radius,campSelector)`：special `0x17` 用
      `record+3`/radius 1，一般 path 用 `record+4`/radius 0 並消費既有 marker。尚未將這些 producer
      同武器 `range_min/range_max` table 完整對位；record producer 已鎖為 `0x4e516(id)=0x619fd+7*id`，
      故 `+3/+4/+6` 是 command ABI raw fields，仍不改寫為「所有武器 max inclusive」或 LOS 定論。
      ——已解(L1118,`doc32`§4.1,2026-08-19續輪):`0x14344`懸念已釐清——Ghidra `getFunctionContaining(0x14344)`
      直接回傳`FUN_00014237`，即本節一直描述的同一個`0x14237`，`0x14344`只是其中段的一個位址，**不是獨立的
      第二個caller**。因`-noanalysis`模式反編譯器未還原該處呼叫參數，精確byte存取(`+0x0b`或`+0x0c`)仍未逐
      位元組核對，但這是既有`0x14237` fail-closed描述範圍內的已知限制，不是新缺口；不改變「不得臆測raw
      `+0x0b..+0x0d`為通用射程」的結論。
      ——L1117(2026-08-19續輪,`doc25`§批次盤點)複核:command record `+3/+4/+6`對應`0x619fd+7*id`靜態
      spell table的`dist/range/mp/target`欄位(IDs 0-35，逐byte核對)已閉合，但這是法術/指令command的
      min/max，不是「武器」的min/max；武器類item row`+0x0b/+0x0c`餵給`0x14818`的`a4/a5`這條路徑已被
      明確撤回過一次「range_min/range_max」命名(remake改用獨立驗證的`weapon_range.json`)，本輪重新確認
      此撤回仍是最後結論。**AOE(範圍效果半徑)／LOS(視線阻擋)／不可用目標灰化的視覺回饋**三項在
      `doc32`/`doc57`現有內容中完全沒有對應章節，本輪未找到新位址線索，維持partial，留給下一輪專門
      排查(建議起點:`0x1ceed` command grid renderer的disabled-item繪製路徑，本輪未及查證)。
- [x] **RE-ATTACK-GEOMETRY-14237**：官方 IDA 9.4 `0x14237→0x14818` 閉合 caller-specific raw geometry：item row `+0x0b/+0x0c` 作 `a5/a4`；`mode<0x10` 時排除 Manhattan `<a5` 的 marker cells，`mode>=0x10` 走 cross 且不套 inner marker。新增 `battle.NativeAttackCandidates` regression；欄位、LOS、item effect 與 UI 仍不命名／不接猜測。
- [x] **RE-NATIVE-TARGET-BYTE5-GATE**：完整 raw roster 時，`NativeCommandTargets`／`NativeAttackCandidates`／`NativeCommandEffectTargets`／command-30 cardinal resolver 已以 raw byte+5 bit0 作唯一 active gate，新增 HP/OnField 相反值 regression；缺 raw 的舊 JSON／測試資料保留 E1 projection，避免猜測性擴大 native binding。
- [x] **RE-ITEM-ROW-CALLER-AUDIT-20260727**：官方 IDA 9.4 交叉檢查 `0x1145a/0x14237/0x1567e/0x1bbdc` 的 `0x4e56c` row consumers；確認 `+1/+3/+5/+7` 是裝備合成輸入，`+0x0b/+0x0c` 只在攻擊 caller 作 geometry inputs，`+0x0d` 另作 effect type dispatch。runtime table 邊界、其餘欄位語意與 normalized row 的一一對應仍未證實，維持 fail-closed。
- [x] **RE-ITEM-WORD-DELTA-TYPE8-10**：Docker Capstone dispatch、
  `0x1145a` base/equipment data flow 與 215-row cross-check 共同閉合
  type8/9/0xa：row `+0xe` 永久增加 base AP/DP/DX
  (`+0x37/+0x39/+0x3e`)，重算後移除來源 slot；IDs198/199/200 amount
  為 9/9/7。`NativeItemWordDeltaRouteForType` 現回傳 typed stat。
  presentation selector、道具名稱與 type17–19 不在此項證據範圍；
  type17–19 已由下方獨立 producer/consumer 證據閉合。
- [~] **UI-03 battle selector input**：Docker/Capstone 重檢 `0x19953`，確認它呼叫 `0x36d98` 讀 ASCII/scancode；Enter/Space/`0xe0`/`0x52` family 走確認回傳、`0x01`/`0x53` family 走取消回傳，`0x4b`/`0x4d` 更新左右選擇狀態。這是 battle selector 的 E0 input ABI，不等於已閉合 action enable/end-turn 或 D8 行軍確認。——本輪(2026-08-19
  續輪,`doc25`§批次盤點,L1138)複核:`91-worklist.md`稽核記錄與doc58都指向同一個未閉合點——doc58「續N」
  的一次live DOSBox-X觀測已確認選單結構(上=系統選單/左=行軍/右=設定/下=END，選「下」觸發結束回合確認框)，
  並規劃「先下斷點在`0x24618`再結束回合，讀EAX」作下一步，但該次live session尚未完成最後一步，本任務
  範圍排除DOSBox-X/WSL2故無法延續。純靜態面:`0x1a30b`家族與end-turn本身的呼叫關係，在現有doc26/56中
  沒有找到新的直接反組譯證據；維持partial，worklist判定(D，可續靜態，非必須live)不變。**注意**:另一批次
  (`doc11`，見上方L1038)已從end-turn team predicate/AI completion timing角度大幅推進，但那是「回合怎麼
  結束」的AI/orchestration面，與本項「D8/END選單本身怎麼呼叫到回合結算」的UI-03 dispatch面是不同問題，
  尚未完全打通。
- [~] **SDD-2 campaign transition matrix**：已從 `campaign_full.json` 逐一展開 30 個 battle 的 `on_win`，
      明確保留 town/shop/church/preparation/inventory-gate/ending 節點與連戰例外，表格已寫入
      `56-fd2-remake-sdd.md` §5.1（E1 editable graph）。仍待逐列補原版 handler E0／DOSBox E2 證據與 save/reload regression，
      未把 authored graph 當作原版已驗證。
- [x] **RE-CAMPAIGN-LOOP-25DE5**：官方 IDA 9.4 閉合外層戰役順序：phase1→固定 `0x22e5c` interlude；phase2→停止 BGM→`funcs_25e23[chapter]` post-handler→`0x2cad7` gate；僅 gate 回傳 zero 才進 `funcs_25e3a[chapter]` 與下一戰 BGM `0x51e63[chapter]`。table entries／`0x2cad7` 的具體 town/shop label 仍 opaque，但已明確撤回「勝利直接接下一戰」的錯誤模型。
- [x] **RE-TOWN-HUB-GATE-2D093**：官方 IDA 9.4 閉合 postbattle hub 分派：`[0x5412b]` option0→`0x2fc85` hotel/inn、1/3→`0x2e341` shop family、4→`0x3072f` church、2→save/confirm 後 `0x318ad` preparation；各 facility 回 hub 並恢復 track10，下一戰 BGM 仍由外層 `0x25de5` 選取。Docker raw bytes 確認 `byte_526b9[22..24]`、`[27..29]`=`1`（preparation-only），`[0..21]`、`[25..26]`=`0`（selectable town hub）；逐章文字與 E2 畫面仍待。
- [x] **RE-HUB-SUBSCENE-CALLEES**：官方 IDA 9.4 閉合 `0x2e341`／`0x2fc85` 的 raw subscene boundaries：shop family 依 selection/resource 走 `0x2f0b0/0x2f642/0x2f883/0x2f8ea`，hotel family 走 `0x2ffa5/0x30012/0x301f4/0x197e5` preparation path；各自保存 indexed fade/return-to-hub。callee 高階服務名未證實者只留 address-level，不接 normalized menu 語意。
- [x] **RE-CHURCH-SERVICE-SELECTOR-2D7BD**：官方 IDA 9.4 閉合教會 selector：`0x2d7bd` 只讀左右 raw scancode `75/77`，四項 `0..3` 循環；Enter/Space (`28/57`) 回 `1`、Esc (`1`) 回 `-1`。`0x3072f` 的 confirmed raw dispatch 為 `0→0x2ffa5`、`1→0x2f8ea`、`2→0x30dc3`、`3→0x31385`；`0x2d669` 的 transition 已補證清除區、`0x526da` signed cell offsets `[-39,-13,13,39]`、open/close divisor 與 stride `0x140`，仍不猜服務名稱或畫面排列。remake `AdvanceNativeChurchServiceSelection` 與 UI 已改用左右循環，未知 callee/renderer 仍 fail-closed。
- [x] **UI-CHURCH-MENU-INDEXED-2D669**：合法 IDA 9.4 重讀固定 FDOTHER#14 entries3/5/7/9 為四個 normal cell，3/4、5/6、7/8、9/10 為 steady normal/pulse pair，原版實檔均24×20；目的基準 `(240,169)`，兩份位移表 `0x526da/0x526ea` 都是 `[-39,-13,13,39]`。`0x2d669` 每 pass 先 restore 104×20、palette74 的 cleared source，再用 opening divisor4/3/2/1或closing1/2/3/4透明 blit並present；更正舊斷言，只有closing在第四幀後restore cleared source。`0x2d85f(0)→0x2d9fe` 以兩BIOS tick gate令counter mod4前進、selected variant=counter/2。`0x3072f` stable base亦已exact合成FDOTHER#5 raw dialogue grid/four-mode digits、#14 entry1、DATO#131 frame0及FDTXT585/586。runtime用獨立draw-ack job接四幀opening／closing＋cleared-source restore，route side effect延至close完成；保存[`native-church-menu-indexed.png`](../figures/native-church-menu-indexed.png)。raw service0及未證實callee仍fail-closed，不以 authored服務名稱取代。
- [~] **RE-CHURCH-RAW-SERVICE-LISTS-2E6B8**：官方 IDA 9.4 閉合 `0x2e6b8/0x2df6b` bounded two-column selector。`0x2f8ea`是church raw1與shop service3共用callee；掃八格 signed flag非負 item，FDTXT510/511/512＋`0x1b8e7→0x1bb8c→0x1b750`閉合物品轉交且不改gold。來源／目的原版 roster、mode1 item list、full feedback與6-open/5-close已接；目的全party roster不排除source，self-transfer現依raw順序重排。保存[`native-transfer-item-indexed.png`](../figures/native-transfer-item-indexed.png)與[`native-transfer-full-indexed.png`](../figures/native-transfer-full-indexed.png)。仍待 DOSBox E2 visual/input diff，故維持 `[~]`。
- [x] **RE-CHURCH-INVENTORY-TRANSFER-1BB8C**：官方 IDA 9.4 閉合 `0x1bb8c(destination,item)`：掃八格、第一個 flag byte `<0` 的 cell 寫 flag `0` 與 item byte，成功回 `1`，滿格回 `-1`；配合 `0x2f8ea` 的 `0x1b8e7(source)` 前置，raw topology 是來源→目的角色的物品轉移，目的格為未裝備。新增 atomic `battle.TransferNativeInventoryItem` 與 full-destination regression；constructor `0x10c50` 的八格 flags 已資料化，church source gate 不再把 `Equipped` 當成 native signed predicate；未將 raw index 1 命名成高階服務或宣稱 native renderer parity。
- [~] **UI-CHURCH-REVIVE-30DC3**：official IDA 閉合 `0x30dc3→0x309ff/0x30c22/0x30a47`。候選只看 roster record `+5 bit0`，不再以 `HP<=0` projection 猜測；費用為 `word_52669[raw class +0x20] × raw level +0x21`，不再自行把 Lv0 提升為1。remake 已接 stateful 三列名單（sprite/name/race/class/currency/五位數fee）、FDTXT590 的 FFFC名字／FFFA費用／FFFE換行、Yes/No，以及 list 6-open/5-close。第二次 IDA caller 重核刪除「確認一律choice4+dialogue5關閉」的錯誤斷言：原版 `0x197e5` 先只關choice四幀；不足金在仍開著的question第三行 `(12,157)` 寫FDTXT504、`0x16c57(1)`等待後才`0x2d31b`五幀關框；無候選則FDTXT588、`0x16c57(0)`。兩條 indexed message lifecycle已接。成功 `0x2f4c6` 因 hub selector固定4而只走case4：FDOTHER#14 entries23..31 sequential transparent blit到 `(147,32)`、每幀2 BIOS ticks，DAC 0→62/62→0每步4ms，`0x17aa9(10/5)`是相對前次latch而非額外hold；monotonic indexed timeline與原版資源 regression已接。再次指令級重核刪除「`sub_25977(17/11)`是PCM SFX」錯誤斷言：它是`play_bgm(track,loop_count)`，直接載FDMUS track17/11並各設loop count1；`playBGMCount`已依動畫前／後時序接入。仍需DOSBox E2視聽diff，故維持 `[~]`。
- [x] **RE-INVENTORY-CONSTRUCTOR-FLAGS-10C50**：官方 IDA 9.4 閉合 constructor 八格 flag writes：cell0=`0x40`；source byte0=`0xff` 時 cell1=`0x80` 並將 source byte1 放入 cell0，否則 cell1=`0x40`；cell2..7 依 source `0xff` 為 `0x80` 否則 `0x00`。新增 `NativeInventoryFlagsFromSource`／signed gate regression，`Load`/`PartyUnits` 持有 raw flags；修正 `0x2f8ea`「只選未裝備」錯誤斷言，`0x40` equipped 亦是非負可選 cell。
- [x] **RE-CHURCH-RAW-0-17AED**：官方 IDA 9.4 與 Docker 指令級重讀固定 `0x2ffa5→0x17aed(actor)` 是單 stack actor（Hex-Rays 第二參數為 artifact）：`0x17e0b(actor)` item/status staging→key wait→`0x1c269(actor,0)` gate→可選 `0x1ceed(actor,-1,...)` command/MP overlay→key wait→restore；body 無 persistent writer，因此撤回「能力服務」命名並定為唯讀角色資訊／狀態 presentation。remake 已接 `0x2e6b8/0x2ea90` 兩欄六人 roster、6-open/5-close+restore，以及 status 12-open、bottom 7-close/7-open、`0x1ceed` FDTXT441+ID/cell92/MP digits、12-close+restore後重開名冊；全部由 Draw acknowledgement 推進。保存 [`native-status-command-indexed.png`](../figures/native-status-command-indexed.png)。command effect/target 不屬此唯讀 service，仍由 UI-03 fail-closed。
- [x] **戰場進入分割滑動原語**：官方 IDA 確認 `0x1f42d/0x1f1cc` 使用 FDOTHER#5 LMI1 第 `0x52` 項，以 456 列距在 `(85-offset,82)`／`(165+offset,81)` 執行 `100,75,50,25,0` 五步，每步呈現後還原；新增 `NativeBattleEntrySplitSlideSteps`、邊緣裁切繪製、回呼執行器與回歸測試。2026-07-29 直接重讀呼叫者 `0x1a30b`，確認它處理戰場記錄與 456 列距戰場緩衝；撤回把這項列為 UI-11 選人視窗動畫的錯誤分類。未命名 MAP/TURN，也未接未證實的行軍輸入。
- [x] **RE-RAW-1A866-FIRST-LOOP**：Docker Capstone 重新讀 `0x1a866` 的第一個 raw loop，固定 `+0x25!=0`、`+0x06==selector`、`+0x05 bit0==0` 三個 gate，以及 `+0x40 -= +0x42/10`、負值 clamp、global divisor write；新增 `ParseNativePreparationRecord`／`NativePreparationEligible`／`NativePreparationAdjustedWord40` 與 malformed/gate/clamp regression。此項只保存 address-level raw branch，不命名 preparation/UI/deployment；同函式第二段 `+0x22..+0x27` decrement 另由 transient lifecycle 條目追蹤。
- [x] **UI-11 preparation dispatch table**：Docker Capstone 固定 `0x1a813` 的 `base+3*i`、16 slots、`+3/+5` gate 與 `+4` function-table index；新增 `FindNativePreparationDispatch`，保留重疊 3-byte raw layout、short-table fail-closed 與多重命中 regression，不執行未命名 callback。
- [x] **UI-11 preparation timer transition**：Docker Capstone 固定 `0x1a941` 對 0x50-byte record 的 selector/inactive gates、六個 `+0x22..+0x27` counter decrement，以及僅 1→0 才產生 `0x1e1+index` downstream source；新增 `TickNativePreparationTimers` in-place raw planner/regression，不命名狀態或效果。
- [x] **UI-11 preparation input ABI**：Docker Capstone 固定 `0x19953` 的 raw scancode branches：`E0/52/1C/39→1`、`01/53→-1`、`4B→cursor0`、`4D→cursor1`，其他輸入繼續等待；新增 `ApplyNativePreparationInput` 與 regression，不把 return 1/-1 猜成 YES/NO。
- [x] **post-resolution raw command stream correction**：重新對照 FDTXT_000，確認 `0x1aa1d` 的 `0x1b0..0x1b3` 是掉落／互動訊息，不是 preparation UI；撤回 `UI-11 preparation command stream` 命名。保留 `0x1ac62` 的 `base+3*i` `{kind byte,payload word}` raw parser（kind 0/1/2/3 observed branches），改名 `ParseNativePostResolutionCommands`，不接 D8。
- [x] **RE-PREPARATION-INPUT-32004**：Docker Capstone 重核 `0x32004` 的雙位元組輸入介面：`0xe0/0x52` 與 `[0x53a8d]==0x20` 都正規化為 `0x1c`；只有未走前述分支且 `[0x53a8e]==0x53` 時才回傳 `1`，其餘保留初始值 `0x10`。呼叫端 `0x31a29` 對 `1`／`0x1c` 的後續分支亦已記錄。先前「`0xe0/0x52` 原樣回傳」的錯誤已修正；`NormalizeNativePreparationKey` 只保存位元組介面，不替按鍵或畫面命名。
- [~] **UI-11 原版整備選人主畫面**：Docker Capstone 重讀
  `0x318ad..0x32004`，固定三區背景、兩組二位數、10 欄角色格、游標先畫、
  已選角色上移三列且走 `0x4deda`、未選走 `0x4de56`，以及左右 ±1／
  上下 ±10 的邊界。新增混合解碼資源包、原子合成器、原始 selector key
  生產接線與真實 FDOTHER／FDICON 回歸；局部證據圖為
  [`preparation-roster-compositor-partial.png`](../figures/preparation-roster-compositor-partial.png)。
  此圖以原始圖像索引 0～19 建立，明確不是 DOSBox 截圖、正常戰役名冊或
  `FD2.SAV` 證據。游標角色的右上狀態已直接重用既有、真實資源驗證的
  `0x17fc0` 合成器與完整 0x50 位元組記錄；缺原始欄位即整張退回。
  `0x1297d` 待機週期已重用 `fdicon.AdvanceNativeMapSpriteCycles`：
  有號 BIOS 低字差值 `>4` 或回繞才前進 raw state，繪圖再由
  `NativeFrameIndex` 把 3 映成1；生產可見序列為 `0,1,2,1`。
  `0x31d3c` 穩定最終確認亦已接：`0x1956b(0x4b)` 的 FDOTHER #5 對話框與
  DATO #75、FDTXT `0x292` 的 `(95,119)` 起筆、`0x16559(0)` 最後肖像覆蓋，
  再疊 `0x19953` 的 FDOTHER #2 Yes／No。保存
  [`preparation-confirmation-compositor-partial.png`](../figures/preparation-confirmation-compositor-partial.png)；
  這是 E1 原始資源合成，不是原版實機。完整生命週期也已接正式路徑：
  `0x1956b` 六幀開框、`0x19953` 四幀展開與兩 tick 脈動、
  `0x197e5` 四幀關選項、`0x2d31b` 五幀關框，再呈現原畫面後才執行結果；
  每一步只在 Draw 確認後前進。保存
  [`preparation-confirmation-lifecycle.png`](../figures/preparation-confirmation-lifecycle.png)。
  下一門檻是跨畫面的行程全域初始相位，以及合法晚期存檔的同狀態實機差分。
- [~] **SDD-3 UI shell vertical slice**：已新增 `TestUIShellVerticalTraceKeepsPostbattleTownAndShopBoundary`，以 title confirm、story→battle、battle win→editable postbattle、town→shop→town 的同一 state trace 固定「戰後不可直跳下一戰」；既有 town/shop/preparation 截圖 artifact 與 Docker/Xvfb regression 可重跑。battle field/action/dialog 的同一條畫面 trace、原版 DOSBox pixel differential 仍待補齊。
- [ ] **SDD-4 native renderer re-audit**：完成 resource provenance 與 indexed buffer contract 前，不得把 finale figure-fade／ending prefix 宣稱為完成。
- [x] **RE-UNIT-STATIC-TABLES**：以 Docker 實際 FD2.EXE 產生/驗證 raw fixture：高 branch `b1-0x44 → 0x61af9` 68×10；lower branch `0x61da1` 32×24／`0x620a1` 68×11。constructor caller 的 level 公式與 `+0x42` join 已由 Capstone 固定；`export_units.py`／`sync_native_selector_fields.py` 將 raw provenance 輸出到 33 張 editable map asset。未被 table 覆蓋的 selector 與 HUD renderer consumer 仍維持 fail-closed；`0x619fd` 不屬於 constructor。
- [x] **INDEXED-FRAME-TEST-CONTRACT**：修正 native compositor fixture 的 `work+0x8088` 來源邊界、range descriptor bank 與 viewport copy 座標；Docker indexedmap regression 通過，未放寬 production fail-closed 條件。
- [x] **REGRESSION-BLOCKERS-2026-07-26**：Docker image 內建 Xvfb 已納入完整 regression command；ch14 final dialogue line mapping 依 FDTXT_015 count-aligned continuation 修正，ch16 conditional spawn 僅 branch-local after LOADCH。完整 suite 通過，未刪除有效 assertion 或放寬 fail-closed compiler。

## 2026-07-20 ending prefix playback slice

- [x] **0x2bce5 可播放前綴（仍 fail-closed）**：`internal/ending.Player` 現以毫秒 clock 依原序執行 frame0/copy/hold、ANI#2、baseline-derived ramp、兩段native text、frame12..108、40/200-pass composite，再銜接`0x2c405`的500-pass scroll。玩家 `FDOTHER/FDTXT/ANI` integration regression精確停在`0x2c548` montage gate；不再沿用「只到第一個text、text/composite一律blocked」的舊描述，也絕不改用generic ending。
- [x] **獨立畫面 oracle**：`FD2_ENDING_PREFIX=1` 會讀玩家自備 DAT，將 indexed VGA DAC 轉為 320×200、2× 顯示於 Ebiten；它不接 campaign，故無法假裝原版終局已完成。可用 `FD2_FDOTHER=/path/FDOTHER.DAT`、`FD2_FDTXT=/path/FDTXT.DAT`、`FD2_ANI=/path/ANI.DAT` 指定素材（FDTXT預設同FDOTHER目錄），並沿用 `FD2_SHOT` 截圖。
- [ ] **下一個 ending gate**：依`native_2c548.json`完成party cycle的FDOTHER#56 backdrop、FIGANI/DATO、dialogue-frame grid、mirror/non-mirror figure fade與輸入skip的dedicated indexed adapter；在此之前不接campaign terminal route。〔2026-08-25(`doc35`§9.14)：`0x2c548`這個字面位址在`FD2Analysis3`裡逐項核對確認是§9.2戰鬥選單carousel系統的內部分支，不具備這裡列的FDOTHER#56/DATO/dialogue-frame grid/input-skip中任一項；`native_2c548.json`描述的內容本身不撤回(來源獨立)，但需要重新在`FD2Analysis3`裡用byte-pattern定位真正位址，不能沿用`0x2c548`這個字面數字。〕

### 2026-07-20 native ending dialogue bridge

- [x] **0x2c39b preview dialogue**：`internal/ending.Player.BlockedDialogue(chapter)` 僅在 `native_text_branch_opaque` 取出 chapter26 then 或 final else blocks；`FD2_ENDING_PREFIX=1` 以 `FD2_ENDING_CHAPTER=26|29` 明確選 branch，讀 editable `ch27.json`／`ch30.json` 的 exact scene,line,count，並強制每句使用 block 的 `portrait_id`（native DATO arg1），不混用 transcript speaker。它沿用 DATO 頭像與 Enter/Space 分頁阻塞；每段全部確認後只resume當前text gate。修正單一`queued` latch未重設造成第二段`0x2bf1c`永遠無法排入的bug，兩段現在皆可依序播放。
- [x] **native text gate resume**：對話所有頁／句皆完成後，preview 只可呼叫 `ResumeBlockedDialogue()` 恢復該一個 `native_text_branch_opaque` segment；任何 composite 或其他 opaque gate 都被拒絕，避免 UI 誤跳過未 RE renderer。每次成功resume會清除preview queue latch，讓後續已證實的第二個text gate可獨立排入。
- [x] **text 後 palette repeat**：`palette_ramp_repeat` 的 native `repeat=3`、63→0、4ms、`tail_delay_ms=200` 現由 player 展開成三組明確 `palette_ramp + delay`，不以普通 fade 代替；其後frame12..108 sequence與第二text gate均已有executor。
- [x] **frame12..108 sequence**：`blit_frame_sequence` 現展開 frame12 到108 的 transparent VGA blit 與每幀20ms wait；第一段 text 後 resume 可走到第二個已知 native text gate。composite 的 string formula 改名 `first_frame_formula`，避免與 sequence integer `first_frame` 的 JSON schema 衝突。
- [x] **ending composite frame selection regression**：`0x2bf60` 與 `0x2c0c5` 的兩張角色 frame 都是 `(i%4)+1` / `(i%4)+5`，不是 `floor(i/4)+1`；timeline 與測試已鎖定。200-pass scheduler 完成後會停在 `0x2c172` 的未恢復 montage gate，不會誤報 ending complete。
- [x] **first 40-pass composite primitive**：新增 640×200 work buffer、`CopyRect`、帶 byte-origin bounds 的 `Frame.BlitAt`，並以 native primary/secondary offsets + viewport x=160 實作 `Composite40(i)`；尚待 scheduler 接線，第二 loop 的 palette helper 繼續封閉。
- [x] **first 40-pass composite scheduler**：player 現以每輪20ms 驅動 `Composite40(i=0..39)`，完成後精確落在第二段 native text gate；200-pass loop 仍因 `0x11d40` 未證實而封閉。
- [x] **second 200-pass composite scheduler**：baseline palette loop 已恢復為200×20ms（0..135 base、136..199 base−1）；其後 `0x2c172` 明確標為 unrecovered montage gate，禁止 player 回報完整 ending。
- [x] **finale 0x2c405 phase-0 map**：已確認 chapter30 text load、`0x36b00` staging/clear、`+0x12c30` text-composite destination、500×(1ms) 的 320×200 row-scroll 與 baseline palette 40→0→上升 cadence。strict FDTXT_031/#44 glyph staging 已恢復；仍只在後續 `0x2c548` montage gate 停止，禁止用 generic fade 或空白畫面替代。
- [x] **finale phase-0 editable script node**：新增 `assets/endings/native_2c405.json` 和嚴格 loader；`0x2c469` 前呼叫 `0x1088d(30)`，依 loader 規則選 FDTXT_031，故 `0x2c` 是其合法實體 string #44（46 strings）。內容是後日談跑馬燈前言，對位跨資源重用的 `ch32.json` scene0 line0；staging/layout/timing/palette cadence 均資料化。asset 可編輯但 `Ready()==false`，直到完整 finale montage 都恢復。
- [x] **native FDTXT/font decoder foundation**：`internal/fdtxt` 現嚴格讀原始 offset-table、保留所有 FFxx 控制字、精確解 `FDOTHER_004` 的 16×16 1bpp（MSB-left）glyph。尚未猜 palette／框／控制碼行為；下一步把已知 `0x15f84` layout 接成 compositor。
- [x] **native glyph staging primitive**：`Font.BlitGlyph` 將 FDOTHER_004 的 set bits 以明確 caller palette index 寫入 indexed buffer、zero bits 完全透明，且有 pixel regression。`0x4ea2a` 的實際色彩／layout 參數仍未假設，不能因此解除 finale gate。
- [x] **0x4ea2a glyph ABI closure**：Docker Capstone 確認 native glyph renderer 是 16×16 前景 + 左／下陰影，background 非零才清 cell；finale `0x2c469` 的 caller 展開為 stride320、foreground `0xCD`、shadow `0x4C`、background0。`BlitNativeGlyph` 已 pixel-test 這個 ABI；FFxx flow/staging backdrop 尚未完成。
- [x] **finale phase-0 raw glyph composition**：`ComposePhase0Text` 現真正把 FDTXT_031 physical #44 的121個 glyph、9個 `FFFE` soft line breaks，以 `staging+0x12c30`、16-byte advance、每行 `25×320` rows、CD/4C/transparent native style 寫入。實機資源 regression 逐 bit 驗 foreground/left/down shadow；除已證實 FFFE 外任一 FFxx 仍拒絕，整段 finale 仍 fail-closed。
- [x] **finale phase-0 scroll scheduler**：`Phase0Player` 精確執行500 passes：每輪 baseline palette→`staging+i×320` 的320×200 copy→wait1ms→i++；i=0..199 每5輪（含0）將40逐步降至0，i=301後每5輪（首個305）升回。完成只回傳 phase done，不會跨 `0x2c548` montage gate。
- [x] **FDTXT archive provenance**：Capstone 直接證實 `0x1088d(30)` 先 `inc` 再傳 `0x111ba`，所以載 archive resource31；其 bytes 已 byte-for-byte 對照 extracted `FDTXT_031.bin`。先前 resource30 mismatch（5762 vs 6756）是 off-by-one，phase preview 可安全取 resource31。
- [x] **finale phase-0 bridge**：`ending.Player.EnableRecoveredPhase0` 只在精確 `0x2c172` hand-off 執行；它取前段 `PresentANI` 已捕捉的原版 DAC baseline（無 provenance 即拒絕）、清 VGA、以 FDTXT_031/#44 與 FDOTHER#4 生成 staging，逐毫秒跑完 500-pass scroll。完成後精確停在未恢復的 `0x2c548`，不會誤宣告 ending complete；regression 覆蓋首幀、baseline 缺失拒絕與 montage gate。
- [x] **finale `0x2c548` first party-cycle map**：Docker Capstone 切出三個 native buffers（128000、64000、64000）、TAI#3 與 FDOTHER#56 backdrop；更正：TAI#3 raw 是 `10×3`、三列 `C9` 的全透明 placeholder，不能誤稱可見 platform。loop index 從 `[0x53bfb]-1` 向下，但必做 `i=0→slot1、i=1→slot0` swap，才以 unit stride80／visual group `+7` 載 `FIGANI group*3+1` 與 `group*3`。`0x29164` 後先有 `0x2b9a1` 的20×1 BIOS-tick loop，再跑 primary FIGANI descriptor `+6` tick frames；舊 `20×1ms` 斷言已刪除。已入 `assets/endings/native_2c548.json`；完整 per-party scheduler/input 與 dedicated indexed renderer仍 fail-closed。
- [x] **finale party portrait/text executable slice**：DATO=`unit+7`；FDTXT_031 的 #10/#11/ending epilogue 與 FDTXT_000 的角色名／職業名，五個 destination 與 CD/4C glyph style 均已直接對齊。DATO 固定貼 `staging+0x0c88`；countdown=0 時重設 `(random&31)+40` 且本輪不減，非零先減，結果 `<2` 用 frame3、其他用 frame0。一般 loop 220 ticks，只有 loop index0（swap後slot1）跑440 ticks並自tick220改用FDTXT_031 #45。`ComposeMontagePortraitFrame` 已以玩家 FDOTHER/FDTXT/DATO 做原資源 regression；未知控制碼仍拒絕。剩餘是把 FIGANI/fade/portrait/input 組成完整 phase，而非再猜 anchor 或 special slot。
- [x] **finale dialogue-frame layout call ABI**：IDA/`14-text-control-codes.md` 交叉確認 `[0x53a81]` 是 `FDOTHER.DAT#5`，不是 DATO；`0x2c773→0x168b6` 實參為 `(destination=C, stride=0x140, arg8=5, argC=7, arg10=5, arg14=5)`，先建立 dialogue frame/grid，後續才由 DATO `[0x53a85]` 經 `0x4e8af` 貼 portrait。已撤回 `dato_layout` 錯誤命名，schema 改為 `dialogue_frame_layout`。
- [x] **DATO indexed decoder foundation**：新增 `internal/dato`，按 `0x4e8af→0x4e916` 高值-run codec 解四個 80×80 mouth frames，零值保持 opaque（不套 transparent sprite 規則），並提供 strict bounds checked indexed blit；synthetic RLE/opaque-zero 與玩家 DATO#37 regression 已加入。mouth cadence 已由 `MouthState` 接入對話更新迴圈，但不宣稱完整 dialogue parity。
- [x] **dialogue-frame `0x168b6` raw grid plan（2026-07-27 correction）**：舊 `Montage.PlanDialogueFrameGrid()` 漏掉 `v6` 的 `a3=5` 並混用 byte/stride 項，所謂 exact arithmetic 斷言錯誤。新增共用 `fdother.PlanNativeDialogueFrameGrid` 逐一保存49次呼叫；首 offsets 修為2245/2328、portrait grid origin=3208、尾格=23752，ending改委派此 planner。
- [x] **FDOTHER#5 raw-cell codec correction**：`0x1685c→0x4e9bb` 只讀 width/height 後逐 row `rep movsb`，不使用 `0x4e916` high-run；新增 `fdother.ParseLMI1RawEntry/DecodeLMI1RawEntry`，真實 #5 entry1 (`3×3`, literal `60 be bd...`) regression 固定此 path，避免把 dialogue frame bank 誤套 LMI1 RLE。
- [x] **dialogue-frame raw compositor**：`RenderDialogueFrameGrid` 依 49 個 verified placements 直接將 `FDOTHER#5` raw cells 寫入 C buffer，明確使用 opaque `rep movsb`（包含 zero bytes），不接 DATO/text/input；synthetic overlap/zero regression 通過。
- [x] **dialogue-frame resource-backed compositor**：`RenderDialogueFrameGridResource` 現實際載入玩家 `FDOTHER.DAT#5` entries 1..17，再按 native placement/overwrite order 寫入 C buffer；缺檔仍 fail-closed，asset regression 驗證非空輸出。
- [x] **DATO opaque paste primitive**：`RenderDATOFrameAt`／`dato.Frame.BlitAtOffset` 對應 `0x4e8af` 的 stride-320 opaque frame paste，destination offset 必須由 caller 明確提供（native 常見 `staging+[0x53c67]`）；不把該 global 猜成固定 anchor，也不接 mouth cadence。
- [x] **finale `0x2c548` official-IDA gate recheck (2026-07-26)**：IDA 9.4 ASM 直接確認 phase-0 的 `0x2c548` gate 先 free 500-pass staging，再配置 `0x1f400`、`0xfa00`、`0xfa00` 三塊 indexed buffer；以 `sub_111ba("TAI.DAT",3)` 與 `sub_111ba("FDOTHER.DAT",0x38)` 載入 montage inputs，FDOTHER #0x38 先以 stride `0x140`、transparent `-1` blit 到第一個 64000-byte buffer，接著由 `[0x53bfb]-1` 反向取 party record。這是專用 indexed montage 的資源/緩衝 ABI，不是 generic fade 或可直接替換的 PNG scene；DATO、FIGANI schedule、mirror branch 與 renderer 未閉合，runtime 仍 fail-closed。
- [x] **indexed FIGANI decoder foundation**：新增 `internal/figani`，直接讀 FIGANI LLLLLL resource、13-byte frame header（signed X/Y、delay、real W/H）和 4-mode RLE，透明 span 以 mask 保留而非轉 palette0；`BlitAt` 寫入 indexed surface，實機 `FIGANI.DAT` #13 regression 通過。下一步是 TAI frame 與 native 0x29164 fade/composite，不能改走 RGBA PNG。
- [x] **native FIGANI scheduler `0x2b9a1` (2026-07-26)**：官方 IDA 確認 `arg4==0` 僅清 `byte_540fc`（subframe）且不 render；非零路徑先以目前 `byte_540fd` frame 呼叫 `0x2935b`，再讀 descriptor `+6` delay，累加 subframe，達 delay 才換 frame 並於 frame count wrap。`internal/figani.NativeScheduler.Step` 已照此實作與 regression；renderer 仍由 caller 顯式提供，未猜測 `0x2935b` 的 presentation semantics。
- [x] **0x29164 first fade closure**：第一參數是 party loop unit index（讀 `[0x53a45]+unit×80+6`），不是 TAI；TAI#3 是尾端 aux argument，7-byte transparent raw 不可餵 `0x2935b`。兩條 native path 都做 `esi=8..0` 共9次 present，每次 DAC baseline delta=`esi×6`（48→0）；geometry／aux platform role 尚待拆完，故 renderer 仍不接。
- [x] **non-mirrored figure-fade schedule**：`native_2c548.json`／`Montage.PlanFigureFade(1)` 現嚴格記錄 final caller 的 `unit+6==1` branch：work stride640、320×200 left viewport、stage byte offset `8..0 ×10`、palette delta `48..0`，TAI#3@164,157 explicit transparent no-op、secondary FIGANI frame0。`unit+6==0` mirrored branch 仍拒絕，不拿非鏡像公式套用。
- [x] **non-mirrored indexed fade primitive**：`RenderFigureFadePass` 現真正執行每輪 B→A（320→640）restore、secondary FIGANI 在 `stage×10` 的 indexed blit、A left viewport→VGA 與 baseline DAC delta；TAI#3 bytes 必須是原始透明 no-op。像素 regression 鎖住 backdrop 保留、stage shift 與 48→2 palette；B→C 的 post-figure `memmove(64000)` 亦已記錄，供下一段 portrait renderer 使用。
- [x] **`0x29164` mirror-branch ABI transcription (2026-07-26)**：官方 IDA 釘出 `unit[+6]==0` 的 `0x2927e..0x29357` 路徑：仍為 `stage=8..0`、每步 palette `stage*6`，但 primary FIGANI source 是 `staging+0x140-stage*10`；只有 `arg4==0` 才額外畫 TAI#3 與 secondary FIGANI。`native_2c548.json` 已保存 `mirror_branch` editable metadata 與 loader regression；這只補齊 ABI 證據，不解除 dedicated indexed renderer gate。
- [x] **mirror fade planner**：`Montage.PlanMirrorFigureFade(unitSide,sideFlag)` 現輸出 9 個 exact stage/offset/palette pass，並明確保存 `arg4==0` 的 secondary/platform gate；純計畫器有 wrong-side 與 side-flag regression，不代表已完成 pixel renderer。
- [x] **mirror indexed fade primitive**：`RenderMirrorFigureFadePass` 依 `0x292ad` 的 caller-preseeded 640-stride right viewport，先 present `work+0x140`，再以 `staging+0x140-stage*10` 畫 primary、按 `arg4==0` 畫 secondary，最後 present 同一 viewport；TAI#3 僅做透明 raw validation。pixel regression 通過，但 DATO/完整 montage 仍 fail-closed。
- [x] **RE-UNIT-RAW-SCHEMA**：`export_units.py` 與 `battle.NativeConstructorTable` 已保存已證實 branch/index/raw records，嚴格拒絕 malformed dimensions；此項只完成資料邊界，不代表 renderer/gameplay 已接通。
- [x] **RE-MAP-SPRITE-RAW-CYCLES**：閉合 `sub_1297d` 的完整 mutation：
  moving `[0x53c07]` 每次 call 必定 0..3 循環；idle `[0x53c0b]`
  只有 signed `BIOS-tick-last<0 || >4` 才循環並更新 `[0x53c0f]`。
  `AdvanceNativeMapSpriteCycles` 保存兩條 pure ABI；舊 HUD-only helper
  委派同一實作。`[0x46c]` 已由 `0x17aa9` 的 0x10000 wrap busy-wait
  及 `0x16d00` 的 two-tick gate閉合為 low 16-bit BIOS timer tick，不是
  VGA scanline；runtime monotonic-clock materialization/call timing尚未接。
- [x] **RE-RUNTIME-POSE-MOTION-LIFECYCLE**：player materializer
  `0x10a77..0x10aad` 與 FDFIELD constructor 都建立 raw `+3/+4=0/0`。
  四向 movement entries 固定寫 `+3=方向`，每格 draw loop 寫
  `+4=1..6`，第七拍更新 X/Y 後寫 `+4=0` 且保留 pose；`0x1366a`
  normal acting 相同，special 只寫 pose。doc54 已刪除錯位 acting dump
  的影片推測，改成 direct writer/consumer lifecycle。remake 現以獨立
  `NativeMapPresentationState` 保存 `+0/+1/+3/+4`；selector materialize
  同時初始化 raw X/Y、pose0、motion0，一般移動與 acting 都跑來源格
  motion1..6／第七拍提交。`NativeUnitLayerEntry` 缺 presentation、
  selector slot 或 record byte5 任一 provenance 即 fail-closed。
- [~] **RUNTIME-NATIVE-MAP-CLOCK-AND-FRAME-INPUT**：成功建立 native
  selector batch 後，`battle.State.NativeMapCycleState` 已擁有
  `[0x53c0b]/[0x53c07]/[0x53c0f]`，且只接受 signed low BIOS word；
  legacy state 不會猜值。official IDA/Capstone另關閉`0x11eee`：
  `[0x51a93]==-1`時signed BIOS delta>2或wrap才令`[0x53c1f]`
  modulo20前進並更新`[0x539f4]`；override0..19直接選phase且不改latch。
  terrain `[0x53a40/0x53a00]`與unit pixel shift
  `[0x53a04/0x53a08]`則是兩組獨立「新BIOS word翻轉」state，均已由
  State持有。`nativeBIOSClock`現以PIT `1193182/65536≈18.2065Hz`
  的battle-local monotonic low word，在每次steady redraw只呼一次
  `0x1297d`並更新terrain phase／兩個binary latch；signed 16-bit wrap
  有regression。七拍movement仍由Ebiten Update驅動，command/target
  range-mode writers也尚未materialize，故整項仍partial。
- [x] **RUNTIME-NATIVE-MAP-RAW-ROSTER**：新增
  `NativeMapFrameRoster`，一次性建立unit/foreground arrays與cycle
  snapshot。foreground另外要求explicit `unit+7`、race、class；
  舊JSON的`BattleFig=Fig` fallback以`HasBattleFig=false`隔離，不能混入
  native compositor。任一record缺provenance即整批拒絕，不回傳半張
  native frame。它已供strict `NativeFrameInput` builder使用；尚待的是
  clock、camera/range/HUD globals的production caller ownership。
- [x] **RUNTIME-NATIVE-FRAME-INPUT-ADMISSION**：
  `buildNativeMapFrameInput`已將original banks、FDFIELD cells、
  selector cache、完整raw roster、terrain LUT phase、idle/moving
  cycles、terrain flip與unit pixel shift組成單一
  `indexedmap.NativeFrameInput`。editable control table必須與實際
  FDSHAP bytes完全相等；camera/range/cursor/HUD globals必須由caller
  明示，禁止從640×400 camera、normalized reach或PNG UI猜值。
  下一步是原版320×200 camera與HUD gate/anchor/clock runtime ownership，
  不是再做一個renderer primitive。
  - [x] 2026-07-28 production neutral-frame bridge：ch01 map JSON重新由
    合法原版輸出576個封存 byte+3、1200-byte control table與event low bytes；
    ch01改走已證實party-first、initial-groups-append constructor順序。
    玩家原始DAT integration test可完整通過`ComposeNativeFrame`並由Ebiten
    呈現，artifact為`docs/figures/native-map-ch01-remake.png`。raw range
    mode只接受campaign明示0；其他UI modes未接前回playable renderer。
- [x] **RE-UNIT-PRESENT-SNAPSHOT-OWNERSHIP**：`0x22253` 只配置一塊
  `0x25680` snapshot：terrain-only狀態供11個intro frames restore；
  `0x22547` entry再把final LMI `#0x7c`畫進同一塊，後續6 contract +
  10 release全部restore這份terrain+LMI snapshot。coordinate rewrite與
  strip-copy bridge不改它。新增atomic
  `ComposeNativeUnitPresentLUTSnapshot`及invalid-input regression，撤回
  contract/release可任意提供不同snapshot的舊註解。
- [x] **RE-UNIT-PRESENT-DIRECT-VGA-BRIDGE**：更正「總共27 presents」
  的不完整斷言：27只計full-viewport `0x11eb0`。contract後另以FDOTHER
  #3 entry0 pointer+1做一次不present的`0x22046`，再逐row從456-stride
  work buffer直接memmove 24 bytes到320-stride VGA，每row delay10ms。
  targetY==cameraY時從target row寫18 rows；否則從上方6 pixels起寫24
  rows。新增layout/progressive-copy/bounds regressions；故可觀察schedule
  是27 full presents + 18/24 direct row reveals。
  `ComposeNativeUnitPresentStripBridge`另將snapshot restore→bridge-only
  LUT/object redraw→direct rows接成單一transaction，並以untouched VGA
  regression防止誤插full viewport copy。
- [x] **RE-UNIT-PRESENT-SHIFTED-LUT**：真實FDOTHER #3 offsets
  `0x66/0x166/0x266...`證實每table連續256 bytes；`0x22547` shared
  epilogue回傳entry0 pointer+1，而`0x22046`仍讀256 entries，故bridge
  table精確為`LUT0[1:256]+LUT1[0]`，不是LUT0或LUT1。
  `NativeUnitPresentBridgeLUT`與player archive regression固定跨entry
  boundary，禁止aligned LUT近似。
- [x] **RE-UNIT-PRESENT-FIVE-ARG-ABI**：五個direct callers固定
  `0x22253(unit,newX,newY,visualX,visualY)`；intro/contract先用visual
  pair，之後才寫record `+0/+1=new pair`再跑bridge/release。command23
  先`new=ff/ff,visual=current`消失、再`new=visual=destination`出現；
  ending只做unit1消失，script helpers用兩pair相等。新增
  `PlanNativeUnitPresentCall` byte-boundary regression，不再泛稱兩pair為
  source/destination。
- [~] **CH29-POST-FLOW-WIRING 勘誤**：撤回 `postbattle_ch29_persist→ch29_post` 的錯接；第29戰依零起算 dispatch 應使用 raw `ch28_post`，未獲 activation gate 前保持未綁定並停在 `preparation_ch30` 前。raw `ch29_post` 的 LOADCH/persistent-roster 與 `0x2bce5` 證據保留，正確 owner 必須和第30戰結局流程另行閉合。——本輪(2026-08-19續輪,`doc56`,L1314)推進:直接讀當前`campaign_full.json`，`postbattle_ch29_persist`仍是`beats:[]`空placeholder，現況未變。`tools/audit_postbattle_binding_gates.py`顯示對應的`handlers/ch28_post.json`本身極簡(handler`0x25464`，只有`dialog@0x231e5(text_index7)→sync_party@0x231ed→set_chapter(28)@0x231f2`，`unknown_ops:0`)，已重組譯確認`0x25464`是純trampoline，不帶參數直接跳進跨多章共用的對白繪製尾端。**這代表`bindings/ch28_post.json`若比照既有模式建立，技術上可以立即啟用`postbattle_ch29_persist`**，但本輪特意不做這個接線:1)stem命名法已有13次「同號錯接」教訓，需位址級xref才能排除誤配；2)存在另一個內容豐富得多的`handlers/ch29_post.json`(含`0x35bba`/`0x12cea`/`0x22253`等未反組譯的unknown ops)與另一個binding wrapper，同一份wrapper檔名在不同前綴下語意不一致；3)未證實「raw ch28_post確實是主迴圈為第29戰選中的handler」前啟用可能重蹈同號錯接覆轍。**結論**:`0x2bce5` ending renderer阻塞(worklist 862-865，見上方doc35§9誠實負面結果)依然是結局流程最終要解的核心缺口；`postbattle_ch29_persist`本身有一個結構簡單的候選binding可用，但啟用前需要指令級xref驗證，非stem猜測。仍需更多靜態反組譯，維持D。
- [x] **RE-PHASE-DISPATCH-GATE**：Docker Capstone 重讀 `0x1d80b` 第一個 phase loop，固定 0x50-byte record stride、`count=[0x53beb]`、raw gates `record+6==1`、`record+5&0x81==0`、`record+0x26==0`；新增 `fdother.FindNativePhaseDispatchCandidates` 與 short-input/opaque-byte regression。只回傳 raw unit/selector，不執行 `0x13a9f` 或命名 event effects。
- [x] **RE-INVENTORY-COMPACTION-AUDIT**：官方 IDA 9.4 decompiler 直接閉合 `0x1b8e7(int unit,int slot)`：`memmove(record+0x0a+2*slot, record+0x0c+2*slot, 2*(7-slot))`，再寫最後 cell flag `record+0x18=0x80`；新增 `battle.RemoveNativeInventorySlot`，保留 stale tail item byte，並覆蓋 slot0/slot2/slot7/short-input regression。先前「第三個 stack argument 未閉合」斷言已刪除。
- [x] **RE-UNIT-MODE-DISPATCH**：Docker Capstone 重讀共享 `0x13a9f`，固定 raw gate `record+5&5==0` 與 mode/argument reads `+0x34&0x0f`、`+0x35`、`+0x36`、`+0x3d`；新增 `fdother.PlanNativeUnitMode`，short/gate/masked-mode regression 通過。只保存 mode plan，不呼叫 `0x14ef0/0x14b78/...` 或命名效果；mode 6/8/其他仍保留未命名分支。
- [~] **RE-ITEM-EFFECT-DISPATCH**：Docker Capstone 固定 `0x20c6f` 的
  type→callee/argument 全 map；`NativeItemEffectRouteForType` 保留 raw
  topology。observed effect branches 5–24 的 typed post-confirm closures
  已完成；item selector UI、indexed presentations 與 normalized engine
  integration 仍是獨立缺口。
- [x] **RE-ITEM-TYPE67-MUTATION**：重讀 `0x22af6` 修正舊 adapter：
  marker 位於 target `record+a5`，不是 parallel `flags[]`。type6/7 用
  `+0x25/+0x26`，nonzero 時 base10→actual9 HP restore、清 record marker，
  再消耗來源 slot。新增 `ApplyNativeItemMarkerClearRestore` 與
  IDs196/197 regression；status/UI 名稱仍未知。
- [x] **RE-ITEM-WORD-DELTA**：官方 IDA 9.4 decompile `0x21082` 固定 `word(record[index]+a3) += low16(a2)`、16-bit wrap，隨後呼叫 `0x1b8e7(a1,a4)`；新增 `battle.ApplyNativeWordDeltaAndRemove`，explicit target/removal units 與 bounds/atomic regression 完成。欄位仍不命名，renderer/effect callback 不接。
- [x] **RE-RNG-GROWTH-MARKER**：官方 Capstone 固定 `0x4e893` 為 `rol16(state+0x9014,3)`；`0x22721/0x22866/0x22997` 的 `idiv 4` 取 EDX remainder，再 `+2` 寫 marker。新增 `fdother.NativeRNGStep/NativeRNGMarker` regression，刪除 quotient-based 誤讀；成長欄位與 FPU multiplier 仍未命名。
- [x] **RE-RAW-WORD-GROWTH-22721**：官方 IDA 9.4 固定 `+0x22` zero gate、RNG marker、`+0x48` 的 `trunc(word*0.15+1)` 與 `2*effective(+0x21)` raw accumulator；新增 `battle.ApplyNativeRawWordStep`，覆蓋 marked skip、RNG consumption、rounding、word update、score 與 preflight bounds。未命名成長效果，未接 presentation/tail。
- [x] **RE-RAW-WORD-GROWTH-22866**：Docker Capstone 固定 `0x22866` 與 `0x22721` 同構，僅 offsets 改為 marker `+0x23`、word `+0x4a`；`ApplyNativeRawWordStepAtOffsets` 共用實作並有 variant regression，未命名欄位。
- [x] **RE-RAW-PAIR-22997**：Docker Capstone 固定 `0x22997` marker
  `+0x24` zero gate、同 RNG marker、`+0x4c/+0x4e` 各 `+0x0f`、score
  `2*effective(+0x21)`；新增 `ApplyNativeRawPairStep` 覆蓋
  wrap/marked skip/preflight。後續 equipment cross-check 已將兩 words
  定案為 derived HIT/EV，type12 caller closure 見下方。
- [x] **RE-ITEM-22D1B-BRANCH**：Docker Capstone 重核撤回舊「兩次 RNG/
  固定10 damage」：gate RNG 成功後 `0x1c81f(base=10)` 消耗第二 RNG，
  實際減9 HP；第三 RNG 才寫 marker。type14/22 item caller 使用
  `+0x26/+0x27` 並保留來源；`ApplyNativeItemMarkerApplication`
  保存 class gate、三次 RNG 與 atomic mutation。status 名稱仍未知。
- [x] **RE-COMMAND23-COORD-WRITE**：官方 IDA 9.4 閉合 `0x22253` 尾端 `record[+0]=a13`、`record[+1]=a14`；`0x2218a` caller 的 `0xff/0xff` 是 pre-render pair，最後寫 cursor-derived pair。新增 `battle.SetNativeUnitCoordinateBytes` raw writer/regression；renderer/pathfinding 仍未接。
- [x] **RE-PERSISTENT-IDENTITY-LOOKUP-24BDE**：Docker Capstone 閉合 `0x24bde` 的 raw lookup：掃 caller-supplied persistent count（native capacity 32），stride `0x50`，只比較 record `+0x08` unsigned byte，命中即回 1、否則 0。新增 `battle.FindNativePersistentIdentity`，保留 first-index/read-only/bounds regression；不把 `+8` 泛化成 portrait、Fig 或 NPC identity。
- [~] **SYNC-PARTY-RAW-IDENTITY-GATE**：`PartyMember.native_identity`/`Unit.NativeIdentity` 已可選地攜帶 native persistent `+0x08`，`syncPartyFromBattle` 有 raw-key matching 與 unknown-key fail-closed regression；缺欄位時才保留 Fig projection。仍未完成全 roster/save/export 的 raw record 接線，故不宣稱 byte-identical。
- [x] **RE-PERSISTENT-COPY-MUTATION-11506**：Docker Capstone 閉合 `0x11506` 配對後 mutation core：runtime→persistent copy `0x50` bytes；清 persistent `+0x22..+0x27`；`+0x05 &= 1`；若結果非1，`+0x40 = +0x42`；固定 `+0x44 = +0x46`。新增 `battle.ApplyNativePersistentRecordCopy` read/write/bounds regression；`0x3453e` zero-identity gate 與 `0x1145a` tail 保留 caller-owned，未猜測性接入 sync runtime。
- [x] **RE-RAW-BYTE5-BIT0-3453E**：Docker Capstone 閉合 `0x3453e(index)`：回傳 selected record `+0x05 & 1`，不改寫資料。新增 `battle.NativeRecordByte5Bit0` mask/bounds regression；保持 raw predicate，不命名 acted/alive/active。
- [x] **RE-EQUIPMENT-RECALC-1145A**：Docker Capstone 閉合 `0x1145a(persistentIndex)` raw arithmetic，並由 `battle.ApplyNativeEquipmentRecalc` 保存 signed base words `+0x37/+0x39/+0x3e`、八格 `0x40` flag gate、`0x4e56c` row stride、四個 raw destinations 與 16-bit wrap。normalized `campaign.RecomputeEquipment` 仍是 projection-only；四個 row 欄位後由全表 cross-check 命名，fresh JOIN production 接線則由 `JOIN-1145A-EQUIPMENT-RECOMPUTATION` 完成。其餘 effect bytes 與完整 campaign byte identity仍未閉合。
- [x] **RE-EQUIPMENT-RAW-ADAPTER-1145A**：新增 `battle.ApplyNativeEquipmentRecalc`，依 raw `[flag,item]` 八格、bit `0x40` gate、`0x602ad+item*0x17` row 與 signed/wrapping word arithmetic 寫入四個 raw destinations；bounds preflight atomic、unequipped/missing-row regression 通過。此項落地時 row 欄位尚未命名；後續全表 cross-check 已在下一項閉合四個 equipment words，但仍未接完整 native campaign record。
- [x] **RE-EQUIPMENT-ROW-WORDS-CROSSCHECK**：215 個已知 runtime rows
  的 `+1/+3/+5/+7` little-endian words 已逐筆與 normalized `item.json`
  AP/HIT/DP/EV 比對，全部一致；Go regression 鎖定 fixture 間 contract，
  `0x1145a` 的 native 寫入順序可定案為 AP/DP/HIT/EV。其餘 effect bytes
  與 table 最終邊界不因本項而開放。
- [x] **RE-ITEM-EFFECT-ROW-4E56C**：已用 Docker Capstone 閉合
  `0x602ad + item*0x17`，並逐 byte 證實 EXE file view 從 `0x540ad`
  起、比 normalized `item.json` 的 `0x540ac` 起點偏移一 byte。新增
  `native_item_effect_rows.json` 保存 215 個已知 selector 的 raw prefix，
  exporter 與 Go loader regression 固定跨 normalized-row 邊界的 byte
  行為。——2026-08-24獨立覆核(doc32§1.3):base `0x602ad`(file
  `0x792c1`)/stride `0x17`=23B/exactly 215列(ID 0..214)，與相鄰
  `target_portraits` class-change table(`0x615FE`)之間零間隙邊界，重新
  反編譯`FUN_0004e8bc`確認`return &DAT_000602ad + param_1*0x17;`——
  table真正終點與215列範圍已閉合，未命名欄位語意/normalized equipment
  完整接線仍是次要延伸，不影響本項RE結案。
- [x] **RE-ITEM-EFFECT-211A4-ABI**：官方 IDA 9.4 閉合
  `0x211a4(actor,count,targetBytes,amount)`；item caller `0x20c6f` 直接傳
  `a3/a4` count/list 與 row `+0x0e` HP amount。type5 返回後經
  `0x1b8e7` 消耗來源 slot，type13 直接 cleanup 並保留來源。
  `ApplyNativeItemHPRestore` 保存 list 順序、sequential RNG、raw score、
  target/source atomic preflight 與 consumption 分歧。renderer/SFX/道具名稱
  仍 fail-closed。
- [x] **RE-ITEM-TWO-STAGE-TARGET-1BBDC**：官方 IDA/Capstone 閉合 case0 的兩次 `0x14818`：actor-origin first stage用 row `+0x10/+0x15`（type0x17 才 inner marker=1），`0x115b6` 確認後以 confirmed-origin row `+0x12/+0x15`、inner=0 產 final list，傳 `0x20c6f(actor,slot,count,list)`。新增 `NativeItemTargetPlanFromRow`／`NativeItemEffectTargets` 與 confirmed-candidate/short-row regression；runtime row producer、renderer與 gameplay 名稱仍 fail-closed。
- [x] **RE-ITEM-211A4-SHARED-CALLERS**：canonical Docker Capstone
  核對 direct callers `0x20ce0` item path 與 opaque selector `0x21`
  path `0x285ed`；後者以 caller-owned list、amount `0x320` 重用 helper，
  故 callee 本身不是 type5/13 專屬 routine。這不否定已由 dispatcher
  caller 閉合的 type5/13 HP restore/consumption；opaque caller 的上層語意
  與 renderer 仍 fail-closed。
- [x] **RE-ITEM-PRESENTATION-1E0DB**：官方 IDA 9.4 閉合 `0x1e0db(value,digitBias,target)` 的 camera gate、四位十進位格式化、queue position codes `2,7,12,17`、target index 與 digit-byte 寫入；`0x1e1dc` 保留 parallel raw queue writer。新增 `battle.AppendNativePresentationDigits` raw adapter/regression。這只關閉 presentation queue ABI，不命名 HP/MP/damage/heal，也不接 normalized item UI。
- [x] **RE-ITEM-ADJACENCY-GATE-1DEBE**：官方 IDA 9.4 閉合 `0x1debe(actor,x,y)` 的 active gate、曼哈頓相鄰一格與 equipped row `+0x0b<=1` 條件；此為 caller-specific precondition，不宣稱 `+0x0b` 是通用 weapon max range。
- [x] **RE-ITEM-PRESENTATION-1C4CC**：官方 IDA 9.4 pseudocode 閉合 `0x1c4cc/0x1c2da` caller ABI：兩者都接 `(opaque actor, raw subcommand, target count, target-byte list)`；`1c4cc` 依三張 33-byte frame table 逐 frame 做 456-stride target redraw、312×192 present、subcommand/frame SFX 分支與 BIOS tick，`1c2da` 以 native cycle/visual bank 做 target blit，再做五次 restore/present pair。這只關閉 presentation ordering/camera bounds/restore cadence，不命名 item effect、frame asset、SFX 或 target producer；`RE-ITEM-EFFECT-211A4` 仍保持 partial。
- [x] **RE-ITEM-20-24-PRESENTATION-1CD17**：官方 IDA 9.4 閉合
  type20/24 共用的 `0x1cd17`：30-byte remap table、固定十幀、每幀
  restore saved indexed buffer、camera-visible target redraw、
  `7-(frame%8)` raw blend argument、312×192 present、單 BIOS tick，
  再恢復原 buffer。此 helper 本身不做 gameplay mutation；其後獨立的
  row-selected command-damage loop 已由下方 caller closure 定案。
- [x] **RE-ITEM-COMPAT-1C1C3**：官方 IDA 9.4 閉合 item selector compatibility predicate：`0x1c1c3(actor,item)` 取 actor class 對應的六-byte raw table，逐一比較 item row `+0`；只保存 six-byte table／row-byte ABI，不命名 class 或 equipment 語意。
- [x] **UI-ITEM-8SLOT-SHELL**：舊 shell保留八個 raw holes並只支援↑↓，
  現已證實這不是 original parity。`0x1b9de` 依 signed flag非負 compact
  occupied prefix成兩欄四列；↑/↓ linear wrap、←/→±4，battle-use
  Enter拒絕effect type0。`0x184c0` 固定 label `(42+150*col,
  103+22*row)`、FDTXT `itemID+181`、selected/unselected raw color
  201/205、category icon59–61/equipped+3及stat icon64–67/41。
  `AdvanceNativeItemSelector`／`NativeItemSelectorCells` regression完成；
  GUI shell/Enter/indexed animation仍待依此改寫。——2026-08-19稽核確認：`remake/cmd/fd2/main.go`(4291/4309行)已將`battle.AdvanceNativeItemSelector`接入Enter/方向鍵處理，7783-7786行註解確認text shell僅作為legacy/缺證據fallback，僅本行未同步。
- [x] **RE-ITEM-SELECTOR-12FRAME-PANELS**：`0x17e0b` opening固定
  frames11→0，`0x1b932` closing固定0→11；每幀由 saved 64000-byte
  buffer重建。`0x18409→0x182ad/0x18312/0x1839b` 的三區已資料化：
  left `(src5,7,86×86)` frame6後left-clip16px；upper
  `(92,7,223×86)` frame3後up-clip16px、frame9消失；bottom
  `(5,94,310×102)` 每幀y+16、frame6消失。`NativeItemPanelSchedule`
  exact reverse/clip regression通過；indexed source已由下方完整
  compositor閉合，GUI animation adapter仍待。
- [x] **RE-ITEM-PANEL-SOURCES-17EEF-17FC0**：official IDA 9.4 確認
  `0x17eef` 以 `0x168b6(dst,320,5,7,5,5)` 建 `(5,7)` 的5×5框，
  unit record `+7` 選 DATO portrait貼 `(8,10)`；FDOTHER#5 directory
  offsets `+86/+90` 即 entries20/21，貼 `(92,7)`／`(5,94)`。
  `0x17fc0` 的2 bar、4 compared-number、8 raw-number、3 FDTXT與
  base/flag icons之 exact destination/record-offset schedule 已落入
  `NativeItemPanelBaseLayoutFor`／`NativeItemPanelDataPlanFor` regression。
  尚未證實的 raw offsets 不命名；下一步是 indexed renderer/Ebiten bridge。
- [x] **UI-ITEM-PANEL-BASE-INDEXED**：`RenderNativeItemPanelBaseResources`
  現從玩家 FDOTHER/DATO archive 原子化執行完整 `0x17eef`：corrected
  49-cell raw grid→DATO frame0→FDOTHER#5 entries20/21。新增
  `LMI1Entry.BlitOpaqueAt` 修正舊「`0x4e8af` index0 transparent」錯誤；
  synthetic overwrite/atomic failure與玩家資產 regression通過。
  `0x17fc0` dynamic overlays已由下方項目閉合；Ebiten bridge仍待。
- [x] **RE-ITEM-TEXT-HELPER-15F84**：official IDA重核
  `0x15f84/0x16559`，刪除 doc35 舊「`[0x53a85]` 是 CJK glyph容器」
  斷言。普通文字實際走
  `0x4ea2a([0x53a75]=FDOTHER#4,fontGlyph,...)`；`0x16559`只從目前
  DATO `[0x53a85]` 取 mouth frame重貼 portrait。item panel三段文字
  style固定 foreground205/shadow76/background0；含控制碼時仍須
  fail-closed。
- [x] **UI-ITEM-PANEL-DYNAMIC-17FC0**：新增
  `RenderNativeItemPanelData/Resources`，完整執行2 bar、4
  compared-number、8 raw-number、3 FDTXT與4 icon calls；精確保存
  `0x18795/0x17d6f` zero/nonzero bar、`0x1875d/0x187d6` padding/
  overflow/color、raw/four-mode/font三 codec與 record `+7` DATO selector。
  整張 atomic commit，control word fail-closed；synthetic與玩家 archive
  regression通過。新增可重現工具 `cmd/fd2-item-panel-oracle` 與
  [`item-panel-native-indexed.png`](../figures/item-panel-native-indexed.png)。
  後續 Ebiten bridge見下一項。
- [x] **UI-ITEM-PANEL-ROWS-EBITEN**：新增
  `RenderNativeItemPanelRows` 完成 `0x184c0` category/stat icons、
  FDTXT `itemID+181`、color201/205及stat number；oracle更新為有實際
  item rows。`NativeItemPanelRecordForUnit` 僅在 raw
  `+6/+8/+0x1f/+0x20`、DATO與8格inventory provenance齊全時建立
  80-byte輸入。
  `cmd/fd2` 已有 complete indexed image adapter、compact四方向input、
  opening11→0與closing0→11；缺證據/archives才用legacy shell。
  Docker/Xvfb玩家資產 regression走完整12+12幀。FDFIELD map roster的
  raw欄位已同步；JOIN `0x112a5` lower record與class-change只改
  `+0x20/+7`的lifecycle亦已接進30章scenario/persistence，正常ch01
  campaign asset可開啟原版面板。tracked IDs198/199/200（type8/9/10）
  及 IDs94/95/96（type17/18/19）已接完整Enter transaction：兩段
  self-target驗證、raw base AP/DP/DX或MaxHP/MaxMP/MV加值、compact消耗、
  必要的equipment recompute、`+5 bit7`及action結束；其他effect/target
  transaction仍fail-closed。——2026-08-19稽核確認：本檔後續`[x]`項「REMAKE-ITEM-HP-MP-TARGET-TRANSACTION」(types5/13/11)、「REMAKE-ITEM-TARGETED-EFFECT-BATCH-2」(types6/7/12/14-16/20-24)、「REMAKE-ITEM-TYPE23-DESTINATION-CURSOR」(type23/item101)已共同關閉此殘留缺口，僅本行未同步（indexed effect presentation仍是另一獨立開放議題）。
- [x] **RE-ITEM-COMPAT-TABLE-4E53E**：官方 IDA 9.4 閉合 `0x4e53e(class)=0x6188a+class*7`；新增 `battle.NativeClassCompatibilityRowOffset` 與 `NativeClassItemCompatible`，嚴格保留 row+0..+5 比對及 row+6 opaque、bounds/short-row regression，不接 normalized class/equipment。
- [x] **RE-RAW-HP-RESTORE-1C916**：新增
  `battle.ApplyNativeRawHPRestore`，保存 RNG step、amount arithmetic、
  current/max HP `+0x40/+0x42` clamp 與 `record+0x07`/class-derived
  score gate；shared primitive 本身不冒充 item，但 type5/13 caller 已另行
  閉合成 HP restore。UI/presentation 仍未完成。
- [x] **RE-RAW-MP-RESTORE-1C9DD**：新增
  `battle.ApplyNativeRawMPRestore` 保存 current/max MP `+0x44/+0x46`
  clamp 與無 class bonus 的 score gate；type11 caller 另由
  `ApplyNativeItemMPRestore` 保存 zero-max target 不消耗 RNG、list order
  與來源 slot consumption。IDs206/207 amounts=80/200；UI/presentation
  仍待完成。
- [x] **RE-ITEM-TYPE12-HIT-EV-22997**：結合 dispatcher tail、
  `0x22997` 與已定案的 derived words，閉合 type12：marker `+0x24`
  非零跳過且不耗 RNG；成功寫 `(rng%4)+2`、HIT/EV
  `+0x4c/+0x4e` 各加15，來源 slot 保留。新增
  `NativeItemHITEVStepRoute`／`ApplyNativeItemHITEVStep` 與 ID210
  fixture regression；marker UI 名稱仍未知。
- [x] **RE-ITEM-EFFECT-COMMAND-DAMAGE-20-21-24**：official IDA 9.4
  固定三 type 都將 row word 當 command ID，逐 target 呼
  `0x1c75e(target,commandID)`；20/24 用 `0x1cd17` 十幀 presentation，
  21 用 `0x2111a→0x1cac7`。dispatcher 不呼 `0x1ca89`、不移除來源。
  type20 IDs11/56/60→commands2/0/2，type21 IDs29/38/51/99→6/1/7/6，
  type24 ID79→command3；typed executor 保存 presentation 分歧與 transaction。
- [x] **RE-ITEM-TYPE23-RELOCATION**：official IDA/Capstone 閉合
  `0x1bbdc→0x2218a`：actor gate 是 raw identity `+8==24` 與 max MP
  `+0x46>=20`，不是舊稱 class/level；只取第一 target，以 command23
  cost20 對 current MP `+0x44` 做 16-bit subtract，按 target
  class/level 加 raw accumulator，再由兩次 `0x22253` 寫
  `0xff/0xff→destination cursor`。dispatcher 保留 item ID101；
  `NativeItemRelocationRoute`／executor 與 MP-wrap/preflight fixture 已補。
- [x] **RE-RELOCATION-MODE6-LEGALITY**：`0x115b6` mode6 Enter predicate
  已資料化：selected target 不算 occupant；其他同座標且 raw
  `+5 bit0==0` 的 record 阻擋。target selector 通常取 class `+0x20`，
  `+7==0x1c` 改1，class `0x13`／race `4,5` 改19；`0x4e555` 的
  29×20 row 在 resolved terrain index 必須為 literal20。新增 editable
  `native_movement_cost_rows.json`、strict loader、pure adapter 與 fixture
  regression；cursor UI／27 full-present + 18/24 direct-row renderer仍未接。
- [x] **RE-RAW-WORD-SUBTRACT-ADDRESS-CORRECTION**：Docker Capstone 證實
  word `+0x44` subtract 位於 `0x1ca89`，`0x1cac7` 是 allocation、
  `0x1cb94` drawing 與四輪 320×192 present helper。修正 adapter attribution
  並刪除 type21 MP-subtract 斷言；兩個地址不再混用。
- [x] **RE-RAW-FLAG-RESTORE-22AF6**：
  `ApplyNativeRawFlagRestore(records,targets,markerOffset,rng)` 現正確保存
  record-local marker read/clear、conditional HP restore、sequential RNG、
  target preflight 與 accumulator；錯誤 detached flags API 已刪除。
- [x] **RE-RAW-APPLICATION-22D1B**：`ApplyNativeRawApplication`／
  `ApplyNativeRawHPDamage` 保存 marker-zero/class gate、gate/damage/
  marker 三次 RNG、base10→actual9 HP subtract、marker `(rng%4)+2`
  與 accumulator；normalized command executor 亦修正為消耗三個 random
  draws。presentation/status 維持 fail-closed。
- [x] **RE-ITEM-TYPE15-16-AP-DP**：type15 marker `+0x23`／derived
  DP `+0x4a`，type16 marker `+0x22`／derived AP `+0x48`；成功增
  `trunc(current×0.15+1)`，marked target 不耗 RNG，來源保留。新增
  `NativeItemAPDPStepRoute`／`ApplyNativeItemAPDPStep` 與
  IDs213/214 fixture regression；marker UI 名稱仍未知。
- [x] **RE-ITEM-TYPE17-19-CAPACITY-MV**：type17/18 將 row amount20
  加到 max HP `+0x42`／max MP `+0x46`；type19 對 word `+0x3b`
  加1，但 caller 保存並恢復 `+0x3c` EXP，故 net effect 是 MV byte +1、
  EXP 不變。三條都由 `0x21082→0x1b8e7` 消耗來源；新增
  `NativeItemCapacityStepRoute`／`ApplyNativeItemCapacityStep` 與
  IDs94/95/96 fixture、atomic removal regression。
- [~] **RE-RAW-BUFFER-LATCH-24D22**：Docker Capstone 重讀 `0x24d22(arg)`：`arg!=0` 只把低 byte 寫入 global `0x51a10` 後返回；`arg==0` 配置 `latch*0x138` bytes，從 `0x53aff+(0xc0-latch)*0x138` 複製，接著以 `0xbf-latch` 向下做 `0x138` bytes row copy，最後再 copy 一列並經 `0x37416` free。此輪只保存 setter/render 分支與 loop 邊界，不命名 global 或把 copy loop 當 generic fade；renderer adapter 仍 fail-closed。
- [x] **RE-RAW-MARKER-REWRITE-24E80**：Docker Capstone 閉合 `0x24e80` 的 raw mutation：從 runtime slot `0x10` 到 caller count，若 record `+0x07==0x1f`，寫 `+0=0x10`、`+1=0x06`。新增 `battle.RewriteNativeMarker1F` 與 prefix/nonmatching/bounds regression；欄位仍不命名，不接 renderer 或 roster identity。
- [~] **RE-CHAPTER-CALLER-24838**：Docker Capstone 重讀唯一 `0x24bde` caller `0x24838`：先以 `0x24b14(0x64)` 分支，成功臂 `dialog #8→join(0x16)`；接著 `0x24bde(0x12)` 命中才走 `dialog #10→acting #0x48→0x32975(0x11)`，缺失時再依 global count `0x53bef<0x0f` 分成 `dialog #13→join(0x13)` 或 `dialog #12→0x32975(0x11)`，共同 sync/presentation 後才進後續 handler。只保存 raw call order；不把 `0x64`、`0x12`、`0x16/0x13` 命名成道具／角色／章節語意，runtime campaign binding 仍 fail-closed。——本輪(2026-08-19,`doc26`§7.5)推進:`0x24838`的`op:unknown`呼叫`0x24bde(0x12)`本體已完整反組譯，逐位元組比對`roster_has`演算法(`0x33499`)的既有pseudocode(`for edx in 0..[0x53bfb]: if byte[[0x53bf7]+edx*0x50+8]==id: return 1`)完全相同，確認`0x24838`應改判為**`roster_has(char_id:18)`**，與`doc26`§7.3記載的`ch17_pre`同一判斷語意一致。**演算法層級已閉合**，但`handler_compile.go`目前`case "roster_has"`只接受`HandlerCondition.CharID`，要把`0x24838`從beat改成if/then/else condition node需要重寫`ch22_post.json`的beat結構，本輪未動JSON/compiler，故runtime campaign binding仍未解，維持`[~]`。
- [x] **RE-RAW-RECORD-BYTE5-32975**：Docker Capstone 閉合 `0x32975(index)`：直接覆寫 selected runtime record `index*0x50+0x05 = 1`，不保留其他 bit。新增 `battle.SetNativeRecordByte5One` overwrite/bounds regression；與 `SetNativeRecordBit7` 分離，不把 byte5 命名成 acted/turn/action。
- [x] **RE-COMMAND23-CALLER-SCOPE-CORRECTION**：Docker Capstone 重讀 `0x250cc→0x22253`，確認 `0x22253` 不是 command-23 專屬：chapter-ending/post handler 在 `0x1c2da` 後也以 unit `1`、pre-render `0xff/0xff`、record `+0/+1` 呼叫同一 indexed routine，隨後才進 `0x25089` cleanup 與 `0x2bce5` ending renderer。故 `SetNativeUnitCoordinateBytes` 僅是 shared raw writer；command-23 selector、ch29 ending layout、renderer/campaign semantics 仍分開且 fail-closed。
- [x] **CHAPTER-ENDING-250CC-BRANCH-AUDIT**：Docker Capstone 對齊 `0x25348` 分支確認：ending path 先送 FDOTHER frame `#0x0d/#0x0e/#0x0f`，呼 `0x1c2da`，再以 shared `0x22253` 寫 unit `1` 的 raw `+0/+1`，送 frame `#0x10`，最後 `0x25089→0x2bce5` 並 self-loop。這只固定 call order/終局邊界，不把 `0x24b14` 回傳或 frame IDs 命名成 town/shop/gameplay；一般戰後 flow 仍不得接此 self-loop。〔**2026-08-25 勘誤**：`0x25089` 之後緊接的下一個 CALL（即 `0x2545d`）逐 byte 核對出目標其實是 `0x31529`，不是 `0x2bce5`（`doc35`§9.11/§9.12，`call_scan(0x2bce5)` 全 exe 窮舉 0 筆）。call order/self-loop 本身的結論不變，只有字面呼叫目標數字需訂正。詳見 `known_address_errata.json`。〕
- [~] **RE-INVENTORY-ITEM-GATE-24B14**：Docker Capstone 閉合 `0x24b14(item)`→`0x31860(unit,item)`→`0x1b8a6/0x1b722`：只掃 runtime unit `0..15`；每 unit 先取 bit7-clear count，再比對 raw slots `0..count-1` 的 item bytes，沒有額外 compact 驗證。成功回 native `1`，缺失回 `-1`。新增 `battle.FindNativeInventoryItemInUnit`／`FindNativeInventoryItem` 與 `NativeInventoryRecords` regression；campaign `partyHasItemID` 在完整 raw provenance 時已走同一 count-sized gate，缺資料才 fallback normalized。——已核對(L1515,`doc32`§7,2026-08-19續輪):`FindNativeInventoryItemInUnit`/`FindNativeInventoryItem`(`native_inventory_search.go:11-46`)完整重現`0x31860→0x1b8a6`→raw slot scan的count-sized prefix搜尋，不驗證compactness，與原生行為一致；`main.go:2683-2690`的函式註解已誠實記載`partyHasItemID`優先呼叫這個exact raw adapter，只有在itemID超出byte範圍或找不到runtime records時才退回normalized/persistent roster掃描，這是刻意保留的相容路徑，不是未修的raw gate缺口。項目描述的「minor殘留範圍」與程式碼現況完全相符，確認完整、無需修改，但保留D(非A，屬「近乎完成」而非「額外解決」)。
- [x] **RE-NATIVE-RNG-LIFECYCLE-627B8**：Docker LE object/fixup audit
  確認 shared RNG word `0x627b8` 位於 initialized object 3，image初值
  `0x0000`；全EXE只有 `0x4e893` 自身load/store兩個reference，save/load
  與chapter handler都不讀寫。因此生命周期是process-wide、初值0、
  不進FD2.SAV。runtime新增獨立`uint16` state，不混用Go RNG。
- [x] **REMAKE-ITEM-HP-MP-TARGET-TRANSACTION**：Ebiten item Enter已將
  types5/13 HP與type11 MP接到兩階段`0x14818` target planner；確認目標後
  才atomic materialize/commit 0x50-byte records、依list order消耗native
  RNG、按type保留或compact移除來源，最後設raw `+5 bit7`並結束action。
  任一unit缺raw provenance即fail-closed；indexed effect presentation與
  types6/7/12/14–16/20–24 runtime接線仍待。
- [x] **RE-COMMAND-DAMAGE-RNG-CORRECTION**：Docker Capstone直讀
  `0x1c75e/0x1c81f`，確認`0x1c7ed`命中與`0x1c869`變異都呼
  `0x4e893`；miss耗1 step、hit耗2 steps。刪除舊
  `math/rand`替代，player command0與item types20/21/24改用同一
  process-wide uint16 state，並補state-sequence regression。
- [x] **REMAKE-ITEM-TARGETED-EFFECT-BATCH-2**：兩階段item target runtime
  已新增types6/7 marker-clear+conditional HP、type12 HIT/EV、
  types15/16 DP/AP、types14/22 marker application+damage，以及
  types20/21/24 command damage。raw transient、HP、derived words、
  retained/consumed inventory皆同步；indexed effect presentations仍待。
- [x] **REMAKE-ITEM-TYPE23-DESTINATION-CURSOR**：item101完成first-target後
  不立即改座標，而是進獨立destination cursor；逐格使用完整raw roster、
  `NativeTerrainMoveCodes`與29×20 cost rows執行literal target-code6的
  occupancy/terrain predicate，合法格才扣command23 MP、寫target raw
  `+0/+1`、保留來源並結束action。原版first-target與destination兩層
  Escape都直接回caller-owned item panel；舊destination→first-target
  行為已刪除。27 full-present + 18/24 direct-row indexed renderer仍待。
- [x] **REMAKE-ITEM-TARGET-SELECTOR-LIFECYCLE**：item target entry以
  `row[+0x12]+2` materialize global selector，first target field仍使用
  `row[+0x10]`／type23 inner marker／`row[+0x15]`。第一次`0x115b6`返回後
  reset所有cell byte+3並恢復selector1；final target list後再reset。
  type23 destination維持global selector1，只把literal code6傳給
  `0x115b6`，不再把兩個「6」混成同一狀態。focused Docker/Xvfb regression
  覆蓋兩層cancel、重新進入、成功commit與grid/selector reset。
- [x] **UI-SHOP-PURCHASE-CONFIRM-E1**：完整重讀`0x2f0b0`後保存四組
  六variant FDTXT表；購買問題展開`FFFC`商品名與`FFFA`十進位價格，
  並接原版`0x19953` Yes/No selected pulse。2026-07-28再以指令順序重核
  修正 framebuffer 斷言：`0x2f2a9`先完成`0x197e5`四幀choice closing，
  再由`0x19913..0x1994c`恢復保存的question region；`0x2f2d3`才在literal
  VGA`0xac44c`／`(12,157)`追加第三行並等待。不再錯誤保留steady
  Yes/No cells或使用第四個inward frame。production已接list close→confirmation
  open/steady/close→cancel或不足金wait→dialogue close→list reopen。
  真實FDOTHER/FDTXT/DATO regression與更正後indexed fixture已補。recipient
  selector與inventory-full後續已有E1 production實作；recipient input/scroll、
  no-recipient/full/success仍無DOSBox E2，不能由production接線推論原版操作
  驗收。下一步是optional-equip/success/debit lifecycle及同狀態E2。
- [x] **UI-SHOP-CONSUMABLE-RECIPIENT-E1**：`0x2f30a`分流已釘死：
  item type≥`0x20`走`0x2e6b8`兩欄六人名冊；type<`0x20`走相容性篩選後
  的`0x2e8cf→0x2ebe0`三列能力比較面板。新增strict consumable wrapper，
  裝備type誤用即fail-closed；真實shop entry16、FDICON與FDTXT regression/
  fixture已補。八格滿分支另保存`word_5265f={1,506,1,506,506,506}`、
  `unit[+7]+1`動態姓名與mode1 wait，未插入也未扣金。下一gate是裝備比較
  renderer、success/equip/debit與production lifecycle。
- [x] **UI-SHOP-EQUIPMENT-RECIPIENT-E1**：完整`0x2e8cf/0x2ebe0/
  0x2ef8f/0x2efb7`閉合type<`0x20`的filtered三列面板。candidate以raw
  base AP/DP/DX＋item `+1/+5/+3/+7`，只保留另一`type<=0x14`類別的
  已裝備貢獻；對derived AP/DP/HIT/EV選digit bank31/42/119
  （equal/increase/decrease）。shop entries16/18..22、FDICON、FDTXT姓名、
  三列geometry、6-open/5-close均已有strict compositor、真實資源regression
  與indexed fixture。下一gate縮為成功insert→optional equip→`0x2f4c6`
  →debit、production owner與E2。
- [~] **UI-SHOP-PURCHASE-SUCCESS/DEBIT**：`0x2f4c6`不可沿用church case4
  當通用動畫。shop variant1/resource12為entries23..27、`(169,45)`、
  每幀2 ticks後portrait mode0 restore；variant3/resource29為entry23、
  `(148,39)`、pre1/post8 ticks後restore；variant5/resource63為
  entries23..29、`(131,28)`、每幀2 ticks且不restore。三條strict plan/
  compositor與真實資源regression已補。DOSBox交易抓圖撤回舊fixture保留
  藍色問句框的錯誤：success必須從已關閉dialogue的bare shop framebuffer開始；
  修正後variant1前四個採樣依序對上source-built frame0/1/2/3。2026-07-29
  再重核`0x1956b/0x2d31b/0x2f4c6/0x16559`，確認裸畫面不得先覆蓋
  DATO第0幀；撤回該覆蓋後四組未遮罩整幀均為AE=0。
  caller順序固定insert→optional equip/recalc→success→`0x2d516` debit
  →product loop。Docker Capstone重讀`0x2d516..0x2d620`後，production已接
  先commit新balance、再用FDOTHER current resource entry2的6x99 strip做八位數
  downward odometer：每個不同digit同步減一、0→9、每值9個opaque 6x9 window、
  每phase `0x375b2(10)`。DOSBox內建320×200 capture進一步抓出roll destination
  是literal`0xa7a90=(16,98)`，不是stable gold的`(16,99)`；修正一列offset後，
  `1000→950`的21張debit樣本有16張分別與45個source phases整幀AE=0，另5張
  中斷在`0x2d620`逐列memmove的partial write。新增
  [`shop-purchase-debit-ch02-original-vs-remake.png`](../figures/shop-purchase-debit-ch02-original-vs-remake.png)
  五phase上下對照，再回六幀product list。
  wall-clock 60Hz會依elapsed取樣10ms phase，不保證每個source phase皆實體present；
  扣款的原子影格E2已關閉。購買成功動畫的25/26個DOSBox樣本也各自找到
  整幀AE=0來源影格；唯一第15張在`0x16886`效果寫入途中只差
  `(184,47)/(184,49)`兩點，下一張同一來源影格即AE=0，不列為原子畫面。
  成功動畫與扣款合成切片可升E2；完整商店仍因其他子面板與正常campaign/save
  路徑未閉合而維持部分完成。
- [~] **NATIVE-CURRENT-SNAPSHOT-ROSTER**：合法 IDA Pro 9.4 閉合
  `0x10010` 的 plaintext `0x0000` `0x8a3` FDFIELD 控制映像、
  `0x08a3` persistent roster、`0x12a3` runtime roster、`0x30a3`
  32-byte battle-local event state 與 `0x30c3` 18-byte header。撤回 header `+0` 是 persistent
  count 的錯誤工具斷言；正確為 `+0=turn counter`、`+1=runtime count`、
  `+9=persistent count`。`fdsave.InspectCurrentSnapshot` 已保存兩份 raw
  records、field control、battle-local event state，限制原生容量並有
  聚焦回歸；使用者
  checksum-valid 原版快照
  實測 persistent identities `[0,9,4,30]`。strict identity/class
  catalog 與單筆 `battle.Unit` materialization 已由下一項閉合。IDA 與
  Capstone 證實 `0x10010` 自己載資源、建 selector、恢復畫面；但
  `0x10616→0x4E031` 只複製 absolute `0x41A` word 到 `0x41C`。共享
  epilogue 返回後，main `0x25DCE` 才呼叫 `0x117E7` 控制器；舊「`0x4E031`
  是戰鬥驅動」及「不存在另一個 CONTINUE owner」說法已撤回。後續 IDA／Capstone 已證實
  `[0x53ad5]` 是 `malloc(0x20)` pointer，writer／reader 對稱保存，
  並由 indexed event paths 消費；`Raw30A3` 因而提升為
  `NativeEventState[32]`。`0x0000..0x08a2` 也由 FDFIELD 資源來源、
  對稱 copy 與 `0x1a813/0x13a44/0x10b4e` consumers 閉合為
  `NativeFieldControl[0x8a3]`。控制映像、runtime records/selectors、timing
  與 future-group constructor 已由下列具型別交易分別閉合；chapter0 未改寫
  live 排程已有嚴格 pending roster consumer 與原版快照測試。真正缺的是
  動態 turn-writer／group-formula 的通用 pending-group binding，以及整組 `battle.State` 到正式
  `Game`／controller 的原子 handoff，故正式 CONTINUE 仍維持失敗即關閉
  → `fd2_current_snapshot_ida.txt`、`fd2_current_event_state_ida.txt`、
  `fd2_current_field_control_ida.txt`
- [~] **NATIVE-CONTINUE-RUNTIME-PREFLIGHT**：合法 IDA Pro 9.4 與
  Capstone 閉合 `0x1035c` 清 selector cache count，接著
  `0x1036a..0x1039c` 依 current runtime record order 取每筆 `+7`
  呼叫 `0x11019`，並覆寫該筆 `+2`。撤回「CONTINUE 必須重播新章
  persistent→FDFIELD group construction order」與「存檔 `+2` 必須等於
  cache slot」兩個錯誤模型。`BuildContinueRuntimeInput` 現以明確
  chapter／field dimensions／FDICON group count 原子驗證 counts、
  FDFIELD unit capacity、camera-cursor identity、active record
  presentation 與 first-seen slots；所有 raw 區域深複製，不改
  `battle.State`。後續 IDA/Capstone 又證實標題 caller 的 range mode
  為開場 `0`／返回 `0x117E7` 控制器前 `1`，資料映像 gate B／anchor seed 均為
  `1`，且 anchor 只依已恢復 visible cursor 精確推進；這些值已收入
  `ContinueMapPresentation`。runtime unit、map timing seed adapter 與完整
  future-group constructor transaction 均已閉合；chapter0 靜態 live
  turn/event 已能只綁 groups3..7 共15筆；saved turn 只保留尚未掃描的
  selector0/1，已於上一輪尾端掃描的 selector2 不重綁。preflight
  仍保留動態 pending-group binding 與 `battle_controller_handoff` 兩個
  待 caller 接管的 owners，
  `ReadyForContinue=false`，故正式 CONTINUE 仍失敗即關閉
  → `fd2_continue_selector_rebuild_ida.txt`、
  `fd2_continue_map_presentation_ida.txt`、
  `fd2_continue_pending_schedule_ida.txt`
  - [~] **CONTINUE pending groups 靜態排程切片**：IDA/Capstone 直接證實
    `0x117E7→0x16F55→0x19DF7` 的存檔分支不先進 `0x1A30B`；後者只由
    `0x13565` 玩家階段收束門檻進入，依 raw selector1/0 掃目前回合後才
    `inc [0x53BEF]`，後段才掃 selector2；故 saved turn 只納入 selector0/1，
    selector2 已消費。新增
    `MaterializeNativeContinuePendingGroups`，只在 live `(turn,event_id)` 與
    scenario 完全相符時深複製 future rows／item table；chapter0 原版快照
    綁定 groups3..7 共15列，排除已出場1/2與未排程10/11。map0 舊31×24
    測試註解已依資產更正為24×24；map25/event61 另以真實資產固定
    selector1／slot／once-state12，live selector 不符即拒絕。動態
    event27/54/57、event47/49 formula、
    ch03 slot條件與多個 turn-byte writer 尚未資料化，故 owner 不移除
  - [x] **CONTINUE map timing seed**：IDA 完整 data xrefs 與 Capstone
    raw data 證實 cycles／terrain phase／兩組 binary latch 初值全零，
    terrain override 為 `-1`；唯 `[0x53C0F]` 由 main
    `0x25D83..0x25D8B` 擷取標題入口 signed BIOS low word。
    `ContinueRuntimeContext.TitleTimerTick` 與 `ContinueMapTimingSeed`
    現嚴格保存這個邊界；`MaterializeNativeContinueMapTiming` 原子安裝
    seed，map compositor 只在實際成功合成時取樣並同時發布 timing/pixels，
    已撤回每次 `Game.Update` 推進的錯誤排程。`0x10494`／`0x105ED`
    redraw 間的固定演出／delay 仍由正式 handoff 排程，但不再列為未知
    `map_timing` owner
    → `fd2_continue_map_timing_seed_ida.txt`
  - [x] **CONTINUE FDFIELD control typed view**：依 `0x53A55` 已證實
    layout，`ContinueFieldControlView` 原子拆出 raw header、16 筆
    turn events、16 筆 field events、16 筆 chest controls 與
    count-delimited 26-byte unit rows，並驗證 caller mutation 不會別名
    到輸出。IDA `0x10BCC` 的 exclusive compare 與 chapter0 current
    snapshot／FDFIELD resource1 全同前綴，另固定 raw `+2=30` 只解出
    30 列；資源第31列與容量尾端不冒充 live unit。控制資源不含
    `[0x53A51]` composition live byte `+3`；
    後者由資源 `3N` 另載並經 `0x4DBFC` 重設。下一步仍是把 typed
    control、saved runtime roster 與 chapter asset bundle 一次映射到
    `battle.State`；不可讓 `battle.Load` 的 serialized map provenance
    冒充 current runtime
    → `fd2_current_field_control_ida.txt`
  - [x] **CONTINUE live control mutation boundary**：IDA 完整 data xrefs
    與 Capstone 直接指令證實 `[0x53A55]` 會在戰鬥中被改寫：
    `0x19357` 更新 chest value，`0x34AB4/0x34AC5` 及多個 chapter
    handler 更新 turn event bytes。故 current snapshot 的
    `NativeFieldControl` 是唯一 live control 來源，不可由原始 FDFIELD
    resource 或 map JSON 覆寫；control rows 只供未來
    `0x10B4E→0x10C50` group append，現有單位仍由 saved runtime
    records 決定。同步刪除 doc26 把 party/FDFIELD constructors 拼成
    單一路徑及把 row bytes 錯套 runtime offsets 的舊表
    → `fd2_current_field_control_mutations_ida.txt`
  - [x] **CONTINUE live field boundary adapter**：
    `MaterializeNativeContinueFieldBoundary` 會從公開 input 重建 snapshot、
    重跑完整 preflight 並逐欄比對，故 marker 存在但內容被竄改也會拒絕；
    再配合相符的 chapter asset，檢查 dimensions／field-event topology 後
    原子安裝 exact control、turn/field/chest/future-unit rows、event
    state、raw round、view、HUD 與 opening range mode 0。輸入與輸出
    均不別名；拒絕路徑不改 state。它明確不碰現有 Units、timing、
    interactive mode 1 或正式 `Game`／`0x117E7` 控制器轉接。原本籠統的
    field-runtime owner 已由後續的 runtime-unit、map-timing 與
    future-group 具型別交易逐項關閉；目前只剩 chapter asset 的 pending-group
    binding，以及正式 `Game`／controller handoff 兩個 caller-owned 邊界。
  - [x] **CONTINUE saved runtime unit projection**：
    `MaterializeNativeContinueRuntimeUnits` 只接受已重驗 input 與逐筆相符的
    live field boundary；先在 detached roster 驗證 raw camp 0/1/2、
    class、active presentation 及 first-seen selector cache，再依 saved
    runtime record 順序原子替換 `State.Units`。它完整保存
    `+0/+1/+3/+4/+5/+6/+7/+8`、command mask、race/class、
    transient、`+34..+36`、`+42/+46`、八格 inventory 與 signed stats；
    saved `+2` 永不採信。撤回「所有 runtime +8 都是 identity」：只有
    native camp2 player record 依 persistent 契約提升
    `NativeIdentity`，其餘只保存 `NativeRecordByte8`。
    checksum-valid 原版 chapter0 current snapshot 的12筆 records 已在
    Docker 整合測試全數通過，前四名為索爾、悠妮、亞雷斯、蓋亞，
    enemy `+8=96` 不具 identity。adapter 不設定 timing、不 append future
    group、不切 interactive mode、不發布正式 `Game`／controller handoff；
    正式 CONTINUE 仍失敗即關閉。
    同輪同步遷移33份 map unit assets：scripted FDFIELD `b1` 現輸出
    `native_record_byte8`，不再輸出 `native_identity`；同步工具
    `--check` 全數零 pending，AI／item-panel raw record consumers 仍取得
    相同位元，但不再攜帶錯誤角色語意。
  - [~] **CONTINUE future group constructor inputs**：完整 Docker
    Capstone `0x10B4E..0x11018` 固定 group row order、6-byte position
    record、`b2→runtime +0x3D`、`b13..16→+0x1A..1D`、
    `b17..19→+0x34..36`、`b22..24→+0x31..33`；`b3/b20/b25`
    在 constructor 內無 reader。撤回 `b2/b3` 是 runtime race/class 的
    暗示，後者來自 b1-selected EXE tables。33份 map assets 已保存 exact
    position record、raw +3D、death triple、未讀 source bytes 與
    b1-selected constructor table record，loader 及 CONTINUE projection
    也保留 runtime raw 欄。`NativeFutureGroupPlacement` 已精確轉寫
    `0x145CD(0/1)` occupancy、raw `[0x53AFA]` gate、全圖 row-major
    Manhattan 與同距離後者勝出；舊半徑環狀 `nearestFree` 已明確降為
    legacy 呈現。`DecodeNativeFutureConstructorBase` 已轉寫兩條 table
    分支，33圖1,885筆 record 的 race/class/HP/MP 交叉驗證通過。
    table dump 已自帶 FD2.EXE size/MD5/SHA-256，sync 在使用前強制對照
    reference manifest；Docker 重生檔與版本化 JSON 逐位元組相同。
    official IDA 9.4 已將 `[0x53AFA]` 完整關閉為唯一 reader＋11組
    set1/call/reset0；25筆 handler spawn 與34筆 global event call 現保存
    source/via/`raw_placement_gate`，缺欄位的原版 handler fail-closed。
    `AppendGroupWithNativePlacement` 已把 handler Beat 接到 exact gate、position
    row、逐列 occupancy 與 group append，且 batch preflight 失敗不改 roster／
    units；runtime Xvfb regression 通過。global turn-event 的45筆 schedule 現
    產生46個 editable actions，全部保存 `native_event_id` 與逐 call
    source/via/gate；排程內六筆 gate=1 固定。正式 runner 對
    `runtime_append_groups` 逐 call 走 exact placement，缺 roster 失敗即關閉；
    未遷移情境仍是正規化相容（normalized compatibility），不是忠實度證據。
    產生器對同回合
    多 schedule／event 改綁拒絕合併，`--scenarios-only` 可避免舊生成拓撲覆蓋
    權威 `campaign_full.json`。ch02 turn3/event6 的版本化 action 已驗證六名
    group3 友軍採 gate=1 原始位置；錯誤不再呼叫回合完成回呼（continuation）。
    official IDA 9.4 已固定 `0x32999` 的四個 caller、本體不含 `0x1366A`、
    FDOTHER #9 固定12次 indexed compositing/presentation；global event1/2
    的 editable call metadata 另保存後續 ACTING(3/4) 與 call-site。handler
    的 `0x32999` adapter 已接 FDOTHER #9 的12次呈現、舊／新增槽位邊界、
    pass6/7/8 快照重建與 pass1 的 FDOTHER #95；完整預檢成功才發布 roster，
    每次 Draw 確認後才前進，再由下一個 beat 執行 caller ACTING。ch00 真實
    handler 回歸已驗證兩次各12幀後仍進入 battle_ch01、戰後、城鎮與整備。
    ch01 global event1/2 亦已由 battle-event runner 承接：turn3 建立14槽 frontier，
    turn4／5 分別 preflight group4／5、各12次呈現、ACTING(3／4)，event2 對話只在
    acting 完成後出現。缺 acting 資源的回歸固定 units／roster／selector cache／
    turn continuation 均不變；低階 `ExecuteActionChecked` 繼續拒絕無畫面擁有者的
    直接呼叫。`0x10C50` 的 table-base、八格 inventory 與 `0x1B750` 即時
    equipment／modifier 重算現已由合法 IDA＋Capstone 閉合，並原子接入
    future-group append；來源 roster 在失敗時不被改寫。正式 CONTINUE 的其他
    owner、完整 0x50-byte identity 與 DOSBox E2 仍維持 fail-closed
    → `fd2_future_group_constructor_capstone.txt`、
      `fd2_future_group_raw_gate_ida.txt`、
      `fd2_runtime_equipment_recalc_1b750_ida.txt`、`fd2_spawn_intro_32999_ida.md`
- [x] **RE-CHAPTER-AUX-GRAPHICS-10652**：合法 IDA Pro 9.4 與 Docker
  Capstone 固定 `0x10652..0x1088d` 只有 CONTINUE、完整章節 loader、
  ch22 post 三個 caller。函式先釋放 `[0x53aff]/[0x53b03]`，再只對 raw
  chapter `9/17/21–25/27–29` 載入或展開特定 FDOTHER 輔助圖形；它不負責
  FDFIELD/FDSHAP/FDTXT/roster 的完整章節載入。撤回 exporter 的
  `load_ch_bg`，改為 `prepare_chapter_aux_graphics`，並以 compiler
  regression 固定尚無 runtime lowering 時必須失敗即關閉。全量重生另
  暴露 exporter 尚無法重建 ch14/ch16/ch25 後續人工閉合的 structured
  branches；在 generator 補齊前不得用全量輸出覆蓋那些 canonical assets
  → `fd2_chapter_aux_graphics_10652_ida.txt`
- [x] **HANDLER-LOADCH-OBSOLETE-NAME-GATE**：全量機械重生確認
  `0x25870→0x1088d` 現由 exporter 正確輸出 `loadch`，同步 ch29 raw／editable
  artifact 與統計。刪除 compiler 對舊 `load_ch_text` 名稱的相容降階；
  現在即使提供完整 binding 也會失敗即關閉，只有 `loadch` 可在 map、
  roster、slot count、story context 完整時降階。
- [~] **NATIVE-PERSISTENT-PARTY-MATERIALIZATION**：新增與參考 EXE
  SHA-256 綁定的可編輯 32 人 identity／class 0–28 catalog，以及嚴格
  `PersistentRecord→battle.Unit` 投影。保留 raw inventory flags、command
  mask、transient、race/class、base/effective stats，並依
  `0x10a77→0x11019` 投影 record `+7` 為 `MapSelectorKey`；不把它推導成
  portrait、Fig、identity、座標或章節。合法 IDA Pro 9.4 已證實
  class 顯示直接使用 `150+raw class`；固定雜湊 FDTXT 的 class 27 是
  兩個全形空格、class 28 是「？？？」，舊 `cls28`／`?`／「職業28」
  占位已移除。`FD2_NATIVE_SAVE_FIXTURE` Docker 整合測試已
  唯讀走完 current snapshot 四筆 record，實得索爾、悠妮、亞雷斯、蓋亞。
  下一步是閉合上述 current battle runtime；目前不接 CONTINUE。四槽 LOAD
  的 `0x2cad7` 戰間 restore owner 已由後續項目接入，尚缺一般玩家有效槽 E2。
- [x] **MAP26-EVENT62-DORMANT-TURN-ACTIVATION**：完整33圖×16列
  `native_turn_event_controls.json` 已由 FDFIELD raw resource 決定性重生；
  目錄同時保存固定 FD2.EXE 雜湊與 `0x2066E` 已證實的戰鬥回合初始值1，
  新戰鬥由此取得 event62 所需回合來源，CONTINUE 則保留快照即時值；
  執行期鎖定完整目錄 SHA-256 與 map 0–32 唯一集合，竄改控制列／寫入端／
  地圖身分的負向回歸均失敗即關閉；
  `0xff` 休眠列不再被 parser 丟棄，也不會進入第255回合排程。event62 的
  selector0／state17／slot0 event63 raw-camp0／native-round+1 已成可編輯規則，
  並接到向左一步第七拍的正式 selector0 owner；raw/typed 不一致與重複觸發
  在 mutation 前拒絕。同步更正 `0x35822` 來源
  `PUSH` 順序為 `(group,y,x)`，以 ch27 `[6,16,0]` 及 ch28 `[8,19,9]`
  非對稱回歸鎖定；event63 兩個 staging calls 已進固定雜湊的
  `event_id_groups.json`；同一擷取器亦保存 event64／66／68／70／72 的
  staging calls，但都仍不冒充一般 spawn。
- [x] **MAP26-EVENT63-DYNAMIC-RUNNER（重製端 E1）**：IDA／Capstone 直接
  順序已閉合 `sub_1A813(0)` 位於 `0x1D8BA` 敵軍 AI 前。ch27 的
  `native_turn_events` 將 live row0 精確交給獨立 raw camp0 owner，並把
  group1／2 從開局 initial roster 移到待增援 roster。runner 依
  `0x358C7..0x358E5` 執行 group1@(3,27)、group2@(15,27) 的 pan、native
  constructor、300ms、全 DAC 白閃、200ms、baseline restore、redraw，完成後
  才啟動 AI；兩批先在私人 state 完整預演，錯誤第二批不會部分發布第一批。
  gate A／anchor 的持續擁有者與 controller gate B=1 已接成
  `native_map_hud_inherited`；production regression 以明確帶 persistent raw
  `+0x42` 的凱麗 fixture 走 indexed DAC，不由 ch27 近似 HP 反推。缺完整 raw
  unit record 時仍只對既有 RGB 戰場使用數學上等價的全白覆蓋，不宣稱一般
  RGB palette adapter。
- [ ] **MAP26-EVENT63-E2-PLAYER-PATH**：從未修改 ch27 一般玩家路徑完成
  event62 向左一步、跨到下一 native round、觸發 event63，再以 DOSBox 同
  camera/roster/tick 逐幀比對兩次白閃與增援。ch27 戰前 view／selector0 已
  閉合並接線，persistent HUD 擁有者也已達 E1；本項剩餘該時點真實 roster
  raw record、CONTINUE 邊界及原版逐幀 oracle。完成前 event63 仍不可標成 E2。
- [ ] **REAL-UI-MOVE-CONFIRM-ENTER-SPACE-INTERMITTENT-INPUT-DROP**(原
  `CH27-REAL-UI-MOVE-CONFIRM-BROKEN`，doc58 續五十四訂正範圍/措辭)：
  `0x115b6`(mode 4)移動確認的 `Enter`/`Space` 鍵**不是 ch27 這個存檔
  100% 壞掉**——doc58 續四十五已用斷點(`FUN_0004e4f6`回傳`5`非`0xff`)
  +screenshot 在**同一份存檔**(`FD2.SAV` md5
  `e6d9a35756cddfc2519969b10f039181`)上，用同一套「Up×5→Enter」手法
  成功走通過一次；但續四十七起到續五十四，同一份存檔、同一手法反覆失敗，
  屬於**跨 session 的間歇性(intermittent)輸入傳遞失效**，不是這個存檔/
  這段程式邏輯必然壞掉。續五十四用斷點在失敗當下直接證實：CPU 確實停在
  `FUN_00012dac`(native `0x12dac..0x12e37`，`0x115b6` 專用阻塞式讀鍵
  輪詢器)合法等鍵，不是當機/跑飛；對已卡住的同一個讀鍵迴圈送 `Enter`
  或 `Space`，`LAB_00011719`(native `0x11719`，confirm 驗證段)與函式
  `RET`(native `0x117e6`)斷點皆從未命中；但在完全相同的一刻送方向鍵
  `Up`，畫面立即正確反應(游標位移)——證實問題精確收斂在 `Enter`/`Space`
  這兩個 scancode 選擇性地沒有被這個讀鍵迴圈觀察到，不是整體輸入管線
  不通，也不是這段反組譯邏輯本身的 bug。續五十四同時用一輪從頭到尾零
  `Alt+Pause` 的乾淨對照組重現過失敗，排除「debugger 介入本身擾動輸入
  時序」是唯一成因；force-release(`xdotool keyup`)後重送也無法修復。
  **仍未解決**：這個選擇性掉鍵背後在 SDL2/DOSBox-X/Xvfb 哪一層發生、
  為何同一存檔同一手法時好時壞，doc58 續五十四誠實列為下一輪候選方向
  (DOSBox-X mapper 對 Return/Space 的特殊處理、`FUN_00010620` 本身尚未
  反組譯)。**doc58 續五十五(2026-08-24)補充**：窮盡搜尋英文+中文 upstream
  資料，找到唯一具體候選——`bugs.freedesktop.org` #4761「`XTestFakeKeyEvent`
  broken in Xvfb」(2005，Xvfb 下部分按鍵事件遺失/重複，真正 X server 不會，
  緩解為每鍵間隔 200ms+)；直接讀 dosbox-x 原始碼(`sdlmain.cpp`/
  `keyboard.cpp`，確認是 SDL2 build)與 xdotool 原始碼(`xdo.c`)均未找到
  Linux 路徑上對 Enter/Space 的差異化處理（唯一特例是 `#if MACOSX` 包住的
  IME 分支，Linux 不編譯）。Live 重現同一卡住畫面後**連續測試 4 種候選並
  全部失敗**：400ms keydown/keyup hold、`xdotool key --delay 300` 原子呼叫、
  Space 300ms hold、`--clearmodifiers`——同一時刻送 `Up` 仍立即正確反應
  (對照組)。**結論：「加長延遲/清除 modifier 能修好」這個具體假說已被明確
  證偽**，不只是未驗證；freedesktop #4761 這類一般性 Xvfb 不可靠即使真實
  存在，也不是這裡選擇性 Enter/Space 掉鍵的直接成因，或至少不是簡單延遲
  能解的那種表現形式。下一輪建議：(a) 靜態反組譯 `FUN_00010620`；
  (b) 用 `xev` 等工具在 X11 層獨立驗證 KeyPress/KeyRelease 事件本身有無
  抵達 X server，把「X11 有沒有收到」與「DOSBox-X/SDL2 有沒有處理」分開
  驗證；(c) 測試「debugger 是否曾經介入過同一個 Xvfb 環境」的殘留效應
  （兩輪失敗重現都沒有專門控制這個變因）。目前繞過方式仍是 SMV-teleport
  (與 ch24 續二十/二十一/二十三/
  二十四已驗證過的手法相同，非新發明)，不是真正解法；攻擊執行本身已在此
  繞過法下用斷點證實無誤(`0x1AD75F`確認閘門通過、`0x1CA2B0`=native
  `0x2e2b0`攻擊orchestrator命中、目標HP `15→0`、Sor `record[+5]`
  `0x00→0x80`，見doc58 續五十三)；本項要解的是「為何真實UI的Enter/Space
  確認移動會間歇性失效」本身，不是攻擊邏輯，也不是這個存檔/章節專屬的問題。
