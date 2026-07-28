package campaign

import (
	"errors"

	"github.com/wicanr2/fd2_re/remake/internal/dato"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
	"github.com/wicanr2/fd2_re/remake/internal/fdtxt"
)

var nativeShopSellQuestionText = [6]int{508, 508, 508, 659, 508, 508}
var nativeShopSellEmptyText = [6]int{509, 509, 509, 509, 509, 509}

func ComposeNativeShopSellQuestion(
	source []byte,
	dialogueCells []fdother.RawCell,
	portrait dato.Frame,
	portraitID int,
	strings *fdtxt.Strings,
	font *fdtxt.Font,
	choices []fdother.RawCell,
	hubVariant, itemID, salePrice, selected, pulse int,
) ([]byte, error) {
	if hubVariant < 0 || hubVariant >= len(nativeShopSellQuestionText) {
		return nil, errors.New("campaign: native shop sell question variant is invalid")
	}
	question, err := composeNativeShopItemPriceMessage(
		source, dialogueCells, portrait, portraitID, strings, font,
		nativeShopSellQuestionText[hubVariant], itemID, salePrice,
	)
	if err != nil {
		return nil, err
	}
	return ComposeNativeConfirmationChoices(
		question, choices, selected, pulse,
	)
}

func ComposeNativeShopSellQuestionBase(
	source []byte,
	dialogueCells []fdother.RawCell,
	portrait dato.Frame,
	portraitID int,
	strings *fdtxt.Strings,
	font *fdtxt.Font,
	hubVariant, itemID, salePrice int,
) ([]byte, error) {
	if hubVariant < 0 || hubVariant >= len(nativeShopSellQuestionText) {
		return nil, errors.New("campaign: native shop sell question variant is invalid")
	}
	return composeNativeShopItemPriceMessage(
		source, dialogueCells, portrait, portraitID, strings, font,
		nativeShopSellQuestionText[hubVariant], itemID, salePrice,
	)
}

func ComposeNativeShopSellEmpty(
	source []byte,
	dialogueCells []fdother.RawCell,
	portrait dato.Frame,
	portraitID int,
	strings *fdtxt.Strings,
	font *fdtxt.Font,
	hubVariant, nameTextIndex int,
) ([]byte, error) {
	if hubVariant < 0 || hubVariant >= len(nativeShopSellEmptyText) {
		return nil, errors.New("campaign: native shop sell-empty variant is invalid")
	}
	frame, err := ComposeNativeChurchDialogueOverlayAt(
		source, dialogueCells, portrait,
		nativeFacilityPortraitOffset(portraitID),
	)
	if err != nil {
		return nil, err
	}
	return ComposeNativeChurchTextWithNameAt(
		frame, strings, font, nativeShopSellEmptyText[hubVariant],
		nameTextIndex, NativeShopTextOffset,
	)
}
