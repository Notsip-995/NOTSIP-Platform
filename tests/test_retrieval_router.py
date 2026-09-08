from notsip.retrieval_router import RetrievalRouter


def test_private_commitment_query_does_not_enable_public_web():
    p=RetrievalRouter().plan('What did I promise Sarah last week?')
    assert 'personal_memory' in p.sources and 'email' in p.sources and 'calendar' in p.sources
    assert p.public_web is False


def test_weather_query_selects_weather_source():
    p=RetrievalRouter().plan('What will the weather be tomorrow?')
    assert 'weather' in p.sources


def test_news_query_selects_news_and_public_sources():
    p=RetrievalRouter().plan('Anything important in the news today?')
    assert 'news' in p.sources and p.public_web is True


def test_financial_and_enterprise_queries_are_not_collapsed_into_generic_web():
    financial=RetrievalRouter().plan('How much did I spend last month?')
    enterprise=RetrievalRouter().plan('Check the enterprise inventory database')
    assert 'financial_db' in financial.sources
    assert 'enterprise_db' in enterprise.sources
