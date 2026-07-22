# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Command line interface for sidra-fetcher (minimal dependencies)."""

from __future__ import annotations

import argparse
import logging
import sys

from quantilica.core.logging import configure_cli_logging
from quantilica.core.progress import batch_progress

from sidra_fetcher import __version__
from sidra_fetcher.download import describe_download_plan
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


def _parse_lista(valor: str | None) -> list[str] | None:
    """Converte uma string separada por vírgulas em lista, ou None se ausente."""
    if not valor:
        return None
    return [item.strip() for item in valor.split(",") if item.strip()]


def _parse_classificacoes(items: list[str]) -> dict[str, list[str]] | None:
    """Converte ``["ID=cat1,cat2", ...]`` em ``{"ID": ["cat1", "cat2"]}``."""
    if not items:
        return None
    classificacoes: dict[str, list[str]] = {}
    for item in items:
        cid, _, categorias = item.partition("=")
        classificacoes[cid.strip()] = [
            c.strip() for c in categorias.split(",") if c.strip()
        ]
    return classificacoes


def handle_download(args: argparse.Namespace):
    """Handle `download`."""
    filtros = {
        "niveis_territoriais": _parse_lista(args.niveis),
        "variaveis": _parse_lista(args.variaveis),
        "periodos": _parse_lista(args.periodos),
        "classificacoes": _parse_classificacoes(args.classificacao),
    }

    with SidraClient() as client:
        try:
            agregado = client.get_agregado(args.agregado_id)
            chunks = client.plan_dados_agregado(
                args.agregado_id, agregado=agregado, **filtros
            )
        except Exception as e:
            print(f"Erro ao planejar download: {e}")
            sys.exit(1)

        resumo = describe_download_plan(chunks)
        print(f"Agregado {agregado.id}: {agregado.nome}")
        print(f"{'Nível':<8}{'Requests':<12}{'Valores estimados'}")
        for nivel, d in resumo["por_nivel"].items():
            print(f"{nivel:<8}{d['n_requests']:<12}{d['n_valores']}")
        print(
            f"\nTotal: {resumo['n_requests']} requests, "
            f"{resumo['n_valores']} valores estimados."
        )

        if args.dry_run:
            return

        with batch_progress("Baixando", total=resumo["n_requests"]) as pbar:
            paths = client.download_dados_agregado(
                args.agregado_id,
                args.output,
                agregado=agregado,
                max_workers=args.max_workers,
                politeness_delay=args.delay,
                on_chunk_done=lambda _chunk: pbar.update(1),
                **filtros,
            )

    for p in paths:
        print(f"Gravado: {p}")


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

    # download
    d_parser = subparsers.add_parser(
        "download", help="Baixar todos os dados de um agregado."
    )
    d_parser.add_argument("agregado_id", type=int, help="ID do agregado.")
    d_parser.add_argument(
        "-o", "--output", default="./sidra_data", help="Diretório de saída."
    )
    d_parser.add_argument(
        "--niveis", help="Níveis territoriais (ex: N3,N6). Padrão: todos."
    )
    d_parser.add_argument(
        "--variaveis", help="IDs de variáveis, separados por vírgula. Padrão: todas."
    )
    d_parser.add_argument(
        "--periodos", help="IDs de períodos, separados por vírgula. Padrão: todos."
    )
    d_parser.add_argument(
        "--classificacao",
        action="append",
        default=[],
        help="ID=cat1,cat2 (repetível). Padrão: todas as categorias.",
    )
    d_parser.add_argument("--max-workers", type=int, default=4)
    d_parser.add_argument(
        "--delay", type=float, default=0.2, help="Pausa entre requests (segundos)."
    )
    d_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Só mostra o plano de download, sem baixar nada.",
    )
    d_parser.set_defaults(func=handle_download)

    return parser


def main(argv: list[str] | None = None) -> None:
    """Main entry point."""
    parser = get_parser()
    args = parser.parse_args(argv)
    configure_cli_logging(verbose=args.verbose)
    if not args.verbose:
        logging.getLogger("quantilica.core").setLevel(logging.WARNING)
        logging.getLogger("sidra_fetcher").setLevel(logging.WARNING)
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nOperação cancelada pelo usuário.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
