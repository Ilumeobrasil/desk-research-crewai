from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Type
from datetime import datetime

from dotenv import load_dotenv
from crewai import Agent, Task, LLM
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from desk_research.tools.asimov_client import AsimovClient

MAX_ITEMS_PER_BATCH = 30

load_dotenv()

def extract_interview_insights(text: str, file_name: str) -> dict[str, Any]:
    """
    Extrai pontos importantes de uma entrevista usando um agente do CrewAI com LLM.
    TUDO deve ser baseado em citações literais da entrevista.
    As informações demográficas (quota) são extraídas pela LLM diretamente do texto.
    """

    llm = LLM(
        model=os.getenv("MODEL"),
        temperature=0.8,
        base_url=os.getenv("OPENAI_API_BASE"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    
    agent = Agent(
        role="Analista Qualitativo de Entrevistas",
        goal="Extrair insights baseados exclusivamente em citações literais de entrevistas, identificando perguntas, informações demográficas, marcas mencionadas, data da entrevista e insights.",
        backstory="Você é um especialista em análise qualitativa de entrevistas. Você extrai insights BASEADOS EXCLUSIVAMENTE em citações literais. Identifica todas as marcas mencionadas. Para cada citação do entrevistado, identifica a pergunta do entrevistador que a precedeu. Extrai informações demográficas e a data da entrevista diretamente do texto ou nome do arquivo. A data geralmente aparece no formato '(May 21, 2025 - 9:20pm)' e deve ser convertida para 'YYYY-MM-DD'.",
        llm=llm,
        verbose=False,
    )
    
    task = Task(
        description=f"""Analise a seguinte entrevista e extraia pontos importantes BASEADOS EXCLUSIVAMENTE EM CITAÇÕES LITERAIS.

TEXTO DA ENTREVISTA:
{text}

NOME DO ARQUIVO (pode conter informações demográficas):
{file_name}

INSTRUÇÕES CRÍTICAS:
1. TODOS os insights devem ser baseados em citações literais do texto
2. NÃO invente ou interprete além do que está nas citações
3. Para cada citação do entrevistado, inclua a PERGUNTA do entrevistador que a precedeu
4. EXTRAIA informações demográficas (quota) diretamente do texto da entrevista ou do nome do arquivo
5. EXTRAIA a data da entrevista do texto. A data geralmente está no formato "(May 21, 2025 - 9:20pm)" ou similar. Procure por timestamps, menções de data no início da entrevista ou contexto temporal. Converta para formato "YYYY-MM-DD" (ex: "2025-05-21")

Extraia e estruture em JSON:

**citacoes**: Lista de objetos, cada um contendo:
- "citacao": Citação literal EXATA do entrevistado
- "pergunta": Pergunta do entrevistador que gerou essa resposta
- "dataEntrevista": Data da entrevista extraída do texto (formato: "YYYY-MM-DD"). Deve ser a mesma para todas as citações
- "quota": Objeto com informações demográficas EXTRAÍDAS DO TEXTO:
  - "nome": Nome do entrevistado
  - "idade": Idade (formato: "XX anos" ou "Não informado")
  - "regiao": Região/Estado (sigla: RJ, SP, etc. ou "Não informado")
  - "classeSocial": Classe social (A1, B1, etc. ou "Não informado")
- "marcaMencionada": Lista de marcas mencionadas na citação (ex: ["Antártica", "Brahma"])
- "insight": Breve interpretação do que a citação revela (máximo 2 frases)

CRITÉRIO DE SELEÇÃO DE CITAÇÕES (EXPANDIDO):
- Extraia TODAS as citações que contenham QUALQUER uma das seguintes informações:
            
MARCAS E PRODUTOS:
- Marcas explicitamente mencionadas
- Produtos específicos (ex: "Brahma Duplo Malte", "Brahma Chopp", "Brahma Zero")
- Linhas de produtos ou variações
            
AVALIAÇÕES E PERCEPÇÕES:
- Avaliações explícitas sobre marcas, produtos ou características
- Preferências declaradas ("prefiro", "gosto mais", "é minha favorita")
- Comparações diretas entre marcas ou produtos
- Sentimentos declarados sobre marcas ou produtos
            
CARACTERÍSTICAS SENSORIAIS E ATRIBUTOS:
- Descrições de sabor, textura, aparência (ex: "cremosa", "leve", "refrescante")
- Características físicas (ex: "cor vermelha", "espuma cremosa")
- Efeitos percebidos (ex: "não causa dor de cabeça", "não precisa ir ao banheiro")
- Qualidade ou consistência do produto
            
CRITÉRIOS DE ESCOLHA:
- Fatores que influenciam a escolha (ex: "custo-benefício", "disponibilidade", "preço")
- Critérios de decisão explícitos
- Harmonização com comida ou petiscos
- Experiência do dia seguinte (ressaca, efeitos colaterais)
            
OCASIÕES DE CONSUMO:
- Quando consome (ex: "antes do almoço", "após treino", "sexta-feira")
- Onde consome (ex: "barzinho", "casa", "eventos")
- Com quem consome (ex: "com amigos", "em família", "sozinho")
- Rotinas e tradições de consumo (ex: "quinta-feira com amigos", "tradição há anos")
- Momentos específicos (ex: "happy hour", "após trabalho", "durante futebol")
            
COMUNICAÇÃO E MARKETING:
- Propagandas e campanhas mencionadas
- Patrocínios e eventos patrocinados
- Embaixadores ou personalidades associadas à marca
- Comunicação da marca ao longo do tempo
- Termos ou conceitos de marca (ex: "brameiro")
            
CONEXÃO CULTURAL:
- Associações com cultura brasileira (ex: futebol, samba, festas populares)
- Eventos culturais e festivais
- Manifestações culturais regionais
- Representação do consumidor brasileiro
            
CONCORRENTES E TENDÊNCIAS:
- Marcas concorrentes mencionadas
- Comparações com outras marcas
- Tendências de mercado (ex: "está crescendo", "está caindo")
- Posicionamento competitivo
            
EMBALAGENS E FORMATOS:
- Preferências por tipo de embalagem (ex: "garrafa de vidro", "latinha", "litrão")
- Percepções sobre diferentes formatos
- Disponibilidade de formatos
            
MUDANÇAS E EVOLUÇÃO:
- Mudanças na relação com a marca ao longo do tempo
- Mudanças na frequência de consumo
- Evolução da percepção da marca
            
SUGESTÕES E RECOMENDAÇÕES:
- O que gostariam de ver na marca
- Inovações desejadas
- Melhorias sugeridas
- Oportunidades identificadas
            
MEMÓRIAS E EXPERIÊNCIAS:
- Memórias marcantes relacionadas à marca ou produto
- Primeiras experiências
- Momentos significativos
            
- NÃO ignore citações que contenham informações comportamentais, percepções sensoriais,
  ocasiões de consumo, critérios de escolha, ou qualquer insight relevante sobre
  marcas, produtos ou categoria, mesmo que não mencionem explicitamente uma marca.
- Extraia citações sobre TODOS os participantes da entrevista, não apenas alguns.

- Mínimo de 15 citações

Retorne APENAS um JSON válido, sem markdown, sem explicações adicionais.""",
        agent=agent,
        expected_output="JSON válido com estrutura: {'citacoes': [{'citacao': '...', 'pergunta': '...', 'dataEntrevista': 'YYYY-MM-DD', 'quota': {...}, 'marcaMencionada': [...], 'insight': '...'}]}"
    )
    
    try:
        result = agent.execute_task(task)
        
        result_text = str(result)
        
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
        
        insights = json.loads(result_text)
        
        if "citacoes" in insights:
            for citacao_item in insights["citacoes"]:
                if "dataEntrevista" not in citacao_item:
                    citacao_item["dataEntrevista"] = "Não informado"
                
                if "quota" not in citacao_item:
                    citacao_item["quota"] = {
                        "nome": "Não informado",
                        "idade": "Não informado",
                        "regiao": "Não informado",
                        "classeSocial": "Não informado"
                    }
                
                if "marcaMencionada" not in citacao_item:
                    citacao_item["marcaMencionada"] = []
                elif not isinstance(citacao_item["marcaMencionada"], list):
                    citacao_item["marcaMencionada"] = []
                
                if "pergunta" not in citacao_item:
                    citacao_item["pergunta"] = "Não identificada"
        
        return insights
        
    except Exception as e:
        return {
            "error": str(e),
            "citacoes": [],
        }

def _format_insights_for_asimov(
    insights: dict[str, Any], 
    file_uuid: str,
    json_data: dict[str, Any],
) -> list[dict[str, str]]:
    """Formata insights baseados em citações para upload no Asimov."""
    snippets = []
    citacoes = insights.get("citacoes", [])

    data_extracao = datetime.now().strftime("%Y-%m-%d")
    
    total_chunks = 1 + len(citacoes)
    
    # CHUNK 1: METADADOS
    metadata_chunk = {
        "uuid": file_uuid,
        "file_name": json_data.get("file_name", ""),
        "total_citacoes": len(citacoes),
        "data_extracao": data_extracao
    }
    
    snippets.append({
        "key": f"{file_uuid}#chunk_01of{total_chunks:02d}",
        "content": json.dumps(metadata_chunk, ensure_ascii=False, indent=2)
    })
    
    # CHUNKS 2+: CITAÇÕES
    for idx, item in enumerate(citacoes, 1):
        
        snippets.append({
            "key": f"{file_uuid}#chunk_{idx + 1:02d}of{total_chunks:02d}",
            "content": json.dumps({
                "citacao": item.get("citacao", ""),
                "pergunta": item.get("pergunta", "Não identificada"),
                "quota": item.get("quota", {}),
                "marcaMencionada": item.get("marcaMencionada", []),
                "dataEntrevista": item.get("dataEntrevista"),
                "key": file_uuid,
                "insight": item.get("insight", "")
            }, ensure_ascii=False, indent=2)
        })
    
    return snippets


class ExtractInsightsArgs(BaseModel):
    ingestor_output_dir: str = Field(..., description="Diretório contendo JSONs gerados pelo ingestor.")
    extractor_output_dir: str = Field(..., description="Diretório para salvar JSONs com insights extraídos.")


class ExtractInsightsTool(BaseTool):
    name: str = "extract_insights_tool"
    description: str = (
        "Processa entrevistas do Consumer Hours para extrair pontos importantes baseados em citações. "
        "Lê JSONs do diretório do ingestor, analisa o texto usando LLM para identificar citações importantes "
        "com perguntas, insights, marcas mencionadas e informações demográficas, "
        "e salva JSONs enriquecidos. Depois, envia os insights para o Asimov em chunks estruturados."
    )
    args_schema: Type[BaseModel] = ExtractInsightsArgs
    
    def _run(
        self,
        ingestor_output_dir: str,
        extractor_output_dir: str,
    ) -> dict[str, Any]:
        ingestor_path = Path(ingestor_output_dir)
        extractor_path = Path(extractor_output_dir)
        
        if not ingestor_path.exists():
            return {"ok": False, "reason": f"ingestor_output_dir_not_found:{ingestor_path}"}
        
        extractor_path.mkdir(parents=True, exist_ok=True)
        
        warnings: list[str] = []
        outputs: list[str] = []
        processed_count = 0
        
        json_files = sorted([p for p in ingestor_path.rglob("*.json") if p.is_file()])
        asimov = AsimovClient.from_env()
        dataset_name = asimov.dataset or (os.getenv("ASIMOV_DATASET") or "").strip() or None
        
        # EXTRAIR INSIGHTS
        for json_file in json_files:
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                text = data.get("text", "")
                file_name = data.get("file_name", "")
                
                if not text:
                    warnings.append(f"empty_text:{json_file.name}")
                    continue
                
                # Verificar se já foi processado
                output_file = extractor_path / json_file.name
                if output_file.exists():
                    try:
                        existing_data = json.loads(output_file.read_text(encoding="utf-8"))
                        if "extracted_insights" in existing_data:
                            outputs.append(str(output_file))
                            processed_count += 1
                            continue
                    except:
                        pass
                
                insights = extract_interview_insights(text, file_name)
                
                if "error" in insights:
                    warnings.append(f"llm_error:{json_file.name}:{insights['error']}")
                    continue
                
                new_data = {
                    "uuid": data.get("uuid"),
                    "file_name": data.get("file_name"),
                    "extracted_insights": insights
                }

                # Salvar JSON
                output_file.write_text(
                    json.dumps(new_data, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                outputs.append(str(output_file))
                processed_count += 1
                
            except Exception as e:
                warnings.append(f"failed:{json_file.name}:{e}")
        
        # ENVIAR PARA ASIMOV
        asimov_upload_stats = {
            "total_attempted": 0,
            "total_uploaded": 0,
            "files_with_upload": 0,
            "files_with_errors": 0,
        }
        
        if asimov.enabled and asimov.is_configured() and dataset_name:
            try:
                if not asimov.ensure_dataset().get("ok"):
                    warnings.append("asimov_ensure_dataset_failed")
                else:
                    extractor_json_files = sorted([p for p in extractor_path.rglob("*.json") if p.is_file()])
                    
                    for json_file in extractor_json_files:
                        try:
                            data = json.loads(json_file.read_text(encoding="utf-8"))
                            
                            # Verificar se já tem upload
                            if "asimov_insights_upload" in data:
                                upload_info = data.get("asimov_insights_upload", {})
                                if upload_info.get("status") == "ok":
                                    continue
                            
                            insights = data.get("extracted_insights", {})
                            if not insights or "citacoes" not in insights:
                                continue
                            
                            # Formatar insights em snippets
                            insight_snippets = _format_insights_for_asimov(
                                insights, 
                                file_uuid=data.get("uuid"),
                                json_data=data
                            )
                            
                            if insight_snippets:
                                uploaded_total = 0
                                upload_errors = []
                                
                                for batch_start in range(0, len(insight_snippets), MAX_ITEMS_PER_BATCH):
                                    batch = insight_snippets[batch_start:batch_start + MAX_ITEMS_PER_BATCH]
                                    result = asimov.upload_snippets(batch, dataset=dataset_name)
                                    
                                    if result.get("ok"):
                                        uploaded_total += result.get("sent_items", len(batch))
                                    else:
                                        upload_errors.append({
                                            "batch": (batch_start // MAX_ITEMS_PER_BATCH) + 1,
                                            "error": result.get("reason") or result.get("error")
                                        })
                                
                                asimov_upload = {
                                    "attempted": len(insight_snippets),
                                    "uploaded": uploaded_total,
                                    "errors": upload_errors,
                                }
                                
                                if len(upload_errors) == 0:
                                    asimov_upload["status"] = "ok"
                                    asimov_upload_stats["files_with_upload"] += 1
                                elif uploaded_total > 0:
                                    asimov_upload["status"] = "partial"
                                    asimov_upload_stats["files_with_upload"] += 1
                                else:
                                    asimov_upload["status"] = "error"
                                    asimov_upload_stats["files_with_errors"] += 1
                                
                                asimov_upload_stats["total_attempted"] += len(insight_snippets)
                                asimov_upload_stats["total_uploaded"] += uploaded_total
                                
                                # Atualizar JSON
                                data["asimov_insights_upload"] = asimov_upload
                                json_file.write_text(
                                    json.dumps(data, ensure_ascii=False, indent=2),
                                    encoding="utf-8"
                                )
                                
                        except Exception as e:
                            warnings.append(f"asimov_upload_error:{json_file.name}:{e}")
                            asimov_upload_stats["files_with_errors"] += 1
                            
            except Exception as e:
                warnings.append(f"asimov_setup_error:{e}")
        
        return {
            "ok": True,
            "ingestor_output_dir": str(ingestor_path),
            "extractor_output_dir": str(extractor_path),
            "input_files": len(json_files),
            "processed_files": processed_count,
            "output_files": len(outputs),
            "outputs": outputs,
            "warnings": warnings,
            "asimov_insights_upload_stats": asimov_upload_stats,
        }


extract_insights_tool = ExtractInsightsTool()

