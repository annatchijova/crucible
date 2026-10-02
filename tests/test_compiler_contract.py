from __future__ import annotations

import json
from pathlib import Path

from crucible.compiler import compile_corpus


def _write_skill(root: Path, name: str, body: str) -> Path:
    skill = root / name
    skill.mkdir()
    (skill / "SKILL.md").write_text(body, encoding="utf-8", newline="\n")
    return skill


def test_compiler_emits_versioned_source_addressable_ir(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "bounded-retries",
        """---\nname: bounded-retries\ndescription: Bound retries for operations.\nlicense: Apache-2.0\n---\n\n# Bounded retries\n\nRetries MUST have a finite budget.\n\nThe operation SHOULD be idempotent before retrying.\n\n## Checks\n\n- Verify the retry budget is present.\n\n## Composes with\n\n- irreversible-action-gate\n\n## References\n\n- https://example.com/retry-guidance\n""",
    )

    artifact = compile_corpus(tmp_path)

    assert artifact["schema_version"] == "skill-ir/v1"
    assert artifact["skills"][0]["identity"]["name"] == "bounded-retries"
    assert artifact["skills"][0]["identity"]["content_digest"].startswith("sha256:")
    assert [rule["modality"] for rule in artifact["skills"][0]["rules"]] == ["MUST", "SHOULD"]
    assert artifact["skills"][0]["rules"][0]["extraction_status"] == "candidate"
    assert artifact["skills"][0]["rules"][0]["source_span"]["line"] == 9
    assert artifact["skills"][0]["relations"]["composes_with"] == ["irreversible-action-gate"]
    assert artifact["skills"][0]["references"] == ["https://example.com/retry-guidance"]


def test_same_corpus_has_identical_canonical_bytes_and_digest(tmp_path: Path) -> None:
    _write_skill(tmp_path, "z-skill", "---\nname: z-skill\ndescription: Z\n---\n\nA MAY run.\n")
    _write_skill(tmp_path, "a-skill", "---\nname: a-skill\ndescription: A\n---\n\nB MUST stop.\n")

    first = compile_corpus(tmp_path)
    second = compile_corpus(tmp_path)

    assert first == second
    assert first["artifact_digest"] == second["artifact_digest"]
    assert json.dumps(first, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def test_invalid_frontmatter_fails_closed_with_path(tmp_path: Path) -> None:
    skill = tmp_path / "broken"
    skill.mkdir()
    (skill / "SKILL.md").write_text("# no frontmatter\n", encoding="utf-8")

    try:
        compile_corpus(tmp_path)
    except ValueError as exc:
        assert "broken/SKILL.md" in str(exc)
        assert "frontmatter" in str(exc).lower()
    else:
        raise AssertionError("invalid frontmatter must not compile")


def test_compiler_preserves_simple_nested_frontmatter_metadata(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "nested",
        """---\nname: nested\ndescription: Nested metadata\nmetadata:\n  short-description: A short description\n---\n\nA MUST remain explicit.\n""",
    )

    artifact = compile_corpus(tmp_path)

    assert artifact["skills"][0]["metadata"]["metadata"]["short-description"] == "A short description"


def test_compiler_parses_a_yaml_sequence_frontmatter_value(tmp_path: Path) -> None:
    """Regression: a real-world SKILL.md (mukul975/Anthropic-Cybersecurity-
    Skills) used `tags:` followed by unindented `- item` lines -- valid
    YAML, but the parser previously only supported nested `key: value`
    mappings under an empty-valued key and raised 'unsupported frontmatter
    line' on the first bullet, crashing the whole corpus compile."""
    _write_skill(
        tmp_path,
        "tagged",
        "---\nname: tagged\ndescription: Has tags\ntags:\n- red-team\n- credential-access\n---\n\nA MUST remain explicit.\n",
    )

    artifact = compile_corpus(tmp_path)

    assert artifact["skills"][0]["metadata"]["tags"] == ["red-team", "credential-access"]


def test_compiler_parses_an_indented_yaml_sequence_frontmatter_value(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "tagged-indented",
        "---\nname: tagged-indented\ndescription: Has tags\ntags:\n  - red-team\n  - dpapi\n---\n\nA MUST remain explicit.\n",
    )

    artifact = compile_corpus(tmp_path)

    assert artifact["skills"][0]["metadata"]["tags"] == ["red-team", "dpapi"]


def test_compiler_empty_valued_key_with_no_children_is_null_not_a_missing_key(tmp_path: Path) -> None:
    """A key with nothing after its colon is YAML null, not an implicit
    empty mapping -- the earlier hand-rolled parser defaulted it to `{}`,
    which was a non-standard, parser-specific quirk rather than real YAML
    semantics; the real YAML parser's `None` is normalized to `""`, same
    as every other null/empty scalar this normalizer handles."""
    _write_skill(
        tmp_path,
        "empty-mapping",
        "---\nname: empty-mapping\ndescription: test\nmetadata:\n---\n\nA MUST remain explicit.\n",
    )

    artifact = compile_corpus(tmp_path)

    assert artifact["skills"][0]["metadata"]["metadata"] == ""


def test_compiler_parses_a_sequence_nested_one_level_inside_a_mapping(tmp_path: Path) -> None:
    """Regression: real-world frontmatter (mukul975/Anthropic-Cybersecurity-
    Skills) nests a YAML sequence one level inside an already-open mapping,
    e.g. `metadata: / version: '1.1' / tactics: / - item / - item`. The
    parser previously only supported a sequence directly under a top-level
    key, not one nested inside a mapping that is itself under a top-level
    key, and raised 'list item under a mapping key' on the first bullet."""
    _write_skill(
        tmp_path,
        "nested-sequence",
        "---\nname: nested-sequence\ndescription: test\nmetadata:\n  version: '1.1'\n  tactics:\n  - resource-development\n  - reconnaissance\n---\n\nA MUST remain explicit.\n",
    )

    artifact = compile_corpus(tmp_path)

    metadata = artifact["skills"][0]["metadata"]["metadata"]
    assert metadata["version"] == "1.1"
    assert metadata["tactics"] == ["resource-development", "reconnaissance"]


def test_compiler_parses_a_sequence_of_mappings_in_frontmatter(tmp_path: Path) -> None:
    """The shape that actually motivated switching to a real YAML parser:
    mukul975/Anthropic-Cybersecurity-Skills nests a sequence of mappings
    (each item itself has multiple key: value pairs) inside a top-level
    key, e.g. `techniques: / - id: T1583.001 / name: ... / tactic: ...`.
    Every hand-rolled special case added for simpler shapes (flat
    sequences, one level of mapping-then-sequence) still could not
    represent this without recursive nesting -- the actual sign that the
    fix needed was a real parser, not one more special case."""
    _write_skill(
        tmp_path,
        "techniques",
        "---\nname: techniques\ndescription: test\nmetadata:\n  techniques:\n  - id: T1583.001\n    name: 'Acquire Infrastructure: Domains'\n    tactic: resource-development\n  - id: T1566.002\n    name: Spearphishing Link\n    tactic: initial-access\n---\n\nA MUST remain explicit.\n",
    )

    artifact = compile_corpus(tmp_path)

    techniques = artifact["skills"][0]["metadata"]["metadata"]["techniques"]
    assert techniques == [
        {"id": "T1583.001", "name": "Acquire Infrastructure: Domains", "tactic": "resource-development"},
        {"id": "T1566.002", "name": "Spearphishing Link", "tactic": "initial-access"},
    ]


def test_compiler_repairs_an_unquoted_colon_inside_a_plain_description(tmp_path: Path) -> None:
    """Regression: migrating to a real YAML parser (needed for the
    mukul975/Anthropic-Cybersecurity-Skills shapes above) is stricter than
    the old hand-rolled parser about one extremely common hand-written
    pattern: an unquoted `description:` whose free text itself contains a
    colon-space, e.g. 'Use whenever evidence is being captured from a live
    system: "acquire the disk", ...'. Strict YAML rejects this (ambiguous
    with a nested mapping key) and, unrepaired, broke 39 of 90 skills in
    this project's own author corpus -- a worse regression than any of the
    external-corpus gaps that motivated the YAML migration. The targeted
    repair re-quotes exactly the one reported top-level line and retries,
    rather than falling back to a second hand-rolled parser."""
    _write_skill(
        tmp_path,
        "volatility",
        '---\nname: volatility\ndescription: Use whenever evidence is being captured from a live system: "acquire the disk", "grab a memory dump", is this forensically sound.\n---\n\nA MUST remain explicit.\n',
    )

    artifact = compile_corpus(tmp_path)

    assert artifact["skills"][0]["metadata"]["description"] == (
        'Use whenever evidence is being captured from a live system: '
        '"acquire the disk", "grab a memory dump", is this forensically sound.'
    )


def test_compiler_does_not_repair_a_colon_problem_inside_a_nested_sequence_item(tmp_path: Path) -> None:
    """The colon-repair is deliberately narrow: it only rewrites a complete
    top-level `key: text` line PyYAML pointed at. A problem reported on an
    indented/nested line (not a bare top-level key) must surface as the
    real YAML error, not be silently papered over by a repair rule scoped
    to a different, specific shape."""
    _write_skill(
        tmp_path,
        "nested-colon-problem",
        "---\nname: nested-colon-problem\ndescription: test\nmetadata:\n  tactics:\n  - first: second: third\n---\n\nA MUST remain explicit.\n",
    )

    try:
        compile_corpus(tmp_path)
    except ValueError as exc:
        assert "invalid frontmatter YAML" in str(exc)
    else:
        raise AssertionError("an unrepairable nested colon ambiguity must not silently compile")


def test_compiler_stringifies_unquoted_numeric_and_boolean_frontmatter_scalars(tmp_path: Path) -> None:
    """A real YAML parser infers types for unquoted scalars (1.1 -> float,
    true -> bool) that the previous hand-rolled parser never produced --
    it treated every scalar as a string regardless of quoting. Frontmatter
    metadata is descriptive text copied into reports, never arithmetic, so
    every scalar is normalized back to a string; in particular, no float
    may reach any caller, matching this project's project-wide invariant
    that a float never enters a decision path."""
    _write_skill(
        tmp_path,
        "typed-scalars",
        "---\nname: typed-scalars\ndescription: test\nversion: 1.1\nactive: true\ncount: 5\n---\n\nA MUST remain explicit.\n",
    )

    artifact = compile_corpus(tmp_path)

    metadata = artifact["skills"][0]["metadata"]
    assert metadata["version"] == "1.1"
    assert metadata["active"] == "true"
    assert metadata["count"] == "5"
    assert all(not isinstance(v, (int, float, bool)) for v in metadata.values())


def test_compiler_rejects_a_sequence_item_after_mapping_entries_exist(tmp_path: Path) -> None:
    """Defensive: a `- item` line appearing after the same key has already
    received nested `key: value` entries is not valid YAML under either
    reading and must fail closed, not silently coerce."""
    _write_skill(
        tmp_path,
        "mixed",
        "---\nname: mixed\ndescription: test\nmetadata:\n  short-description: ok\n- stray item\n---\n\nA MUST remain explicit.\n",
    )

    try:
        compile_corpus(tmp_path)
    except ValueError as exc:
        assert "invalid frontmatter YAML" in str(exc)
    else:
        raise AssertionError("a sequence item under a populated mapping key must not compile")


def test_compiler_folds_a_plain_multiline_scalar_without_a_block_indicator(tmp_path: Path) -> None:
    """Regression: real-world frontmatter (mukul975/Anthropic-Cybersecurity-
    Skills) wrapped a long `description:` across two lines using plain YAML
    scalar folding -- no `>`/`|` indicator, just a continuation line
    indented further than the key. The parser previously only recognized
    continuation after an explicit block indicator and raised 'unsupported
    frontmatter line' on the bare continuation line."""
    _write_skill(
        tmp_path,
        "wrapped",
        "---\nname: wrapped\ndescription: Detect dangerous ACL misconfigurations\n  using ldap3 to identify abuse paths\ntags: unrelated\n---\n\nA MUST remain explicit.\n",
    )

    artifact = compile_corpus(tmp_path)

    assert artifact["skills"][0]["metadata"]["description"] == (
        "Detect dangerous ACL misconfigurations using ldap3 to identify abuse paths"
    )
    assert artifact["skills"][0]["metadata"]["tags"] == "unrelated"


def test_compiler_folds_a_single_quoted_multiline_scalar(tmp_path: Path) -> None:
    """Regression: real-world frontmatter (mukul975/Anthropic-Cybersecurity-
    Skills) opened `description:` with a single quote that doesn't close on
    the same line, wrapped across several lines (including a blank line),
    and closed with the matching quote alone on its own line -- valid YAML,
    but the parser previously treated the unterminated leading quote as
    part of the value and then choked on the bare closing-quote line as an
    'unsupported frontmatter line'."""
    _write_skill(
        tmp_path,
        "quoted-wrap",
        "---\nname: quoted-wrap\ndescription: 'Parses access logs to detect\n  BOLA/IDOR attacks and injection attempts.\n\n  '\ndomain: cybersecurity\n---\n\nA MUST remain explicit.\n",
    )

    artifact = compile_corpus(tmp_path)

    # Real YAML folding turns a blank line inside a quoted scalar into a
    # literal "\n" (a paragraph break), not nothing -- more correct than
    # this parser's previous space-everything approximation.
    assert artifact["skills"][0]["metadata"]["description"] == (
        "Parses access logs to detect BOLA/IDOR attacks and injection attempts.\n"
    )
    assert artifact["skills"][0]["metadata"]["domain"] == "cybersecurity"


def test_compiler_unescapes_doubled_single_quote_in_multiline_scalar(tmp_path: Path) -> None:
    """YAML's single-quote escape for a literal quote character is `''`."""
    _write_skill(
        tmp_path,
        "quoted-escape",
        "---\nname: quoted-escape\ndescription: 'It''s a wrapped\n  value\n  '\n---\n\nA MUST remain explicit.\n",
    )

    artifact = compile_corpus(tmp_path)

    assert artifact["skills"][0]["metadata"]["description"] == "It's a wrapped value "


def test_compiler_folds_multiline_scalar_containing_an_escaped_quote_before_the_real_close(
    tmp_path: Path,
) -> None:
    """Regression: a naive "does this line contain the quote character"
    scan mistakes a mid-value `''` escape (e.g. "a sample''s execution")
    for the real closing quote and truncates the value early. The true
    close must be found by scanning with the escape rule applied, even
    when it lands on a later line than the escaped one."""
    _write_skill(
        tmp_path,
        "quoted-escape-then-close",
        "---\nname: quoted-escape-then-close\ndescription: 'Analyzes a sample''s execution\n  guards and then some more text\n  after the escape, finally closing\n  here.'\n---\n\nA MUST remain explicit.\n",
    )

    artifact = compile_corpus(tmp_path)

    assert artifact["skills"][0]["metadata"]["description"] == (
        "Analyzes a sample's execution guards and then some more text after the escape, finally closing here."
    )


def test_compiler_rejects_an_unterminated_quoted_frontmatter_value(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "unterminated",
        "---\nname: unterminated\ndescription: 'never closes\n  still open\n---\n\nA MUST remain explicit.\n",
    )

    try:
        compile_corpus(tmp_path)
    except ValueError as exc:
        assert "invalid frontmatter YAML" in str(exc)
    else:
        raise AssertionError("an unterminated quoted frontmatter value must not compile")


def test_compiler_supports_folded_description_block(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "folded",
        """---\nname: folded\ndescription: >\n  First line of the description.\n  Second line remains part of it.\n---\n\nA MUST remain explicit.\n""",
    )

    artifact = compile_corpus(tmp_path)

    assert artifact["skills"][0]["metadata"]["description"] == (
        "First line of the description. Second line remains part of it."
    )


def test_symlinked_skill_fails_closed(tmp_path: Path) -> None:
    target = _write_skill(tmp_path, "target", "---\nname: target\ndescription: Target\n---\n")
    link = tmp_path / "linked"
    link.mkdir()
    (link / "SKILL.md").symlink_to(target / "SKILL.md")

    try:
        compile_corpus(tmp_path)
    except ValueError as exc:
        assert "symlink" in str(exc).lower()
    else:
        raise AssertionError("symlinked skill must not compile")


def test_duplicate_skill_names_fail_closed(tmp_path: Path) -> None:
    body = "---\nname: duplicate\ndescription: Same identity\n---\n"
    _write_skill(tmp_path, "one", body)
    _write_skill(tmp_path, "two", body)

    try:
        compile_corpus(tmp_path)
    except ValueError as exc:
        assert "duplicate skill name" in str(exc).lower()
    else:
        raise AssertionError("duplicate skill names must not compile")


def test_shell_comment_inside_code_fence_is_not_a_heading(tmp_path: Path) -> None:
    """Regression: running the compiler against mukul975/Anthropic-
    Cybersecurity-Skills found that a shell comment like "# Check for
    known UEFI malware patterns" inside a ```bash fence matches the same
    regex as a real level-1 Markdown heading, since fenced code was never
    excluded from heading detection. 544/818 skills in that corpus
    contained at least one such comment, producing 10,749 phantom headings
    against 11,332 real ones corpus-wide (nearly 1:1) -- and a phantom
    heading whose text happens to contain "check" then misclassifies the
    unrelated reference list that follows it as a batch of checks. This
    corrupted `_section_ranges`, which is shared by check, procedural-step,
    and composition/delegation-relation extraction."""
    _write_skill(
        tmp_path,
        "bootkit",
        "---\nname: bootkit\ndescription: Analyze bootkit samples for persistence mechanisms and indicators.\n---\n\n## Workflow\n\n```bash\n# Check for known UEFI malware patterns\necho hello\n```\n\nKnown indicators:\n- Modified SPI flash\n- Added DXE driver\n",
    )

    artifact = compile_corpus(tmp_path)

    # The shell comment must not have opened a fake "check for known uefi
    # malware patterns" section that swallows the "Known indicators" list
    # as checks.
    assert artifact["skills"][0]["checks"] == []


def test_real_checks_section_containing_a_code_block_only_extracts_bullets_outside_it(
    tmp_path: Path,
) -> None:
    """A legitimate "## Checks" section may itself contain a code example;
    a shell comment inside that embedded code block must not be extracted
    as a check bullet, even though the section title correctly matches."""
    _write_skill(
        tmp_path,
        "with-embedded-code",
        "---\nname: with-embedded-code\ndescription: Has a real checks section with embedded code.\n---\n\n## Checks\n\n- Verify the output matches expectations\n\n```bash\n# Check exit code\necho $?\n```\n\n- Confirm no errors were logged\n",
    )

    artifact = compile_corpus(tmp_path)

    check_texts = [c["text"] for c in artifact["skills"][0]["checks"]]
    assert check_texts == [
        "Verify the output matches expectations",
        "Confirm no errors were logged",
    ]


def test_numbered_comment_inside_code_fence_in_a_steps_section_is_not_a_step(
    tmp_path: Path,
) -> None:
    """The same code-fence exclusion must apply to procedural-step
    extraction within a genuinely titled "## Steps" section, not only to
    checks."""
    _write_skill(
        tmp_path,
        "with-numbered-comment",
        "---\nname: with-numbered-comment\ndescription: Has a steps section with an embedded numbered comment in code.\n---\n\n## Steps\n\n1. Run the initial scan\n\n```python\n# 1. this looks like a numbered step but is a code comment\nprint('scanning')\n```\n\n2. Review the results\n",
    )

    artifact = compile_corpus(tmp_path)

    step_texts = [s["text"] for s in artifact["skills"][0]["procedural_steps"]]
    assert step_texts == ["Run the initial scan", "Review the results"]


def test_verification_starter_recognizes_the_full_oracle_command_verb_list(tmp_path: Path) -> None:
    """Regression: _VERIFICATION_STARTER (decides whether prose becomes a
    check at all) had drifted to a 7-verb subset of the 13-verb canonical
    list ADR-0015 fixed for oracle_kind "command" classification. A real
    skill from mukul975/Anthropic-Cybersecurity-Skills had a standalone
    sentence "Validate false positive rate by running against 7 days of
    production data..." that never became a check at all because "validate"
    was missing from the starter list, even though oracle_kind's command
    pattern already recognized it -- the check simply never existed to be
    classified. 36/70 (51%) of that corpus's REQUIREMENT_WITHOUT_CHECK
    findings had this exact shape. Both lists now come from one shared
    tuple so they cannot drift apart again."""
    _write_skill(
        tmp_path,
        "missing-verbs",
        "---\nname: missing-verbs\ndescription: Exercises every previously-missing verification verb.\n---\n\n"
        "## Workflow\n\n"
        "Run the scanner against the target host.\n"
        "Query the results database for matching entries.\n"
        "Inspect the output for anomalies.\n"
        "Does the output match the expected baseline.\n"
        "Ensure the baseline file has not been modified.\n"
        "Validate the scan completed without errors.\n",
    )

    artifact = compile_corpus(tmp_path)

    check_texts = [c["text"] for c in artifact["skills"][0]["checks"]]
    assert len(check_texts) == 6
    for expected_starter in ("Run", "Query", "Inspect", "Does", "Ensure", "Validate"):
        assert any(text.startswith(expected_starter) for text in check_texts), (
            f"expected a check starting with {expected_starter!r}, got {check_texts!r}"
        )
    for check in artifact["skills"][0]["checks"]:
        assert check["oracle_kind"] == "command"


def test_a_verification_shaped_bullet_is_a_check_not_also_a_step(tmp_path: Path) -> None:
    """Regression, found via variant analysis of the two compiler bugs
    above (same family: two things meant to describe related concepts had
    drifted). _ACTION_VERBS (decides whether a prose bullet outside a
    procedural section is a step) independently duplicates every verb in
    _VERIFICATION_VERBS (validate/verify/check/test/assert/confirm/
    demonstrate/prove/inspect/run), with no cross-function deduplication
    against _extract_checks. A bullet like "- Validate the configuration
    file before deployment." was extracted as BOTH a check and a step --
    confirmed on 250/818 (31%) of mukul975/Anthropic-Cybersecurity-Skills.
    A verification-shaped bullet must be a check only, by the same
    precedence this function already applies to a titled Checks/
    Verification section ("those are checks, not steps")."""
    _write_skill(
        tmp_path,
        "dual-extract",
        "---\nname: dual-extract\ndescription: Exercises a bullet outside any section that matches both extraction paths.\n---\n\n## Overview\n\n- Validate the configuration file before deployment.\n",
    )

    artifact = compile_corpus(tmp_path)

    assert len(artifact["skills"][0]["checks"]) == 1
    assert artifact["skills"][0]["procedural_steps"] == []


def test_step_n_heading_is_extracted_as_a_procedural_step(tmp_path: Path) -> None:
    """ADR-0019 Option B, part 1: procedural_steps's section-title filter
    checked for the substring "steps" (plural) and never matched the
    "### Step N: Title" convention (singular + number) -- confirmed by
    induction that a real skill with four such headings and runnable code
    extracted 0 procedural_steps before this fix. The heading's own title
    is the step; this corpus's convention puts the actual procedure in a
    fenced code block underneath, not a bullet/numbered list."""
    _write_skill(
        tmp_path,
        "step-headings",
        "---\nname: step-headings\ndescription: Exercises Step N heading recognition.\n---\n\n"
        "## Workflow\n\n"
        "### Step 1: Extract Configuration with CobaltStrikeParser\n\n"
        "```python\nprint('irrelevant code, no bullets or numbered lists here')\n```\n\n"
        "### Step 2: Manual XOR Decryption of Beacon Config\n\n"
        "More prose, still no bullet or numbered list.\n",
    )

    artifact = compile_corpus(tmp_path)

    step_texts = [s["text"] for s in artifact["skills"][0]["procedural_steps"]]
    assert step_texts == [
        "Extract Configuration with CobaltStrikeParser",
        "Manual XOR Decryption of Beacon Config",
    ]


def test_step_n_heading_accepts_the_observed_separator_variants(tmp_path: Path) -> None:
    """A corpus survey found ':' (dominant), em-dash '—', and a literal
    '---' all in real use as the separator between the step number and
    its descriptive title, plus lettered sub-steps like "Step 2a:"."""
    _write_skill(
        tmp_path,
        "step-separators",
        "---\nname: step-separators\ndescription: Exercises every observed Step-N separator variant.\n---\n\n"
        "### Step 1: Colon Separator\n\ntext\n\n"
        "### Step 2 — Em Dash Separator\n\ntext\n\n"
        "### Step 3 --- Triple Hyphen Separator\n\ntext\n\n"
        "### Step 2a: Lettered Sub-Step\n\ntext\n",
    )

    artifact = compile_corpus(tmp_path)

    step_texts = [s["text"] for s in artifact["skills"][0]["procedural_steps"]]
    assert step_texts == [
        "Colon Separator",
        "Em Dash Separator",
        "Triple Hyphen Separator",
        "Lettered Sub-Step",
    ]


def test_step_n_heading_with_no_descriptive_title_falls_back_to_the_heading_text(
    tmp_path: Path,
) -> None:
    """A bare "### Step 3" with nothing after the number must not be
    silently dropped just because it has no descriptive suffix."""
    _write_skill(
        tmp_path,
        "bare-step",
        "---\nname: bare-step\ndescription: Exercises a Step heading with no title suffix.\n---\n\n"
        "### Step 3\n\ntext\n",
    )

    artifact = compile_corpus(tmp_path)

    step_texts = [s["text"] for s in artifact["skills"][0]["procedural_steps"]]
    assert step_texts == ["Step 3"]


def test_plural_steps_heading_without_a_number_is_not_a_step_n_heading(tmp_path: Path) -> None:
    """Regression guard explicitly named in ADR-0019: a heading that
    merely contains the word "step(s)" in prose, with no number
    immediately following the singular "Step", must not match path 4
    (the new Step-N heading recognizer added by this fix). Surveyed
    shapes: "## Next Steps to Consider" and "## Steps Overview".

    Deliberately uses plain prose paragraphs, not bullets: a bullet under
    "## Next Steps to Consider" would be extracted by the pre-existing,
    unrelated path 1 (its title contains the substring "steps", which
    _PROCEDURAL_SECTIONS already matched before this change) -- this test
    isolates path 4's own behavior, not path 1's."""
    _write_skill(
        tmp_path,
        "plural-steps",
        "---\nname: plural-steps\ndescription: Exercises headings that must not match the Step-N pattern.\n---\n\n"
        "## Next Steps to Consider\n\nSome unstructured prose, no bullets or numbers.\n\n"
        "## Steps Overview\n\nMore unstructured prose.\n",
    )

    artifact = compile_corpus(tmp_path)

    assert artifact["skills"][0]["procedural_steps"] == []


def test_a_genuine_action_verb_bullet_is_still_extracted_as_a_step(tmp_path: Path) -> None:
    """The fix above must not over-exclude: a bullet starting with an
    action verb that is NOT also a verification verb (e.g. "Deploy", not
    in _VERIFICATION_VERBS) must still become a step as before."""
    _write_skill(
        tmp_path,
        "genuine-step",
        "---\nname: genuine-step\ndescription: Exercises a genuine action-verb bullet.\n---\n\n## Overview\n\n- Deploy the configuration to all nodes.\n",
    )

    artifact = compile_corpus(tmp_path)

    assert artifact["skills"][0]["checks"] == []
    step_texts = [s["text"] for s in artifact["skills"][0]["procedural_steps"]]
    assert step_texts == ["Deploy the configuration to all nodes."]


# ---------------------------------------------------------------------------
# structural_headings (ADR-0019 Option B, part 2)
# ---------------------------------------------------------------------------

def test_structural_headings_excludes_boilerplate_sections(tmp_path: Path) -> None:
    """Overview/When to Use/Prerequisites/References/Key Concepts are
    universal boilerplate in this corpus style and must not count as
    structural content on their own."""
    _write_skill(
        tmp_path,
        "boilerplate-only",
        "---\nname: boilerplate-only\ndescription: Exercises the boilerplate exclusion list.\n---\n\n"
        "## Overview\n\ntext\n\n## When to Use\n\ntext\n\n"
        "## Prerequisites\n\ntext\n\n## References\n\ntext\n\n## Key Concepts\n\ntext\n",
    )

    artifact = compile_corpus(tmp_path)

    assert artifact["skills"][0]["structural_headings"] == []


def test_structural_headings_excludes_the_document_title(tmp_path: Path) -> None:
    """The level-1 heading names the skill, not a content section, and is
    present even on a skill with zero real body structure -- it must not
    count toward the non-boilerplate heading signal."""
    _write_skill(
        tmp_path,
        "titled",
        "---\nname: titled\ndescription: Exercises the title-heading exclusion.\n---\n\n"
        "# Titled Skill\n\n## Overview\n\ntext\n",
    )

    artifact = compile_corpus(tmp_path)

    assert artifact["skills"][0]["structural_headings"] == []


def test_structural_headings_collects_non_boilerplate_sections(tmp_path: Path) -> None:
    """A real, domain-specific section heading is collected, lowercased,
    in document order, with duplicates collapsed."""
    _write_skill(
        tmp_path,
        "real-structure",
        "---\nname: real-structure\ndescription: Exercises real structural headings.\n---\n\n"
        "# Real Structure\n\n## Overview\n\ntext\n\n"
        "## Running Hindsight\n\ntext\n\n## Key Artifact Files\n\ntext\n\n"
        "## Running Hindsight\n\nrepeated section\n",
    )

    artifact = compile_corpus(tmp_path)

    assert artifact["skills"][0]["structural_headings"] == [
        "running hindsight",
        "key artifact files",
    ]


def test_structural_headings_excludes_code_fence_lines(tmp_path: Path) -> None:
    """A shell comment inside a code fence must not be misread as a
    structural heading, same exclusion _section_ranges already applies."""
    _write_skill(
        tmp_path,
        "fenced",
        "---\nname: fenced\ndescription: Exercises the code-fence exclusion.\n---\n\n"
        "## Real Section\n\n```bash\n# Not a heading\n```\n",
    )

    artifact = compile_corpus(tmp_path)

    assert artifact["skills"][0]["structural_headings"] == ["real section"]
