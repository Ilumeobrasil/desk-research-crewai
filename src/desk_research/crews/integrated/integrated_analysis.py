import json
import sys
import logging

from typing import Callable, Dict, Any, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from desk_research.utils.makelog.makeLog import make_log
from pydantic import BaseModel, Field
from crewai import Agent, Task, Crew, Process
from crewai.project import CrewBase, agent, task, crew

from desk_research.constants import VERBOSE_AGENTS, VERBOSE_CREW
from desk_research.crews.consumer_hours.consumer_hours import run_consumer_hours_analysis
from desk_research.crews.genie.genie import run_genie_analysis
from desk_research.crews.youtube.youtube import run_youtube_analysis
from desk_research.crews.academic.academic import run_academic_research
from desk_research.crews.web.web import run_web_research
from desk_research.crews.x.twitter_x_crew import run_twitter_social_listening
from desk_research.utils.reporting import export_report

logger = logging.getLogger(__name__)

MODOS = {
    'genie': {
        'runner': run_genie_analysis,
        'args': ['topic'],
    },
    'academic': {
        'runner': run_academic_research,
        'args': ['topic', 'max_papers'],
    },
    'youtube': {
        'runner': run_youtube_analysis,
        'args': ['topic'],
    },
    'web': {
        'runner': run_web_research,
        'args': ['topic', 'max_web_results'],
    },
    'x': {
        'runner': run_twitter_social_listening,
        'args': ['topic'],
    },
    'consumer_hours': {
        'runner': run_consumer_hours_analysis,
        'args': ['topic'],
    },
}

class QualityReview(BaseModel):
    score: int = Field(default=0, description="Nota de 0 a 100 para a qualidade do relatório.")
    feedback: str = Field(default="Sem feedback fornecido.", description="Críticas construtivas e pontos específicos de melhoria.")
    approved: bool = Field(default=False, description="Se a nota for >= 80, aprovado. Caso contrário, reprovado.")
    
    class Config:
        # Garantir que o modelo seja totalmente resolvido
        frozen = False

@CrewBase
class IntegratedCrew:

    agents: List[Agent]
    tasks: List[Task]

    @agent
    def chief_editor_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['chief_editor_agent'],
            verbose=True,
            allow_delegation=False
        )

    @agent
    def evaluator_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['evaluator_agent'],
            verbose=True,
            allow_delegation=False
        )

    @task
    def synthesis_task(self) -> Task:
        return Task(
            config=self.tasks_config['synthesis_task'],
            agent=self.chief_editor_agent()
        )

    @task
    def evaluation_task(self) -> Task:
        return Task(
            config=self.tasks_config['evaluation_task'],
            agent=self.evaluator_agent(),
            output_pydantic=QualityReview
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.chief_editor_agent()],
            tasks=[self.synthesis_task()],
            process=Process.sequential,
            verbose=VERBOSE_CREW
        )

def _run_crew(params: Dict[str, Any], func: Callable, *args) -> tuple[str, str]:
    try:
        res = func(*args)
        return params.get('crew_name'), f"=== RELATÓRIO {params.get('crew_name').upper()} ===\n{res}\n======================\n"
    except Exception as e:
        sys.stderr.write(f"❌ Erro no {params.get('crew_name').upper()}: {e}\n")
        return params.get('crew_name'), f"=== ERRO {params.get('crew_name').upper()} ===\n{e}\n"

def run_integrated_research(topic: str, selected_modos: List[str], params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        sys.stderr.write(f"\n🚀 INICIANDO PESQUISA INTEGRADA: {topic}\n")
        sys.stderr.write(f"📋 Modos selecionados: {selected_modos}\n")

        results_buffer = []
        tasks = []
        
        arg_values = {
            'topic': topic,
            'max_papers': params.get('max_papers', 5),
            'max_web_results': params.get('max_web_results', 10),
        }
        
        for modo in selected_modos:
            if modo in MODOS:
                config = MODOS[modo]
                mapped_args = [arg_values.get(arg, arg) for arg in config['args']]
                tasks.append(
                    (modo, _run_crew, params, config['runner'], *mapped_args)
                )
        
        if tasks:
            sys.stderr.write(f"\n⚡ Executando {len(tasks)} crews em paralelo...\n")
            with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
                future_to_mode = {
                    executor.submit(func, *args): mode 
                    for mode, func, args in tasks
                }
                
                results_dict = {}
                for future in as_completed(future_to_mode):
                    mode = future_to_mode[future]
                    try:
                        mode_name, result = future.result()
                        results_dict[mode_name] = result
                    except Exception as e:
                        sys.stderr.write(f"❌ Erro inesperado no modo {mode}: {e}\n")
                        results_dict[mode] = f"=== ERRO {mode.upper()} ===\n{str(e)}\n"
                
                for mode in selected_modos:
                    if mode in results_dict:
                        results_buffer.append(results_dict[mode])
            
            sys.stderr.write("✅ Execução paralela concluída.\n")

        sys.stderr.write("\n✍️ INICIANDO SÍNTESE FINAL (EDITOR-CHEFE)...\n")
        
        all_reports_text = "\n".join(results_buffer)
        
        if not all_reports_text.strip():
            return {"error": "Nenhum relatório foi gerado pelos crews selecionados."}

        inputs = {
            'topic': topic,
            'reports_context': all_reports_text,
            'date': datetime.now().strftime('%d/%m/%Y'),
            'instruction': ""
        }
        make_log({
            "logName": "integrated_analysis",
            "content": {
                'topic': topic,
                'reports_context': all_reports_text,
                'date': datetime.now().strftime('%d/%m/%Y'),
                'instruction': ""
            }
        })

        crew_instance = IntegratedCrew()
        master_result = crew_instance.crew().kickoff(inputs=inputs)
                
        master_text = ""
        if hasattr(master_result, 'raw'):
            master_text = master_result.raw
        elif hasattr(master_result, 'tasks_output') and master_result.tasks_output:
            master_text = master_result.tasks_output[-1].raw
        else:
            master_text = str(master_result)
        
        anexos_text = ""
        for res in results_buffer:
            clean_res = res.replace("======================", "---")
            anexos_text += f"\n{clean_res}\n"

        export_report(master_text, topic, prefix="integrated_master", crew_name="integrated_analysis")
        
        return {
            "topic": topic,
            "master_report": master_result,
            "individual_results": results_buffer
        }
    except Exception as e:
        logger.error(f"Erro ao executar social listening: {e}", exc_info=True)
        raise
