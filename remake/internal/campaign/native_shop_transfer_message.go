package campaign

import (
	"errors"

	"github.com/wicanr2/fd2_re/remake/internal/dato"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
	"github.com/wicanr2/fd2_re/remake/internal/fdtxt"
)

type NativeShopTransferMessage byte

const (
	NativeShopTransferDestinationPrompt NativeShopTransferMessage = iota
	NativeShopTransferEmptySource
	NativeShopTransferSourcePrompt
)

var nativeShopTransferText = [...]int{510, 511, 512}

// ComposeNativeShopTransferMessage reproduces the three fixed FDTXT messages
// owned by 0x2f8ea. Empty-source text expands FFFC with the selected actor;
// the two prompts contain no dynamic operand.
func ComposeNativeShopTransferMessage(
	source []byte,
	dialogueCells []fdother.RawCell,
	portrait dato.Frame,
	portraitID int,
	strings *fdtxt.Strings,
	font *fdtxt.Font,
	message NativeShopTransferMessage,
	nameTextIndex int,
) ([]byte, error) {
	if len(source) != NativeShopWidth*NativeShopHeight ||
		len(dialogueCells) <= 17 || strings == nil || font == nil ||
		int(message) < 0 || int(message) >= len(nativeShopTransferText) {
		return nil, errors.New(
			"campaign: native shop transfer message state is invalid",
		)
	}
	frame, err := ComposeNativeChurchDialogueOverlayAt(
		source, dialogueCells, portrait,
		nativeFacilityPortraitOffset(portraitID),
	)
	if err != nil {
		return nil, err
	}
	if message == NativeShopTransferEmptySource {
		if nameTextIndex < 0 {
			return nil, errors.New(
				"campaign: native shop transfer source name is invalid",
			)
		}
		return ComposeNativeChurchTextWithNameAt(
			frame, strings, font, nativeShopTransferText[message],
			nameTextIndex, NativeShopTextOffset,
		)
	}
	return ComposeNativeChurchTextAt(
		frame, strings, font, nativeShopTransferText[message],
		NativeShopTextOffset,
	)
}
