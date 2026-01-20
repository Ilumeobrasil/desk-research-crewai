from datetime import datetime
from typing import Any

from crewai import Crew
from crewai.flow.flow import Flow, start, listen, and_, or_, router

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
from desk_research.utils.reporting import export_report
from desk_research.utils.logging_utils import safe_print
from desk_research.constants import MIN_APPROVAL_SCORE, MAX_RETRY_COUNT, DEFAULT_TOPIC, VERBOSE_CREW


class DeskResearchFlow(Flow[DeskResearchState]):

    @start()
    def initialize_research(self):
        safe_print("🚀 INICIANDO DESK RESEARCH FLOW...")
        
        if hasattr(self, 'inputs') and self.inputs:
            self.state.topic = self.inputs.get('topic', self.state.topic)
            self.state.selected_crews = self.inputs.get('selected_crews', self.state.selected_crews)
            self.state.params = self.inputs.get('params', self.state.params)

        safe_print(f"📌 Tópico no State: {self.state.topic}")

        if not self.state.topic:
            safe_print("⚠️  AVISO: Tópico vazio! Verifique os inputs.")
            self.state.topic = DEFAULT_TOPIC

        self.state.results = {}
        return "initialized"

    @listen(initialize_research)
    def run_academic(self):
        if "academic" in self.state.selected_crews:
            result = AcademicCrewExecutor.run(
                topic=self.state.topic,
                max_papers=self.state.params.get('max_papers', 5)
            )
            self.state.results["academic"] = result
        else:
            safe_print("⏭️ Skipping Academic")

    @listen(initialize_research)
    def run_web(self):
        if "web" in self.state.selected_crews:
            result = WebCrewExecutor.run(
                topic=self.state.topic,
                max_results=self.state.params.get('max_web_results', 5)
            )
            self.state.results["web"] = result
        else:
            safe_print("⏭️ Skipping Web")

    @listen(initialize_research)
    def run_x(self):
        if "x" in self.state.selected_crews:
            result = XCrewExecutor.run(topic=self.state.topic)
            self.state.results["x"] = result
        else:
            safe_print("⏭️ Skipping X")

    @listen(initialize_research)
    def run_genie(self):
        if "genie" in self.state.selected_crews:
            result = GenieCrewExecutor.run(topic=self.state.topic)
            self.state.results["genie"] = result
        else:
            safe_print("⏭️ Skipping Genie")
            
    @listen(initialize_research)
    def run_youtube(self):
        if "youtube" in self.state.selected_crews:
            result = YouTubeCrewExecutor.run(topic=self.state.topic)
            self.state.results["youtube"] = result
        else:
            safe_print("⏭️ Skipping YouTube")

    @listen(initialize_research)
    def run_consumer_hours(self):
        if "consumer_hours" in self.state.selected_crews:
            result = ConsumerHoursCrewExecutor.run()
            self.state.results["consumer_hours"] = result
        else:
            safe_print("⏭️ Skipping Consumer Hours")

    @listen(or_(and_(run_academic, run_web, run_x, run_genie, run_youtube, run_consumer_hours), "retry_synthesis"))
    def synthesize_report(self):
        safe_print(f"\n✍️ SÍNTESE FINAL (Tentativa {self.state.retry_count + 1})")
        
        all_reports_text = self._build_reports_text()
        
        if not all_reports_text.strip():
            safe_print("⚠️ Nenhum relatório gerado para síntese.")
            return

        master_result = self._run_synthesis_crew(all_reports_text)
        self.state.final_report = str(master_result)
        
        return "report_generated"

    def _build_reports_text(self) -> str:
        results_buffer = []
        for crew_id, res in self.state.results.items():
            content = self._extract_content(res)
            results_buffer.append(
                f"=== RELATÓRIO {crew_id.upper()} ===\n{content}\n======================\n"
            )
        return "\n".join(results_buffer)

    @staticmethod
    def _extract_content(result: Any) -> str:
        if isinstance(result, dict):
            return result.get('report_markdown') or result.get('result') or str(result)
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
            'instruction': self.state.feedback,
            'date': datetime.now().strftime('%d/%m/%Y')
        }

        return crew_runner.kickoff(inputs=inputs)

    @listen(synthesize_report)
    def evaluate_report(self):
        safe_print("\n⚖️ AVALIANDO QUALIDADE (Self-Refine)...")
        
        integ_crew = IntegratedCrew()
        task = integ_crew.evaluation_task()
        qa_crew = Crew(
            agents=[integ_crew.evaluator_agent()],
            tasks=[task],
            verbose=VERBOSE_CREW
        )
        
        reports_context = self._build_reports_text()
        
        inputs = {
            "report_content": self.state.final_report,
            "reports_context": reports_context
        }
        qa_result = qa_crew.kickoff(inputs=inputs)
        
        review = qa_result.pydantic or qa_result
        score, feedback = self._extract_review_data(review)

        safe_print(f"📊 Nota: {score}/100")
        safe_print(f"📝 Feedback: {feedback}")
        
        if score >= MIN_APPROVAL_SCORE:
            safe_print("✅ Relatório APROVADO!")
            self.state.feedback = ""
            return "approved"
        else:
            safe_print("❌ Relatório REPROVADO. Solicitando melhorias...")
            self.state.feedback = feedback
            self.state.retry_count += 1
            return "rejected"

    @staticmethod
    def _extract_review_data(review: Any) -> tuple[int, str]:
        if hasattr(review, 'score'):
            return review.score, review.feedback
        return 100, "Approved (Fallback)"

    @router(evaluate_report)
    def flow_control(self):
        if self.state.retry_count > MAX_RETRY_COUNT:
            safe_print("⚠️ Limite de retries atingido.")
            return "max_retries"
        
        if self.state.feedback:
            return "retry_synthesis"
        
        return "approved"

    @listen("approved")
    def finalize_approved(self):
        self._export_final()

    @listen("max_retries")
    def finalize_forced(self):
        safe_print("⚠️ Finalizando com versão 'Best Effort'.")
        self._export_final()

    @listen("rejected")
    def retry_synthesis(self):
        pass

    def _export_final(self):
        safe_print("\n📚 MONTANDO RELATÓRIO COMPLETO...")
        
        try:
            master_report = self.state.final_report
            if not master_report:
                safe_print("⚠️  AVISO: Relatório vazio. Nada a exportar.")
                return ""

            export_report(master_report, self.state.topic, prefix="integrated_master", crew_name="integrated_analysis")
            safe_print("\n✅ FLOW FINALIZADO COM SUCESSO! (Relatório Exportado)")
            return {
                "result": master_report
            }

        except Exception as e:
            safe_print(f"❌ ERRO CRÍTICO AO MONTAR RELATÓRIO: {e}")
            return self.state.final_report

