package campaign

import (
	"errors"

	"github.com/wicanr2/fd2_re/remake/internal/dato"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

const nativeChurchReviveEffectOffset = 665747 - 655360

// NativeChurchReviveSuccessPlan preserves the case-4 branch of 0x2f4c6.
// BIOS waits and millisecond DAC waits remain distinct because the original
// uses 0x17aa9 for the former and delay(4) for the latter.
type NativeChurchReviveSuccessPlan struct {
	StartMusicTrack         int
	ReturnMusicTrack        int
	MusicLoopCount          int
	AnimationDelayBIOSTicks int
	RisePaletteDeltas       []int
	PaletteDelayMS          int
	RiseLatchBIOSTicks      int
	FallPaletteDeltas       []int
	FallLatchBIOSTicks      int
}

func PlanNativeChurchReviveSuccess() NativeChurchReviveSuccessPlan {
	rise := make([]int, 0, 32)
	for delta := 0; delta < 64; delta += 2 {
		rise = append(rise, delta)
	}
	fall := make([]int, 0, 32)
	for delta := 62; delta >= 0; delta -= 2 {
		fall = append(fall, delta)
	}
	return NativeChurchReviveSuccessPlan{
		StartMusicTrack:         17,
		ReturnMusicTrack:        11,
		MusicLoopCount:          1,
		AnimationDelayBIOSTicks: 2,
		RisePaletteDeltas:       rise,
		PaletteDelayMS:          4,
		RiseLatchBIOSTicks:      10,
		FallPaletteDeltas:       fall,
		FallLatchBIOSTicks:      5,
	}
}

// ComposeNativeChurchReviveSuccessFrames reproduces the nine sequential
// 0x16886 calls using FDOTHER#14 entries 23..31 at literal VGA (147,32).
// Each frame is applied over the preceding frame; the native caller does not
// restore the background between calls. The returned final frame includes the
// DATO mode-0 restore performed after the palette sequence.
func ComposeNativeChurchReviveSuccessFrames(
	background []byte,
	effectFrames []fdother.Frame,
	portrait dato.Frame,
) (animation [][]byte, final []byte, err error) {
	if len(background) != 320*200 || len(effectFrames) != 9 {
		return nil, nil, errors.New("campaign: native revive success assets are invalid")
	}
	staged := append([]byte(nil), background...)
	animation = make([][]byte, 0, len(effectFrames))
	for _, effect := range effectFrames {
		if err := effect.BlitAt(
			staged, 320, nativeChurchReviveEffectOffset, -1,
		); err != nil {
			return nil, nil, err
		}
		animation = append(animation, append([]byte(nil), staged...))
	}
	final = append([]byte(nil), staged...)
	if err := portrait.BlitAtOffset(final, 320, 4*320+118); err != nil {
		return nil, nil, err
	}
	return animation, final, nil
}
