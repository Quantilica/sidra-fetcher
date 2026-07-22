# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Typer plugin for quantilica-cli integration."""

from __future__ import annotations

from typing import Annotated

import typer
from quantilica.core.cli import get_console, setup_rich_logging
from rich.panel import Panel
from rich.progress import Progress
from rich.table import Table

from sidra_fetcher.cli import _parse_classificacoes, _parse_lista
from sidra_fetcher.download import describe_download_plan
from sidra_fetcher.fetcher import SidraClient

app = typer.Typer(help="Interface para as APIs SIDRA/Agregados do IBGE.")
list_sub = typer.Typer(help="Listar pesquisas e agregados do IBGE.")
app.add_typer(list_sub, name="list")
console = get_console()


@list_sub.command("pesquisas")
def cmd_list_pesquisas(
    verbose: Annotated[bool, typer.Option("--verbose", help="Logs detalhados")] = False,
) -> None:
    """Listar todas as pesquisas disponíveis no sistema de agregados."""
    setup_rich_logging(verbose, console=console)
    with SidraClient() as client:
        pesquisas = client.get_indice_pesquisas_agregados()

    table = Table(title="Pesquisas do IBGE", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Nome", style="green")
    table.add_column("Qtd Agregados", style="magenta")

    for p in pesquisas:
        table.add_row(str(p.id), p.nome, str(len(p.agregados)))

    console.print(table)


@list_sub.command("agregados")
def cmd_list_agregados(
    pesquisa_id: Annotated[int, typer.Argument(help="ID da pesquisa (ex: 73)")],
    verbose: Annotated[bool, typer.Option("--verbose", help="Logs detalhados")] = False,
) -> None:
    """Listar todos os agregados de uma pesquisa específica."""
    setup_rich_logging(verbose, console=console)
    with SidraClient() as client:
        pesquisas = client.get_indice_pesquisas_agregados()
        pesquisa = next((p for p in pesquisas if p.id == pesquisa_id), None)

    if not pesquisa:
        console.print(f"[red]Erro:[/red] Pesquisa {pesquisa_id} não encontrada.")
        raise typer.Exit(1)

    table = Table(title=f"Agregados da Pesquisa: {pesquisa.nome}", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Nome", style="green")

    for a in pesquisa.agregados:
        table.add_row(str(a.id), a.nome)

    console.print(table)


@app.command("info")
def cmd_info(
    agregado_id: Annotated[int, typer.Argument(help="ID do agregado (ex: 1612)")],
    verbose: Annotated[bool, typer.Option("--verbose", help="Logs detalhados")] = False,
) -> None:
    """Exibir metadados detalhados de um agregado."""
    setup_rich_logging(verbose, console=console)
    with SidraClient() as client:
        try:
            metadados = client.get_agregado_metadados(agregado_id)
        except Exception as e:
            console.print(f"[red]Erro ao buscar metadados:[/red] {e}")
            raise typer.Exit(1) from e

    console.print(
        Panel(
            f"[bold cyan]{metadados.nome}[/bold cyan]\n[dim]{metadados.assunto}[/dim]",
            title=f"Agregado {metadados.id}",
        )
    )

    v_table = Table(title="Variáveis", show_header=True, header_style="bold magenta")
    v_table.add_column("ID", style="cyan")
    v_table.add_column("Nome")
    v_table.add_column("Unidade", style="green")
    for v in metadados.variaveis:
        v_table.add_row(str(v.id), v.nome, v.unidade)
    console.print(v_table)

    if metadados.classificacoes:
        c_table = Table(
            title="Classificações",
            show_header=True,
            header_style="bold yellow",
        )
        c_table.add_column("ID", style="cyan")
        c_table.add_column("Nome")
        c_table.add_column("Categorias", style="dim")
        for c in metadados.classificacoes:
            c_table.add_row(str(c.id), c.nome, str(len(c.categorias)))
        console.print(c_table)


@app.command("periods")
def cmd_periods(
    agregado_id: Annotated[int, typer.Argument(help="ID do agregado (ex: 1612)")],
    verbose: Annotated[bool, typer.Option("--verbose", help="Logs detalhados")] = False,
) -> None:
    """Listar os períodos disponíveis para um agregado."""
    setup_rich_logging(verbose, console=console)
    with SidraClient() as client:
        try:
            periodos = client.get_agregado_periodos(agregado_id)
        except Exception as e:
            console.print(f"[red]Erro ao buscar períodos:[/red] {e}")
            raise typer.Exit(1) from e

    table = Table(title=f"Períodos para Agregado {agregado_id}", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Nome", style="green")
    table.add_column("Modificação", style="dim")

    for p in periodos:
        table.add_row(p.id, p.nome, p.modificacao.isoformat())

    console.print(table)


@app.command("download")
def cmd_download(
    agregado_id: Annotated[int, typer.Argument(help="ID do agregado (ex: 1705)")],
    output: Annotated[
        str, typer.Option("--output", "-o", help="Diretório de saída")
    ] = "./sidra_data",
    niveis: Annotated[
        str | None,
        typer.Option(
            "--niveis", help="Níveis territoriais (ex: N3,N6). Padrão: todos."
        ),
    ] = None,
    variaveis: Annotated[
        str | None,
        typer.Option("--variaveis", help="IDs de variáveis, separados por vírgula."),
    ] = None,
    periodos: Annotated[
        str | None,
        typer.Option("--periodos", help="IDs de períodos, separados por vírgula."),
    ] = None,
    classificacao: Annotated[
        list[str],
        typer.Option(
            "--classificacao", help="ID=cat1,cat2 (repetível). Padrão: todas."
        ),
    ] = [],  # noqa: B006 - typer exige um default mutável para opções repetíveis
    max_workers: Annotated[int, typer.Option("--max-workers")] = 4,
    delay: Annotated[
        float, typer.Option("--delay", help="Pausa entre requests (segundos)")
    ] = 0.2,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Só mostra o plano, sem baixar")
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", help="Logs detalhados")] = False,
) -> None:
    """Baixar todos os dados de um agregado, respeitando o limite da API."""
    setup_rich_logging(verbose, console=console)
    filtros = {
        "niveis_territoriais": _parse_lista(niveis),
        "variaveis": _parse_lista(variaveis),
        "periodos": _parse_lista(periodos),
        "classificacoes": _parse_classificacoes(classificacao),
    }

    with SidraClient() as client:
        try:
            agregado = client.get_agregado(agregado_id)
            chunks = client.plan_dados_agregado(
                agregado_id, agregado=agregado, **filtros
            )
        except Exception as e:
            console.print(f"[red]Erro ao planejar download:[/red] {e}")
            raise typer.Exit(1) from e

        resumo = describe_download_plan(chunks)
        table = Table(
            title=f"Plano de download — Agregado {agregado.id}: {agregado.nome}",
            show_header=True,
        )
        table.add_column("Nível", style="cyan")
        table.add_column("Requests", style="magenta")
        table.add_column("Valores estimados", style="green")
        for nivel, d in resumo["por_nivel"].items():
            table.add_row(nivel, str(d["n_requests"]), str(d["n_valores"]))
        console.print(table)
        console.print(
            f"Total: {resumo['n_requests']} requests, "
            f"{resumo['n_valores']} valores estimados."
        )

        if dry_run:
            return

        with Progress(console=console) as progress:
            task = progress.add_task("Baixando", total=resumo["n_requests"])
            paths = client.download_dados_agregado(
                agregado_id,
                output,
                agregado=agregado,
                max_workers=max_workers,
                politeness_delay=delay,
                on_chunk_done=lambda _chunk: progress.advance(task),
                **filtros,
            )

    for p in paths:
        console.print(f"[green]Gravado:[/green] {p}")


if __name__ == "__main__":
    app()
