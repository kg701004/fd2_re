package fdother

import (
	"os"
	"testing"
)

func TestDecodeFDSHAP000SpriteBankFromPlayerArchive(t *testing.T) {
	const datPath = "../../../org_game/炎龍騎士團/FLAME2/FDSHAP.DAT"
	if _, err := os.Stat(datPath); os.IsNotExist(err) {
		t.Skip("player-provided FDSHAP.DAT is absent")
	}
	bank, err := DecodeSpriteBankResource(datPath, 0)
	if err != nil {
		t.Fatal(err)
	}
	if len(bank.Sprites) != 288 {
		t.Fatalf("FDSHAP#0 sprite count=%d, want 288", len(bank.Sprites))
	}
}
