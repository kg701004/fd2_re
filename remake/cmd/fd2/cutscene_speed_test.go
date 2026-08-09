package main

import (
	"os"
	"testing"
)

// TestMain 讓整個 cmd/fd2 測試套件用原版節奏(cutsceneSpeedUp=1)跑。既有的
// beat/battle-event 計時測試(如 TestBeatFadeBothDirectionsCallThen、
// TestBeatScrollStepSlot2MatchesCh00ACT99Followup、
// TestChapter3Turn3BattleEventBlocksTurnUntilOriginalSequenceCompletes)是
// 逐 tick 對照反組譯位址算出來的原版精確節奏(doc50/doc46),寫測試時預設
// 1 tick=1 原生幀;過場加速只該影響實際遊玩體驗,不能讓這些證據性測試跟著
// 變快而失真。cutsceneSpeedUp 本身的 loadCutsceneSpeedUp()/decTimer() 邏輯有
// 自己專屬的測試(TestLoadCutsceneSpeedUp*/TestDecTimer*),不受此影響。
func TestMain(m *testing.M) {
	cutsceneSpeedUp = 1
	os.Exit(m.Run())
}

func TestLoadCutsceneSpeedUpDefaultsToFast(t *testing.T) {
	t.Setenv("FD2_CUTSCENE_SPEED", "")
	if got := loadCutsceneSpeedUp(); got != 5 {
		t.Errorf("loadCutsceneSpeedUp() with no env = %d, want 5", got)
	}
}

func TestLoadCutsceneSpeedUpHonorsEnvOverride(t *testing.T) {
	t.Setenv("FD2_CUTSCENE_SPEED", "1")
	if got := loadCutsceneSpeedUp(); got != 1 {
		t.Errorf("loadCutsceneSpeedUp() with FD2_CUTSCENE_SPEED=1 = %d, want 1 (native pacing)", got)
	}
}

func TestLoadCutsceneSpeedUpIgnoresInvalidOverride(t *testing.T) {
	for _, bad := range []string{"0", "-3", "not-a-number", "1.5"} {
		t.Run(bad, func(t *testing.T) {
			t.Setenv("FD2_CUTSCENE_SPEED", bad)
			if got := loadCutsceneSpeedUp(); got != 5 {
				t.Errorf("loadCutsceneSpeedUp() with FD2_CUTSCENE_SPEED=%q = %d, want fallback 5", bad, got)
			}
		})
	}
}

func TestDecTimerFloorsAtZeroForExactEqualityChecks(t *testing.T) {
	old := cutsceneSpeedUp
	cutsceneSpeedUp = 5
	defer func() { cutsceneSpeedUp = old }()

	cases := []struct{ in, want int }{
		{10, 5},
		{5, 0},
		{3, 0}, // must floor at 0, not go negative, so callers' `== 0` check still fires
		{1, 0},
		{0, 0},
	}
	for _, c := range cases {
		if got := decTimer(c.in); got != c.want {
			t.Errorf("decTimer(%d) = %d, want %d", c.in, got, c.want)
		}
	}
}
