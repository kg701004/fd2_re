package main

import (
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/campaign"
	"github.com/wicanr2/fd2_re/remake/internal/objectives"
)

// TestLoadCHBeatShowsObjectivesScreenThenResumesBeatRunner exercises the real
// integration path: a compiled "loadch" beat (assets/cutscenes/bindings/
// ch01_pre.json, the same binding TestChapter1PreLoadCHUsesFiveMemberJoinOrderAndSpawnFrontiers
// uses) should, after successfully applying chapter state, block the beat
// runner behind the objectives screen instead of immediately advancing — and
// resume once dismissObjectivesScreen runs (the campInput Enter/Space path,
// factored out so this doesn't need to drive ebiten's key polling).
func TestLoadCHBeatShowsObjectivesScreenThenResumesBeatRunner(t *testing.T) {
	beats, issues, err := campaign.CompileHandlerBinding(assetPath("assets/cutscenes/bindings/ch01_pre.json"))
	if err != nil || len(issues) != 0 || len(beats) == 0 || beats[0].LoadCH == nil {
		t.Fatalf("compile ch01_pre err=%v issues=%#v first=%#v", err, issues, beats)
	}
	if beats[0].LoadCH.Chapter != 1 {
		t.Fatalf("test assumes ch01_pre's loadch is the 0-based stage-1 (walkthrough ch2) transition, got Chapter=%d", beats[0].LoadCH.Chapter)
	}

	g := newBeatTestGame(t, beats)
	g.partyMembers = map[int]bool{0: true, 9: true, 4: true, 30: true, 1: true}
	g.partyJoinOrder = []int{0, 9, 4, 30, 1}

	g.beatAdvance() // beatIdx -1 → 0, starts the loadch beat

	if g.objChapter != 2 {
		t.Fatalf("after loadch(stage=1) objChapter = %d, want 2 (walkthrough chapter 2, per objectives package doc: N == stage+1)", g.objChapter)
	}
	if g.beatIdx != 0 {
		t.Fatalf("beat runner must stay parked on the loadch beat while the objectives screen is shown, beatIdx=%d", g.beatIdx)
	}
	wantTitle := objectives.Chapters[1].Title // Chapters is 0-indexed; chapter 2 is slice index 1
	if c, ok := objectives.ByNumber(g.objChapter); !ok || c.Title != wantTitle {
		t.Fatalf("objectives.ByNumber(%d) = %+v, ok=%v; want title %q", g.objChapter, c, ok, wantTitle)
	}

	g.dismissObjectivesScreen()

	if g.objChapter != 0 {
		t.Fatalf("dismissObjectivesScreen left objChapter=%d, want 0", g.objChapter)
	}
	if g.beatIdx != 1 {
		t.Fatalf("dismissing the objectives screen should advance past the loadch beat, beatIdx=%d, want 1", g.beatIdx)
	}
}

// TestLoadCHBeatSkipsObjectivesScreenForChapterWithoutData covers a stage
// number outside internal/objectives' 30-chapter walkthrough table (e.g. the
// prologue/epilogue "bonus chapter" stages 31-33 documented in
// FD2_format_notes.md, which have no player-visible win/fail/recruit entry):
// the beat runner must advance immediately, exactly as it did before this
// feature existed, rather than blocking on a screen with no content. Reuses
// map0's real assets and only changes Chapter, since applyLoadCH itself does
// not otherwise care what the stage number is.
func TestLoadCHBeatSkipsObjectivesScreenForChapterWithoutData(t *testing.T) {
	loadCH := &campaign.LoadCHState{
		Chapter:       99, // 遠超 objectives.Chapters 涵蓋的 1..30(walkthrough),故意測「無資料」路徑
		Map:           "assets/maps/map0",
		Roster:        "assets/maps/map0/map0_units.json",
		SlotCount:     30,
		Script:        "assets/story/ch01.json",
		PartyScenario: "assets/scenarios/ch01.json",
		PartyOrder:    []int{0, 9, 4, 30},
	}
	if _, ok := objectives.ByNumber(loadCH.Chapter + 1); ok {
		t.Fatal("test setup assumption broken: Chapter=99 should fall outside the 30-chapter table")
	}
	beats := []campaign.Beat{{Op: "loadch", LoadCH: loadCH}, {Op: "dialog", Line: 0, Count: 1}}
	g := newBeatTestGame(t, beats)

	g.beatAdvance()

	if g.objChapter != 0 {
		t.Fatalf("chapter with no objectives data must not block on the screen, objChapter=%d", g.objChapter)
	}
	if g.beatIdx != 1 {
		t.Fatalf("beat runner should have advanced straight past loadch to the dialog beat, beatIdx=%d, want 1", g.beatIdx)
	}
}
