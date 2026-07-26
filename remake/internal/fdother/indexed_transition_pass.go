package fdother

import "fmt"

// BuildNativeIndexedTransitionPass transcribes the raw 0x22046 argument
// mapping. The caller's a1/a2/a3/a4/a5 become the radial center/radius and row
// bounds; notably a2 is both radial CenterY and the final rectangle's exclusive
// EndY in the native routine. Keep this odd alias explicit instead of
// normalizing it into a guessed screen-space rectangle.
func BuildNativeIndexedTransitionPass(centerX, centerY, radius, startY, endY int) (IndexedTransitionPass, error) {
	if centerX < 0 || centerX >= NativeTransitionStageWidth || centerY < 0 || radius <= 0 || startY < 0 || endY < startY || endY > NativeTransitionStageHeight {
		return IndexedTransitionPass{}, fmt.Errorf("indexed transition: invalid raw 0x22046 args")
	}
	return IndexedTransitionPass{
		FirstRadial: RadialLUTRemap{
			CenterX: centerX, CenterY: centerY, Radius: radius, Scale: 16,
			StartY: startY, EndY: endY, ClipWidth: NativeTransitionStageWidth,
		},
		SecondRadial: RadialLUTRemap{
			CenterX: centerX, CenterY: centerY, Radius: radius, Scale: 16,
			StartY: centerY, EndY: endY, ClipWidth: NativeTransitionStageWidth,
		},
		FinalRect: CenteredRectLUTRemap{
			CenterX: centerX, HorizontalRadius: radius * 16 / 10,
			StartY: startY, EndY: centerY, ClipWidth: NativeTransitionStageWidth,
		},
	}, nil
}
