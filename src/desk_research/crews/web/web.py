import datetime
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from desk_research.constants import VERBOSE_AGENTS, VERBOSE_CREW
from desk_research.tools.research_tools import google_search_tool, web_scraper_tool, url_validator_tool
from desk_research.utils.console_time import Console
from desk_research.utils.extract_urls_from_markdown import extract_urls_from_markdown
from desk_research.utils.reporting import export_report

@CrewBase
class WebCrew:
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    @agent
    def web_researcher_url(self) -> Agent:
        return Agent(
            config=self.agents_config['web_researcher_url'],
            tools=[
                google_search_tool,
                url_validator_tool
            ],
            verbose=VERBOSE_AGENTS
        )

    @agent
    def web_report_writer(self) -> Agent:
        return Agent(
            config=self.agents_config['web_report_writer'],
            verbose=True,
            reasoning=True,
            max_reasoning_attempts=3 
        )

    @task
    def search_web_urls(self) -> Task:
        return Task(
            config=self.tasks_config['search_web_urls'],
            agent=self.web_researcher_url()
        )

    @task
    def evidence_consolidation_task(self) -> Task:
        return Task(
            config=self.tasks_config['evidence_consolidation_task'],
            agent=self.web_report_writer(),
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=VERBOSE_CREW
        )


def _extract_content_from_urls(urls: list[str], max_chars: int = 3000) -> str:
    """Extrai conteúdo de cada URL e retorna em formato markdown"""
    extracted_contents = []
    
    for url in urls:
        print(f"Extraindo conteúdo de {url}")
        try:
            # Usar web_scraper_tool diretamente
            result = web_scraper_tool.run(url)
            
            # Extrair apenas o conteúdo (remover prefixo "CONTEÚDO EXTRAÍDO (url):\n\n")
            if "CONTEÚDO EXTRAÍDO" in result:
                content = result.split("CONTEÚDO EXTRAÍDO", 1)[1]
                if ":\n\n" in content:
                    content = content.split(":\n\n", 1)[1]
            else:
                content = result
            
            # Limitar a 3000 caracteres
            if len(content) > max_chars:
                content = content[:max_chars] + "\n[TRUNCADO]"
            
            # Formatar como markdown
            extracted_contents.append(
                f"### {url}\n- **URL**: {url}\n- **Conteúdo extraído**:\n{content}\n"
            )
        except Exception as e:
            print(f"⚠️ Erro ao extrair conteúdo de {url}: {e}")
            continue

    return "\n".join(extracted_contents)

def run_web_research(query: str, max_results: int = 10):
    Console.time("RUN_WEB_RESEARCH")
    try:    
        inputs = {
            'query': query,
            'max_results': max_results,
            'max_results_extractions': max_results + 5,
            'current_date': datetime.datetime.now().strftime('%d/%m/%Y')
        }
        
        crew_instance = WebCrew()
        search_task = crew_instance.search_web_urls()
        
        search_crew = Crew(
            agents=[crew_instance.web_researcher_url()],
            tasks=[search_task],
            process=Process.sequential,
            verbose=VERBOSE_CREW
        )
        
        search_result = search_crew.kickoff(inputs=inputs)
        
        search_output = str(search_result)
        if hasattr(search_result, 'raw'):
            search_output = search_result.raw
        elif hasattr(search_result, 'tasks_output') and search_result.tasks_output:
            search_output = search_result.tasks_output[0].raw
        
        urls = extract_urls_from_markdown(search_output)
        
        if not urls:
            print("⚠️ Nenhuma URL encontrada no resultado da busca")
            return None
        
        print(f"📋 Encontradas {len(urls)} URLs. Extraindo conteúdo...")
        
        extracted_content = _extract_content_from_urls(urls, max_chars=3000)
        
        consolidation_task = crew_instance.evidence_consolidation_task()
        
        from crewai import Task
        modified_consolidation_task = Task(
            description=f"{consolidation_task.description}\n\n=== CONTEÚDO EXTRAÍDO DAS URLs ===\n\n{extracted_content}",
            agent=consolidation_task.agent,
            expected_output=consolidation_task.expected_output
        )
        
        consolidation_crew = Crew(
            agents=[crew_instance.web_report_writer()],
            tasks=[modified_consolidation_task],
            process=Process.sequential,
            verbose=VERBOSE_CREW
        )
        
        final_result = consolidation_crew.kickoff(inputs=inputs)
        
        make_log({
            "logName": "web_research",
            "content": {
                "result": final_result,
                "query": query,
                "max_results": max_results,
                "urls_found": len(urls),
                "current_date": datetime.datetime.now().strftime('%d/%m/%Y')
            }
        })
        
        export_report(final_result, query, prefix="web_report", crew_name="web")
        
        Console.time_end("RUN_WEB_RESEARCH")
        return final_result
    except Exception as e:
        print(f"Error running web research: {e}")
        return None