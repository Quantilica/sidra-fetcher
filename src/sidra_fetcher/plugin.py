# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Typer plugin for quantilica-cli integration."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Annotated

import typer
from quantilica.cli.sdk import CheckPlan, CheckPlanItem, FetcherApp
from quantilica.cli.ui import (
    ProgressPool,
    get_console,
    make_batch_progress,
    make_download_progress,
    setup_rich_logging,
)
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from sidra_fetcher.check import check_agregado
from sidra_fetcher.cli import _parse_classificacoes, _parse_lista
from sidra_fetcher.download import describe_download_plan
from sidra_fetcher.fetcher import SidraClient


class SidraFetcherApp(FetcherApp):
    def _build_commands(self) -> None:
        # Override to avoid creating default sync/list commands,
        # as SIDRA uses custom list (SubTyper) and download (Custom Planner).
        pass


_DEFAULT_OUTPUT = Path("/data/sidra")


def sidra_list_datasets(group: str) -> list[dict]:
    """List datasets for the SIDRA plugin.

    Args:
        group (str): The group identifier.

    Returns:
        list[dict]: A list of dataset dictionaries.
    """
    return []


def sidra_path_builder(output_dir: Path, entry: dict, last_modified) -> Path:
    """Build the output path for a SIDRA dataset entry.

    Args:
        output_dir (Path): The base output directory.
        entry (dict): The dataset entry dictionary.
        last_modified: The last modified date/time.

    Returns:
        Path: The constructed path for the dataset.
    """
    return output_dir / entry.get("id", "unknown")


fetcher_app = SidraFetcherApp(
    name="sidra-fetcher",
    help="Interface para as APIs SIDRA/Agregados do IBGE.",
    groups_dict={},
    aliases_dict={},
    list_datasets=sidra_list_datasets,
    path_builder=sidra_path_builder,
    default_output=_DEFAULT_OUTPUT,
)

app = fetcher_app.app
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


@app.command("sync")
def cmd_sync(
    agregado_id: Annotated[
        int | None,
        typer.Argument(help="ID do agregado (ex: 1705). Ignorado com --from-plan."),
    ] = None,
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Diretório de saída")
    ] = _DEFAULT_OUTPUT,
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
    workers: Annotated[int, typer.Option("--workers", help="Downloads paralelos")] = 4,
    delay: Annotated[
        float, typer.Option("--delay", help="Pausa entre requests (segundos)")
    ] = 0.2,
    from_plan: Annotated[
        Path | None,
        typer.Option(
            "--from-plan",
            help="Baixar somente os níveis com ação 'download' de um plano "
            "gerado por 'check' (não combinar com filtros).",
        ),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Só mostra o plano, sem baixar")
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", help="Logs detalhados")] = False,
) -> None:
    """Baixar todos os dados de um agregado, respeitando o limite da API."""
    _run_sync(
        agregado_id,
        output,
        niveis,
        variaveis,
        periodos,
        classificacao,
        workers,
        delay,
        from_plan,
        dry_run,
        verbose,
    )


@app.command(
    "download",
    help="Alias DEPRECADO de 'sync' (equivale a 'sync'; será removido; "
    "use 'sync'. '--from-plan' só existe em 'sync').",
)
def cmd_download(
    agregado_id: Annotated[int, typer.Argument(help="ID do agregado (ex: 1705)")],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Diretório de saída")
    ] = _DEFAULT_OUTPUT,
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
    workers: Annotated[int, typer.Option("--workers", help="Downloads paralelos")] = 4,
    delay: Annotated[
        float, typer.Option("--delay", help="Pausa entre requests (segundos)")
    ] = 0.2,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Só mostra o plano, sem baixar")
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", help="Logs detalhados")] = False,
) -> None:
    """Alias DEPRECADO de `sync` (equivale a `sync`; será removido).

    Use `sync`. `--from-plan` só existe em `sync`.
    """
    console.print(
        "[yellow]Aviso:[/yellow] 'download' está depreciado e será removido; "
        "use 'sync'."
    )
    _run_sync(
        agregado_id,
        output,
        niveis,
        variaveis,
        periodos,
        classificacao,
        workers,
        delay,
        None,
        dry_run,
        verbose,
    )


def _run_sync(
    agregado_id: int,
    output: Path,
    niveis: str | None,
    variaveis: str | None,
    periodos: str | None,
    classificacao: list[str],
    workers: int,
    delay: float,
    from_plan: Path | None,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Implementação compartilhada de `sync` (e do alias `download`)."""
    setup_rich_logging(verbose, console=console)
    if from_plan is not None:
        if niveis or variaveis or periodos or classificacao:
            console.print(
                "[red]Erro:[/red] '--from-plan' não combina com filtros "
                "(--niveis/--variaveis/--periodos/--classificacao); o plano "
                "já define o escopo."
            )
            raise typer.Exit(1)
        try:
            plan = CheckPlan.from_json(from_plan.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            console.print(f"[red]Plano inválido:[/red] {exc}")
            raise typer.Exit(1) from None
        dl = [it for it in plan.items if it.action == "download"]
        if not dl:
            console.print("[green]Nada a baixar:[/green] plano sem ação 'download'.")
            return
        filtros = dict(dl[0].entry.get("filtros") or {})
        try:
            agregado_id = int(dl[0].entry.get("agregado_id", agregado_id))
        except (TypeError, ValueError) as exc:
            console.print(f"[red]Plano inválido:[/red] agregado_id ({exc})")
            raise typer.Exit(1) from None
        niveis_list = sorted({str(it.entry.get("nivel", "")) for it in dl} or {None})
        filtros["niveis_territoriais"] = [n for n in niveis_list if n]
        console.print(
            f"[dim]Plano {from_plan}: {len(dl)} nível(is) com ação 'download' "
            f"de {len(plan.items)} verificado(s).[/dim]"
        )
    else:
        if agregado_id is None:
            console.print(
                "[red]Erro:[/red] informe o ID do agregado (ou use --from-plan)."
            )
            raise typer.Exit(1)
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

        batch_progress = make_batch_progress(console)
        file_progress = make_download_progress(console)
        pool = ProgressPool(workers=workers, file_prog=file_progress)

        with Live(
            Group(batch_progress, file_progress),
            console=console,
            refresh_per_second=10,
        ):
            level_tasks = {}

            def on_chunk_done(chunk) -> None:
                nivel = chunk.nivel_territorial
                if nivel not in level_tasks:
                    total = resumo["por_nivel"][nivel]["n_requests"]
                    level_tasks[nivel] = batch_progress.add_task(
                        f"[cyan]Nível {nivel}[/cyan]", total=total
                    )
                batch_progress.update(level_tasks[nivel], advance=1)

            def acquire_slot(desc: str):
                return pool.acquire(description=f"[cyan]{desc}[/cyan]")

            try:
                paths = client.download_dados_agregado(
                    agregado_id,
                    output,
                    agregado=agregado,
                    max_workers=workers,
                    politeness_delay=delay,
                    on_chunk_done=on_chunk_done,
                    acquire_slot=acquire_slot,
                    **filtros,
                )
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrompido.[/yellow]")
                raise typer.Exit(130) from None

    for p in paths:
        console.print(f"[green]Gravado:[/green] {p}")


@app.command("check")
def cmd_check(
    agregado_id: Annotated[int, typer.Argument(help="ID do agregado (ex: 1705)")],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Diretório de saída")
    ] = _DEFAULT_OUTPUT,
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
    as_json: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Imprime o plano em JSON (para 'sync --from-plan').",
        ),
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", help="Logs detalhados")] = False,
) -> None:
    """Verificar frescor de um agregado sem baixar (plano por nível)."""
    setup_rich_logging(verbose, console=console)
    filtros = {
        "niveis_territoriais": _parse_lista(niveis),
        "variaveis": _parse_lista(variaveis),
        "periodos": _parse_lista(periodos),
        "classificacoes": _parse_classificacoes(classificacao),
    }
    with SidraClient() as client:
        try:
            veredictos, _resumo = check_agregado(client, agregado_id, output, filtros)
        except Exception as e:
            console.print(f"[red]Erro ao verificar agregado:[/red] {e}")
            raise typer.Exit(1) from e
    generated = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    plan = CheckPlan(
        fetcher="sidra-fetcher",
        output_dir=str(output),
        generated_at=generated,
        items=[CheckPlanItem(**v) for v in veredictos],
    )
    if as_json:
        print(plan.to_json())
    else:
        plan.render_table()


if __name__ == "__main__":
    app()
