package campaign

import (
	"errors"
	"path/filepath"

	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
	"github.com/wicanr2/fd2_re/remake/internal/fdtxt"
)

const (
	NativeTownWidth        = 320
	NativeTownHeight       = 200
	nativeTownLabelX       = 244
	nativeTownLabelY       = 162
	nativeTownTextOffset   = 168*NativeTownWidth + 252
	nativeTownViewportX    = 4
	nativeTownViewportY    = 4
	nativeTownViewportW    = 312
	nativeTownViewportH    = 192
	nativeTownTextBase     = 0x1ef
	nativeTownVariantCount = 3
)

var nativeTownBackgroundResources = [...]int{11, 61, 62}

var nativeTownSelectionX = [nativeTownVariantCount][6]int{
	{29, 41, 59, 154, 182, 10},
	{90, 33, 53, 148, 222, 196},
	{59, 10, 59, 130, 242, 136},
}

var nativeTownSelectionY = [nativeTownVariantCount][6]int{
	{46, 109, 163, 139, 65, 10},
	{30, 105, 163, 139, 85, 8},
	{26, 144, 163, 150, 31, 20},
}

// NativeTownAssets are the exact resources consumed by 0x265ec..0x2670d
// (the real per-frame town-hub redraw, ground-truthed 2026-08-26 -- see
// doc56's erratum; 0x2cd46..0x2d05a was a stale, disproven address from an
// earlier EXE build): three full-screen backgrounds, FDOTHER#10's opaque
// current-label panel, and the full FDICON bank the selector sprite is
// resolved from at draw time.
type NativeTownAssets struct {
	Backgrounds [nativeTownVariantCount][]byte
	Label       fdother.LMI1Entry
	Units       *fdicon.Bank
}

func DecodeNativeTownAssets(
	fdotherPath, fdiconPath string,
) (*NativeTownAssets, error) {
	if fdotherPath == "" || fdiconPath == "" {
		return nil, errors.New("campaign: native town asset path is empty")
	}
	out := &NativeTownAssets{}
	for variant, resourceID := range nativeTownBackgroundResources {
		raw, err := fdother.ReadResource(fdotherPath, resourceID)
		if err != nil {
			return nil, err
		}
		frame, err := fdother.ParseSingleFrame(raw)
		if err != nil || frame.Width != NativeTownWidth ||
			frame.Height != NativeTownHeight {
			return nil, errors.New(
				"campaign: native town background is not 320x200",
			)
		}
		background := make([]byte, NativeTownWidth*NativeTownHeight)
		if err := frame.Blit(background, NativeTownWidth, -1); err != nil {
			return nil, err
		}
		out.Backgrounds[variant] = background
	}
	labelRaw, err := fdother.ReadResource(fdotherPath, 10)
	if err != nil {
		return nil, err
	}
	out.Label, err = fdother.ParseOpaqueRunCell(labelRaw)
	if err != nil || out.Label.Width != 62 || out.Label.Height != 26 {
		return nil, errors.New(
			"campaign: native town label panel is not 62x26",
		)
	}
	bank, err := fdicon.DecodeFile(filepath.Clean(fdiconPath))
	if err != nil || len(bank.Sprites) == 0 {
		return nil, errors.New("campaign: native town FDICON bank is incomplete")
	}
	out.Units = bank
	return out, nil
}

// ComposeNativeTownFrame reproduces 0x265ec's steady redraw (ground-truthed
// 2026-08-26; 0x2cf71 was a stale, disproven address -- see doc56's
// erratum). It starts from the caller-selected FDOTHER background, redraws
// the current-label panel and FDTXT_000 selection name, then draws the
// selector sprite and copies the native 312x192 viewport to VGA (4,4).
//
// leaderKey is the raw FDICON.B24 group key for the selector sprite. It is
// not a fixed asset index: 0x26152's town-hub setup primes the shared
// FDICON pointer cache (0x11019) once per roster record before the redraw
// loop starts, and 0x265ec's draw call always reads the *first*-primed
// cache block, i.e. group 0 = whichever key primed first. That is always
// persistent roster record 0 (0x53bf7 + 0*0x50 + 7) -- the fixed,
// always-present party leader, never the currently-selected town-hub menu
// item. Passing a fixed sprite index here (the pre-2026-08-26 behavior)
// silently assumed that leader's raw key was 0; three real FD2.SAV files
// (chapters 1/2/0xb) all show record 0's byte+7 = 0x20 (32), not 0. Pose is
// always 0 (0x265ec never adds a pose*3 term); cycle is the pulse sequence
// 0,1,2,1, matching 0x2670e's counter-3-to-1 remap.
func ComposeNativeTownFrame(
	assets *NativeTownAssets,
	strings *fdtxt.Strings,
	font *fdtxt.Font,
	variant, selection, pulse, leaderKey int,
) ([]byte, error) {
	if assets == nil || strings == nil || font == nil ||
		variant < 0 || variant >= nativeTownVariantCount ||
		selection < 0 || selection > 5 || pulse < 0 || pulse > 3 ||
		leaderKey < 0 || leaderKey > 0xff ||
		len(assets.Backgrounds[variant]) != NativeTownWidth*NativeTownHeight {
		return nil, errors.New("campaign: native town state is invalid")
	}
	scene := append([]byte(nil), assets.Backgrounds[variant]...)
	if err := assets.Label.BlitOpaqueAt(
		scene, NativeTownWidth, nativeTownLabelX, nativeTownLabelY, false,
	); err != nil {
		return nil, err
	}
	var err error
	scene, err = ComposeNativeChurchTextAt(
		scene, strings, font, nativeTownTextBase+selection,
		nativeTownTextOffset,
	)
	if err != nil {
		return nil, err
	}
	frame := pulse
	if frame == 3 {
		frame = 1
	}
	sprite, err := assets.Units.SpriteFor(leaderKey, 0, frame)
	if err != nil {
		return nil, err
	}
	if err := sprite.BlitAt(
		scene, NativeTownWidth,
		nativeTownSelectionX[variant][selection],
		nativeTownSelectionY[variant][selection],
	); err != nil {
		return nil, err
	}
	vga := make([]byte, NativeTownWidth*NativeTownHeight)
	for row := 0; row < nativeTownViewportH; row++ {
		copy(
			vga[(nativeTownViewportY+row)*NativeTownWidth+nativeTownViewportX:],
			scene[row*NativeTownWidth:row*NativeTownWidth+nativeTownViewportW],
		)
	}
	return vga, nil
}
