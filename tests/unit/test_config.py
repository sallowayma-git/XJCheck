from pathlib import Path

import pytest
import yaml

from dwg_audit.utils.config import DEFAULT_CONFIG
from dwg_audit.utils.config import load_config
from dwg_audit.utils.config import resolve_report_formats
from dwg_audit.utils.config import resolve_runtime_profile


RECOGNITION_CONTRACT = {
    "primary_engine": "legacy",
    "legacy_neighborhood": {
        "mode": "shadow-compatible",
        "allow_for_text_candidates": True,
        "allow_for_connectivity": False,
        "allow_for_final_pair": False,
    },
}

WIRE_COMPONENTS_CONTRACT = {
    "inline_body_families": ["KLP", "ZKK"],
}


def test_load_config_uses_legacy_shadow_compatible_recognition_defaults() -> None:
    assert load_config()["recognition"] == RECOGNITION_CONTRACT
    assert DEFAULT_CONFIG["recognition"] == RECOGNITION_CONTRACT


def test_load_config_deep_merges_recognition_contract(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "recognition:\n"
        "  legacy_neighborhood:\n"
        "    allow_for_connectivity: true\n",
        encoding="utf-8",
    )

    recognition = load_config(config_path)["recognition"]

    assert recognition["primary_engine"] == "legacy"
    assert recognition["legacy_neighborhood"] == {
        "mode": "shadow-compatible",
        "allow_for_text_candidates": True,
        "allow_for_connectivity": True,
        "allow_for_final_pair": False,
    }


def test_default_config_template_declares_recognition_contract() -> None:
    template_path = Path(__file__).parents[2] / "configs" / "default.yml"

    template = yaml.safe_load(template_path.read_text(encoding="utf-8"))

    assert template["recognition"] == RECOGNITION_CONTRACT


def test_default_config_declares_inline_body_families() -> None:
    assert DEFAULT_CONFIG["wire_components"] == WIRE_COMPONENTS_CONTRACT
    assert set(load_config()["wire_components"]["inline_body_families"]) == {"KLP", "ZKK"}


def test_default_config_template_declares_inline_body_families() -> None:
    template_path = Path(__file__).parents[2] / "configs" / "default.yml"

    template = yaml.safe_load(template_path.read_text(encoding="utf-8"))

    assert template["wire_components"] == WIRE_COMPONENTS_CONTRACT


def test_default_config_declares_adaptive_oda_resource_gate() -> None:
    gate = DEFAULT_CONFIG["ingest"]["resource_gate"]
    assert gate["enabled"] is True
    assert gate["cpu_high_percent"] == 80.0
    assert gate["cpu_low_percent"] == 65.0
    assert gate["memory_high_percent"] == 80.0
    assert gate["memory_low_percent"] == 70.0
    assert gate["pressure_samples"] == 2
    assert gate["recovery_samples"] == 4

    template_path = Path(__file__).parents[2] / "configs" / "default.yml"
    template = yaml.safe_load(template_path.read_text(encoding="utf-8"))
    assert template["ingest"]["resource_gate"] == gate


def test_resource_gate_config_deep_merges_without_dropping_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "ingest:\n"
        "  resource_gate:\n"
        "    cpu_high_percent: 90\n",
        encoding="utf-8",
    )

    gate = load_config(config_path)["ingest"]["resource_gate"]

    assert gate["cpu_high_percent"] == 90
    assert gate["cpu_low_percent"] == 65.0
    assert gate["enabled"] is True


def test_default_runtime_profile_uses_production_markdown_policy() -> None:
    config = load_config()

    assert config["runtime"]["profile"] == "production"
    assert resolve_runtime_profile(config) == "production"
    assert resolve_report_formats(config) == ["md"]

    template_path = Path(__file__).parents[2] / "configs" / "default.yml"
    template = yaml.safe_load(template_path.read_text(encoding="utf-8"))
    assert template["runtime"]["profile"] == "production"
    assert template["report"]["export_formats"] == ["md"]


def test_runtime_profile_and_report_formats_deep_merge(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "runtime:\n"
        "  profile: diagnostic\n"
        "report:\n"
        "  export_formats: html, md, html\n",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config["runtime"]["persist_page_findings_files"] is False
    assert config["report"]["include_candidate_details"] is True
    assert resolve_runtime_profile(config) == "diagnostic"
    assert resolve_report_formats(config) == ["html", "md"]


def test_runtime_profile_rejects_unknown_value(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text("runtime:\n  profile: turbo\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported runtime profile"):
        load_config(config_path)


def test_report_formats_are_validated_and_regression_forces_full_set(tmp_path: Path) -> None:
    regression_path = tmp_path / "regression.yml"
    regression_path.write_text(
        "runtime:\n  profile: regression\nreport:\n  export_formats: md\n",
        encoding="utf-8",
    )
    invalid_path = tmp_path / "invalid.yml"
    invalid_path.write_text(
        "runtime:\n  profile: regression\nreport:\n  export_formats: [pdf]\n",
        encoding="utf-8",
    )

    assert resolve_report_formats(load_config(regression_path)) == ["md", "html", "xlsx"]
    with pytest.raises(ValueError, match="Unsupported report format"):
        load_config(invalid_path)


def test_default_config_declares_table_structure_tolerances() -> None:
    assert DEFAULT_CONFIG["table_structure"]["axis_tolerance"] == 0.5
    assert DEFAULT_CONFIG["table_structure"]["intersection_tolerance"] == 0.5
    assert DEFAULT_CONFIG["table_structure"]["min_axis_count"] == 3
    loaded = load_config()
    assert loaded["table_structure"]["min_axis_count"] == 3

