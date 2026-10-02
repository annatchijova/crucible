"""Contract tests for the L15 final report assembler."""

from crucible.confirm import MockConfirmExecutor
from crucible.final_report import build_final_report
from crucible.narrator import MockNarrationExecutor


def test_final_report_assembles_all_levels_for_the_readme_demo_fixture():
    report = build_final_report(
        "tests/fixtures/readme-demo",
        MockConfirmExecutor(),
        MockNarrationExecutor(),
    )
    assert report["schema_version"] == "crucible-final-report/v1"
    assert report["skill_count"] == 1
    assert "retry-example" in report["skills"]
    skill = report["skills"]["retry-example"]
    assert skill["recommendation"] in {"KEEP", "NEEDS_CONFIRMATION", "MODIFY", "DELETE"}
    assert isinstance(skill["findings"], list)
    assert report["summary"]["total_skills"] == 1
    assert sum(report["summary"]["by_recommendation"].values()) == 1


def test_final_report_is_deterministic_for_identical_inputs():
    report_a = build_final_report(
        "tests/fixtures/readme-demo", MockConfirmExecutor(), MockNarrationExecutor()
    )
    report_b = build_final_report(
        "tests/fixtures/readme-demo", MockConfirmExecutor(), MockNarrationExecutor()
    )
    assert report_a["report_digest"] == report_b["report_digest"]


def test_final_report_does_not_retain_the_corpus_root_path():
    report = build_final_report(
        "tests/fixtures/readme-demo", MockConfirmExecutor(), MockNarrationExecutor()
    )
    assert "corpus_root" not in report
    assert "tests/fixtures/readme-demo" not in str(report)
