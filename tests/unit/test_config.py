from pathlib import Path

import yaml

from dwg_audit.utils.config import DEFAULT_CONFIG, load_config


RECOGNITION_CONTRACT = {
    "primary_engine": "legacy",
    "legacy_neighborhood": {
        "mode": "shadow-compatible",
        "allow_for_text_candidates": True,
        "allow_for_connectivity": False,
        "allow_for_final_pair": False,
    },
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
