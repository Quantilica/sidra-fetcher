# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Testes da fiação argparse (rename sync/download, check, from-plan)."""

from __future__ import annotations

from sidra_fetcher.cli import get_parser


def test_sync_parser_aceita_from_plan() -> None:
    """`sync` aceita --from-plan sem agregado posicional."""
    args = get_parser().parse_args(
        ["sync", "--from-plan", "/tmp/plan.json", "-o", "/tmp/x"]
    )
    assert args.command == "sync"
    assert args.agregado_id is None
    assert args.from_plan == "/tmp/plan.json"


def test_download_parser_mantido_como_alias() -> None:
    """`download` continua parseando (alias depreciado)."""
    args = get_parser().parse_args(["download", "1705", "-o", "/tmp/x"])
    assert args.command == "download"
    assert args.agregado_id == 1705


def test_check_parser_com_json() -> None:
    """`check` parseia agregado, filtros e --json."""
    args = get_parser().parse_args(
        ["check", "1705", "--niveis", "N1", "-o", "/tmp/x", "--json"]
    )
    assert args.command == "check"
    assert args.agregado_id == 1705
    assert args.niveis == "N1"
    assert args.json is True
