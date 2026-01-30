import datetime
import os
from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from dotenv import load_dotenv
from desk_research.constants import VERBOSE_AGENTS, VERBOSE_CREW
from desk_research.tools.research_tools import google_search_tool, web_scraper_tool, url_validator_tool
from desk_research.utils.console_time import Console
from desk_research.utils.extract_urls_from_markdown import extract_urls_from_markdown
from desk_research.utils.reporting import export_report

load_dotenv()

@CrewBase
class WebCrew:
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    llm_web_researcher = LLM(
        model=os.getenv("MODEL"),
        temperature = 0.0,
        top_p = 1.0,
        base_url=os.getenv("OPENAI_API_BASE"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    llm_web_report = LLM(
        model=os.getenv("MODEL"),
        temperature=0.4,
        top_p = 1.0,
        base_url=os.getenv("OPENAI_API_BASE"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    @agent
    def web_researcher_url(self) -> Agent:
        return Agent(
            config=self.agents_config['web_researcher_url'],
            tools=[
                google_search_tool,
                url_validator_tool
            ],
            verbose=VERBOSE_AGENTS,
            llm=self.llm_web_researcher,
        )

    @agent
    def web_report_writer(self) -> Agent:
        return Agent(
            config=self.agents_config['web_report_writer'],
            verbose=VERBOSE_AGENTS,
            reasoning=True,
            max_reasoning_attempts=3,
            llm=self.llm_web_report,
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
            context=[
                self.search_web_urls()
            ]
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=VERBOSE_CREW
        )


def _extract_content_from_urls(urls: list[str], max_chars: int = 4000) -> str:
    """Extrai conteúdo de cada URL e retorna em formato markdown"""
    extracted_contents = []
    
    for url in urls:
        try:
            result = web_scraper_tool.run(url)
            
            if "CONTEÚDO EXTRAÍDO" in result:
                content = result.split("CONTEÚDO EXTRAÍDO", 1)[1]
                if ":\n\n" in content:
                    content = content.split(":\n\n", 1)[1]
            else:
                content = result
            
            if len(content) > max_chars:
                content = content[:max_chars] + "\n[TRUNCADO]"
            
            publication_date = None
            try:
                import trafilatura
                downloaded = trafilatura.fetch_url(url)
                if downloaded:
                    metadata = trafilatura.extract_metadata(downloaded)
                    if metadata and metadata.date:
                        publication_date = metadata.date
            except Exception as e:
                pass
            
            date_str = ""
            if publication_date:
                try:
                    if isinstance(publication_date, str):
                        date_str = publication_date
                    else:
                        date_str = publication_date.strftime('%d/%m/%Y')
                except:
                    date_str = str(publication_date)
            
            date_section = f"- **Data de publicação**: {date_str}\n" if date_str else ""
            
            extracted_contents.append(
                f"### {url}\n- **URL**: {url}\n{date_section}- **Conteúdo extraído**:\n{content}\n"
            )
        except Exception as e:
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
            return None
        
        extracted_content = _extract_content_from_urls(urls, max_chars=3500)
    
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
        
        export_report(final_result, query, prefix="web_report", crew_name="web")
        
        Console.time_end("RUN_WEB_RESEARCH")
        return final_result
    except Exception as e:
        import traceback
        return None