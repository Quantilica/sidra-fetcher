# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Command line interface for sidra-fetcher (minimal dependencies)."""

from __future__ import annotations

import argparse
import logging
import sys

from quantilica_core.logging import configure_cli_logging

from sidra_fetcher import __version__
from sidra_fetcher.fetcher import SidraClient


def handle_list_pesquisas(args: argparse.Namespace):
    """Handle `list pesquisas`."""
    with SidraClient() as client:
        pesquisas = client.get_indice_pesquisas_agregados()

    print(f"{'ID':<10} {'Nome':<60} {'Agregados':<10}")
    print("-" * 80)
    for p in pesquisas:
        print(f"{p.id:<10} {p.nome[:59]:<60} {len(p.agregados):<10}")


def handle_list_agregados(args: argparse.Namespace):
    """Handle `list agregados`."""
    with SidraClient() as client:
        pesquisas = client.get_indice_pesquisas_agregados()
        pesquisa = next((p for p in pesquisas if p.id == args.pesquisa_id), None)

    if not pesquisa:
        print(f"Erro: Pesquisa {args.pesquisa_id} não encontrada.")
        sys.exit(1)

    print(f"Agregados da Pesquisa: {pesquisa.nome}")
    print(f"{'ID':<10} {'Nome'}")
    print("-" * 80)
    for a in pesquisa.agregados:
        print(f"{a.id:<10} {a.nome}")


def handle_info(args: argparse.Namespace):
    """Handle info command."""
    with SidraClient() as client:
        try:
            metadados = client.get_agregado_metadados(args.agregado_id)
        except Exception as e:
            print(f"Erro ao buscar metadados: {e}")
            sys.exit(1)

    print(f"\nAgregado {metadados.id}: {metadados.nome}")
    print(f"Assunto: {metadados.assunto}")
    print("-" * 80)
    print("\nVariáveis:")
    print(f"{'ID':<10} {'Nome':<50} {'Unidade'}")
    for v in metadados.variaveis:
        print(f"{v.id:<10} {v.nome[:49]:<50} {v.unidade}")

    if metadados.classificacoes:
        print("\nClassificações:")
        print(f"{'ID':<10} {'Nome':<50} {'Categorias'}")
        for c in metadados.classificacoes:
            print(f"{c.id:<10} {c.nome[:49]:<50} {len(c.categorias)}")


def handle_periods(args: argparse.Namespace):
    """Handle periods command."""
    with SidraClient() as client:
        try:
            periodos = client.get_agregado_periodos(args.agregado_id)
        except Exception as e:
            print(f"Erro ao buscar períodos: {e}")
            sys.exit(1)

    print(f"Períodos para Agregado {args.agregado_id}:")
    print(f"{'ID':<10} {'Nome':<30} {'Modificação'}")
    print("-" * 60)
    for p in periodos:
        print(f"{p.id:<10} {p.nome:<30} {p.modificacao.isoformat()}")


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sidra-fetcher",
        description="Interface para as APIs SIDRA/Agregados do IBGE.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Exibir logs detalhados em vez de barra de progresso",
    )
    parser.set_defaults(func=lambda _: parser.print_help())
    subparsers = parser.add_subparsers(dest="command")

    # list
    list_parser = subparsers.add_parser(
        "list", help="Listar pesquisas e agregados do IBGE."
    )
    list_sub = list_parser.add_subparsers(dest="subcommand", required=True)
    list_sub.add_parser(
        "pesquisas", help="Listar todas as pesquisas disponíveis."
    ).set_defaults(func=handle_list_pesquisas)
    agg_parser = list_sub.add_parser(
        "agregados", help="Listar agregados de uma pesquisa."
    )
    agg_parser.add_argument("pesquisa_id", type=int, help="ID da pesquisa.")
    agg_parser.set_defaults(func=handle_list_agregados)

    # info
    info_parser = subparsers.add_parser("info", help="Exibir metadados de um agregado.")
    info_parser.add_argument("agregado_id", type=int, help="ID do agregado.")
    info_parser.set_defaults(func=handle_info)

    # periods
    p_parser = subparsers.add_parser("periods", help="Listar períodos de um agregado.")
    p_parser.add_argument("agregado_id", type=int, help="ID do agregado.")
    p_parser.set_defaults(func=handle_periods)

    return parser


def main(argv: list[str] | None = None) -> None:
    """Main entry point."""
    parser = get_parser()
    args = parser.parse_args(argv)
    configure_cli_logging(verbose=args.verbose)
    if not args.verbose:
        logging.getLogger("quantilica_core").setLevel(logging.WARNING)
        logging.getLogger("sidra_fetcher").setLevel(logging.WARNING)
    args.func(args)


if __name__ == "__main__":
    main()
