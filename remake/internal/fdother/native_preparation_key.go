package fdother

// NormalizeNativePreparationKey preserves the return-byte contract observed at
// 0x32004. The native helper seeds [0x53a8e] with 0x10, reads a two-byte raw
// input record through 0x36d98, then applies these byte-level branches:
// extended 0xe0/0x52 and [0x53a8d]==0x20 yield 0x1c. Otherwise,
// [0x53a8e]==0x53 yields 1. This intentionally does not name actions or mutate
// the preparation roster; those meanings belong to the caller at 0x31a29.
func NormalizeNativePreparationKey(raw53a8d, raw53a8e byte) byte {
	if raw53a8e == 0xe0 || raw53a8e == 0x52 {
		raw53a8e = 0x1c
	} else if raw53a8d == 0x20 {
		raw53a8e = 0x1c
	}
	if raw53a8e == 0x53 {
		raw53a8e = 1
	}
	return raw53a8e
}
