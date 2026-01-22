import requests
import PyPDF2
from desk_research.utils.makelog.makeLog import make_log
import pdfplumber
import io
import re
from crewai.tools import tool
from bs4 import BeautifulSoup

@tool("pdf_analyzer")
def pdf_analyzer_tool(url: str) -> str:
    """
    Analisa um PDF acadêmico extraindo todo o conteúdo textual.

    Esta ferramenta é compatível com o padrão CrewAI e usa lógica robusta
    para baixar e extrair texto de PDFs (via pdfplumber e PyPDF2).

    Args:
        url: URL direta do PDF (ex: https://arxiv.org/pdf/XXXX.XXXXX or https://domain.com/paper.pdf)

    Returns:
        Texto completo extraído do PDF
    """
    try:
        print("------------------------------------------------------------------------------------------------")
        print(f"📥 Verificando URL: {url}")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        try:
            head_resp = requests.head(url, headers=headers, allow_redirects=True, timeout=10)
            content_type = head_resp.headers.get('Content-Type', '').lower()
            
            if 'application/pdf' not in content_type:
                # Se não for PDF, pode ser uma landing page. Tentar GET e procurar link.
                print(f"⚠️ URL não parece ser PDF direto (Type: {content_type}). Tentando encontrar link na página...")
                get_resp = requests.get(url, headers=headers, timeout=15)
                get_resp.raise_for_status()
                
                if 'application/pdf' in get_resp.headers.get('Content-Type', '').lower():
                    # Era PDF mesmo, mas HEAD falhou ou servidor não mandou type correto no HEAD
                    print(f"✅ Era PDF mesmo, mas HEAD falhou ou servidor não mandou type correto no HEAD")
                    response = get_resp
                else:
                    # É HTML. Tentar achar link de PDF.
                    print(f"✅ É HTML. Tentar achar link de PDF.")
                    soup = BeautifulSoup(get_resp.content, 'html.parser')
                    
                    # Heurística: procurar links que terminam em .pdf ou contêm 'pdf' no href/texto
                    pdf_link = None
                    for a in soup.find_all('a', href=True):
                        href = a['href']
                        if href.lower().endswith('.pdf') or 'download' in href.lower() or 'pdf' in a.get_text().lower():
                            pdf_link = href
                            if not pdf_link.startswith('http'):
                                from urllib.parse import urljoin
                                pdf_link = urljoin(url, pdf_link)
                            break
                    
                    if pdf_link:
                        print(f"✅ Link de PDF encontrado na página: {pdf_link}")
                        url = pdf_link
                        response = requests.get(url, headers=headers, timeout=30)
                    else:
                        print(f"❌ URL retorna HTML e nenhum link de PDF explícito foi encontrado: {url}")
                        return f"ERRO: URL retorna HTML e nenhum link de PDF explícito foi encontrado: {url}"
            else:
                # É PDF, baixar
                print(f"✅ É PDF, baixar")
                response = requests.get(url, headers=headers, timeout=30)
                
        except Exception as e:
            print(f"❌ ERRO ao acessar URL: {str(e)}")
            return f"ERRO ao acessar URL: {str(e)}"

        response.raise_for_status()
        
        pdf_bytes = io.BytesIO(response.content)
        print(f"✅ PDF baixado ({len(response.content)} bytes)")
        print(f"📄 Extraindo texto...")
        
        # Extrair texto com pdfplumber
        try:
            text_parts = []
            with pdfplumber.open(pdf_bytes) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            text = "\n\n".join(text_parts)
            print(f"✅ Texto extraído com pdfplumber: {len(text)} caracteres")
        except Exception as e:
            print(f"⚠️ pdfplumber falhou. Tentando PyPDF2...")
            pdf_bytes.seek(0)
            text_parts = []
            reader = PyPDF2.PdfReader(pdf_bytes)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            text = "\n\n".join(text_parts)
            print(f"✅ Texto extraído com PyPDF2: {len(text)} caracteres")
        
        if not text or len(text) < 100:
            return "ERRO: Não foi possível extrair texto do PDF."
        
        # Limpar texto
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        
        # Extrair metadados
        metadata = {'title': '', 'abstract': '', 'sections': []}
        
        # Título
        lines = text.split('\n')[:20]
        for line in lines:
            if 10 < len(line.strip()) < 200 and not metadata['title']:
                metadata['title'] = line.strip()
                break
        
        # Abstract
        abstract_match = re.search(
            r'(?:Abstract|ABSTRACT)[:\s]+(.*?)(?:\n\n|\n[A-Z])', 
            text, re.DOTALL | re.IGNORECASE
        )
        if abstract_match:
            metadata['abstract'] = abstract_match.group(1).strip()[:500]
        
        # Seções
        for section in ['Introduction', 'Methodology', 'Methods', 'Results', 'Discussion', 'Conclusion']:
            if re.search(rf'\n\s*(\d+\.?\s*)?{section}\s*\n', text, re.IGNORECASE):
                metadata['sections'].append(section)
        
        # Formatar saída
        parts = [
            "="*80,
            "ANÁLISE COMPLETA DO PDF",
            "="*80,
            f"\n📄 URL: {url}",
            f"📏 Tamanho: {len(text)} caracteres (~{len(text.split())} palavras)",
            "\n" + "="*80,
        ]
        
        if metadata['title']:
            parts.append(f"\n📋 TÍTULO:\n{metadata['title']}")
        if metadata['abstract']:
            parts.append(f"\n📝 ABSTRACT:\n{metadata['abstract']}")
        if metadata['sections']:
            parts.append(f"\n📑 SEÇÕES: {', '.join(metadata['sections'])}")
        
        parts.extend([
            "\n" + "="*80,
            "CONTEÚDO COMPLETO:",
            "="*80,
            text,
            "\n" + "="*80,
            "FIM DA ANÁLISE",
            "="*80,
        ])
        
        result = "\n".join(parts)
        print(f"✅ Análise concluída: {len(result)} caracteres")
        make_log({
            "logName": f"pdf_analyzer-{url.split('/')[-1]}",
            "content": result
        })
        return result
        
    except Exception as e:
        return f"ERRO ao processar PDF: {str(e)}"
