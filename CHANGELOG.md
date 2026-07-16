# Changelog

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [0.7.2] - 2026-07-16

### Corrigido

- Dependência de `quantilica-core` trocada de `git+https://...` para `quantilica-core[cli]>=0.3.1`
  (versão publicada no PyPI, com o extra `cli` que fornece `typer`/`rich` exigidos pelo
  entry point `quantilica.fetchers`, corrigindo um `ModuleNotFoundError: typer` em
  instalações isoladas via `pip install sidra-fetcher`)
- Instrução de instalação no README (`pip install sidra-fetcher`, em vez de git+https)

### Adicionado

- `py.typed` (marcador de pacote tipado, consistente com o classifier `Typing :: Typed`)
- Primeiro release público no PyPI
