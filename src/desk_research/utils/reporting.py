"""
Módulo compartilhado para geração de relatórios (Markdown e PDF)
"""
import os
import re
import logging
import unicodedata
from pathlib import Path
from fpdf import FPDF
from typing import Literal

logger = logging.getLogger(__name__)

CrewName = Literal["genie", "youtube", "academic", "web", "x", "integrated_analysis", "consumer_hours", "knowledge_bar_stravito"]

class AcademicPDF(FPDF):
    """Classe customizada para PDF com cabeçalho e rodapé AMBEV"""
    def header(self):
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, 'AMBEV Research System', new_x="LMARGIN", new_y="NEXT", align='R')
        self.ln(5)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f'Página {self.page_no()}', new_x="RIGHT", new_y="TOP", align='C')

def clean_markdown_formatting(text):
    """Remove formatação Markdown para texto plano limpo"""
    if not isinstance(text, str):
        return str(text)
        
    # Remove negrito/itálico: **texto** -> texto, *texto* -> texto
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    # Remove código inline: `texto` -> texto
    text = re.sub(r'`(.*?)`', r'\1', text)
    # Remove links: [texto](url) -> texto (url)
    text = re.sub(r'\[(.*?)\]\((.*?)\)', r'\1 (\2)', text)
    # Remove imagens: ![texto](url) -> [Imagem: texto]
    text = re.sub(r'!\[(.*?)\]\((.*?)\)', r'[Imagem: \1]', text)
    # Remove cabeçalhos markdown
    text = re.sub(r'#+\s', '', text)
    
    # Limpeza de artefatos de encoding e Emojis
    # 1. Normalizar smart quotes e traços que viram ? em Latin-1
    replacements = {
        '“': '"', '”': '"', "‘": "'", "’": "'",
        '–': '-', '—': '-', '…': '...',
        '•': '-', '●': '-', '▪': '-'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
        
    return text

def safe_multi_cell(pdf, w, h, txt, is_header=False):
    """Renderiza texto com tratamento de encoding e quebra de linha"""
    # Limpar Markdown inline
    clean_txt = clean_markdown_formatting(txt)
    
    try:
        # Tentar encode latin-1 (padrão FPDF)
        try:
            # Tentar encode latin-1 (padrão FPDF). 'ignore' remove emojis restantes em vez de virar '?'
            encoded_txt = clean_txt.encode('latin-1', 'ignore').decode('latin-1')
        except:
            encoded_txt = clean_txt
        
        # Verificação de segurança de largura manual (simples)
        # Ajuste preventivo se estiver muito perto da margem inferior
        if pdf.get_y() > (pdf.h - pdf.b_margin - 10):
            pdf.add_page()
            # Se for nova página, garantir que X está na margem
            pdf.set_x(pdf.l_margin)
        
        pdf.multi_cell(w, h, encoded_txt, new_x="LMARGIN", new_y="NEXT", align='L')
    except Exception:
        # Fallback agressivo
        try:
            pdf.set_font('Courier', '', 8 if not is_header else 10)
            # Quebrar em chunks menores e substituir aspas
            clean_txt = clean_txt.replace('’', "'").replace('“', '"').replace('”', '"')
            clean_txt = ''.join(c for c in clean_txt if ord(c) < 256)
            
            # Se for cabeçalho, não quebrar tanto
            limit = 60 if not is_header else 80
            chunks = [clean_txt[i:i+limit] for i in range(0, len(clean_txt), limit)]
            for chunk in chunks:
                pdf.multi_cell(w, h, chunk, new_x="LMARGIN", new_y="NEXT", align='L')
        except Exception as e:
            logger.warning(f"Falha ao renderizar linha: {txt[:20]}... {e}")

def slugify(value):
    """Normaliza string para ser usada como nome de arquivo."""
    value = str(value)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[-\s]+', '_', value)

def export_report(result: any, topic: str, prefix: str = "report", crew_name: CrewName | None = None) -> dict:
    # Garantir que a pasta base 'outputs' existe
    base_output_dir = Path('outputs')
    base_output_dir.mkdir(exist_ok=True)
    
    if crew_name:
        output_dir = base_output_dir / slugify(crew_name)
    else:
        output_dir = base_output_dir

    output_dir.mkdir(exist_ok=True)
    
    # Preparar nome do arquivo
    topic_slug = slugify(topic)
    if len(topic_slug) > 50:
        topic_slug = topic_slug[:50].rstrip('_')
        
    base_filename = f"{prefix}_{topic_slug}"
    
    # Extrair conteúdo texto
    if hasattr(result, 'raw'):
        content = result.raw
    elif isinstance(result, str):
        content = result
    elif isinstance(result, dict) and 'result' in result:
         # Fallback para dicionário
        content = str(result['result'])
    else:
        content = str(result)
        
    # --- 1. Salvar Markdown ---
    md_path = output_dir / f'{base_filename}.md'
    md_path.write_text(content, encoding='utf-8')
    logger.info(f"✅ Relatório salvo: {md_path}")
    
    # --- 2. Gerar PDF ---
    pdf_output_path = output_dir / f'{base_filename}.pdf'
    
    try:
        from desk_research.utils.pdf_exporter import markdown_to_pdf
        
        pdf_path = markdown_to_pdf(
            markdown_path=str(md_path),
            pdf_path=str(pdf_output_path),
            title=f"Relatório: {topic}",
            author="Desk Research System"
        )
        logger.info(f"✅ PDF gerado: {pdf_path}")
        
    except Exception as e:
        try:
            pdf = AcademicPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            
            replacements = {
                '•': '*', '→': '->', '✓': '[v]', '✅': '[OK]', '❌': '[X]',
                '’': "'", '‘': "'", '“': '"', '”': '"', '–': '-', '—': '-',
                '\u200b': '', '\xa0': ' '
            }
            safe_content = content
            for k, v in replacements.items():
                safe_content = safe_content.replace(k, v)
            
            # Filtrar caracteres não imprimíveis básicos
            safe_content = ''.join(char for char in safe_content if ord(char) >= 32 or char in '\n\r\t')
            
            for line in safe_content.split('\n'):
                line = line.strip()
                if not line:
                    pdf.ln(3)
                    continue
                
                # Detectar Cabeçalhos com Regex para robustez
                header_match = re.match(r'^(#+)\s+(.+)$', line)
                if header_match:
                    level = len(header_match.group(1))
                    text = header_match.group(2)
                    
                    if level == 1:
                        pdf.set_font('Helvetica', 'B', 16)
                        pdf.set_text_color(0, 51, 102) # Azul Escuro
                        pdf.ln(5)
                        safe_multi_cell(pdf, 0, 10, text, is_header=True)
                        pdf.set_text_color(0, 0, 0)
                    elif level == 2:
                        pdf.set_font('Helvetica', 'B', 14)
                        pdf.set_text_color(0, 102, 204) # Azul Médio
                        pdf.ln(4)
                        safe_multi_cell(pdf, 0, 8, text, is_header=True)
                        pdf.set_text_color(0, 0, 0)
                    elif level >= 3:
                        pdf.set_font('Helvetica', 'B', 12)
                        pdf.set_text_color(50, 50, 50) # Cinza Escuro
                        pdf.ln(2)
                        safe_multi_cell(pdf, 0, 6, text, is_header=True)
                        pdf.set_text_color(0, 0, 0)
                    continue
                
                # Listas
                if line.startswith('* ') or line.startswith('- '):
                    pdf.set_font('Helvetica', '', 10)
                    pdf.set_x(15) # Indentar
                    pdf.write(5, '* ')
                    safe_multi_cell(pdf, 0, 5, line[2:])
                    pdf.set_x(10) # Resetar margem
                    continue
                
                # Imagens: ![alt](path)
                img_match = re.match(r'^!\[(.*?)\]\((.*?)\)$', line)
                if img_match:
                    img_path = img_match.group(2)
                    try:
                        pdf.ln(2)
                        pdf.image(img_path, w=170, x=20) 
                        pdf.ln(5)
                    except Exception as e:
                        safe_multi_cell(pdf, 0, 5, f"[Imagem: {img_match.group(1)} - Falha ao carregar]")
                    continue

                # Texto normal
                pdf.set_font('Helvetica', '', 10)
                safe_multi_cell(pdf, 0, 5, line)
                
            pdf.output(str(pdf_output_path))
            logger.info(f"✅ PDF gerado via FPDF (Fallback): {pdf_output_path}")
            
        except Exception as e2:
            logger.error(f"❌ Falha fatal na geração de PDF (fallback também falhou): {e2}")
        
    return {
        "md_path": str(md_path),
        "pdf_path": str(pdf_output_path)
    }
