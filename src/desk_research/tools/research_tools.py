import os
from crewai.tools import tool
import requests
import json
import time
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin
import re
import http.client

from desk_research.utils.makelog.makeLog import make_log


@tool("serper_scholar_search")
def serper_scholar_tool(query: str, num: int= 15) -> str:
    """
    Busca papers acadêmicos no Google Scholar via API Serper

    Esta ferramenta DEVE ser usada PRIMEIRO em qualquer pesquisa acadêmica.
    Protocolo obrigatório: serper_scholar_search → outras ferramentas

    Args:
        query: Termo de busca acadêmico
        num: Número de resultados buscados

    Returns:
        JSON string com papers encontrados
    """
    try:
        api_key = os.getenv("SERPER_API_KEY")

        url = "https://google.serper.dev/scholar"

        payload = json.dumps({
            "q": query,
            "yearLow": 2018,
            "sort": "relevance",
            "num": num
        })
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}

        response = requests.post(url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()

        data = response.json()

        papers = []
        for idx, result in enumerate(
            data.get("organic", [])[:20]
        ):  # Aumentando para 20
            # Tentar encontrar links de PDF
            link = result.get("link", "N/A")
            pdf_link = None
            if link and link.lower().endswith(".pdf"):
                pdf_link = link

            # Serper as vezes coloca link do PDF em fields específicos ou no snippet
            # Se não tiver PDF explícito, o próprio link pode ser um gateway.

            paper = {
                "titulo": result.get("title", "N/A"),
                "autores": [result.get("publication_info", {}).get("summary", "N/A")],
                "ano": _extract_year(
                    result.get("publication_info", {}).get("summary", "")
                ),
                "instituicao": None,
                "resumo": result.get("snippet", "N/A"),
                "citacoes": int(
                    result.get("inline_links", {}).get("cited_by", {}).get("total", 0)
                ),
                "url": link,
                "pdf_url": pdf_link,
                "fonte": "Serper Scholar (Google Scholar)",
                "posicao": idx + 1,
            }
            papers.append(paper)

        return json.dumps(
            {
                "fonte": "Serper Scholar",
                "query": query,
                "total": len(papers),
                "papers": papers,
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"error": f"Erro no Serper Scholar: {str(e)}", "papers": []})


@tool("semantic_scholar_search")
def semantic_scholar_tool(query: str) -> str:
    """
    Busca papers no Semantic Scholar (API gratuita)

    Args:
        query: Termo de busca

    Returns:
        JSON string com papers encontrados
    """
    try:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"

        params = {
            "query": query,
            "limit": 20,
            "fields": "title,authors,year,abstract,citationCount,url,venue,openAccessPdf",
        }

        # Implementar Backoff para 429 (Rate Limit)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params, timeout=10)

                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 5  # 5s, 10s...
                        print(
                            f"⚠️ Semantic Scholar 429 (Rate Limit). Aguardando {wait_time}s..."
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        return json.dumps(
                            {
                                "error": "Semantic Scholar Unavailable (Rate Limit Exceeded)",
                                "papers": [],
                            }
                        )

                response.raise_for_status()
                break  # Sucesso

            except requests.exceptions.RequestException as e:
                # Se for o último attempt ou erro não-HTTP
                if attempt == max_retries - 1:
                    raise e

        data = response.json()

        papers = []
        for idx, paper_data in enumerate(data.get("data") or []):
            if not paper_data:
                continue

            # Safely handle authors
            authors_raw = paper_data.get("authors") or []
            authors = [a.get("name") for a in authors_raw if a and a.get("name")]

            paper = {
                "titulo": paper_data.get("title", "N/A"),
                "autores": authors,
                "ano": paper_data.get("year"),
                "instituicao": None,  # Semantic Scholar não fornece diretamente
                "resumo": (paper_data.get("abstract") or "Resumo não disponível")[:500],
                "citacoes": paper_data.get("citationCount") or 0,
                "url": paper_data.get("url")
                or f"https://www.semanticscholar.org/paper/{paper_data.get('paperId', '')}",
                "fonte": "Semantic Scholar",
                "revista": paper_data.get("venue", "N/A"),
                "posicao": idx + 1,
            }
            papers.append(paper)

        return json.dumps(
            {
                "fonte": "Semantic Scholar",
                "query": query,
                "total": len(papers),
                "papers": papers,
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps(
            {"error": f"Erro no Semantic Scholar: {str(e)}", "papers": []}
        )


@tool("scielo_tool")
def scielo_tool(query: str) -> str:
    """
    Busca papers no SciELO_tool

    Args:
        query: Termo de busca

    Returns:
        JSON string com papers encontrados
    """
    try:
        query_clean = query.strip()

        url = "https://api.scielo.org/article/"
        params = {
            "q": query_clean,
            "lang": "pt",
            "size": 20,
        }

        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()

        data = response.json()

        papers = []

        for idx, item in enumerate(data.get("results", [])):
            paper = {
                "titulo": item.get("title"),
                "autores": item.get("authors", []),
                "ano": item.get("publication_year"),
                "instituicao": None,
                "resumo": item.get("abstract"),
                "citacoes": None,
                "url": item.get("url"),
                "fonte": "SciELO",
                "periodico": item.get("journal"),
                "pdf_url": item.get("pdf"),
                "posicao": idx + 1,
            }
            papers.append(paper)

        return json.dumps(
            {
                "fonte": "SciELO",
                "query": query,
                "total": len(papers),
                "papers": papers,
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"error": f"Erro no SciELO: {str(e)}", "papers": []})


@tool("google_scholar_search")
def google_scholar_tool(query: str) -> str:
    """
    Busca no Google Scholar via scraping (fallback)

    USO: Apenas como Ãºltimo recurso se Serper Scholar falhar

    Args:
        query: Termo de busca

    Returns:
        JSON string com papers encontrados
    """
    try:
        from scholarly import scholarly

        # Tenta usar proxy generator se disponível, senão falha graciosamente
        # EVITAR HANG: Configurar timeout curto ou desabilitar proxy se for interativo
        print(
            "⚠️ Tentando Google Scholar (scholarly)... isso pode demorar ou falhar com CAPTCHA."
        )

        # Hack para evitar interação manual do scholarly
        # Se falhar conexão com TOR ou Proxies, ele pode tentar lançar browser.
        # Vamos tentar um search direto protegendo contra KeyboardInterrupt/Hang
        try:
            # Timeout simulado não é fácil com scholarly síncrono, mas vamos tentar encapsular
            search_query = scholarly.search_pubs(query)
        except KeyboardInterrupt:
            return json.dumps(
                {"error": "Google Scholar interrompido (Timeout/Captcha)", "papers": []}
            )

        papers = []
        for idx in range(10):
            try:
                # Proteção extra para o next() que pode triggar o Selenium
                result = next(search_query)

                # Lógica para priorizar PDF
                pub_url = result.get("pub_url", "N/A")
                eprint_url = result.get("eprint_url", "N/A")

                # Se eprint terminar em pdf, usa ele. Se não, usa pub_url se existir
                final_url = pub_url
                pdf_url = None
                if eprint_url and eprint_url.lower().endswith(".pdf"):
                    final_url = eprint_url
                    pdf_url = eprint_url
                elif eprint_url and "pdf" in eprint_url.lower():
                    final_url = eprint_url  # Tentativa

                paper = {
                    "titulo": result.get("bib", {}).get("title", "N/A"),
                    "autores": result.get("bib", {}).get("author", []),
                    "ano": result.get("bib", {}).get("pub_year"),
                    "instituicao": None,
                    "resumo": result.get("bib", {}).get("abstract", "N/A")[:500],
                    "citacoes": result.get("num_citations", 0),
                    "url": final_url,
                    "pdf_url": pdf_url,
                    "fonte": "Google Scholar (scholarly)",
                    "posicao": idx + 1,
                }
                papers.append(paper)
            except StopIteration:
                break
            except Exception as e:
                print(f"Erro ao processar paper {idx+1}: {str(e)}")
                continue

        return json.dumps(
            {
                "fonte": "Google Scholar",
                "query": query,
                "total": len(papers),
                "papers": papers,
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"error": f"Erro no Google Scholar: {str(e)}", "papers": []})

@tool("researchgate_scraper")
def researchgate_scraper_tool(query: str, max_results: int = 10) -> str:
    """
    Scraper customizado para ResearchGate

    Busca papers no ResearchGate e extrai metadados completos.

    NOVO: Implementado para atender requisito AMBEV de
    "scraping customizado para portais acadÃªmicos (ResearchGate, Scielo, etc.)"

    Args:
        query: Termo de busca
        max_results: NÃºmero mÃ¡ximo de resultados (padrÃ£o 10)

    Returns:
        String JSON com lista de papers encontrados
    """
    try:
        papers = []

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        search_url = (
            f"https://www.researchgate.net/search/publication?q={quote_plus(query)}"
        )

        response = requests.get(search_url, headers=headers, timeout=10)

        if response.status_code == 403:
            return json.dumps(
                {
                    "status": "blocked",
                    "message": "ResearchGate bloqueou acesso (403). Use Selenium ou API oficial.",
                    "papers": [],
                }
            )

        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        articles = soup.find_all(
            "div", class_="nova-legacy-c-card__body", limit=max_results
        )

        for idx, article in enumerate(articles):
            try:
                title_elem = article.find("a", class_="nova-legacy-e-link--theme-bare")
                if not title_elem:
                    continue

                paper = {
                    "titulo": title_elem.get_text(strip=True),
                    "url": urljoin(
                        "https://www.researchgate.net", title_elem.get("href", "")
                    ),
                    "autores": [],
                    "ano": None,
                    "instituicao": None,
                    "resumo": "Resumo disponÃ­vel na pÃ¡gina do paper",
                    "citacoes": 0,
                    "fonte": "ResearchGate",
                    "posicao": idx + 1,
                }

                # Tentar extrair citaÃ§Ãµes
                citations_elem = article.find(text=re.compile(r"Citations"))
                if citations_elem:
                    match = re.search(r"(\d+)", citations_elem)
                    if match:
                        paper["citacoes"] = int(match.group(1))

                papers.append(paper)
                time.sleep(0.5)  # Delay anti-bot

            except Exception as e:
                continue

        return json.dumps(
            {
                "fonte": "ResearchGate",
                "query": query,
                "total": len(papers),
                "papers": papers,
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"error": f"Erro ResearchGate: {str(e)}", "papers": []})


@tool("scielo_scraper")
def scielo_scraper_tool(query: str, max_results: int = 10) -> str:
    """
    Scraper para Scielo

    Busca papers no Scielo usando API pública.

    Args:
        query: Termo de busca
        max_results: Número máximo de resultados (padrão 10)

    Returns:
        String JSON com lista de papers encontrados
    """
    try:
        api_url = "https://search.scielo.org/"

        "https://search.scielo.org/?fb=&q=cerveja&lang=pt&count=15&from=1&output=site&sort=&format=summary&page=1&where="
        params = {
            "q": query, 
            "lang": "pt", 
            "count": max_results,
            "from": 1,
            "output": "json"
        }

        headers = {"User-Agent": "Academic Research Bot", "Accept": "application/json"}

        response = requests.get(api_url, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()

        papers = []
        results = data.get("response", {}).get("docs", [])

        for idx, doc in enumerate(results[:max_results]):
            paper = {
                "titulo": doc.get("ti_en")
                or doc.get("ti_pt")
                or doc.get("ti_es", "N/A"),
                "autores": doc.get("au", []),
                "ano": int(doc.get("da", "").split("-")[0]) if doc.get("da") else None,
                "instituicao": doc.get("in", [None])[0] if doc.get("in") else None,
                "resumo": (
                    doc.get("ab_en") or doc.get("ab_pt") or doc.get("ab_es", "N/A")
                )[:500],
                "citacoes": 0,
                "url": f"https://www.scielo.br/j/{doc.get('id', '')}",
                "fonte": "Scielo API",
                "idioma": doc.get("la", ["pt"])[0],
                "revista": doc.get("ta", "N/A"),
                "posicao": idx + 1,
            }
            papers.append(paper)

        return json.dumps(
            {"fonte": "Scielo", "query": query, "total": len(papers), "papers": papers},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"error": f"Erro Scielo: {str(e)}", "papers": []})


# =============================================================================
# 9. OPENALEX SEARCH TOOL (NOVO) ⭐
# =============================================================================

@tool("openalex_search")
def openalex_search_tool(query: str) -> str:
    """
    Busca papers no OpenAlex (Base acadêmica aberta e gratuita)

    Fonte robusta e gratuita com mais de 250M de trabalhos.
    Excelente para metadados e links de PDF (Open Access).

    Args:
        query: Termo de busca

    Returns:
        JSON string com papers encontrados
    """
    try:
        # Codificar query
        url = "https://api.openalex.org/works"

        params = {
            "search": query,
            "per-page": 20,  # Aumentado para aumentar chance de achar PDFs
            "sort": "relevance_score:desc",
        }

        headers = {
            "User-Agent": "Academic Research Bot (mailto:researcher@example.com)",
            "Accept": "application/json",
        }

        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()

        data = response.json()
        results = data.get("results", [])

        papers = []
        for idx, work in enumerate(results):
            try:
                # Extrair autores
                authors = []
                # Proteção extra: authorships pode ser None
                authorships = work.get("authorships") or []
                for authorship in authorships:
                    if not authorship:
                        continue
                    author_obj = authorship.get("author")
                    if author_obj:
                        author_name = author_obj.get("display_name")
                        if author_name:
                            authors.append(author_name)

                # Extrair PDF URL
                pdf_url = None
                # Proteção extra: open_access pode ser None
                open_access = work.get("open_access")
                if (
                    open_access
                    and isinstance(open_access, dict)
                    and open_access.get("is_oa")
                ):
                    best_oa = work.get("best_oa_location")
                    if best_oa and isinstance(best_oa, dict):
                        pdf_url = best_oa.get("pdf_url")
                        # REMOVIDO FALLBACK PARA LANDING PAGE
                        # O objetivo é PDF direto. Se não tiver, melhor deixar vazio para o agente saber.

                # Extrair Abstract
                abstract_text = "Resumo detalhado disponível no link."

                # Se não tiver PDF url, pular esse resultado?
                # O prompt diz "Encontrar NO MINIMO 3 papers... com PDFs acessíveis".
                # Vamos priorizar resultados com PDF.
                if not pdf_url:
                    continue  # Pular se não tiver PDF direto (OpenAlex é grande, podemos ser seletivos)

                paper = {
                    "titulo": work.get("display_name", "N/A"),
                    "autores": authors[:5],  # Limitar a 5 para não poluir
                    "ano": work.get("publication_year"),
                    "instituicao": (
                        (work.get("institutions") or [{}])[0].get("display_name")
                        if work.get("institutions")
                        else None
                    ),
                    "resumo": abstract_text,
                    "citacoes": work.get("cited_by_count", 0),
                    "url": pdf_url,  # URL principal AGORA É O PDF
                    "pdf_url": pdf_url,
                    "fonte": "OpenAlex",
                    "revista": (work.get("primary_location") or {})
                    .get("source", {})
                    .get("display_name", "N/A"),
                    "posicao": idx + 1,
                }
                papers.append(paper)

            except Exception as e:
                # Log error but continue
                # print(f"⚠️ Erro no OpenAlex paper {idx}: {e}")
                continue

        return json.dumps(
            {
                "fonte": "OpenAlex",
                "query": query,
                "total": len(papers),
                "papers": papers,
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"error": f"Erro no OpenAlex: {str(e)}", "papers": []})


# =============================================================================
# 8. URL VALIDATOR TOOL
# =============================================================================


@tool("url_validator")
def url_validator_tool(url: str) -> str:
    """
    Valida se uma URL está acessível e retorna o status.

    Use esta ferramenta OBRIGATORIAMENTE para validar TODAS as URLs encontradas
    antes de incluí-las como fontes confiáveis. URLs inacessíveis devem ser descartadas.

    Args:
        url: URL para validar (ex: https://example.com/article)

    Returns:
        Status da URL indicando se está acessível (200) ou não
    """

    try:
        response = requests.head(url, timeout=5, allow_redirects=True)
        if response.status_code == 200:
            return f"URL acessível: {url}"
        else:
            return f"URL retornou status {response.status_code}: {url}"
    except Exception as e:
        return f"âŒ URL inacessÃ­vel: {url}\nErro: {str(e)}"


# =============================================================================
# FUNÃ‡Ã•ES AUXILIARES
# =============================================================================


def _extract_year(text: str) -> int:
    """Extrai ano de um texto"""
    match = re.search(r"\b(19|20)\d{2}\b", text)
    return int(match.group()) if match else None

__all__ = [
    "serper_scholar_tool",
    "semantic_scholar_tool",
    "scielo_tool",
    "google_scholar_tool",
    "researchgate_scraper_tool",  
    "scielo_scraper_tool",  
    "openalex_search_tool",  
    "url_validator_tool",
]

@tool("google_search")
def google_search_tool(query: str) -> str:
    """
    Realiza busca no Google (via Serper) e retorna resultados normalizados
    para fácil consumo por agentes LLM.

    Args:
        query: Termo de busca

    Returns:
        JSON string com resultados da busca normalizados
    """
    try:
        conn = http.client.HTTPSConnection("google.serper.dev")

        url = "https://google.serper.dev/search"
        payload = {"q": query, "num": 10}

        headers = {
            "X-API-KEY": os.getenv("SERPER_API_KEY", ""),
            "Content-Type": "application/json",
        }

        response = requests.request("POST", url, headers=headers, json=payload)
        response.raise_for_status()

        organic_results = response.json().get("organic", [])

        if not organic_results:
            return "⚠️ Nenhum resultado orgânico encontrado para a busca."

        normalized_output = []
        for idx, item in enumerate(organic_results, start=1):
            title = item.get("title", "Título não disponível")
            link = item.get("link", "URL não disponível")
            snippet = item.get("snippet", "Resumo não disponível")

            normalized_output.append(
                f"""RESULTADO {idx}
Título: {title}
URL: {link}
Resumo: {snippet}
"""
            )

        return "\n".join(normalized_output)

        # return json.dumps(resp.json().get('organic', []), indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Erro na busca Google (Serper): {query} - {str(e)}")
        return f"❌ Erro na busca Google (Serper): {str(e)}"


@tool("web_scraper")
def web_scraper_tool(url: str) -> str:
    """
    Extrai texto de uma página web.
    """

    try:
        import trafilatura

        # 1. Download
        downloaded = trafilatura.fetch_url(url)
        if downloaded is None:
            return f"⚠️ Erro: Não foi possível baixar o conteúdo de {url} (Trafilatura fetch failed)."

        # 2. Extract
        result = trafilatura.extract(
            downloaded, include_comments=False, include_tables=True, no_fallback=False
        )

        if not result:
            return f"⚠️ Aviso: Nenhum conteúdo extraído de {url}. A página pode usar JS pesado ou bloquear bots."

        # 3. Metadados opcionais (se trafilatura extrair)
        # Trafilatura metadata extraction is separate, but extract() returns main text.

        return f"CONTEÚDO EXTRAÍDO ({url}):\n\n{result[:12000]}"  # Aumentando limite pois trafilatura é limpo

    except ImportError:
        return "❌ Erro Crítico: Biblioteca 'trafilatura' não instalada. Adicione ao pyproject.toml."
    except Exception as e:
        return f"❌ Erro ao processar URL {url}: {e}"


# Atualizar exports
__all__.extend(["google_search_tool", "web_scraper_tool"])
