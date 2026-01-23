from datetime import datetime
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from desk_research.constants import VERBOSE_AGENTS, VERBOSE_CREW
from desk_research.tools.ingestion_tools import ingest_folder_tool
from desk_research.utils.reporting import export_report
from desk_research.tools.treatment_tools import treat_folder_tool

import logging

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[4]

DATA_DIR = PROJECT_ROOT / "data"
INPUT_RAW_DIR = DATA_DIR / "input_raw"
OUTPUT_INGESTOR_DIR = DATA_DIR / "output_ingestor"
OUTPUT_TREATMENT_DIR = DATA_DIR / "output_treatment"

DEFAULT_SNIPPET_CHUNK_CHARS = 3500
DEFAULT_MAX_SNIPPETS_PER_REQUEST = 30
SAMPLE_OUTPUTS_COUNT = 3
DEFAULT_UPLOAD_TO_ASIMOV = True
DEFAULT_ENABLE_RAG = True
DEFAULT_POLL_ATTEMPTS = 3
DEFAULT_POLL_SLEEP_S = 2
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 2000

TEXT_EXTRACTION_KEYS = [
    "text",
    "full_text",
    "transcript",
    "content",
    "raw_text",
    "document_text",
    "body",
]

TRUTHY_VALUES = {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Paths:
    input_dir: str
    output_dir: str
    treatment_output_dir: str


@dataclass(frozen=True)
class LLMConfig:
    model: str
    api_key: str
    api_base: str | None


@dataclass(frozen=True)
class AsimovConfig:
    enabled: bool
    api_base: str | None
    api_key: str | None
    dataset: str | None


@dataclass(frozen=True)
class Settings:
    paths: Paths
    llm: LLMConfig
    asimov: AsimovConfig


def _is_truthy(value: str | None) -> bool:
    return bool(value and value.strip().lower() in TRUTHY_VALUES)

def _load_environment_files() -> None:
    load_dotenv(PROJECT_ROOT / ".env", override=False)


def _get_optional_env_string(key: str) -> str | None:
    value = os.getenv(key)
    return value.strip() if value and value.strip() else None


def get_settings() -> Settings:
    _load_environment_files()

    input_dir = os.getenv("INGESTOR_INPUT_DIR") or str(INPUT_RAW_DIR)
    output_dir = os.getenv("INGESTOR_OUTPUT_DIR") or str(OUTPUT_INGESTOR_DIR)
    treatment_output_dir = os.getenv("TREATMENT_OUTPUT_DIR") or str(OUTPUT_TREATMENT_DIR)

    llm_config = LLMConfig(
        model=(os.getenv("MODEL") or "").strip(),
        api_key=(os.getenv("OPENAI_API_KEY") or "").strip(),
        api_base=_get_optional_env_string("OPENAI_API_BASE"),
    )

    asimov_config = AsimovConfig(
        enabled=_is_truthy(os.getenv("ASIMOV_ENABLED")),
        api_base=_get_optional_env_string("ASIMOV_API_BASE"),
        api_key=_get_optional_env_string("ASIMOV_API_KEY"),
        dataset=_get_optional_env_string("ASIMOV_DATASET"),
    )

    return Settings(
        paths=Paths(input_dir=input_dir, output_dir=output_dir, treatment_output_dir=treatment_output_dir),
        llm=llm_config,
        asimov=asimov_config,
    )


def _is_url(path: str) -> bool:
    return path.startswith(("http://", "https://"))


def _ensure_directory(path: str | Path) -> Path | str:
    if isinstance(path, str) and _is_url(path):
        return path
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory

def _find_longest_string_in_structure(data: Any) -> str:
    longest_text = ""
    stack: list[Any] = [data]

    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, str) and len(item) > len(longest_text):
            longest_text = item

    return longest_text


def _extract_text_from_json(payload: dict[str, Any]) -> str:
    for key in TEXT_EXTRACTION_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return _find_longest_string_in_structure(payload)


def _calculate_snippets_count(text_length: int, chunk_size: int) -> int:
    return int(math.ceil(text_length / chunk_size))


def _estimate_snippets_from_outputs(output_dir: str, chunk_size: int) -> dict[str, Any]:
    if _is_url(output_dir):
        return {
            "output_json_files": 0,
            "snippet_chunk_chars_assumed": chunk_size,
            "estimated_total_chars": 0,
            "estimated_total_snippets": 0,
            "json_unreadable_or_no_text": 0,
            "sample_outputs": [],
            "note": "SharePoint URL: estimativa não disponível sem biblioteca de acesso ao SharePoint",
        }

    output_path = Path(output_dir)
    json_files = sorted(output_path.glob("*.json"))

    total_chars = 0
    total_snippets = 0
    unreadable_count = 0

    for file_path in json_files:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            text = _extract_text_from_json(data)

            if not text:
                unreadable_count += 1
                continue

            total_chars += len(text)
            total_snippets += _calculate_snippets_count(len(text), chunk_size)

        except (json.JSONDecodeError, OSError):
            unreadable_count += 1

    return {
        "output_json_files": len(json_files),
        "snippet_chunk_chars_assumed": chunk_size,
        "estimated_total_chars": total_chars,
        "estimated_total_snippets": total_snippets,
        "json_unreadable_or_no_text": unreadable_count,
        "sample_outputs": [str(f) for f in json_files[:SAMPLE_OUTPUTS_COUNT]],
    }


@CrewBase
class IngestorCrew:
    agents: list[Agent]
    tasks: list[Task]

    @agent
    def ingestor(self) -> Agent:
        return Agent(
            config=self.agents_config["ingestor"],
            tools=[ingest_folder_tool],
            verbose=VERBOSE_AGENTS,
            reasoning=True,
            max_reasoning_attempts=3,
        )
    
    @agent
    def treater(self) -> Agent:
        return Agent(
            config=self.agents_config["treater"],
            tools=[treat_folder_tool],
            verbose=VERBOSE_AGENTS,
            reasoning=True,
            max_reasoning_attempts=3,
        )
    
    @agent
    def writer(self) -> Agent:
        return Agent(
            config=self.agents_config["writer"],
            verbose=VERBOSE_AGENTS,
            allow_delegation=False,
            reasoning=True,
            max_reasoning_attempts=3,
        )

    @task
    def ingest(self) -> Task:
        return Task(
            config=self.tasks_config["ingest"],
            agent=self.ingestor(),
            output_key="ingestion_result"
        )
    
    
    @task
    def treat(self) -> Task:
        return Task(
            config=self.tasks_config["treat"],
            agent=self.treater(),
            output_key="treatment_result",
            context=[self.ingest()],
        )
    
    @task
    def write(self) -> Task:
        # Cria uma task customizada que inclui os dados tratados agregados
        write_task = Task(
            config=self.tasks_config["write_report"],
            agent=self.writer(),
            output_key="report_markdown",
            context=[self.treat()],
        )
        return write_task

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=VERBOSE_CREW,
            planning=True,
            planning_llm="openai/openai/gpt-4o-mini",
        )

def _calculate_asimov_batches(total_snippets: int, max_per_request: int) -> int:
    return int(math.ceil(total_snippets / max_per_request)) if total_snippets > 0 else 0


def _enrich_snippets_estimate(estimate: dict[str, Any], max_per_request: int) -> dict[str, Any]:
    estimate["max_snippets_per_request_assumed"] = max_per_request
    estimate["estimated_asimov_batches"] = _calculate_asimov_batches(
        estimate["estimated_total_snippets"], max_per_request
    )
    return estimate


def _get_snippet_config() -> tuple[int, int]:
    chunk_size = int(os.getenv("SNIPPET_CHUNK_CHARS", str(DEFAULT_SNIPPET_CHUNK_CHARS)))
    max_per_request = int(
        os.getenv("MAX_SNIPPETS_PER_REQUEST", str(DEFAULT_MAX_SNIPPETS_PER_REQUEST))
    )
    return chunk_size, max_per_request

def _build_result_payload(
    settings: Settings, crew_result: Any, snippets_estimate: dict[str, Any]
) -> dict[str, Any]:
    return {
        "input_dir": settings.paths.input_dir,
        "output_dir": settings.paths.output_dir,
        "treatment_output_dir": settings.paths.treatment_output_dir,
        "result": str(crew_result),
        "asimov": {
            "enabled": settings.asimov.enabled,
            "dataset": settings.asimov.dataset,
            "api_base": settings.asimov.api_base,
        },
        "snippets_estimate": snippets_estimate,
    }


def _aggregate_treated_data(output_dir: str) -> dict[str, Any]:
    """
    Agrega os dados tratados de todos os arquivos JSON no diretório de saída.
    Retorna um dicionário com os dados consolidados para uso no relatório.
    """
    output_path = Path(output_dir)
    json_files = sorted(output_path.glob("*.json"))
    
    aggregated = {
        "total_interviews": 0,
        "interviews": [],
        "all_themes": [],
        "all_sentiments": [],
        "all_moments": [],
        "all_brand_mentions": [],
        "all_evidence": [],
    }
    
    themes_count: dict[str, int] = {}
    sentiments_count: dict[str, int] = {}
    moments_count: dict[str, int] = {}
    brand_mentions_count: dict[str, int] = {}
    
    for file_path in json_files:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            
            # Verifica se é um arquivo tratado (tem semantics)
            if not isinstance(data, dict) or "semantics" not in data:
                continue
            
            aggregated["total_interviews"] += 1
            
            semantics = data.get("semantics", {})
            cleaned_text = data.get("cleaned_text", "")
            resumo = data.get("resumo")
            
            # Agrega temas
            themes = semantics.get("themes", [])
            for theme in themes:
                if theme:
                    themes_count[theme] = themes_count.get(theme, 0) + 1
                    if theme not in aggregated["all_themes"]:
                        aggregated["all_themes"].append(theme)
            
            # Agrega sentimentos
            sentiments = semantics.get("sentiments", [])
            for sentiment in sentiments:
                if sentiment:
                    sentiments_count[sentiment] = sentiments_count.get(sentiment, 0) + 1
                    if sentiment not in aggregated["all_sentiments"]:
                        aggregated["all_sentiments"].append(sentiment)
            
            # Agrega momentos
            moments = semantics.get("moments", [])
            for moment in moments:
                if moment:
                    moments_count[moment] = moments_count.get(moment, 0) + 1
                    if moment not in aggregated["all_moments"]:
                        aggregated["all_moments"].append(moment)
            
            # Agrega marcas
            brand_mentions = semantics.get("brand_mentions", [])
            for brand in brand_mentions:
                if brand:
                    brand_mentions_count[brand] = brand_mentions_count.get(brand, 0) + 1
                    if brand not in aggregated["all_brand_mentions"]:
                        aggregated["all_brand_mentions"].append(brand)
            
            # Agrega evidências
            evidence = semantics.get("evidence", [])
            if evidence:
                aggregated["all_evidence"].extend(evidence)
            
            # Adiciona dados da entrevista
            interview_data = {
                "uuid": data.get("uuid"),
                "source_file": data.get("source_file") or data.get("file"),
                "cleaned_text": cleaned_text[:5000] if cleaned_text else "",  # Limita tamanho
                "resumo": resumo,
                "themes": themes,
                "sentiments": sentiments,
                "moments": moments,
                "brand_mentions": brand_mentions,
                "evidence": evidence,
            }
            aggregated["interviews"].append(interview_data)
            
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Erro ao processar arquivo {file_path}: {e}")
            continue
    
    # Adiciona contagens
    aggregated["themes_count"] = themes_count
    aggregated["sentiments_count"] = sentiments_count
    aggregated["moments_count"] = moments_count
    aggregated["brand_mentions_count"] = brand_mentions_count
    
    return aggregated


def _get_task_inputs(settings: Settings, topic: str = "Entrevistas em Profundidade") -> dict[str, Any]:
    chunk_size, max_per_request = _get_snippet_config()
    
    upload_to_asimov = os.getenv("UPLOAD_TO_ASIMOV") or str(DEFAULT_UPLOAD_TO_ASIMOV).lower()
    enable_rag = os.getenv("ENABLE_RAG") or str(DEFAULT_ENABLE_RAG).lower()
    
    # Inputs específicos para a tarefa ingest
    ingest_input_dir = settings.paths.input_dir  # Onde estão os .docx
    ingest_output_dir = settings.paths.output_dir  # Onde escrever os .json do ingestor
    
    # Inputs específicos para a tarefa treat
    # O treater lê do output_dir do ingestor (onde estão os .json gerados)
    treat_input_dir = settings.paths.output_dir  # Onde o ingestor escreveu os .json
    treat_output_dir = settings.paths.treatment_output_dir  # Onde escrever os .json tratados (diretório separado)
    
    return {
        # Inputs para tarefa ingest
        "ingest_input_dir": ingest_input_dir,
        "ingest_output_dir": ingest_output_dir,
        
        # Inputs para tarefa treat
        "treat_input_dir": treat_input_dir,
        "treat_output_dir": treat_output_dir,
        
        # Configurações compartilhadas
        "upload_to_asimov": upload_to_asimov,
        "snippet_chunk_chars": chunk_size,
        "max_snippets_per_request": max_per_request,
        "enable_rag": enable_rag,
        "poll_attempts": int(os.getenv("POLL_ATTEMPTS", str(DEFAULT_POLL_ATTEMPTS))),
        "poll_sleep_s": int(os.getenv("POLL_SLEEP_S", str(DEFAULT_POLL_SLEEP_S))),
        "temperature": float(os.getenv("TEMPERATURE", str(DEFAULT_TEMPERATURE))),
        "max_tokens": int(os.getenv("MAX_TOKENS", str(DEFAULT_MAX_TOKENS))),
        "date": datetime.now().strftime("%d/%m/%Y"),
        "topic": topic,
    }


def _execute_crew(settings: Settings, topic: str) -> Any:
    try:
        crew_instance = IngestorCrew()

        crew = crew_instance.crew()

        inputs = _get_task_inputs(settings, topic=topic)

        # Executa o crew para obter o resultado
        result = crew.kickoff(inputs=inputs)
        
        # Agrega os dados tratados para incluir no contexto da task write_report
        # Isso garante que os dados estejam disponíveis mesmo que o treatment_result
        # contenha apenas o resumo estatístico
        aggregated_data = _aggregate_treated_data(settings.paths.treatment_output_dir)
        
        # Converte os dados agregados em formato JSON string para incluir no contexto
        aggregated_data_json = json.dumps(aggregated_data, ensure_ascii=False, indent=2)
        
        # Se o resultado não contiver os dados tratados, podemos re-executar apenas a task write
        # Mas por enquanto, vamos confiar que o contexto está sendo passado corretamente
        # através do treatment_result e dos dados agregados no diretório
        
        export_report(result, topic, prefix="consumer_hours", crew_name="consumer_hours")
        
        return {
            "topic": topic,
            "report_markdown": result,
        }
    except Exception as e:
        logger.error(f"Erro ao executar consumer hours: {e}", exc_info=True)
        raise



def run_consumer_hours_analysis(topic: str) -> dict[str, Any]:
    settings = get_settings()

    _ensure_directory(settings.paths.input_dir)
    _ensure_directory(settings.paths.output_dir)
    _ensure_directory(settings.paths.treatment_output_dir)

    crew_result = _execute_crew(settings, topic=topic)

    chunk_size, max_per_request = _get_snippet_config()
    snippets_estimate = _estimate_snippets_from_outputs(settings.paths.output_dir, chunk_size)
    snippets_estimate = _enrich_snippets_estimate(snippets_estimate, max_per_request)

    _build_result_payload(settings, crew_result, snippets_estimate)

    return crew_result
