# Changelog

## [0.10.3] - 2026-08-31
### Corrigido
- `load_agregado()` restaurado em `sidra_fetcher.reader` — o refactor v0.9.0 removeu o par de leitura de `save_agregado()`, quebrando o round-trip de metadata consumido por `sidra-sql` (`Storage.read_metadata`). Novo teste de round-trio cobre o par save/load.

## [0.10.2] - 2026-08-30
### Corrigido
- Testes adaptados à migração `httpx` → `httpx2` no `quantilica-core` (alvos de patch `quantilica.core.http.httpx2.Client`).
- Dependência `quantilica-core` elevada para `>=0.6.0`.

## [0.10.1] - 2026-08-10
### Corrigido
- Atualizada dependência `quantilica-core` para `>=0.5.0` devido às novas assinaturas requeridas pelo CLI.

## [0.10.0] - 2026-08-10
### Alterado
- Migração arquitetural: O app Typer agora compõe e herda as assinaturas canônicas da `FetcherApp` (`SidraFetcherApp`), alinhando o plugin à SDK padrão da CLI.

## [0.9.0] - 2026-08-07
### Alterado
- Refatoração arquitetural: Remoção de dependências (`quantilica-cli` e `quantilica-catalog`) e limpeza de imports. Os fetchers agora são pacotes de extração puros, dependendo estritamente do `quantilica-core`.

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [0.8.0] - 2026-07-22

### Adicionado

- Novo módulo `download.py`: planejamento (chunking) e download completo de dados
  de um agregado a partir de só um `agregado_id`, respeitando o limite documentado
  de 100.000 valores por requisição do endpoint `/values`. Divide automaticamente
  por período → lote de localidades → variável → combinação de categorias de
  classificação, priorizando nessa ordem; cada nível territorial é baixado
  separadamente.
- `SidraClient.plan_dados_agregado`/`get_dados_agregado`/`iter_dados_agregado`/
  `download_dados_agregado` (este último grava NDJSON + `DownloadManifest` por
  nível territorial). `AsyncSidraClient.plan_dados_agregado` (planejamento puro,
  sem download assíncrono).
- `DataRepository.path_dados` em `storage.py`.
- Comando `download` na CLI standalone (`sidra-fetcher download <id>`) e no plugin
  typer (`quantilica sidra download <id>`), com `--dry-run` para pré-visualizar o
  plano (requests e valores estimados) antes de baixar.
- `SidraClient`/`AsyncSidraClient` aceitam `attempts`/`retry_base_delay` no
  construtor, repassados ao `HttpClient` interno.

### Corrigido

- Limitador de taxa thread-safe: o `politeness_delay` agora é aplicado dentro do
  worker (não no laço de submit), evitando que respostas completas se acumulem na
  memória enquanto a thread principal dormia — mantém o streaming NDJSON incremental
  em tabelas grandes.
- Resposta inesperada do SIDRA (HTTP 200 com corpo que não é lista) levanta
  `FetchError` claro em vez de um `TypeError` obscuro no meio do download.
- `plan_agregado_download` valida os filtros (`variaveis`/`periodos`/
  `classificacoes`/`niveis_territoriais`) contra os ids reais do agregado e levanta
  `ValueError` em id inexistente ou seleção vazia — antes um filtro que não casava
  podia baixar tudo silenciosamente.

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
