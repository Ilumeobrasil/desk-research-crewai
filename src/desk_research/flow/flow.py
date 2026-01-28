from datetime import datetime
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from crewai import Crew
from crewai.flow.flow import Flow, start, listen, or_, router

from desk_research.flow.state import DeskResearchState
from desk_research.flow.crew_executors import (
    AcademicCrewExecutor,
    WebCrewExecutor,
    XCrewExecutor,
    GenieCrewExecutor,
    YouTubeCrewExecutor,
    ConsumerHoursCrewExecutor
)
from desk_research.crews.integrated.integrated_analysis import IntegratedCrew
from desk_research.utils.console_time import Console
from desk_research.utils.reporting import export_report
from desk_research.utils.logging_utils import safe_print
from desk_research.constants import DEFAULT_MAX_PAPERS, DEFAULT_MAX_WEB_RESULTS, MIN_APPROVAL_SCORE, MAX_RETRY_COUNT, DEFAULT_TOPIC, VERBOSE_CREW, IS_ACTIVE_ANALYSIS_INTEGRATED


class DeskResearchFlow(Flow[DeskResearchState]):

    @start()
    def initialize_research(self):
        safe_print("🚀 INICIANDO DESK RESEARCH FLOW...")
        
        if hasattr(self, 'inputs') and self.inputs:
            self.state.topic = self.inputs.get('topic', self.state.topic)
            self.state.selected_crews = self.inputs.get('selected_crews', self.state.selected_crews)
            self.state.params = self.inputs.get('params', self.state.params)

        if not self.state.topic:
            self.state.topic = DEFAULT_TOPIC

        self.state.results = {}
        self._synthesis_executed = False
        return "initialized"

    @listen(initialize_research)
    def run_all_crews_parallel(self):
        """Executa todos os crews selecionados em paralelo"""
        
        tasks = []
        
        if "academic" in self.state.selected_crews:
            tasks.append(("academic", self._run_academic_parallel))
        
        if "web" in self.state.selected_crews:
            tasks.append(("web", self._run_web_parallel))
        
        if "x" in self.state.selected_crews:
            tasks.append(("x", self._run_x_parallel))
        
        if "genie" in self.state.selected_crews:
            tasks.append(("genie", self._run_genie_parallel))
        
        if "youtube" in self.state.selected_crews:
            tasks.append(("youtube", self._run_youtube_parallel))
        
        if "consumer_hours" in self.state.selected_crews:
            tasks.append(("consumer_hours", self._run_consumer_hours_parallel))
        
        if not tasks:
            return "no_crews"
        
        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            future_to_crew = {
                executor.submit(func): crew_name 
                for crew_name, func in tasks
            }
            
            for future in as_completed(future_to_crew):
                crew_name = future_to_crew[future]
                try:
                    result = future.result()
                    self.state.results[crew_name] = result
                except Exception as e:
                    import traceback
                    self.state.results[crew_name] = f"Erro: {str(e)}"
        
        return "all_completed"
    
    def _run_academic_parallel(self):
        """Executa o crew acadêmico"""
        result = AcademicCrewExecutor.run(
            topic=self.state.topic,
            max_papers=self.state.params.get('max_papers', DEFAULT_MAX_PAPERS)
        )
        return result
    
    def _run_web_parallel(self):
        """Executa o crew web"""
        result = WebCrewExecutor.run(
            topic=self.state.topic,
            max_results=self.state.params.get('max_web_results', DEFAULT_MAX_WEB_RESULTS)
        )
        return result
    
    def _run_x_parallel(self):
        """Executa o crew X (Twitter)"""
        return XCrewExecutor.run(topic=self.state.topic)
    
    def _run_genie_parallel(self):
        """Executa o crew Genie"""
        return GenieCrewExecutor.run(topic=self.state.topic)
    
    def _run_youtube_parallel(self):
        """Executa o crew YouTube"""
        return YouTubeCrewExecutor.run(topic=self.state.topic)
    
    def _run_consumer_hours_parallel(self):
        """Executa o crew Consumer Hours"""
        return ConsumerHoursCrewExecutor.run(topic=self.state.topic)

    @listen(or_(run_all_crews_parallel))
    def synthesize_report(self):
        if not self.state.results:
            return "no_reports"
        
        if hasattr(self, '_synthesis_executed') and self._synthesis_executed:
            return "already_executed"
        
        Console.time("SYNTHESIS_REPORT")
        all_reports_text = self._build_reports_text()
        
        if not all_reports_text.strip():
            return "no_reports"

        self._synthesis_executed = True
        
        master_result = self._run_synthesis_crew(all_reports_text)
        self.state.final_report = str(master_result)
        
        Console.time_end("SYNTHESIS_REPORT")
        return "direct_export"

    def _build_reports_text(self) -> str:
        results_buffer = []
        for crew_id, res in self.state.results.items():
            content = self._extract_content(res)
            results_buffer.append(
                f"=== RELATÓRIO {crew_id.upper()} ===\n{content}\n======================\n"
            )
        return "\n".join(results_buffer)

    @router(synthesize_report)
    def route_after_synthesis(self):
        return "direct_export"

    @listen("direct_export")
    def export_directly(self):
        """Exporta o relatório"""
        return self._export_final()
        
    @staticmethod
    def _extract_content(result: Any) -> str:
        if isinstance(result, dict):
            return result.get('report_markdown') or result.get('result') or str(result)
        
        # Tratar objetos CrewAI
        if hasattr(result, 'raw'):
            return result.raw
        if hasattr(result, 'tasks_output') and result.tasks_output:
            return result.tasks_output[-1].raw if hasattr(result.tasks_output[-1], 'raw') else str(result.tasks_output[-1])
        
        return str(result)

    def _run_synthesis_crew(self, reports_text: str) -> Any:
        integ_crew = IntegratedCrew()
        task = integ_crew.synthesis_task()
        crew_runner = Crew(
            agents=[integ_crew.chief_editor_agent()],
            tasks=[task],
            verbose=VERBOSE_CREW
        )
        
        inputs = {
            'topic': self.state.topic,
            'reports_context': reports_text,
            'feedback': self.state.feedback,
            'instruction': self.state.feedback if self.state.feedback else "",
            'date': datetime.now().strftime('%d/%m/%Y')
        }

        return crew_runner.kickoff(inputs=inputs)

    @staticmethod
    def _extract_review_data(review: Any) -> tuple[int, str]:
        return 100, "Approved (Fallback)"


    def _export_final(self):
        try:
            master_report = self.state.final_report
            if not master_report:
                return ""

            export_report(master_report, self.state.topic, prefix="integrated_master", crew_name="integrated_analysis")
            safe_print("\n✅ FLOW FINALIZADO COM SUCESSO! (Relatório Exportado)")
            return master_report

        except Exception as e:
            safe_print(f"❌ ERRO CRÍTICO AO MONTAR RELATÓRIO: {e}")
            return self.state.final_report

