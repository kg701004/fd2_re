// Package objectives holds the player-visible per-chapter win/lose/recruit
// conditions used by the level-start objectives screen.
//
// Evidence level: E3 (authored reference). This table is transcribed from
// docs/knowledge-base/28-chapter-objectives-and-recruits.md, which is itself
// normalized from a player walkthrough (青衫攻略) cross-checked against a
// handful of partially-closed native handler addresses. It is NOT a verified
// native ABI decode: per that document, "攻略與 battle_events.json 只能作
// authored/normalized 起點，不能取代逐章 handler...的證據" (the walkthrough
// is only an authored starting point; it cannot replace per-chapter native
// handler evidence). Do not present this data to a player, or consume it in
// gameplay-affecting logic, as if it were a decoded native rule — it is a
// convenience reference pending per-chapter closure.
//
// Chapter numbering follows the walkthrough's 1-based "第 N 章" and matches
// FDTXT.DAT block N directly (see FD2_format_notes.md's complete 34-block
// chapter map): walkthrough chapter N == remake chapter index N-1 ==
// battle_events.json chapter N-1 == FDFIELD.DAT stage N-1.
package objectives

// Chapter is one walkthrough-sourced chapter's player-visible objective set.
type Chapter struct {
	// Number is the 1-based walkthrough chapter number ("攻略第 N 章").
	Number int
	// Title is the chapter's walkthrough title.
	Title string
	// WinCondition describes the player-visible victory condition in
	// Traditional Chinese, ready for direct on-screen display.
	WinCondition string
	// GuardTargets lists additional units whose death causes defeat, beyond
	// the universal "索爾死亡" (Sol's death) rule common to every chapter.
	// Empty when the chapter has no extra guard target.
	GuardTargets []string
	// Recruits lists characters who may join this chapter, with their
	// join condition in Traditional Chinese when the walkthrough records
	// one (e.g. "出現前勿滅完", "未死"). Empty when nobody joins.
	Recruits []RecruitCondition
}

// RecruitCondition is one candidate recruit and the walkthrough-recorded
// condition for them to actually join the party this chapter.
type RecruitCondition struct {
	// Who is the character's name.
	Who string
	// Condition is the join condition in Traditional Chinese, or empty
	// when the walkthrough records no extra condition beyond surviving
	// the chapter.
	Condition string
}

// FailCondition is the universal, chapter-independent defeat rule common to
// every chapter in the walkthrough table (source doc28 §2 header note).
const FailConditionUniversal = "索爾死亡"

// Chapters is the complete 30-chapter table, indexed 0..29 matching
// battle_events.json's 0-based chapter field (== walkthrough chapter - 1).
// Use ByNumber to look up by the player-visible 1-based walkthrough number.
var Chapters = []Chapter{
	{Number: 1, Title: "初試身手", WinCondition: "敵全滅",
		Recruits: []RecruitCondition{{Who: "哈諾", Condition: "出現前勿滅完"}}},
	{Number: 2, Title: "羅德鎮", WinCondition: "敵全滅",
		GuardTargets: []string{"村民全滅"},
		Recruits:     []RecruitCondition{{Who: "希莉亞"}}},
	{Number: 3, Title: "往塞拉村途中", WinCondition: "敵全滅",
		Recruits: []RecruitCondition{{Who: "鐵諾", Condition: "未死"}}},
	{Number: 4, Title: "塞拉村前", WinCondition: "敵全滅"},
	{Number: 5, Title: "塞拉村", WinCondition: "消滅卡特那",
		Recruits: []RecruitCondition{{Who: "瑪琳"}}},
	{Number: 6, Title: "普里茲港", WinCondition: "敵全滅",
		Recruits: []RecruitCondition{{Who: "貝克威"}}},
	{Number: 7, Title: "往王城途中", WinCondition: "敵全滅",
		Recruits: []RecruitCondition{{Who: "凱麗", Condition: "未死"}}},
	{Number: 8, Title: "王城前的戰鬥", WinCondition: "敵全滅",
		Recruits: []RecruitCondition{{Who: "洛娜"}}},
	{Number: 9, Title: "騎士的抉擇", WinCondition: "敵全滅",
		Recruits: []RecruitCondition{{Who: "萊汀"}}},
	{Number: 10, Title: "洞窟中的激戰", WinCondition: "敵全滅",
		GuardTargets: []string{"索菲亞", "卡納恩三世"},
		Recruits:     []RecruitCondition{{Who: "萊汀"}, {Who: "索菲亞"}}},
	{Number: 11, Title: "幻之森林", WinCondition: "敵全滅",
		Recruits: []RecruitCondition{{Who: "珊"}}},
	{Number: 12, Title: "北山道", WinCondition: "敵全滅",
		GuardTargets: []string{"米亞斯多德"},
		Recruits:     []RecruitCondition{{Who: "米亞斯多德"}}},
	{Number: 13, Title: "哈斯米爾之戰", WinCondition: "敵全滅",
		GuardTargets: []string{"精靈族全滅"}},
	{Number: 14, Title: "平原的會戰", WinCondition: "敵全滅"},
	{Number: 15, Title: "拉卡湖的激戰", WinCondition: "敵全滅",
		GuardTargets: []string{"賽可邦勒"},
		Recruits:     []RecruitCondition{{Who: "賽可邦勒"}}},
	{Number: 16, Title: "冰原之戰", WinCondition: "敵全滅",
		GuardTargets: []string{"蜜蒂"},
		Recruits:     []RecruitCondition{{Who: "蜜蒂", Condition: "HP320以上／18回合內／部下陣亡未過半"}}},
	{Number: 17, Title: "血與冰之刃", WinCondition: "敵全滅",
		Recruits: []RecruitCondition{{Who: "凱拉斯"}}},
	{Number: 18, Title: "遙遠的彼岸", WinCondition: "黑暗騎士死亡",
		GuardTargets: []string{"約拿", "蘭斯洛特"},
		Recruits:     []RecruitCondition{{Who: "約拿"}, {Who: "蘭斯洛特"}}},
	{Number: 19, Title: "黑暗中的狙擊", WinCondition: "敵全滅",
		GuardTargets: []string{"巴拿羅西亞"},
		Recruits:     []RecruitCondition{{Who: "巴拿羅西亞", Condition: "出現前勿滅完"}}},
	{Number: 20, Title: "死亡般的沈寂", WinCondition: "沼澤怪物外敵全滅",
		GuardTargets: []string{"謝多", "精靈全滅"},
		Recruits:     []RecruitCondition{{Who: "謝多"}, {Who: "達可塞", Condition: "15回合內"}}},
	{Number: 21, Title: "亞述森林", WinCondition: "敵全滅",
		GuardTargets: []string{"羅蘭", "希爾法"},
		Recruits:     []RecruitCondition{{Who: "希爾法"}, {Who: "羅蘭"}}},
	{Number: 22, Title: "遠古呼喚", WinCondition: "敵全滅",
		GuardTargets: []string{"希爾法"},
		Recruits:     []RecruitCondition{{Who: "莎拉", Condition: "出現前勿滅完"}}},
	{Number: 23, Title: "向天空之旅", WinCondition: "擊毀機甲隊長",
		GuardTargets: []string{"希爾法", "卡里斯", "羅德曼"},
		Recruits:     []RecruitCondition{{Who: "卡里斯", Condition: "持天空之鑰"}}},
	{Number: 24, Title: "在天空的彼方", WinCondition: "敵全滅"},
	{Number: 25, Title: "火焰的審判", WinCondition: "敵全滅",
		GuardTargets: []string{"聖寇拉斯"},
		Recruits:     []RecruitCondition{{Who: "亞奇梅吉"}, {Who: "聖寇拉斯"}}},
	{Number: 26, Title: "未知的迴廊", WinCondition: "敵全滅",
		GuardTargets: []string{"悠妮", "亞奇梅吉"},
		Recruits:     []RecruitCondition{{Who: "渥德"}}},
	{Number: 27, Title: "命運的交會點", WinCondition: "擊毀機甲隊長",
		GuardTargets: []string{"悠妮"}},
	{Number: 28, Title: "探索者", WinCondition: "擊毀機甲隊長",
		GuardTargets: []string{"悠妮"}},
	{Number: 29, Title: "探索者(防衛)", WinCondition: "解除防衛系統",
		GuardTargets: []string{"悠妮"}},
	{Number: 30, Title: "傳說的終章", WinCondition: "空魔神死亡",
		GuardTargets: []string{"悠妮", "(地/水/風/火魔神連鎖)"}},
}

// ByNumber returns the chapter with the given 1-based walkthrough number and
// true, or a zero Chapter and false when out of range.
func ByNumber(number int) (Chapter, bool) {
	for _, c := range Chapters {
		if c.Number == number {
			return c, true
		}
	}
	return Chapter{}, false
}
