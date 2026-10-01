# Installed listing identity review

Base: `cb22b90`, fix absent. Runtime: Python 3.12.3, pytest 9.1.0.
Scope: legacy installed scan, from initial listing to package discovery.

## Threat model

A local package author can rename and replace source directories during a scan.
They cannot change Crucible, its private staging tree, the kernel or sealed output.
Controlled test hooks schedule filesystem operations; they are not attacker code
executed by the product. This reviews input-selection integrity, not remote code
execution or a broken digest.

## Hypotheses and evidence

Prediction before patch: ordinary root/package replacement after listing is
accepted because discovery records a fresh identity. Rival: descriptor pinning
already rejects every replacement. A symlink variant discriminates the no-follow
control from the missing cross-stage identity control.

**CONFIRMED BY INDUCTION, under the model above — software defect:** both ordinary
replacement cases failed their rejection assertions on the base. Listing returned
paths, the author replaced a directory, and discovery accepted its new identity.

**FALSIFIED for the tested symlink variants:** both were already rejected on the
base. No new symlink bypass is claimed.

The patch records device/inode pairs from initial root enumeration and preserves
them into discovery and bounded reads. Discovery no longer overwrites a supplied
root identity. All four unchanged adversarial cases pass after the patch.

## Reproduction

Fixture and executable evidence: `tests/test_installed_listing_identity.py`.
SHA-256: `ba8519de161c4cf96fc38b91979e6a53ba35107cbe823b5ee6189d6034651725`.

Run `PYTHONPATH=src python3 -m pytest tests/test_installed_listing_identity.py -q`.
To repeat the before state, use an isolated checkout of `cb22b90` and copy only
that test file into it: expected result is two failures and two passes. After
the fix, all four pass. The fixture is created solely under pytest temporary paths.

## Limits

Not a full filesystem snapshot. Inode reuse, same-inode edits, mount semantics,
disappearing entries and initial root selection remain distinct considerations.
Duplicate packages are skipped by established precedence, not content-verified.
The independent installed-collection walker is outside this patch's scope.
