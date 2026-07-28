package campaign

import (
	"errors"
	"fmt"
	"strconv"

	"github.com/wicanr2/fd2_re/remake/internal/dato"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
	"github.com/wicanr2/fd2_re/remake/internal/fdtxt"
)

type NativeShopPurchaseMessage byte

const (
	NativeShopPurchaseQuestion NativeShopPurchaseMessage = iota
	NativeShopPurchaseInsufficientGold
	NativeShopPurchaseNoEligibleRecipient
	NativeShopPurchaseEquipQuestion
)

// These are the four six-variant word tables copied by 0x2f0c5..0x2f0f4.
// Even variants contain the native placeholder index 1 because only the odd
// facility variants enter these shop message branches.
var nativeShopPurchaseText = [4][6]int{
	{1, 502, 1, 439, 1, 439},
	{1, 504, 1, 438, 1, 438},
	{1, 505, 1, 437, 1, 437},
	{1, 507, 1, 507, 1, 507},
}

// This is word_5265f, also consumed by the transfer caller. Purchase selects
// it only after the chosen recipient's exact eight native slots are full.
var nativeShopRecipientFullText = [6]int{1, 506, 1, 506, 506, 506}

func NativeShopPurchaseTextIndex(
	message NativeShopPurchaseMessage,
	hubVariant int,
) (int, bool) {
	if message > NativeShopPurchaseEquipQuestion ||
		hubVariant < 0 || hubVariant >= len(nativeShopPurchaseText[0]) {
		return 0, false
	}
	return nativeShopPurchaseText[message][hubVariant], true
}

// ComposeNativeShopPurchaseMessage reproduces the stable target after
// 0x1956b and 0x15f84 for one purchase branch. FFFC expands the selected
// item name (FDTXT itemID+181) and FFFA expands its decimal price.
func ComposeNativeShopPurchaseMessage(
	source []byte,
	dialogueCells []fdother.RawCell,
	portrait dato.Frame,
	portraitID int,
	strings *fdtxt.Strings,
	font *fdtxt.Font,
	message NativeShopPurchaseMessage,
	hubVariant, itemID, price int,
) ([]byte, error) {
	if len(source) != NativeShopWidth*NativeShopHeight ||
		len(dialogueCells) <= 17 || strings == nil || font == nil ||
		itemID < 0 || price < 0 {
		return nil, errors.New("campaign: native shop purchase message state is invalid")
	}
	if message == NativeShopPurchaseInsufficientGold {
		return nil, errors.New(
			"campaign: insufficient-gold feedback requires an open purchase confirmation",
		)
	}
	textIndex, ok := NativeShopPurchaseTextIndex(message, hubVariant)
	if !ok {
		return nil, errors.New("campaign: native shop purchase message variant is invalid")
	}
	frame, err := ComposeNativeChurchDialogueOverlayAt(
		source, dialogueCells, portrait,
		nativeFacilityPortraitOffset(portraitID),
	)
	if err != nil {
		return nil, err
	}
	words, err := strings.Words(textIndex)
	if err != nil {
		return nil, err
	}
	name, err := strings.Words(itemID + 181)
	if err != nil {
		return nil, err
	}
	priceWords := make([]uint16, 0, 8)
	for _, digit := range strconv.Itoa(price) {
		priceWords = append(priceWords, uint16(digit-'0'))
	}
	expanded := make([]uint16, 0, len(words)+len(name)+len(priceWords))
	for _, word := range words {
		switch word {
		case 0xfffc:
			expanded = append(expanded, name...)
		case 0xfffa:
			expanded = append(expanded, priceWords...)
		case 0xfffe:
			expanded = append(expanded, word)
		default:
			if word >= fdtxt.ControlMin {
				return nil, fmt.Errorf(
					"campaign: unsupported shop purchase control %#x", word,
				)
			}
			expanded = append(expanded, word)
		}
	}
	return composeNativeChurchWordsAt(
		frame, font, expanded, NativeShopTextOffset,
	)
}

// ComposeNativeShopPurchaseInsufficientGold reproduces the 0x2f16f branch:
// the question and 0x19953 choice cells remain open while FDTXT 504/438 is
// appended at literal VGA 0xac44c, which is framebuffer offset (12,157).
func ComposeNativeShopPurchaseInsufficientGold(
	confirmation []byte,
	strings *fdtxt.Strings,
	font *fdtxt.Font,
	hubVariant int,
) ([]byte, error) {
	if len(confirmation) != NativeShopWidth*NativeShopHeight ||
		strings == nil || font == nil {
		return nil, errors.New(
			"campaign: native shop insufficient-gold state is invalid",
		)
	}
	textIndex, ok := NativeShopPurchaseTextIndex(
		NativeShopPurchaseInsufficientGold, hubVariant,
	)
	if !ok {
		return nil, errors.New(
			"campaign: native shop insufficient-gold variant is invalid",
		)
	}
	return ComposeNativeChurchTextAt(
		confirmation, strings, font, textIndex, 157*NativeShopWidth+12,
	)
}

// ComposeNativeShopPurchaseRecipientFull reproduces the 0x2f36d branch:
// rebuild the facility dialogue overlay, expand FFFC with unit[+7]+1, wait in
// mode one, then close back to the purchase product loop. This compositor
// returns the stable open-message target; wait/close remain caller-owned.
func ComposeNativeShopPurchaseRecipientFull(
	source []byte,
	dialogueCells []fdother.RawCell,
	portrait dato.Frame,
	portraitID int,
	strings *fdtxt.Strings,
	font *fdtxt.Font,
	hubVariant, recipientNameTextIndex int,
) ([]byte, error) {
	if len(source) != NativeShopWidth*NativeShopHeight ||
		len(dialogueCells) <= 17 || strings == nil || font == nil ||
		hubVariant < 0 || hubVariant >= len(nativeShopRecipientFullText) ||
		recipientNameTextIndex < 0 {
		return nil, errors.New(
			"campaign: native shop recipient-full state is invalid",
		)
	}
	frame, err := ComposeNativeChurchDialogueOverlayAt(
		source, dialogueCells, portrait,
		nativeFacilityPortraitOffset(portraitID),
	)
	if err != nil {
		return nil, err
	}
	return ComposeNativeChurchTextWithNameAt(
		frame, strings, font,
		nativeShopRecipientFullText[hubVariant],
		recipientNameTextIndex,
		NativeShopTextOffset,
	)
}

func ComposeNativeShopPurchaseConfirmation(
	source []byte,
	dialogueCells []fdother.RawCell,
	portrait dato.Frame,
	portraitID int,
	strings *fdtxt.Strings,
	font *fdtxt.Font,
	choices []fdother.RawCell,
	message NativeShopPurchaseMessage,
	hubVariant, itemID, price, selected, pulse int,
) ([]byte, error) {
	if message != NativeShopPurchaseQuestion &&
		message != NativeShopPurchaseEquipQuestion {
		return nil, errors.New(
			"campaign: native shop confirmation message has no yes/no lifecycle",
		)
	}
	question, err := ComposeNativeShopPurchaseMessage(
		source, dialogueCells, portrait, portraitID, strings, font,
		message, hubVariant, itemID, price,
	)
	if err != nil {
		return nil, err
	}
	return ComposeNativeConfirmationChoices(question, choices, selected, pulse)
}
