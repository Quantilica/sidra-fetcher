"""O plugin declara o FetcherInfo do registro de fetchers."""

from ibge_sidra_fetcher.plugin import fetcher_app


def test_info_declarado():
    app = fetcher_app
    assert app.info_declared is True
    assert app.info.id == "ibge-sidra"
    assert app.info.aliases == ("sidra", "ibge")
    assert app.source_id == "sidra"
    assert app.info.orgao
