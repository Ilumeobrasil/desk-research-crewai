"""
Pydantic Models para Academic Crew
Estruturas de dados padronizadas para outputs
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

class PaperMetadata(BaseModel):
    """
    Metadados estruturados de um paper acadêmico
    
    Atende requisito AMBEV:
    "Extração de metadados (autor, ano, instituição, resumo)"
    """
    titulo: str = Field(
        ..., 
        description="Título completo do paper",
        min_length=5
    )
    
    autores: Optional[List[str]] = Field(
        default_factory=list, 
        description="Lista de autores do paper",
        min_items=0
    )

    @field_validator('autores', mode='before')
    @classmethod
    def validate_autores(cls, v):
        """Converte None em lista vazia e strings únicas em lista"""
        if v is None:
            return []
        if isinstance(v, list):
            return v
        # Se for string única, converte para lista
        if isinstance(v, str):
            return [v]
        return []
    
    ano: Optional[int] = Field(
        default=None, 
        description="Ano de publicação"
    )
    
    instituicao: Optional[str] = Field(
        None,
        description="Instituição principal do primeiro autor"
    )
    
    resumo: str = Field(
        ..., 
        description="Abstract/resumo do paper",
        min_length=50
    )
    
    citacoes: int = Field(
        0, 
        description="Número de citações do paper",
        ge=0
    )
    
    url: str = Field(
        ..., 
        description="Link completo para o paper"
    )
    
    fonte: str = Field(
        ..., 
        description="Base de dados de origem (Serper Scholar, arXiv, Semantic Scholar, etc.)"
    )
    
    idioma: Optional[str] = Field(
        "en",
        description="Idioma do paper (en, pt, es, etc.)"
    )
    
    tipo_publicacao: Optional[str] = Field(
        None,
        description="Tipo de publicação (journal, conference, preprint, etc.)"
    )
    
    palavras_chave: Optional[List[str]] = Field(
        None,
        description="Palavras-chave do paper"
    )
    
    # Campos de Análise Profunda
    referencia_abnt: Optional[str] = Field(None, description="Referência completa em formato ABNT", min_length=30)
    
    introducao_contexto: Optional[str] = Field(None, description="1. Introdução e Contexto (ESCREVA UM TEXTO LONGO E DETALHADO. Mínimo 2-3 parágrafos explicativos)", min_length=30)
    fundamentacao_teorica: Optional[str] = Field(None, description="2. Fundamentação Teórica (ESCREVA UM TEXTO LONGO E DETALHADO. Cite conceitos chave)", min_length=30)
    metodologia_detalhada: Optional[str] = Field(None, description="3. Metodologia Detalhada (Explique passo a passo como foi feito. Seja exaustivo)", min_length=30)
    resultados_detalhados: Optional[str] = Field(None, description="4. Resultados Quantitativos e Qualitativos (Traga NÚMEROS e CITAÇÕES DIRETAS. Seja detalhista)", min_length=30)
    discussao: Optional[str] = Field(None, description="5. Discussão e Interpretação (Correlacione com outros autores. Análise profunda)", min_length=30)
    contribuicoes: Optional[str] = Field(None, description="6. Contribuições Originais (O que este paper trouxe de novo para a ciência?)", min_length=30)
    limitacoes_futures: Optional[str] = Field(None, description="7. Limitações e Trabalhos Futuros (O que faltou? O que sugerem?)", min_length=30)
    avaliacao_critica: Optional[str] = Field(None, description="8. Qualidade e Rigor Científico (Sua opinião crítica sobre a validade do estudo)", min_length=30)
    
    class Config:
        json_schema_extra = {
            "example": {
                "titulo": "Sustainable Packaging Solutions for the Beverage Industry",
                "autores": ["Silva, J.", "Santos, M.", "Oliveira, P."],
                "ano": 2024,
                "instituicao": "Universidade de São Paulo",
                "resumo": "This paper explores innovative sustainable packaging solutions...",
                "citacoes": 15,
                "url": "https://scholar.google.com/paper_example",
                "fonte": "Serper Scholar",
                "idioma": "en",
                "tipo_publicacao": "journal",
                "palavras_chave": ["sustainable packaging", "beverages", "circular economy"]
            }
        }


class LimitacaoPesquisa(BaseModel):
    """
    Limitação identificada durante a pesquisa
    
    Atende requisito AMBEV:
    "Eventuais limitações encontradas no processo de pesquisa"
    """
    tipo: str = Field(
        ...,
        description="Tipo de limitação (acesso, temporal, metodológica, etc.)"
    )
    
    descricao: str = Field(
        ...,
        description="Descrição detalhada da limitação"
    )
    
    impacto: str = Field(
        ...,
        description="Impacto da limitação nos resultados (baixo, médio, alto)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "tipo": "Acesso a PDFs",
                "descricao": "15 papers identificados estavam atrás de paywall e não puderam ser analisados em profundidade",
                "impacto": "médio"
            }
        }


class InsightAcademico(BaseModel):
    """
    Insight extraído da análise de literatura
    """
    categoria: str = Field(
        ...,
        description="Categoria do insight (tendência, gap, metodologia, etc.)"
    )
    
    descricao: str = Field(
        ...,
        description="Descrição do insight"
    )
    
    papers_relacionados: List[str] = Field(
        ...,
        description="Títulos dos papers que suportam este insight"
    )
    
    relevancia: str = Field(
        ...,
        description="Relevância para AMBEV (alta, média, baixa)"
    )


class AcademicReport(BaseModel):
    """
    Relatório acadêmico estruturado completo
    
    Atende requisito AMBEV:
    "Gerar um relatório estruturado com os principais insights, 
    dados suportados por referências à fonte consultada e 
    eventuais limitações encontradas no processo de pesquisa"
    """
    
    # Metadados do relatório
    tema: str = Field(
        ...,
        description="Tema/query de pesquisa"
    )
    
    data_pesquisa: datetime = Field(
        default_factory=datetime.now,
        description="Data e hora da execução da pesquisa"
    )
    
    versao_crew: str = Field(
        "1.0",
        description="Versão da Academic Crew"
    )
    
    # Estatísticas da pesquisa
    total_papers_encontrados: int = Field(
        ...,
        description="Total de papers encontrados em todas as bases",
        ge=0
    )
    
    total_papers_analisados: int = Field(
        ...,
        description="Total de papers analisados em profundidade",
        ge=1
    )
    
    bases_consultadas: List[str] = Field(
        ...,
        description="Lista de bases de dados consultadas"
    )
    
    # Papers analisados
    papers: List[PaperMetadata] = Field(
        ...,
        description="Lista de papers analisados com metadados completos",
        min_items=0
    )
    
    # Análise e insights
    insights: List[InsightAcademico] = Field(
        ...,
        description="Principais insights extraídos da literatura"
    )
    
    tendencias_identificadas: List[str] = Field(
        ...,
        description="Tendências identificadas na literatura"
    )
    
    gaps_pesquisa: List[str] = Field(
        ...,
        description="Gaps de pesquisa identificados"
    )
    
    metodologias_predominantes: List[str] = Field(
        ...,
        description="Metodologias mais usadas nos papers analisados"
    )
    
    # Conclusões e recomendações
    conclusoes: List[str] = Field(
        ...,
        description="Conclusões da revisão de literatura"
    )
    
    recomendacoes: List[str] = Field(
        ...,
        description="Recomendações práticas baseadas nos achados"
    )
    
    # Limitações (OBRIGATÓRIO)
    limitacoes: List[LimitacaoPesquisa] = Field(
        ...,
        description="Limitações encontradas durante o processo de pesquisa",
        min_items=0
    )
    
    # Análises em Texto Corrido (Novos Campos para Robustez)
    introducao_geral: Optional[str] = Field(
        None,
        description="Introdução completa do relatório (Contexto, Objetivos, Metodologia de Busca - Mínimo 300 palavras)"
    )
    
    analise_comparativa_completa: Optional[str] = Field(
        None,
        description="Análise conjunta e comparativa de TODOS os papers (Convergências, Divergências, Padrões - Mínimo 500 palavras)"
    )
    
    # Metadados adicionais
    tempo_execucao_minutos: Optional[float] = Field(
        None,
        description="Tempo de execução da crew em minutos"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "tema": "sustainable packaging beverage industry",
                "data_pesquisa": "2024-11-29T10:30:00",
                "versao_crew": "1.0",
                "total_papers_encontrados": 25,
                "total_papers_analisados": 5,
                "bases_consultadas": ["Serper Scholar", "Semantic Scholar", "arXiv"],
                "papers": [],  # Lista de PaperMetadata
                "insights": [],  # Lista de InsightAcademico
                "tendencias_identificadas": [
                    "Crescimento de embalagens biodegradáveis",
                    "Adoção de economia circular"
                ],
                "gaps_pesquisa": [
                    "Poucos estudos sobre custo-benefício de embalagens sustentáveis",
                    "Falta de dados sobre aceitação do consumidor"
                ],
                "metodologias_predominantes": [
                    "Análise de ciclo de vida (LCA)",
                    "Estudos de caso"
                ],
                "conclusoes": [
                    "Embalagens sustentáveis são viáveis tecnicamente",
                    "Necessário investimento em infraestrutura de reciclagem"
                ],
                "recomendacoes": [
                    "Investir em P&D de materiais biodegradáveis",
                    "Parcerias com startups de embalagens inovadoras"
                ],
                "limitacoes": [
                    {
                        "tipo": "Acesso a PDFs",
                        "descricao": "10 papers atrás de paywall",
                        "impacto": "médio"
                    }
                ],
                "tempo_execucao_minutos": 5.3
            }
        }


class SearchPapersOutput(BaseModel):
    """
    Output estruturado da task search_papers
    """
    query: str = Field(..., description="Query de busca utilizada")
    papers_encontrados: List[PaperMetadata] = Field(..., description="Papers encontrados")
    total: int = Field(..., description="Total de papers encontrados")
    bases_usadas: List[str] = Field(..., description="Bases de dados consultadas")
    limitacoes_busca: List[str] = Field(default_factory=list, description="Limitações encontradas durante a busca")


class AnalyzeLiteratureOutput(BaseModel):
    """
    Output estruturado da task analyze_literature
    """
    papers_analisados: List[PaperMetadata] = Field(..., description="Papers analisados")
    insights: List[InsightAcademico] = Field(..., description="Insights extraídos")
    metodologias: List[str] = Field(..., description="Metodologias identificadas")
    tendencias: List[str] = Field(..., description="Tendências identificadas")
    gaps: List[str] = Field(..., description="Gaps de pesquisa")


# Função auxiliar para validação
def validar_relatorio(relatorio) -> dict:
    """
    Valida se o relatório atende aos critérios mínimos AMBEV
    
    Args:
        relatorio: Instância de AcademicReport (structured output do CrewAI)
    
    Returns:
        dict: Dicionário com status de validação de cada critério
        
    Validações AMBEV:
    ✅ 1. Mínimo 3 papers analisados
    ✅ 2. Seção "Limitações da Pesquisa" obrigatória
    ✅ 3. Referências completas com URLs
    ✅ 4. Introdução presente
    ✅ 5. Conclusões e recomendações
    """
    
    erros = []
    
    # ==========================================
    # VALIDAÇÃO 1: Papers Analisados (Mínimo 3)
    # ==========================================
    try:
        total_papers = getattr(relatorio, 'total_papers_analisados', 0)
        tem_papers_suficientes = total_papers >= 3
        if not tem_papers_suficientes:
            erros.append(f"Relatório deve ter no mínimo 3 papers analisados (tem {total_papers})")
    except Exception as e:
        tem_papers_suficientes = False
        total_papers = 0
        erros.append(f"Erro ao verificar total_papers_analisados: {str(e)}")
    
    # ==========================================
    # VALIDAÇÃO 2: Limitações da Pesquisa
    # ==========================================
    try:
        # Tentar diferentes variações do atributo
        limitacoes = getattr(relatorio, 'limitacoes', None)
        if limitacoes is None:
            limitacoes = getattr(relatorio, 'limitacoes_pesquisa', [])
        
        if isinstance(limitacoes, str):
            # Se for string, considerar válido se não for vazio
            tem_limitacoes = len(limitacoes.strip()) > 0
            total_limitacoes = 1 if tem_limitacoes else 0
        elif isinstance(limitacoes, list):
            tem_limitacoes = len(limitacoes) > 0
            total_limitacoes = len(limitacoes)
        else:
            tem_limitacoes = False
            total_limitacoes = 0
        
        if not tem_limitacoes:
            erros.append("Relatório deve documentar pelo menos 1 limitação")
    except Exception as e:
        tem_limitacoes = False
        total_limitacoes = 0
        erros.append(f"Erro ao verificar limitações: {str(e)}")
    
    # ==========================================
    # VALIDAÇÃO 3: Introdução
    # ==========================================
    try:
        introducao = getattr(relatorio, 'introducao', '')
        tem_introducao = bool(introducao and len(str(introducao).strip()) > 0)
        if not tem_introducao:
            erros.append("Relatório deve ter introdução")
    except Exception as e:
        tem_introducao = False
        erros.append(f"Erro ao verificar introdução: {str(e)}")
    
    # ==========================================
    # VALIDAÇÃO 4: Conclusões
    # ==========================================
    try:
        conclusoes = getattr(relatorio, 'conclusoes', '')
        tem_conclusoes = bool(conclusoes and len(str(conclusoes).strip()) > 0)
        if not tem_conclusoes:
            erros.append("Relatório deve ter conclusões")
    except Exception as e:
        tem_conclusoes = False
        erros.append(f"Erro ao verificar conclusões: {str(e)}")
    
    # ==========================================
    # VALIDAÇÃO 5: Recomendações
    # ==========================================
    try:
        recomendacoes = getattr(relatorio, 'recomendacoes', '')
        tem_recomendacoes = bool(recomendacoes and len(str(recomendacoes).strip()) > 0)
        if not tem_recomendacoes:
            erros.append("Relatório deve ter recomendações")
    except Exception as e:
        tem_recomendacoes = False
        erros.append(f"Erro ao verificar recomendações: {str(e)}")
    
    # ==========================================
    # VALIDAÇÃO 6: Referências (Papers com URL)
    # ==========================================
    try:
        papers = getattr(relatorio, 'papers', [])
        tem_referencias = False
        total_referencias = 0
        
        if papers:
            papers_com_url = [p for p in papers if hasattr(p, 'url') and p.url]
            tem_referencias = len(papers_com_url) > 0
            total_referencias = len(papers_com_url)
        
        if not tem_referencias:
            erros.append("Relatório deve ter referências com URLs")
    except Exception as e:
        tem_referencias = False
        total_referencias = 0
        erros.append(f"Erro ao verificar referências: {str(e)}")
    
    # ==========================================
    # RESULTADO FINAL
    # ==========================================
    is_valid = len(erros) == 0
    
    return {
        # Status de cada validação
        'tem_papers': tem_papers_suficientes,
        'tem_limitacoes': tem_limitacoes,
        'tem_introducao': tem_introducao,
        'tem_conclusoes': tem_conclusoes,
        'tem_recomendacoes': tem_recomendacoes,
        'tem_referencias': tem_referencias,
        
        # Contadores
        'total_papers': total_papers,
        'total_limitacoes': total_limitacoes,
        'total_referencias': total_referencias,
        
        # Status geral
        'is_valid': is_valid,
        'erros': erros,
        
        # Mensagem amigável
        'mensagem': '✅ Relatório válido' if is_valid else f'❌ {len(erros)} validações falharam'
    }

# Exemplo de uso
if __name__ == "__main__":
    # Exemplo de criação de PaperMetadata
    paper = PaperMetadata(
        titulo="Sustainable Packaging in Beverage Industry",
        autores=["Silva, J.", "Santos, M."],
        ano=2024,
        instituicao="USP",
        resumo="This paper explores sustainable packaging solutions for beverages...",
        citacoes=15,
        url="https://scholar.google.com/paper",
        fonte="Serper Scholar"
    )
    
    print("✅ PaperMetadata criado com sucesso!")
    print(paper.model_dump_json(indent=2))
    
    # Exemplo de validação de relatório
    limitacao = LimitacaoPesquisa(
        tipo="Acesso",
        descricao="Papers atrás de paywall",
        impacto="médio"
    )
    
    relatorio = AcademicReport(
        tema="sustainable packaging",
        total_papers_encontrados=10,
        total_papers_analisados=3,
        bases_consultadas=["Serper Scholar"],
        papers=[paper],
        insights=[],
        tendencias_identificadas=["Sustentabilidade"],
        gaps_pesquisa=["Custo-benefício"],
        metodologias_predominantes=["LCA"],
        conclusoes=["Viável"],
        recomendacoes=["Investir em P&D"],
        limitacoes=[limitacao]
    )
    
    is_valid, erros = validar_relatorio(relatorio)
    print(f"\n✅ Relatório válido: {is_valid}")
    if erros:
        print("❌ Erros encontrados:")
        for erro in erros:
            print(f"  - {erro}")
