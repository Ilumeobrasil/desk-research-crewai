import requests
import PyPDF2
import pdfplumber
import io
import re
from crewai.tools import tool
from bs4 import BeautifulSoup

@tool("pdf_analyzer")
def pdf_analyzer_tool(url: str) -> str:
    """
    Analisa um PDF acadêmico extraindo todo o conteúdo textual.

    Args:
        url: URL direta do PDF

    Returns:
        Texto completo extraído do PDF
    """
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.google.com/",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        session.headers.update(headers)

        try:
            head_resp = session.head(url, allow_redirects=True, timeout=10)
            content_type = head_resp.headers.get("Content-Type", "").lower()

            if "application/pdf" not in content_type:
                get_resp = session.get(url, timeout=15)
                get_resp.raise_for_status()

                if (
                    "application/pdf"
                    in get_resp.headers.get("Content-Type", "").lower()
                ):
                    response = get_resp
                else:
                    soup = BeautifulSoup(get_resp.content, "html.parser")

                    pdf_link = None
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        if (
                            href.lower().endswith(".pdf")
                            or "download" in href.lower()
                            or "pdf" in a.get_text().lower()
                        ):
                            pdf_link = href
                            if not pdf_link.startswith("http"):
                                from urllib.parse import urljoin

                                pdf_link = urljoin(url, pdf_link)
                            break

                    if pdf_link:
                        url = pdf_link
                        response = session.get(url, timeout=30)
                    else:
                        return f"ERRO: URL retorna HTML e nenhum link de PDF explícito foi encontrado: {url}"
            else:
                response = session.get(url, timeout=30)

        except Exception as e:
            return f"FALHA NO ACESSO AO PDF: Não foi possível baixar o PDF. Continue analisando os demais papers normalmente."

        response.raise_for_status()

        pdf_bytes = io.BytesIO(response.content)

        try:
            text_parts = []
            with pdfplumber.open(pdf_bytes) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            text = "\n\n".join(text_parts)
        except Exception as e:
            pdf_bytes.seek(0)
            text_parts = []
            reader = PyPDF2.PdfReader(pdf_bytes)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            text = "\n\n".join(text_parts)

        if not text or len(text) < 100:
            return "ERRO: Não foi possível extrair texto do PDF."

        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)

        metadata = {"title": "", "abstract": "", "sections": []}

        lines = text.split("\n")[:20]
        for line in lines:
            if 10 < len(line.strip()) < 200 and not metadata["title"]:
                metadata["title"] = line.strip()
                break

        abstract_match = re.search(
            r"(?:Abstract|ABSTRACT)[:\s]+(.*?)(?:\n\n|\n[A-Z])",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if abstract_match:
            metadata["abstract"] = abstract_match.group(1).strip()[:500]

        for section in [
            "Introduction",
            "Methodology",
            "Methods",
            "Results",
            "Discussion",
            "Conclusion",
        ]:
            if re.search(rf"\n\s*(\d+\.?\s*)?{section}\s*\n", text, re.IGNORECASE):
                metadata["sections"].append(section)

        parts = [
            "=" * 80,
            "ANÁLISE COMPLETA DO PDF",
            "=" * 80,
            f"\n📄 URL: {url}",
            f"📏 Tamanho: {len(text)} caracteres (~{len(text.split())} palavras)",
            "\n" + "=" * 80,
        ]

        if metadata["title"]:
            parts.append(f"\n📋 TÍTULO:\n{metadata['title']}")
        if metadata["abstract"]:
            parts.append(f"\n📝 ABSTRACT:\n{metadata['abstract']}")
        if metadata["sections"]:
            parts.append(f"\n📑 SEÇÕES: {', '.join(metadata['sections'])}")

        parts.extend(
            [
                "\n" + "=" * 80,
                "CONTEÚDO COMPLETO:",
                "=" * 80,
                text,
                "\n" + "=" * 80,
                "FIM DA ANÁLISE",
                "=" * 80,
            ]
        )

        result = "\n".join(parts)
        return result

    except Exception as e:
        return f"ERRO ao processar PDF: {str(e)}"
