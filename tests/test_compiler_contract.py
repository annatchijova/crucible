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
