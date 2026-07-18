# Changelog

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [0.7.3] - 2026-07-17

### Corrigido

- Dependência revertida de `quantilica-core[cli]>=0.3.1` para `quantilica-core>=0.3.1`.
  Conforme a arquitetura de CLI híbrida do ecossistema, `typer`/`rich` são **fornecidos
  pelo host `quantilica-cli`** (que já depende de `quantilica-core[cli]`), não declarados
  pelo fetcher. A CLI standalone (`cli.py`) usa `argparse` e não precisa deles. Declarar
  o extra `[cli]` forçava `typer`/`rich` em toda instalação, contrariando o princípio de
  leveza do pacote.

## [0.7.2] - 2026-07-16

### Corrigido

- Dependência de `quantilica-core` trocada de `git+https://...` para uma versão de
  registro publicada no PyPI, removendo o bloqueador de upload ao índice
- Instrução de instalação no README (`pip install sidra-fetcher`, em vez de git+https)

### Adicionado

- `py.typed` (marcador de pacote tipado, consistente com o classifier `Typing :: Typed`)
- Primeiro release público no PyPI

> Nota: a 0.7.2 foi publicada declarando `quantilica-core[cli]>=0.3.1` por engano;
> a 0.7.3 corrige para `quantilica-core>=0.3.1`.
