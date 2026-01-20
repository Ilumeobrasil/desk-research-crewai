import os
import time

from typing import Dict, Any
from collections.abc import Iterable
from desk_research.constants import MODE_CONFIG
from desk_research.system.parameter_collectors import (
    GenieParameterCollector,
    YouTubeParameterCollector,
    AcademicParameterCollector,
    WebParameterCollector,
    XParameterCollector,
    ConsumerHoursParameterCollector,
    IntegratedParameterCollector
)
from desk_research.flow.flow import DeskResearchFlow
from desk_research.crews.genie.genie import run_genie_analysis
from desk_research.crews.youtube.youtube import run_youtube_analysis
from desk_research.crews.academic.academic import run_academic_research
from desk_research.crews.web.web import run_web_research
from desk_research.crews.x.twitter_x_crew import run_twitter_social_listening
from desk_research.crews.consumer_hours.consumer_hours import run_consumer_hours_analysis

class DeskResearchSystem:
    def __init__(self):
        self.modos_disponiveis = MODE_CONFIG
        self._parameter_collectors = {
            "genie": GenieParameterCollector,
            "youtube": YouTubeParameterCollector,
            "academic": AcademicParameterCollector,
            "web": WebParameterCollector,
            "x": XParameterCollector,
            "consumer_hours": ConsumerHoursParameterCollector,
            "integrated": IntegratedParameterCollector
        }
        self._executors = {
            "genie": self.executar_genie,
            "youtube": self.executar_youtube,
            "academic": self.executar_academic,
            "web": self.executar_web,
            "x": self.executar_x,
            "consumer_hours": self.executar_consumer_hours,
            "integrated": self.executar_integrated
        }

    def listar_modos(self):
        print("\n")
        print("=" * 73)
        print("|" + "📋 MODOS DE PESQUISA DISPONÍVEIS".center(70) + "|")
        print("=" * 73)

        for i, (modo_id, info) in enumerate(self.modos_disponiveis.items(), 1):
            print("\n")
            print(f"   [{i}] {info['emoji']} {info['nome']}")
            print(f"       ID: {modo_id} - Descrição: {info['descricao']}")

    def selecionar_modo_interativo(self) -> str:
        self.listar_modos()
        modos_lista = list(self.modos_disponiveis.keys())

        while True:
            print("\n")
            print("=" * 73)
            print("|" + "🔹 ESCOLHA O MODO DE PESQUISA".center(70) + "|")
            print("=" * 73)

            escolha = input(f"• Digite o número [1-{len(modos_lista)}] ou o ID do modo: ").strip()

            if escolha.isdigit():
                idx = int(escolha) - 1
                if 0 <= idx < len(modos_lista):
                    modo_selecionado = modos_lista[idx]
                    break
            elif escolha in self.modos_disponiveis:
                modo_selecionado = escolha
                break

            print("   ❌ Opção inválida! Tente novamente.")

        info = self.modos_disponiveis[modo_selecionado]
        print("\n")
        print(f"✅ Modo selecionado: {info['emoji']} {info['nome']}")
        print("\n")
        
        return modo_selecionado

    @staticmethod
    def format_value(value):
        if value is None:
            return "None"

        if isinstance(value, bool):
            return str(value)

        if isinstance(value, (int, float)):
            return str(value)

        if isinstance(value, str):
            return value if value.strip() else "''"

        if isinstance(value, dict):
            return ", ".join(
                f"{k}={DeskResearchSystem.format_value(v)}"
                for k, v in value.items()
            )

        if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            return ", ".join(map(str, value))

        return str(value)

    def executar_interativo(self) -> Any:
        while True:
            modo = self.selecionar_modo_interativo()
            
            collector = self._parameter_collectors.get(modo)
            if not collector:
                print(f"❌ Modo '{modo}' não suportado.\n")
                continue

            params = collector.collect()
            if params is None:
                print("\n⬅️  Voltando para seleção de modo...\n")
                continue
            
            executor = self._executors.get(modo)
            
            if not executor:
                print(f"❌ Executor para modo '{modo}' não encontrado.")
                continue

            start_time = time.time()
            result = executor(**params)
            end_time = time.time()

            execution_time = end_time - start_time

            print("\n")
            print("=" * 73)
            print("|" + "✅ PESQUISA CONCLUÍDA COM SUCESSO!".center(70) + "|")
            print("=" * 73)

            print("\n")
            print(f"📋 Modo: {MODE_CONFIG[modo]['emoji']} {MODE_CONFIG[modo]['nome']}")
            print(f"🤖 Modelo utilizado: {os.getenv('MODEL')}")
            print(f"🕒 Tempo de execução: {time.strftime("%H:%M:%S", time.gmtime(execution_time))}")
            
            print("\n")
            if params:
                print("📊 Parâmetros utilizados:")
                for key, value in params.items():
                    print(f"  • {key}: {self.format_value(value)}")

            
            print("\n")

            return result

    def executar_genie(self, pergunta: str, contexto: str = "") -> Dict[str, Any]:
        print(f"\n🧞 Iniciando análise Genie...")
        print(f"Pergunta: {pergunta}")
        if contexto:
            print(f"Contexto: {contexto}")
        print("")

        result = run_genie_analysis(pergunta=pergunta, contexto=contexto)
        return {
            "modo": "genie",
            "resultado": result,
            "metadados": {"pergunta": pergunta, "contexto": contexto}
        }

    def executar_youtube(self, topic: str) -> Dict[str, Any]:
        print(f"\n📺 Iniciando análise YouTube...")
        print(f"Tópico: {topic}\n")
        result = run_youtube_analysis(topic=topic)
        return {
            "modo": "youtube",
            "resultado": result,
            "metadados": {"topic": topic}
        }

    def executar_academic(self, topic: str, max_papers: int = 10) -> Dict[str, Any]:
        print(f"\n🎓 Iniciando pesquisa acadêmica...")
        print(f"Tópico: {topic}")
        print(f"Máximo de papers: {max_papers}\n")
        result = run_academic_research(topic=topic, max_papers=max_papers)
        return {
            "modo": "academic",
            "resultado": result,
            "metadados": {"topic": topic, "max_papers": max_papers}
        }

    def executar_web(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        print(f"\n🌐 Iniciando pesquisa web...")
        print(f"Query: {query}")
        print(f"Máximo de resultados: {max_results}\n")
        result = run_web_research(query=query, max_results=max_results)
        return {
            "modo": "web",
            "resultado": result,
            "metadados": {"query": query, "max_results": max_results}
        }

    def executar_x(self, topic: str) -> Dict[str, Any]:
        print(f"\n🐦 Iniciando Social Listening no X...")
        print(f"Tema: {topic}\n")
        result = run_twitter_social_listening(topic=topic)
        return {
            "modo": "x",
            "resultado": result,
            "metadados": {"topic": topic}
        }

    def executar_consumer_hours(self) -> Dict[str, Any]:
        print(f"\n⏳ Iniciando Consumer Hours...")
        try:
            result = run_consumer_hours_analysis()
            return {
                "modo": "consumer_hours",
                "resultado": result,
                "metadados": {}
            }
        except Exception as e:
            print(f"❌ Erro na execução: {e}")
            return {"erro": str(e)}

    def executar_integrated(self, topic: str, selected_modos: list, params: dict) -> Dict[str, Any]:
        print(f"\n🧠 Iniciando Pesquisa Integrada (FLOW)...")
        print(f"Tema: {topic}")
        print(f"Modos: {selected_modos}\n")
        
        try:
            flow = DeskResearchFlow()
            inputs = {
                "topic": topic,
                "selected_crews": selected_modos,
                "params": params
            }
            final_result = flow.kickoff(inputs=inputs)
         
            return {
                "modo": "integrated",
                "resultado": final_result,
                "outputs_parciais": flow.state.results,
                "metadados": inputs
            }
        except Exception as e:
            print(f"❌ Erro crítico no Flow: {e}")
            import traceback
            traceback.print_exc()
            return {"erro": str(e)}


