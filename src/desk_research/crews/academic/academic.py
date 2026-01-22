import logging
from desk_research.constants import VERBOSE_AGENTS, VERBOSE_CREW
from desk_research.tools.pdf_analyzer import pdf_analyzer_tool
from desk_research.utils.reporting import export_report
from dotenv import load_dotenv
from datetime import datetime
import json
import httpx
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from desk_research.tools.research_tools import (
    serper_scholar_tool,
    scielo_tool,
    openalex_search_tool,
)
from desk_research.models.academic_models import AcademicReport, validar_relatorio

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# HTTPX Patch for 401 handling
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

    def academic_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['academic_researcher'],
            tools=[
                serper_scholar_tool,
                openalex_search_tool,
                #scielo_tool,
                #pdf_analyzer_tool
            ],
            verbose=True
        )
    
    @agent
    def literature_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config['literature_analyst'],
            tools=[pdf_analyzer_tool],
            verbose=False
        )
    
    @agent
    def academic_synthesizer(self) -> Agent:
        return Agent(
            config=self.agents_config['academic_synthesizer'],
            tools=[],
            verbose=VERBOSE_AGENTS
        )
    
    @task
    def search_papers_task(self) -> Task:
        return Task(
            config=self.tasks_config['search_papers_task'],
            agent=self.academic_researcher()
        )
    
    @task
    def analyze_literature_task(self) -> Task:
        return Task(
            config=self.tasks_config['analyze_literature_task'],
            agent=self.literature_analyst(),
            context=[self.search_papers_task()]
        )
    
    @task
    def synthesize_report_task(self) -> Task:
        return Task(
            config=self.tasks_config['synthesize_report_task'],
            agent=self.academic_synthesizer(),
            context=[
                self.search_papers_task(),
                self.analyze_literature_task()
            ],
            output_pydantic=AcademicReport
        )
    
    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=VERBOSE_CREW
        )
    
    def run(self, topic: str, max_papers: int = 3) -> dict:
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

def run_academic_research(topic: str, max_papers: int = 10) -> dict:
    try:
        crew = AcademicResearchCrew()
        return crew.run(topic=topic, max_papers=max_papers)
    except Exception as e:
        print(f"Error running academic research: {e}")
        return None

""" def run_academic_research(topic: str, max_papers: int = 10) -> dict:
    try:
        inputs = {
            'topic': topic,
            'max_papers': max_papers
        }

        crew = AcademicResearchCrew()
        result = crew.crew().kickoff(inputs=inputs)
        
        export_report(result, topic, prefix="academic_report", crew_name="academic")

        return result
    except Exception as e:
        print(f"Error running academic research: {e}")
        return None
 """
AcademicCrew = AcademicResearchCrew

