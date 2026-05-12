# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Typer plugin for quantilica-cli integration."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sidra_fetcher.fetcher import SidraClient

app = typer.Typer(help="Interface para as APIs SIDRA/Agregados do IBGE.")
console = Console()


@app.command("list-pesquisas")
def list_pesquisas() -> None:
    """Lista todas as pesquisas disponíveis no sistema de agregados."""
    with SidraClient() as client:
        pesquisas = client.get_indice_pesquisas_agregados()

    table = Table(title="Pesquisas do IBGE", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Nome", style="green")
    table.add_column("Qtd Agregados", style="magenta")

    for p in pesquisas:
        table.add_row(str(p.id), p.nome, str(len(p.agregados)))

    console.print(table)


@app.command("list-agregados")
def list_agregados(
    pesquisa_id: Annotated[int, typer.Argument(help="ID da pesquisa (ex: 73)")]
) -> None:
    """Lista todos os agregados de uma pesquisa específica."""
    with SidraClient() as client:
        pesquisas = client.get_indice_pesquisas_agregados()
        pesquisa = next((p for p in pesquisas if p.id == pesquisa_id), None)

    if not pesquisa:
        console.print(f"[red]Erro:[/red] Pesquisa {pesquisa_id} não encontrada.")
        raise typer.Exit(1)

    table = Table(
        title=f"Agregados da Pesquisa: {pesquisa.nome}", show_header=True
    )
    table.add_column("ID", style="cyan")
    table.add_column("Nome", style="green")

    for a in pesquisa.agregados:
        table.add_row(str(a.id), a.nome)

    console.print(table)


@app.command("info")
def info(
    agregado_id: Annotated[
        int, typer.Argument(help="ID do agregado (ex: 1612)")
    ]
) -> None:
    """Exibe metadados detalhados de um agregado."""
    with SidraClient() as client:
        try:
            metadados = client.get_agregado_metadados(agregado_id)
        except Exception as e:
            console.print(f"[red]Erro ao buscar metadados:[/red] {e}")
            raise typer.Exit(1)

    console.print(
        Panel(
            f"[bold cyan]{metadados.nome}[/bold cyan]\n[dim]{metadados.assunto}[/dim]",
            title=f"Agregado {metadados.id}",
        )
    )

    # Variáveis
    v_table = Table(
        title="Variáveis", show_header=True, header_style="bold magenta"
    )
    v_table.add_column("ID", style="cyan")
    v_table.add_column("Nome")
    v_table.add_column("Unidade", style="green")
    for v in metadados.variaveis:
        v_table.add_row(str(v.id), v.nome, v.unidade)
    console.print(v_table)

    # Classificações
    if metadados.classificacoes:
        c_table = Table(
            title="Classificações", show_header=True, header_style="bold yellow"
        )
        c_table.add_column("ID", style="cyan")
        c_table.add_column("Nome")
        c_table.add_column("Categorias", style="dim")
        for c in metadados.classificacoes:
            c_table.add_row(str(c.id), c.nome, str(len(c.categorias)))
        console.print(c_table)


@app.command("periods")
def periods(
    agregado_id: Annotated[
        int, typer.Argument(help="ID do agregado (ex: 1612)")
    ]
) -> None:
    """Lista os períodos disponíveis para um agregado."""
    with SidraClient() as client:
        try:
            periodos = client.get_agregado_periodos(agregado_id)
        except Exception as e:
            console.print(f"[red]Erro ao buscar períodos:[/red] {e}")
            raise typer.Exit(1)

    table = Table(
        title=f"Períodos para Agregado {agregado_id}", show_header=True
    )
    table.add_column("ID", style="cyan")
    table.add_column("Nome", style="green")
    table.add_column("Modificação", style="dim")

    for p in periodos:
        table.add_row(p.id, p.nome, p.modificacao.isoformat())

    console.print(table)


if __name__ == "__main__":
    app()
