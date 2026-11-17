# Publication addendum

The recorded evaluation ran at `84006ac3ff35d834949d6e65ded80e82e950f99b`.
Its receipts and `code-fingerprint.json` are unchanged. The exact wrapper that
ran is preserved in `replay-recorded.py.txt`; its SHA-256 is
`e11c5938f07304cb1f82ce4b2cf6b85bfbf53009b5667f3625b804711d99f28a`, matching the recorded `wrapper_sha256`.

For publication, `replay.py` uses equivalent expanded control-flow formatting,
drops an unused local binding while retaining its validation read, reports Git
command failures explicitly and
refuses to write a fingerprint without checkout identity. This edit has not
been used to repeat the evaluation. It does not change or renew the recorded
live-call authorization. Existing overwrite and repeated-call guards remain.

The separately referenced native Aura screenshot stays local because it shows
account metadata. Its historical receipt is unchanged; the image is omitted
from the published repository.
