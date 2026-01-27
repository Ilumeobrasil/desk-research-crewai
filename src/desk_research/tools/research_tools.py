import os
from crewai.tools import tool
import requests
import json
import time
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin
import re

@tool("serper_scholar_search")
def serper_scholar_tool(query: str, num: int= 15, gl: str = 'br') -> str:
    """
    Busca papers acadêmicos no Google Scholar via API Serper

    Args:
        query: Termo de busca acadêmico
        num: Número de resultados buscados
        gl: country da busca (br, us, etc.)
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
            "num": num,
        })
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}

        response = requests.post(url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()

        data = response.json()

        papers = []
        for idx, result in enumerate(data.get("organic", [])[:20]): 
            link = result.get("link", "N/A")
            pdf_link = None

            if(result.get("pdfUrl")):
                pdf_link = result.get("pdfUrl")
            elif(link and link.lower().endswith(".pdf")):
                pdf_link = link

            paper = {
                "titulo": result.get("title", "N/A"),
                "autores": [result.get("publication_info", {}).get("summary", "N/A")],
                "ano": result.get("year", ''),
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

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params, timeout=10)

                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 5  
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
                break

            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise e

        data = response.json()

        papers = []
        for idx, paper_data in enumerate(data.get("data") or []):
            if not paper_data:
                continue

            authors_raw = paper_data.get("authors") or []
            authors = [a.get("name") for a in authors_raw if a and a.get("name")]

            paper = {
                "titulo": paper_data.get("title", "N/A"),
                "autores": authors,
                "ano": paper_data.get("year"),
                "instituicao": None, 
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


@tool("google_scholar_search")
def google_scholar_tool(query: str) -> str:
    """
    Busca no Google Scholar via scraping (fallback)

    Args:
        query: Termo de busca

    Returns:
        JSON string com papers encontrados
    """
    try:
        from scholarly import scholarly

        try:
            search_query = scholarly.search_pubs(query)
        except KeyboardInterrupt:
            return json.dumps(
                {"error": "Google Scholar interrompido (Timeout/Captcha)", "papers": []}
            )

        papers = []
        for idx in range(10):
            try:
                result = next(search_query)

                pub_url = result.get("pub_url", "N/A")
                eprint_url = result.get("eprint_url", "N/A")

                final_url = pub_url
                pdf_url = None
                if eprint_url and eprint_url.lower().endswith(".pdf"):
                    final_url = eprint_url
                    pdf_url = eprint_url
                elif eprint_url and "pdf" in eprint_url.lower():
                    final_url = eprint_url 

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

    Args:
        query: Termo de busca
        max_results: Número máximo de resultados (padrão 10)

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

                citations_elem = article.find(text=re.compile(r"Citations"))
                if citations_elem:
                    match = re.search(r"(\d+)", citations_elem)
                    if match:
                        paper["citacoes"] = int(match.group(1))

                papers.append(paper)
                time.sleep(0.5) 

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


@tool("openalex_search")
def openalex_search_tool(query: str) -> str:
    """
    Busca papers no OpenAlex

    Args:
        query: Termo de busca

    Returns:
        JSON string com papers encontrados
    """
    try:
        url = "https://api.openalex.org/works"

        params = {
            "search": query,
            "per-page": 20,
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
                authors = []
                authorships = work.get("authorships") or []
                for authorship in authorships:
                    if not authorship:
                        continue
                    author_obj = authorship.get("author")
                    if author_obj:
                        author_name = author_obj.get("display_name")
                        if author_name:
                            authors.append(author_name)

                pdf_url = None
                open_access = work.get("open_access")
                if (
                    open_access
                    and isinstance(open_access, dict)
                    and open_access.get("is_oa")
                ):
                    best_oa = work.get("best_oa_location")
                    if best_oa and isinstance(best_oa, dict):
                        pdf_url = best_oa.get("pdf_url")

                abstract_text = "Resumo detalhado disponível no link."

                if not pdf_url:
                    continue

                paper = {
                    "titulo": work.get("display_name", "N/A"),
                    "autores": authors[:5],
                    "ano": work.get("publication_year"),
                    "instituicao": (
                        (work.get("institutions") or [{}])[0].get("display_name")
                        if work.get("institutions")
                        else None
                    ),
                    "resumo": abstract_text,
                    "citacoes": work.get("cited_by_count", 0),
                    "url": pdf_url,
                    "pdf_url": pdf_url,
                    "fonte": "OpenAlex",
                    "revista": (work.get("primary_location") or {})
                    .get("source", {})
                    .get("display_name", "N/A"),
                    "posicao": idx + 1,
                }
                papers.append(paper)

            except Exception as e:
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

@tool("url_validator")
def url_validator_tool(url: str) -> str:
    """
    Valida se uma URL está acessível e retorna o status.

    Args:
        url: URL para validar

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
def google_search_tool(query: str, gl: str = 'br') -> str:
    """
    Realiza busca no Google (via Serper) e retorna resultados normalizados
    para fácil consumo por agentes LLM.

    Args:
        query: Termo de busca

    Returns:
        JSON string com resultados da busca normalizados
    """
    try:
        url = "https://google.serper.dev/search"
        payload = {
            "q": query, 
            "num": 10,
        }

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
            date = item.get("date", "Data não disponível")
            link = item.get("link", "URL não disponível")
            snippet = item.get("snippet", "Resumo não disponível")

            normalized_output.append(
                f"""RESULTADO {idx} | Título: {title} | Data: {date} | URL: {link} | Resumo: {snippet} \n"""
            )

        return "\n".join(normalized_output)

    except Exception as e:
        return f"❌ Erro na busca Google (Serper): {str(e)}"


@tool("web_scraper")
def web_scraper_tool(url: str) -> str:
    """
    Extrai texto de uma página web.
    """

    try:
        import trafilatura

        downloaded = trafilatura.fetch_url(url)
        if downloaded is None:
            return f"⚠️ Erro: Não foi possível baixar o conteúdo de {url} (Trafilatura fetch failed)."

        result = trafilatura.extract(
            downloaded, include_comments=False, include_tables=True, no_fallback=False
        )

        if not result:
            return f"⚠️ Aviso: Nenhum conteúdo extraído de {url}. A página pode usar JS pesado ou bloquear bots."

        return f"CONTEÚDO EXTRAÍDO ({url}):\n\n{result[:12000]}" 

    except ImportError:
        return "❌ Erro Crítico: Biblioteca 'trafilatura' não instalada. Adicione ao pyproject.toml."
    except Exception as e:
        return f"❌ Erro ao processar URL {url}: {e}"


__all__.extend(["google_search_tool", "web_scraper_tool"])
