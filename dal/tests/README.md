# Regenerating `vectors.json`

The vectors are emitted by the **Go** code the TEE stack signs with —
`go-flare-common/pkg/signing` and `tee-node/pkg/types.ActionResult.Hash` — not
by anything in this repository. That is the whole point of them: a Python gate
checked only against Python agrees with its own misreading of the scheme, and a
wrong sighash does not fail loudly. It produces a signature that verifies
against nothing, and the symptom appears much later as an artifact that no
consumer will accept.

`vectors_gen.go.txt` is the generator, kept as text so it is not built by
anything here. To regenerate, put it in a module that `replace`s
`go-flare-common` and `tee-node` with checkouts of those repositories, and run
it.

The signing key is the well-known go-ethereum test key. Nothing in these
vectors is a secret, and nothing in them may be reused as an identity.
