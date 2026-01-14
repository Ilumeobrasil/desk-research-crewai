"""
PDF Exporter - Academic Crew
Converte relatórios Markdown para PDF com formatação profissional

AMBEV - Desk Research System
"""

import markdown2
from weasyprint import HTML, CSS
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def markdown_to_pdf(
    markdown_path: str,
    pdf_path: str = None,
    title: str = "Relatório Acadêmico",
    author: str = "Academic Crew - AMBEV",
    css_custom: str = None
) -> str:
    """
    Converte arquivo Markdown para PDF com formatação profissional
    
    Args:
        markdown_path: Caminho do arquivo .md
        pdf_path: Caminho de saída .pdf (opcional, usa mesmo nome do .md)
        title: Título do documento
        author: Autor do documento
        css_custom: CSS customizado (opcional)
    
    Returns:
        Caminho do PDF gerado
    """
    
    try:
        # Validar arquivo de entrada
        md_file = Path(markdown_path)
        if not md_file.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {markdown_path}")
        
        # Definir caminho de saída
        if pdf_path is None:
            pdf_path = md_file.with_suffix('.pdf')
        else:
            pdf_path = Path(pdf_path)
        
        # Ler Markdown
        logger.info(f"📄 Lendo Markdown: {md_file}")
        with open(md_file, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        
        # Converter Markdown → HTML
        html_content = markdown2.markdown(
            markdown_content,
            extras=[
                'tables',           # Suporte a tabelas
                'fenced-code-blocks',  # Blocos de código
                'strike',           # Texto tachado
                'task_list',        # Listas de tarefas
                'header-ids'        # IDs em cabeçalhos
            ]
        )
        
        # CSS para formatação profissional
        default_css = """
        @page {
            size: A4;
            margin: 2.5cm 2cm 2cm 2cm;
            
            @top-center {
                content: string(heading);
                font-size: 9pt;
                color: #666;
            }
            
            @bottom-right {
                content: "Página " counter(page) " de " counter(pages);
                font-size: 9pt;
                color: #666;
            }
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
            text-align: justify;
        }
        
        h1 {
            color: #1a5490;
            font-size: 24pt;
            font-weight: bold;
            margin-top: 0;
            margin-bottom: 20pt;
            page-break-after: avoid;
            border-bottom: 3px solid #1a5490;
            padding-bottom: 10pt;
        }
        
        h2 {
            color: #2c5f8d;
            font-size: 18pt;
            font-weight: bold;
            margin-top: 24pt;
            margin-bottom: 12pt;
            page-break-after: avoid;
            border-bottom: 1px solid #ccc;
            padding-bottom: 6pt;
        }
        
        h3 {
            color: #3d6fa3;
            font-size: 14pt;
            font-weight: bold;
            margin-top: 18pt;
            margin-bottom: 10pt;
            page-break-after: avoid;
        }
        
        h4 {
            color: #4d7fb8;
            font-size: 12pt;
            font-weight: bold;
            margin-top: 14pt;
            margin-bottom: 8pt;
        }
        
        p {
            margin-bottom: 10pt;
            orphans: 3;
            widows: 3;
        }
        
        ul, ol {
            margin-bottom: 12pt;
            padding-left: 30pt;
        }
        
        li {
            margin-bottom: 6pt;
        }
        
        a {
            color: #1a5490;
            text-decoration: none;
        }
        
        a:hover {
            text-decoration: underline;
        }
        
        blockquote {
            margin: 15pt 30pt;
            padding: 10pt 15pt;
            background-color: #f5f5f5;
            border-left: 4px solid #1a5490;
            font-style: italic;
        }
        
        code {
            font-family: 'Consolas', 'Courier New', monospace;
            background-color: #f4f4f4;
            padding: 2pt 4pt;
            border-radius: 3pt;
            font-size: 10pt;
        }
        
        pre {
            background-color: #f4f4f4;
            padding: 12pt;
            border-radius: 5pt;
            overflow-x: auto;
            margin-bottom: 12pt;
            border-left: 3px solid #1a5490;
        }
        
        pre code {
            background-color: transparent;
            padding: 0;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15pt;
            page-break-inside: avoid;
        }
        
        th {
            background-color: #1a5490;
            color: white;
            font-weight: bold;
            padding: 8pt;
            text-align: left;
            border: 1px solid #ddd;
        }
        
        td {
            padding: 8pt;
            border: 1px solid #ddd;
        }
        
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        
        .metadata {
            font-size: 9pt;
            color: #666;
            margin-bottom: 20pt;
            padding: 10pt;
            background-color: #f9f9f9;
            border-radius: 5pt;
        }
        
        .page-break {
            page-break-before: always;
        }
        
        strong {
            color: #1a5490;
        }
        
        em {
            color: #555;
        }
        """
        
        # Usar CSS customizado se fornecido
        css_final = css_custom if css_custom else default_css
        
        # Metadata do documento
        metadata_html = f"""
        <div class="metadata">
            <strong>Documento:</strong> {title}<br>
            <strong>Gerado por:</strong> {author}<br>
            <strong>Data:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M')}<br>
            <strong>Fonte:</strong> {md_file.name}
        </div>
        """
        
        # HTML completo
        full_html = f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <title>{title}</title>
        </head>
        <body>
            {metadata_html}
            {html_content}
        </body>
        </html>
        """
        
        # Gerar PDF
        logger.info(f"📑 Gerando PDF: {pdf_path}")
        HTML(string=full_html).write_pdf(
            pdf_path,
            stylesheets=[CSS(string=css_final)]
        )
        
        logger.info(f"✅ PDF gerado com sucesso: {pdf_path}")
        logger.info(f"📊 Tamanho: {pdf_path.stat().st_size / 1024:.2f} KB")
        
        return str(pdf_path)
        
    except Exception as e:
        logger.error(f"❌ Erro ao gerar PDF: {str(e)}")
        raise


def export_academic_report_to_pdf(markdown_path: str) -> dict:
    """
    Função específica para exportar relatórios do Academic Crew
    
    Args:
        markdown_path: Caminho do relatório .md
    
    Returns:
        Dicionário com informações do PDF gerado
    """
    try:
        pdf_path = markdown_to_pdf(
            markdown_path=markdown_path,
            title="Relatório Acadêmico - Desk Research System",
            author="Academic Crew - AMBEV"
        )
        
        pdf_file = Path(pdf_path)
        
        return {
            'success': True,
            'pdf_path': str(pdf_path),
            'pdf_name': pdf_file.name,
            'size_kb': pdf_file.stat().st_size / 1024,
            'markdown_source': markdown_path
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'markdown_source': markdown_path
        }


if __name__ == "__main__":
    # Teste standalone
    import sys
    
    if len(sys.argv) > 1:
        md_file = sys.argv[1]
        result = export_academic_report_to_pdf(md_file)
        
        if result['success']:
            print(f"\n✅ PDF gerado com sucesso!")
            print(f"📄 Arquivo: {result['pdf_path']}")
            print(f"📊 Tamanho: {result['size_kb']:.2f} KB")
        else:
            print(f"\n❌ Erro: {result['error']}")
    else:
        print("Uso: python pdf_exporter.py <arquivo.md>")
