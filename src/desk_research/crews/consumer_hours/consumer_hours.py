from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

# Tools import
from desk_research.tools.ingestion_tools import ingest_folder_tool
from desk_research.tools.asimov_client import AsimovClient

# =========================
# SETTINGS & PATHS (Ported from state.py)
# =========================

# Raiz do projeto (ajustado para a nova estrutura src/desk_research/crews/consumer_hours)
# .../src/desk_research/crews/consumer_hours/consumer_hours.py -> parents[4] = Project Root
PROJECT_ROOT = Path(__file__).resolve().parents[4]

DATA_DIR = PROJECT_ROOT / "data"
INPUT_RAW_DIR = DATA_DIR / "input_raw"
OUTPUT_INGESTOR_DIR = DATA_DIR / "output_ingestor"

# Subpasta padrão do agente 1 (pode mudar via env)
DEFAULT_INPUT_SUBDIR = "Brand_Audit"
DEFAULT_INPUT_DIR = INPUT_RAW_DIR / DEFAULT_INPUT_SUBDIR

@dataclass(frozen=True)
class Paths:
    """Paths efetivos (strings) para interpolação em YAML e Tasks."""
    input_dir: str
    output_dir: str

@dataclass(frozen=True)
class LLMConfig:
    """Config de LLM."""
    model: str
    api_key: str
    api_base: Optional[str]

@dataclass(frozen=True)
class AsimovConfig:
    """Config do Asimov (S) para upload/RAG via tools."""
    enabled: bool
    api_base: Optional[str]
    api_key: Optional[str]
    dataset: Optional[str]

@dataclass(frozen=True)
class Settings:
    paths: Paths
    llm: LLMConfig
    asimov: AsimovConfig

def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "y", "on"}

def _load_env_files() -> None:
    """
    Carrega:
      - .env (LLM / Crew)
      - .env.asimov (Asimov)
    """
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    load_dotenv(PROJECT_ROOT / ".env.asimov", override=False)

def get_settings() -> Settings:
    """
    Fonte única de verdade para paths e configs.
    """
    _load_env_files()

    # Paths: permitem override por env
    input_dir = os.getenv("INGESTOR_INPUT_DIR")
    output_dir = os.getenv("INGESTOR_OUTPUT_DIR")

    if not input_dir:
        input_dir = str(DEFAULT_INPUT_DIR)
    if not output_dir:
        output_dir = str(OUTPUT_INGESTOR_DIR)

    # LLM
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("MODEL", "").strip()
    api_base = (os.getenv("OPENAI_API_BASE") or "").strip() or None

    # Nota: Em ambiente produtivo, validar se chaves existem. 
    # Aqui permitimos vazio se o user não tiver configurado tudo ainda.
    
    llm_cfg = LLMConfig(
        model=model,
        api_key=api_key,
        api_base=api_base,
    )

    # Asimov
    asimov_cfg = AsimovConfig(
        enabled=_truthy(os.getenv("ASIMOV_ENABLED")),
        api_base=(os.getenv("ASIMOV_API_BASE") or "").strip() or None,
        api_key=(os.getenv("ASIMOV_API_KEY") or "").strip() or None,
        dataset=(os.getenv("ASIMOV_DATASET") or "").strip() or None,
    )

    return Settings(
        paths=Paths(input_dir=input_dir, output_dir=output_dir),
        llm=llm_cfg,
        asimov=asimov_cfg,
    )

def _ensure_dir(p: str | Path) -> Path:
    """Garante que o diretório exista."""
    p = Path(p)
    p.mkdir(parents=True, exist_ok=True)
    return p

# =========================
# CREW (Ported from ingestor_crew.py)
# =========================

@CrewBase
class IngestorCrew:
    """
    Crew de ingestão (Consumer Hours).
    """
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"
    
    @agent
    def ingestor(self) -> Agent:
        s = get_settings()
        # Se quiser passar o LLM vindo do settings dinamicamente:
        # llm = LLM(model=s.llm.model, api_key=s.llm.api_key, base_url=s.llm.api_base)
        # Por enquanto mantemos o padrão do framework que pega do env, 
        # ou passamos explicitamente se o original fazia isso.
        
        return Agent(
            config=self.agents_config["ingestor"],
            tools=[ingest_folder_tool],
            verbose=True,
            # llm=s.llm.model # Descomente se precisar forçar o modelo do settings
        )

    @task
    def ingest(self) -> Task:
        return Task(
            config=self.tasks_config["ingest"],
            agent=self.ingestor(),
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )

# =========================
# RUNNER (Ported from flow.py)
# =========================

def run_consumer_hours_analysis() -> dict[str, Any]:
    """
    Executa a análise de Consumer Hours (Brand Audit), replicando a lógica do Flow original.
    """
    s = get_settings()

    # 1. Garantir diretórios
    _ensure_dir(s.paths.input_dir)
    _ensure_dir(s.paths.output_dir)

    # 2. Executar Crew
    crew = IngestorCrew().crew()
    result = crew.kickoff(
        inputs={
            "input_dir": s.paths.input_dir,
            "output_dir": s.paths.output_dir,
        }
    )

    payload: dict[str, Any] = {
        "input_dir": s.paths.input_dir,
        "output_dir": s.paths.output_dir,
        "result": str(result),
    }

    # 3. Upload no Asimov (se habilitado)
    if s.asimov.enabled:
        try:
            print("\n🔄 Processando upload para Asimov...")
            client = AsimovClient(api_key=s.asimov.api_key, api_base=s.asimov.api_base)
            client.upload_folder(
                dataset=s.asimov.dataset,
                folder_path=s.paths.output_dir,
                metadata={
                    "project": "consumer_hours_flow",
                    "step": "ingestor",
                    "input_dir": s.paths.input_dir,
                },
            )
            payload["asimov_upload"] = "ok"
            print("✅ Upload Asimov concluído.")
        except Exception as e:
            msg = f"error: {e!r}"
            payload["asimov_upload"] = msg
            print(f"❌ Falha no upload Asimov: {msg}")

    # 4. Log opcional local (flow_result.json)
    try:
        out_dir = Path(s.paths.output_dir)
        (out_dir / "flow_result.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass

    return payload
