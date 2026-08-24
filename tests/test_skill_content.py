"""SKILL.md の記述が実際の CLI と一致していることを見る。

skill はエージェントが唯一読む説明書なので、実装から静かにずれると、そこに書かれた
存在しないフラグをエージェントが叩き続けることになる。コマンドを足したときに気付ける
よう、記述と実装の対応をテストで固定する。
"""

import re

import pytest

from pyselector import install
from pyselector.cli import build_parser
from pyselector.utils import errors


def _subcommands():
    parser = build_parser()
    action = next(
        item
        for item in parser._actions
        if getattr(item, "choices", None) and "find" in item.choices
    )
    return action.choices


def _flags(subparser):
    """そのサブコマンドが受け付けるオプション。record のような入れ子も辿る。"""
    found = set()
    for action in subparser._actions:
        found.update(action.option_strings)
        if isinstance(getattr(action, "choices", None), dict):
            for nested in action.choices.values():
                for nested_action in getattr(nested, "_actions", []):
                    found.update(nested_action.option_strings)
    return found


def _examples():
    """skill に載っているコマンド例を (コマンド, フラグ列, 行) で返す。"""
    for line in install.SKILL_CONTENT.splitlines():
        stripped = line.strip()
        if not stripped.startswith("pyselector "):
            continue
        tokens = stripped.split()
        if len(tokens) < 2:
            continue
        flags = [token.split("=")[0].strip("[],") for token in tokens[2:] if token.startswith("--")]
        yield tokens[1], flags, stripped


def test_the_skill_only_shows_commands_that_exist():
    commands = _subcommands()

    unknown = sorted({command for command, _, _ in _examples() if command not in commands})

    assert unknown == []


def test_every_flag_in_the_skill_exists():
    commands = _subcommands()
    problems = []

    for command, flags, line in _examples():
        if command not in commands:
            continue
        available = _flags(commands[command])
        for flag in flags:
            if flag and flag not in available:
                problems.append(f"{command}: {flag} ({line})")

    assert problems == []


def test_every_flag_mentioned_anywhere_exists():
    """本文中のフラグも見る。

    フラグの大半はコマンド例ではなく地の文で説明されるため、例だけを見ていると
    綴り間違いや削除されたフラグを取り逃す。どのサブコマンドでもよいので実在する
    ことだけを確かめる（コマンドとの対応は上のテストが例で見ている）。
    """
    commands = _subcommands()
    every_flag = set()
    for subparser in commands.values():
        every_flag |= _flags(subparser)

    mentioned = {
        match.group(1)
        for match in re.finditer(r"`(--[a-z][a-z0-9-]*)`", install.SKILL_CONTENT)
    }

    assert sorted(mentioned - every_flag) == []


def test_every_command_is_documented():
    commands = _subcommands()
    # serve は利用者が管理するもので、エージェントには触らせない方針。
    # version は説明を要さない。
    expected = set(commands) - {"serve", "version"}

    undocumented = sorted(
        name for name in expected if not re.search(rf"`{re.escape(name)}`", install.SKILL_CONTENT)
    )

    assert undocumented == []


def test_every_exit_code_mentioned_exists():
    known = {
        value
        for name, value in vars(errors).items()
        if name.startswith("EXIT_") and isinstance(value, int)
    }

    mentioned = {int(match.group(1)) for match in re.finditer(r"exit (\d+)", install.SKILL_CONTENT)}

    assert mentioned <= known


@pytest.mark.parametrize(
    "phrase",
    [
        # 取り違えると危険な規律。文言が消えていないことだけ確かめる。
        "Do not create or edit `.env` yourself",
        "Never decide that a check passed by reading a tree dump yourself",
        "does not import pyselector",
    ],
)
def test_the_safety_rules_are_still_there(phrase):
    assert phrase in install.SKILL_CONTENT


def test_the_frontmatter_is_intact():
    assert install.SKILL_CONTENT.startswith("---\nname: pyselector-cli\ndescription: ")
    assert install.SKILL_CONTENT.count("\n---\n") == 1
