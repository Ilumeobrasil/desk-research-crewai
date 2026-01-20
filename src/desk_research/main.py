import logging
import os
import sys
from desk_research.system.research_system import DeskResearchSystem
from desk_research.utils.logging_utils import safe_print

logging.getLogger("LiteLLM").setLevel(logging.WARNING)

os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["ANONYMIZED_TELEMETRY"] = "False"

def main():
    print("\n")
    print("=" * 73)
    print("|" + "🚀 SISTEMA DESK RESEARCH - PESQUISA INTEGRADA AMBEV".center(70) + "|")
    print("=" * 73)
    
    system = DeskResearchSystem()
    result = system.executar_interativo()
    return result

    """ twitter_search_tool = SocialNetworkXSearchTool()
    result = twitter_search_tool._run(query="#JuventudeSaudável", max_results=100, days_window=90, min_engagement=50)
    print(result) """


def kickoff():
    try:
        main()
    except Exception as e:
        safe_print(f"Erro na execução: {e}")
        sys.exit(1)


def plot():
    safe_print("⚠️  Plotting not yet implemented for integrated system.")


def train():
    safe_print("⚠️  Training not available for integrated system yet.")


def replay():
    safe_print("⚠️  Replay not available for integrated system yet.")


def test():
    safe_print("⚠️  Testing not available for integrated system yet.")


if __name__ == "__main__":
    main()
