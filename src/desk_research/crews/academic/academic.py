import logging
import re
from desk_research.constants import DEFAULT_MAX_PAPERS, VERBOSE_AGENTS, VERBOSE_CREW
from desk_research.tools.pdf_analyzer import pdf_analyzer_tool
from desk_research.utils.console_time import Console
from dotenv import load_dotenv
from datetime import datetime
import json
import httpx
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from desk_research.tools.research_tools import (
    semantic_scholar_tool,
    serper_scholar_tool,
    openalex_search_tool,
)
from desk_research.models.academic_models import AcademicReport

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

_original_send = httpx.Client.send

def patched_send(self, request, *args, **kwargs):
    if request.method == 'POST' and 'chat/completions' in str(request.url):
        try:
            body = request.content.decode('utf-8')
            payload = json.loads(body)
            
            if 'model' in payload and isinstance(payload['model'], str):
                if not payload['model'].startswith('openai/'):
                    original_model = payload['model']
                    payload['model'] = f'openai/{original_model}'
                    logger.info(f"Model patched: {original_model} -> {payload['model']}")
                    
                    new_body = json.dumps(payload).encode('utf-8')
                    request._content = new_body
                    request.headers['content-length'] = str(len(new_body))
        except Exception as e:
            logger.warning(f"Error patching request: {e}")
    
    return _original_send(self, request, *args, **kwargs)

httpx.Client.send = patched_send

@CrewBase
class AcademicResearchCrew:
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    @agent
    def academic_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['academic_researcher'],
            tools=[
                serper_scholar_tool,
                openalex_search_tool,
                semantic_scholar_tool
            ],
            verbose=VERBOSE_AGENTS,
        )
    
    @agent
    def academic_synthesizer(self) -> Agent:
        return Agent(
            config=self.agents_config['academic_synthesizer'],
            tools=[],
            verbose=VERBOSE_AGENTS,
            reasoning=True,
            max_reasoning_attempts=3 
        )
    
    @task
    def search_papers_task(self) -> Task:
        return Task(
            config=self.tasks_config['search_papers_task'],
            agent=self.academic_researcher()
        )
    
    @task
    def synthesize_report_task(self) -> Task:
        return Task(
            config=self.tasks_config['synthesize_report_task'],
            agent=self.academic_synthesizer(),
            context=[
                self.search_papers_task()
            ],
        )
    
    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=VERBOSE_CREW
        )
    
    def run(self, topic: str, max_papers: int = DEFAULT_MAX_PAPERS) -> dict:
        Console.time("ACADEMIC_RESEARCH")

        result = self.crew().kickoff(inputs={
            'topic': topic,
            'max_papers': max_papers
        })
        
        self._export_report(result, topic)
        
        md_content = ""
        if hasattr(result, 'pydantic') and result.pydantic:
             md_content = self._convert_pydantic_to_markdown(result.pydantic, original_topic=topic)
        else:
             md_content = str(result)

        Console.time_end("ACADEMIC_RESEARCH")
        return {
            'result': md_content,
            'original_output': result
        }
    
    def _convert_pydantic_to_markdown(self, report, original_topic: str = None) -> str:
        if not report:
            return ""
            
        titulo = original_topic if original_topic else (report.tema if report.tema and report.tema.strip() else "Relatório de Pesquisa Acadêmica")
        md = f"# {titulo}\n\n"
        
        md += f"**Data:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        md += f"**Papers Analisados:** {report.total_papers_analisados}/{report.total_papers_encontrados}\n\n"
        
        md += "## 1. Introdução\n"
        if report.introducao_geral:
            md += f"{report.introducao_geral}\n\n"
        else:
            md += "Esta pesquisa acadêmica visa analisar o estado da arte referente ao tema acima.\n\n"
        
        md += "## 2. Revisão Bibliográfica\n\n"
        for i, paper in enumerate(report.papers, 1):
            md += f"### {i}. {paper.titulo}\n"
            md += f"**Autores:** {', '.join(paper.autores)}\n"
            md += f"**Ano:** {paper.ano} | **Fonte:** {paper.fonte}\n\n"
            
            if paper.introducao_contexto:
                md += f"#### Introdução e Contexto\n{paper.introducao_contexto}\n\n"
                md += f"#### Fundamentação Teórica\n{paper.fundamentacao_teorica or 'N/A'}\n\n"
                md += f"#### Metodologia\n{paper.metodologia_detalhada or 'N/A'}\n\n"
                md += f"#### Resultados\n{paper.resultados_detalhados or 'N/A'}\n\n"
                md += f"#### Discussão\n{paper.discussao or 'N/A'}\n\n"
                md += f"#### Contribuições\n{paper.contribuicoes or 'N/A'}\n\n"
            else:
                md += f"**Resumo:** {paper.resumo}\n\n"
            
            md += "---\n\n"
            
        md += "## 3. Análise Comparativa Integrada\n"
        if report.analise_comparativa_completa:
             md += f"{report.analise_comparativa_completa}\n\n"
        else:
             md += "_Análise comparativa não gerada._\n\n"

        md += "## 4. Conclusão\n"
        for conc in report.conclusoes:
            md += f"- {conc}\n"
        md += "\n"
        
        if report.recomendacoes:
            md += "**Recomendações:**\n"
            for rec in report.recomendacoes:
                md += f"- {rec}\n"
            md += "\n"
        
        md += "## 5. Limitações\n"
        for limit in report.limitacoes:
            md += f"- **{limit.tipo}**: {limit.descricao} (Impacto: {limit.impacto})\n"
        md += "\n"

        md += "## 6. Referências Bibliográficas\n"
        refs_counter = 0
        for paper in report.papers:
            if paper.referencia_abnt:
                md += f"- {paper.referencia_abnt}\n"
                refs_counter += 1
            elif paper.url:
                autores = ', '.join(paper.autores) if paper.autores else "S.A."
                md += f"- {autores}. **{paper.titulo}**. Disponível em: <{paper.url}>. Acesso em: {report.data_pesquisa}.\n"
                refs_counter += 1
        
        if refs_counter == 0:
            md += "_Nenhuma referência formatada._\n"
            
        return md

    def _export_report(self, result, topic: str):
        try:
            from desk_research.utils.reporting import export_report as shared_export_report
            
            content = ""
            if hasattr(result, 'pydantic') and result.pydantic:
                content = self._convert_pydantic_to_markdown(result.pydantic, original_topic=topic)
            elif hasattr(result, 'raw'):
                content = result.raw
            else:
                try:
                    content = self._convert_pydantic_to_markdown(result, original_topic=topic)
                except:
                    content = str(result)

            shared_export_report(content, topic, prefix="academic_report", crew_name="academic")
            
        except Exception as e:
            logger.error(f"Error exporting report: {e}")
            import sys
            sys.stderr.write(f"Error exporting report: {e}\n")

def _extract_pdf_urls_from_output(output_text: str) -> list[str]:
    """Extrai URLs de PDF do output da task search_papers_task"""
    pdf_urls = []
    
    markdown_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    markdown_matches = re.findall(markdown_pattern, output_text)
    for _, url in markdown_matches:
        if url.startswith('http') and ('.pdf' in url.lower() or 'pdf' in url.lower()):
            pdf_urls.append(url)
    
    url_pattern = r'https?://[^\s\)]+\.pdf[^\s\)]*'
    direct_urls = re.findall(url_pattern, output_text)
    pdf_urls.extend(direct_urls)
    
    try:
        if '{' in output_text and 'papers' in output_text.lower():
            json_match = re.search(r'\{.*"papers".*\}', output_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                papers = data.get('papers', [])
                for paper in papers:
                    pdf_url = paper.get('pdf_url') or paper.get('url')
                    if pdf_url and pdf_url.startswith('http'):
                        pdf_urls.append(pdf_url)
    except:
        pass
    
    pdf_label_pattern = r'(?:URL do PDF|PDF|pdf_url|url)[:\s]+(https?://[^\s\n]+)'
    label_matches = re.findall(pdf_label_pattern, output_text, re.IGNORECASE)
    pdf_urls.extend(label_matches)
    
    seen = set()
    unique_urls = []
    for url in pdf_urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    
    return unique_urls

def _extract_content_from_pdfs(pdf_urls: list[str], max_chars: int = 3000) -> str:
    """Extrai conteúdo de cada PDF e retorna em formato estruturado"""
    extracted_contents = []

    for idx, pdf_url in enumerate(pdf_urls, 1):
        try:
            result = pdf_analyzer_tool.run(pdf_url)
            
            if "CONTEÚDO COMPLETO:" in result:
                parts = result.split("CONTEÚDO COMPLETO:")
                if len(parts) > 1:
                    content = parts[1].split("FIM DA ANÁLISE")[0].strip()
                else:
                    content = result
            else:
                content = result
            
            if len(content) > max_chars:
                content = content[:max_chars] + "\n[TRUNCADO]"
            
            extracted_contents.append(
                f"### Paper {idx}\n- **URL do PDF**: {pdf_url}\n- **Conteúdo extraído**:\n{content}\n"
            )
        except Exception as e:
            continue
    
    return "\n".join(extracted_contents)

def run_academic_research(topic: str, max_papers: int = 3) -> dict:
    Console.time("ACADEMIC_RESEARCH")
    
    crew_instance = AcademicResearchCrew()
    
    search_task = crew_instance.search_papers_task()
    search_crew = Crew(
        agents=[crew_instance.academic_researcher()],
        tasks=[search_task],
        process=Process.sequential,
        verbose=VERBOSE_CREW
    )
    
    search_result = search_crew.kickoff(inputs={
        'topic': topic,
        'max_papers': max_papers
    })
    
    search_output = str(search_result)
    if hasattr(search_result, 'raw'):
        search_output = search_result.raw
    elif hasattr(search_result, 'tasks_output') and search_result.tasks_output:
        search_output = search_result.tasks_output[0].raw
    
    pdf_urls = _extract_pdf_urls_from_output(search_output)
    
    if not pdf_urls:
        pdf_content = ""
    else:
        pdf_content = _extract_content_from_pdfs(pdf_urls, max_chars=4000)
        
    synthesize_task = crew_instance.synthesize_report_task()
    
    modified_synthesize_task = Task(
        description=f"{synthesize_task.description}\n\n=== CONTEÚDO EXTRAÍDO DOS PDFs ===\n\n{pdf_content}\n\n=== RESULTADO DA BUSCA DE PAPERS ===\n\n{search_output}",
        agent=synthesize_task.agent,
        expected_output=synthesize_task.expected_output
    )
    
    synthesize_crew = Crew(
        agents=[crew_instance.academic_synthesizer()],
        tasks=[modified_synthesize_task],
        process=Process.sequential,
        verbose=VERBOSE_CREW
    )
    
    result = synthesize_crew.kickoff(inputs={
        'topic': topic,
        'max_papers': max_papers
    })
    
    try:
        from desk_research.utils.reporting import export_report as shared_export_report
        
        content = ""
        if hasattr(result, 'pydantic') and result.pydantic:
            content = crew_instance._convert_pydantic_to_markdown(result.pydantic, original_topic=topic)
        elif hasattr(result, 'raw'):
            content = result.raw
        else:
            try:
                content = crew_instance._convert_pydantic_to_markdown(result, original_topic=topic)
            except:
                content = str(result)

        shared_export_report(content, topic, prefix="academic_report", crew_name="academic")
    except Exception as e:
        logger.error(f"Error exporting report: {e}")
    
    md_content = ""
    if hasattr(result, 'pydantic') and result.pydantic:
         md_content = crew_instance._convert_pydantic_to_markdown(result.pydantic, original_topic=topic)
    else:
         md_content = str(result)
    
    Console.time_end("ACADEMIC_RESEARCH")
    return {
        'result': md_content,
        'original_output': result
    }

AcademicCrew = AcademicResearchCrew

