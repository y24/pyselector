import pytest

from pyselector.config import load_config
from pyselector.env import read_env_file
from pyselector.utils.errors import ArgumentError


def _env(tmp_path, monkeypatch, text):
    (tmp_path / ".env").write_text(text, encoding="utf-8")
    monkeypatch.delenv("PYSELECTOR_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)


def test_ui_actions_are_disabled_without_an_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("PYSELECTOR_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)

    assert load_config().act.allow_actions is False


def test_the_env_file_enables_ui_actions(monkeypatch, tmp_path):
    _env(tmp_path, monkeypatch, "PYSELECTOR_ALLOW_ACTIONS=true\n")

    assert load_config().act.allow_actions is True


def test_the_env_file_can_disable_ui_actions(monkeypatch, tmp_path):
    _env(tmp_path, monkeypatch, "PYSELECTOR_ALLOW_ACTIONS=false\n")

    assert load_config().act.allow_actions is False


def test_the_process_environment_is_used_without_an_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("PYSELECTOR_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PYSELECTOR_ALLOW_ACTIONS", "1")

    assert load_config().act.allow_actions is True


def test_the_env_file_wins_over_the_process_environment(monkeypatch, tmp_path):
    """許可の所在をファイル 1 つに寄せる。シェルの古い値に負けない。"""
    _env(tmp_path, monkeypatch, "PYSELECTOR_ALLOW_ACTIONS=false\n")
    monkeypatch.setenv("PYSELECTOR_ALLOW_ACTIONS", "true")

    assert load_config().act.allow_actions is False


def test_the_permission_is_read_from_the_current_directory(monkeypatch, tmp_path):
    """設定ファイルと同じ基準。常駐モードでもクライアントの cwd で判定される。"""
    allowing = tmp_path / "allowing"
    refusing = tmp_path / "refusing"
    allowing.mkdir()
    refusing.mkdir()
    (allowing / ".env").write_text("PYSELECTOR_ALLOW_ACTIONS=true\n", encoding="utf-8")
    monkeypatch.delenv("PYSELECTOR_CONFIG", raising=False)

    monkeypatch.chdir(allowing)
    assert load_config().act.allow_actions is True

    monkeypatch.chdir(refusing)
    assert load_config().act.allow_actions is False


def test_an_unreadable_value_is_rejected(monkeypatch, tmp_path):
    _env(tmp_path, monkeypatch, "PYSELECTOR_ALLOW_ACTIONS=maybe\n")

    with pytest.raises(ArgumentError) as error:
        load_config()

    assert "PYSELECTOR_ALLOW_ACTIONS must be true or false" in str(error.value)


def test_the_env_file_ignores_comments_and_quotes_and_export(tmp_path):
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "# コメント行",
                "PYSELECTOR_ALLOW_ACTIONS = 'true'",
                "export OTHER=1",
                'QUOTED="value"',
                "壊れた行",
                "",
            ]
        ),
        encoding="utf-8",
    )

    values = read_env_file(tmp_path / ".env")

    assert values == {"PYSELECTOR_ALLOW_ACTIONS": "true", "OTHER": "1", "QUOTED": "value"}


def test_a_missing_env_file_is_not_an_error(tmp_path):
    assert read_env_file(tmp_path / ".env") == {}
