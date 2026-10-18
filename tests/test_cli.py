# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Testes da fiação argparse (rename sync/download, check, from-plan)."""

from __future__ import annotations

import datetime as dt

from sidra_fetcher.agregados import Periodo
from sidra_fetcher.cli import get_parser, main


class _FakeClient:
    """Cliente sem rede: devolve períodos fixos."""

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def get_agregado_periodos(self, agregado_id: int) -> list[Periodo]:
        return [
            Periodo(
                id="202401",
                literals=["janeiro 2024"],
                modificacao=dt.date(2024, 2, 9),
                frequencia="monthly",
            )
        ]


def test_periods_via_cli_main_imprime_id_e_modificacao(monkeypatch, capsys) -> None:
    """`periods` usa só atributos de `Periodo` (não `nome`)."""
    import sidra_fetcher.cli as cli

    monkeypatch.setattr(cli, "SidraClient", _FakeClient)
    main(["periods", "1737"])
    captured = capsys.readouterr()
    assert "202401" in captured.out
    assert "2024-02-09" in captured.out


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
