package campaign

import "errors"

const nativeShopServiceBaseOffset = 0xd430

var nativeShopServiceDisplacements = [4]int{-39, -13, 13, 39}

// ComposeNativeShopServiceOpeningFrame reproduces one of 0x2d669's four
// option-spread frames. Step zero is nearest the common anchor; step three
// reaches the native steady destinations. All four entries use their odd
// (normal) resource variants exactly as the opening loop does.
func ComposeNativeShopServiceOpeningFrame(
	stable []byte,
	assets *NativeShopAssets,
	step int,
) ([]byte, error) {
	if len(stable) != NativeShopWidth*NativeShopHeight || assets == nil ||
		step < 0 || step > 3 {
		return nil, errors.New("campaign: native shop service opening state is invalid")
	}
	frame := append([]byte(nil), stable...)
	divisor := 4 - step
	baseX := nativeShopServiceBaseOffset % NativeShopWidth
	baseY := nativeShopServiceBaseOffset / NativeShopWidth
	for option := 0; option < 4; option++ {
		x := baseX + nativeShopServiceDisplacements[option]/divisor
		if err := assets.ServiceCells[option][0].BlitAt(
			frame, NativeShopWidth, x, baseY,
		); err != nil {
			return nil, err
		}
	}
	return frame, nil
}

// ComposeNativeShopServiceClosingFrame reproduces 0x2d669(a1!=0): each
// option contracts from its full displacement using divisor step+1. After
// step three the native caller restores the cleared stable snapshot.
func ComposeNativeShopServiceClosingFrame(
	stable []byte,
	assets *NativeShopAssets,
	step int,
) ([]byte, error) {
	if len(stable) != NativeShopWidth*NativeShopHeight || assets == nil ||
		step < 0 || step >= 4 {
		return nil, errors.New("campaign: native shop service closing state is invalid")
	}
	frame := append([]byte(nil), stable...)
	divisor := step + 1
	baseX := nativeShopServiceBaseOffset % NativeShopWidth
	baseY := nativeShopServiceBaseOffset / NativeShopWidth
	for option := range assets.ServiceCells {
		x := baseX + nativeShopServiceDisplacements[option]/divisor
		if err := assets.ServiceCells[option][0].BlitAt(
			frame, NativeShopWidth, x, baseY,
		); err != nil {
			return nil, err
		}
	}
	return frame, nil
}

// ComposeNativeShopServiceSteadyFrame reproduces 0x2d9fe's selected-option
// redraw on the fully spread menu. Native phase/2 selects the odd normal cell
// for phases 0..1 and the adjacent even selected cell for phases 2..3.
func ComposeNativeShopServiceSteadyFrame(
	stable []byte,
	assets *NativeShopAssets,
	selected, phase int,
) ([]byte, error) {
	if len(stable) != NativeShopWidth*NativeShopHeight || assets == nil ||
		selected < 0 || selected >= 4 || phase < 0 || phase >= 4 {
		return nil, errors.New("campaign: native shop service steady state is invalid")
	}
	frame := append([]byte(nil), stable...)
	baseX := nativeShopServiceBaseOffset % NativeShopWidth
	baseY := nativeShopServiceBaseOffset / NativeShopWidth
	for option := 0; option < 4; option++ {
		variant := 0
		if option == selected {
			variant = phase / 2
		}
		x := baseX + nativeShopServiceDisplacements[option]
		if err := assets.ServiceCells[option][variant].BlitAt(
			frame, NativeShopWidth, x, baseY,
		); err != nil {
			return nil, err
		}
	}
	return frame, nil
}
