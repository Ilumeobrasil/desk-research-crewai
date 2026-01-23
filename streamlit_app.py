import streamlit as st
from datetime import datetime
import os
import sys
import logging
import traceback
from pathlib import Path
from typing import Optional, Dict, Any

# Adiciona o diretório src ao path ANTES das importações de desk_research
# Usa caminho absoluto para garantir funcionamento em produção
_current_file = Path(__file__).resolve()
_current_dir = _current_file.parent
_src_dir = _current_dir / "src"

# Tenta múltiplas estratégias para encontrar o diretório src
if not _src_dir.exists():
    # Fallback: tenta encontrar src a partir do diretório atual de trabalho
    _cwd = Path.cwd()
    _src_dir_alt = _cwd / "src"
    if _src_dir_alt.exists():
        _src_dir = _src_dir_alt
    else:
        # Último fallback: procura src em diretórios pais
        for parent in _current_dir.parents:
            _src_dir_candidate = parent / "src"
            if _src_dir_candidate.exists():
                _src_dir = _src_dir_candidate
                break

# Adiciona ao path se encontrado e ainda não estiver lá
if _src_dir.exists():
    _src_path = str(_src_dir.resolve())
    if _src_path not in sys.path:
        sys.path.insert(0, _src_path)
    
    # Verifica se o módulo desk_research existe
    _desk_research_dir = _src_dir / "desk_research"
    if not _desk_research_dir.exists():
        raise ImportError(
            f"Diretório desk_research não encontrado em {_src_dir}. "
            f"Arquivo atual: {_current_file}, Diretório atual: {_current_dir}, "
            f"Diretório de trabalho: {Path.cwd()}"
        )
else:
    # Log de erro para debug em produção
    error_msg = (
        f"Não foi possível encontrar o diretório src. "
        f"Procurou em: {_current_dir / 'src'}, {Path.cwd() / 'src'}. "
        f"Arquivo atual: {_current_file}, Diretório atual: {_current_dir}, "
        f"Diretório de trabalho: {Path.cwd()}, sys.path: {sys.path[:3]}"
    )
    logging.error(error_msg)
    raise ImportError(error_msg)

# Importações do módulo desk_research
try:
    from desk_research.system.research_system import DeskResearchSystem
    from desk_research.constants import MODE_CONFIG, PERGUNTAS_PADRAO, DEFAULT_MAX_PAPERS, DEFAULT_MAX_WEB_RESULTS
except ImportError as e:
    error_msg = (
        f"Erro ao importar módulo desk_research: {e}. "
        f"sys.path inclui: {[p for p in sys.path if 'src' in p or 'desk' in p]}. "
        f"Diretório src encontrado: {_src_dir if _src_dir.exists() else 'NÃO ENCONTRADO'}"
    )
    logging.error(error_msg)
    raise ImportError(error_msg) from e


logging.getLogger("LiteLLM").setLevel(logging.WARNING)
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["ANONYMIZED_TELEMETRY"] = "False"

DEFAULT_CHAT_NAME = "Nova Pesquisa"
DEFAULT_MODE = "integrated"
MAX_TITLE_LENGTH = 28

st.set_page_config(
    page_title="Desk Research System",
    page_icon="💬",
    layout="wide",
)

X_QUESTIONS = PERGUNTAS_PADRAO.get("geral", [])
VIEW_INTERACTIVE_MENU = os.getenv("VIEW_INTERACTIVE_MENU", "FALSE").upper() == "TRUE"
VIEW_SELECT_INTEGRATED_MENU = os.getenv("VIEW_SELECT_INTEGRATED_MENU", "FALSE").upper() == "TRUE"

def _title_from_text(text: str, max_len: int = MAX_TITLE_LENGTH) -> str:
    """Extrai um título do texto fornecido."""
    t = " ".join((text or "").strip().split())
    if not t:
        return DEFAULT_CHAT_NAME
    return t[:max_len].strip()

def _unique_chat_name(base: str) -> str:
    """Gera um nome único para o chat, adicionando número se necessário."""
    name = base
    i = 2
    while name in st.session_state.chats:
        name = f"{base} ({i})"
        i += 1
    return name

def bump_chat_to_top(chat_name: str) -> None:
    """Move um chat para o topo da lista de ordem."""
    if "chat_order" not in st.session_state:
        st.session_state.chat_order = list(st.session_state.chats.keys())
    if chat_name in st.session_state.chat_order:
        st.session_state.chat_order.remove(chat_name)
    st.session_state.chat_order.insert(0, chat_name)

def rename_chat(old: str, new: str) -> bool:
    """Renomeia um chat. Retorna True se bem-sucedido."""
    new = (new or "").strip()
    if not new or new in st.session_state.chats:
        return False

    st.session_state.chats[new] = st.session_state.chats.pop(old)

    if "chat_order" in st.session_state and old in st.session_state.chat_order:
        idx = st.session_state.chat_order.index(old)
        st.session_state.chat_order[idx] = new

    st.session_state.active_chat = new
    return True

def maybe_autoname_chat(chat_name: str, user_text: str) -> str:
    """Renomeia automaticamente o chat se tiver nome genérico."""
    is_generic = chat_name == DEFAULT_CHAT_NAME or chat_name.startswith("Chat ")
    if not is_generic:
        return chat_name

    base = _title_from_text(user_text)
    new_name = _unique_chat_name(base)

    if new_name != chat_name:
        rename_chat(chat_name, new_name)
        return new_name

    return chat_name

def extract_result_text(result: Any) -> str:
    """Extrai texto formatado dos resultados dos crews."""
    if isinstance(result, dict):
        for key in ['resultado', 'result', 'master_report']:
            if key in result:
                return extract_result_text(result[key])
        
        if 'report_markdown' in result:
            return result['report_markdown']
        if 'final_report' in result:
            return result['final_report']
        if 'erro' in result:
            return f"❌ Erro: {result['erro']}"
    
    if hasattr(result, 'raw'):
        return result.raw
    if hasattr(result, 'tasks_output') and result.tasks_output:
        last_task = result.tasks_output[-1]
        return last_task.raw if hasattr(last_task, 'raw') else str(last_task)
    if hasattr(result, 'pydantic'):
        return str(result.pydantic)
    
    return str(result)

def format_result_for_chat(result: Any, modo: Optional[str] = None) -> str:
    """Formata o resultado para exibição no chat."""
    texto = extract_result_text(result)
    
    if modo and modo in MODE_CONFIG:
        modo_info = MODE_CONFIG[modo]
        return f"**{modo_info['emoji']} {modo_info['nome']}**\n\n{texto}"
    
    return texto 

def _prepare_research_params(modo: str, user_text: str, selected_modos: Optional[list] = None) -> Optional[Dict[str, Any]]:
    """Prepara os parâmetros para execução da pesquisa baseado no modo."""
    params_map = {
        "genie": {"pergunta": user_text, "contexto": ""},
        "youtube": {"topic": user_text},
        "academic": {"topic": user_text, "max_papers": DEFAULT_MAX_PAPERS},
        "web": {"query": user_text, "max_results": DEFAULT_MAX_WEB_RESULTS},
        "x": {"topic": user_text},
        "consumer_hours": {"topic": user_text},
        "integrated": {
            "topic": user_text,
            "selected_modos": selected_modos if selected_modos else ['web'],
            "params": {
                "max_papers": DEFAULT_MAX_PAPERS,
                "max_web_results": DEFAULT_MAX_WEB_RESULTS
            }
        }
    }
    return params_map.get(modo)

def execute_research(user_text: str, modo_selecionado: Optional[str] = None, selected_modos: Optional[list] = None) -> str:
    """Executa a pesquisa usando o DeskResearchSystem."""
    try:
        system = DeskResearchSystem()
        
        if not modo_selecionado:
            if VIEW_SELECT_INTEGRATED_MENU:
                modo_selecionado = "integrated"
            else:
                modo_selecionado = DEFAULT_MODE if not VIEW_INTERACTIVE_MENU else None
        
        if not modo_selecionado:
            return "❌ Erro: Nenhum modo selecionado."
        
        params = _prepare_research_params(modo_selecionado, user_text, selected_modos)
        if params is None:
            return f"❌ Modo '{modo_selecionado}' não suportado."
        
        executor = system._executors.get(modo_selecionado)
        if not executor:
            return f"❌ Executor para modo '{modo_selecionado}' não encontrado."
        
        resultado = executor(**params)
        return format_result_for_chat(resultado, modo_selecionado)
        
    except Exception as e:
        error_msg = f"❌ Erro na execução: {str(e)}\n\n```\n{traceback.format_exc()}\n```"
        return error_msg

st.markdown(
    """
    <style>
    /* ===== Fundo geral ===== */
    .stApp {
        background-color: #ffffff;
        color: #0f172a;
    }

    /* ===== Sidebar ===== */
    section[data-testid="stSidebar"] {
        background-color: #f9f9f9;
        border-right: 1px solid #e5e7eb;
    }

    /* ===== Títulos ===== */
    h1, h2, h3, h4 {
        color: #0f172a !important;
    }

    /* ===== Container do chat ===== */
    .chat-wrap {
        max-width: 900px;
        margin: 0 auto;
        padding: 16px 12px 96px 12px;
    }

    /* ===== Bolhas ===== */
    .bubble {
        padding: 12px 14px;
        border-radius: 14px;
        margin: 10px 0;
        line-height: 1.5;
        font-size: 15px;
        max-width: 85%;
        border: 1px solid #e5e7eb;
        white-space: pre-wrap;
        word-wrap: break-word;
        background-color: #ffffff;
    }

    .user {
        background-color: #f4f4f5;
        margin-left: auto;
    }

    .assistant {
        background-color: #ffffff;
        margin-right: auto;
    }

    /* ===== Label (Você / Assistente) ===== */
    .meta {
        font-size: 12px;
        color: #6b7280;
        margin-bottom: 4px;
    }

    /* ===== Input fixo ===== */
    .input-bar {
        position: fixed;
        bottom: 16px;
        left: 0;
        right: 0;
        z-index: 9999;
        display: flex;
        justify-content: center;
        pointer-events: none;
    }

    .input-inner {
        width: min(900px, 92vw);
        background-color: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 10px 12px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.08);
        pointer-events: auto;
    }

    textarea {
        background-color: #ffffff !important;
        color: #0f172a !important;
        border-radius: 10px !important;
        border: 1px solid #e5e7eb !important;
    }

    textarea::placeholder {
        color: #9ca3af !important;
    }

    /* ===== Botões ===== */
    .stButton>button {
        background-color: #f3f4f6 !important;
        color: #0f172a !important;
        border: 1px solid #e5e7eb !important;
        border-radius: 10px !important;
    }

    .stButton>button:hover {
        background-color: #e5e7eb !important;
    }

    /* ===== Ajustes gerais ===== */
    .block-container {
        padding-top: 12px;
        padding-bottom: 0px;
    }

    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }

    /* ===== Ocultar toolbar/header do Streamlit (Share etc.) ===== */
    div[data-testid="stToolbar"] { display: none !important; }
    div[data-testid="stToolbarActions"] { display: none !important; }
    .stAppToolbar { display: none !important; }
    header[data-testid="stHeader"] { display: none !important; }

    /* ===== Ajuste do container do botão Enviar ===== */
    form[data-testid="stForm"] div[data-testid="stVerticalBlock"]:has(button[data-testid="stBaseButton-secondaryFormSubmit"]),
    form[data-testid="stForm"] div[data-testid="stColumn"]:last-child div[data-testid="stVerticalBlock"],
    div.stVerticalBlock[data-testid="stVerticalBlock"] {
        justify-content: flex-start !important;
        align-items: flex-end !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

def _initialize_session_state() -> None:
    """Inicializa o estado da sessão com valores padrão."""
    if "chats" not in st.session_state:
        st.session_state.chats = {
            DEFAULT_CHAT_NAME: [
                {"role": "assistant", "content": "Oi! Esse é a IA da Ambev. 😊\n\nMe manda uma mensagem aí embaixo."}
            ]
        }
        st.session_state.active_chat = DEFAULT_CHAT_NAME
        st.session_state.chat_order = [DEFAULT_CHAT_NAME]

    print("SESSION STATE CHATS: ", st.session_state.chats)
    if "chat_order" not in st.session_state:
        st.session_state.chat_order = list(st.session_state.chats.keys())

    if "sidebar_section" not in st.session_state:
        st.session_state.sidebar_section = "chats" 

    if "pending_user_message" not in st.session_state:
        st.session_state.pending_user_message = ""

    if "pending_mode" not in st.session_state:
        st.session_state.pending_mode = None

    if "pending_research" not in st.session_state:
        st.session_state.pending_research = None

    if "system" not in st.session_state:
        st.session_state.system = DeskResearchSystem()
    
    if "selected_crews" not in st.session_state:
        st.session_state.selected_crews = []

_initialize_session_state()

def new_chat() -> None:
    """Cria um novo chat."""
    name = _unique_chat_name(f"Chat {len(st.session_state.chats)+1}")
    st.session_state.chats[name] = [
        {"role": "assistant", "content": "Começamos uma novo chat. Como posso ajudar?"}
    ]
    st.session_state.active_chat = name
    bump_chat_to_top(name)

with st.sidebar:
    if st.session_state.sidebar_section == "chats":
        st.markdown("### Chats")
        st.button("➕ Novo chat", use_container_width=True, on_click=new_chat)

        st.markdown("---")
        for chat_name in st.session_state.chat_order:
            is_active = (chat_name == st.session_state.active_chat)
            label = f"{chat_name}" if is_active else chat_name

            if st.button(label, key=f"chat_{chat_name}", use_container_width=True):
                st.session_state.active_chat = chat_name

active = st.session_state.active_chat
messages = st.session_state.chats[active]

st.markdown(f"## {active}")

modo_selecionado = None
selected_crews = []

if VIEW_INTERACTIVE_MENU:
    st.markdown("---")
    modo_selecionado = st.selectbox(
        "🔧 Escolha o modo de pesquisa:",
        options=["integrated"] + [k for k in MODE_CONFIG.keys() if k != "integrated"],
        format_func=lambda x: f"{MODE_CONFIG[x]['emoji']} {MODE_CONFIG[x]['nome']}",
        key=f"mode_select_{active}",
        help="Selecione qual tipo de pesquisa deseja executar"
    )
    st.markdown("---")
elif VIEW_SELECT_INTEGRATED_MENU:
    # Quando VIEW_SELECT_INTEGRATED_MENU=TRUE e VIEW_INTERACTIVE_MENU=FALSE
    # Sempre usa o modo integrated e mostra multi-select para escolher agentes
    modo_selecionado = "integrated"
    st.markdown("---")
    st.markdown("### Desk research (BETA) v.0.0.3")
    st.caption("Selecione quais agentes deseja ativar para a pesquisa integrada")
    
    # Opções disponíveis (excluindo integrated e consumer_hours)
    modos_disponiveis = [k for k in MODE_CONFIG.keys() if k not in ["integrated"]]
    
    selected_crews = st.multiselect(
        "🤖 Selecione os agentes:",
        options=modos_disponiveis,
        default=st.session_state.selected_crews if st.session_state.selected_crews else ['web'],
        format_func=lambda x: f"{MODE_CONFIG[x]['emoji']} {MODE_CONFIG[x]['nome']}",
        key=f"crews_select_{active}",
        help="Selecione pelo menos um agente para executar a pesquisa integrada"
    )
    
    # Validação: pelo menos um crew deve ser selecionado
    if not selected_crews:
        st.warning("⚠️ Por favor, selecione pelo menos um agente para continuar.")
    
    st.session_state.selected_crews = selected_crews
    st.markdown("---")
else:
    # Comportamento padrão quando nenhuma das variáveis está ativa
    modo_selecionado = DEFAULT_MODE

st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)

for m in messages:
    role = m["role"]
    content = m["content"]

    who = "Você" if role == "user" else "Assistente"
    css_class = "user" if role == "user" else "assistant"
    meta = f'<div class="meta">{who} • {datetime.now().strftime("%H:%M")}</div>'

    st.markdown(
        f"""
        <div>
            {meta}
            <div class="bubble {css_class}">{content}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown("</div>", unsafe_allow_html=True)

if not st.session_state.pending_research:
    with st.form("chat_form", clear_on_submit=True):
        user_text = st.text_area("Mensagem", placeholder="Digite sua mensagem...", label_visibility="collapsed", height=70)
        col1, col2 = st.columns([6, 1])
        with col2:
            send = st.form_submit_button("Enviar")
else:
    user_text = ""
    send = False

def process_user_message(message: str, modo: Optional[str] = None, selected_crews: Optional[list] = None) -> None:
    """Processa uma mensagem do usuário e adiciona resposta ao chat."""
    if not message.strip():
        return
    
    active_before = st.session_state.active_chat
    
    # Determina o modo para execução
    if VIEW_INTERACTIVE_MENU:
        modo_para_execucao = modo
    elif VIEW_SELECT_INTEGRATED_MENU:
        modo_para_execucao = "integrated"
    else:
        modo_para_execucao = None
    
    st.session_state.chats[active_before].append({"role": "user", "content": message.strip()})
    
    st.session_state.pending_research = {
        "message": message.strip(),
        "modo": modo_para_execucao,
        "selected_crews": selected_crews,
        "chat_name": active_before
    }
    st.rerun()

def execute_pending_research() -> None:
    """Executa uma pesquisa pendente e adiciona a resposta ao chat."""
    if not st.session_state.pending_research:
        return
    
    pesquisa = st.session_state.pending_research
    st.session_state.pending_research = None
    
    active_before = pesquisa["chat_name"]
    message = pesquisa["message"]
    modo_para_execucao = pesquisa["modo"]
    selected_crews = pesquisa.get("selected_crews", [])
    
    # Validação: se for integrated e não tiver crews selecionados, retorna erro
    if modo_para_execucao == "integrated" and not selected_crews:
        st.session_state.chats[active_before].append({
            "role": "assistant", 
            "content": "❌ Erro: É necessário selecionar pelo menos um agente para executar a pesquisa integrada."
        })
        st.rerun()
        return
    
    with st.spinner("🔄 Processando pesquisa... Isso pode levar alguns minutos."):
        resposta = execute_research(message, modo_para_execucao, selected_crews)
    
    active_after = maybe_autoname_chat(active_before, message)
    st.session_state.chats[active_after].append({"role": "assistant", "content": resposta})
    
    bump_chat_to_top(active_after)
    st.rerun()

if st.session_state.pending_user_message.strip():
    injected = st.session_state.pending_user_message.strip()
    st.session_state.pending_user_message = ""
    # Usa o session_state se VIEW_SELECT_INTEGRATED_MENU estiver ativo
    crews_para_usar = st.session_state.selected_crews if VIEW_SELECT_INTEGRATED_MENU else selected_crews
    process_user_message(injected, modo_selecionado, crews_para_usar)

if send and user_text.strip():
    # Usa o session_state se VIEW_SELECT_INTEGRATED_MENU estiver ativo
    crews_para_usar = st.session_state.selected_crews if VIEW_SELECT_INTEGRATED_MENU else selected_crews
    # Validação: se for integrated e não tiver crews selecionados, não permite enviar
    if VIEW_SELECT_INTEGRATED_MENU and modo_selecionado == "integrated" and not crews_para_usar:
        st.error("⚠️ Por favor, selecione pelo menos um agente antes de enviar.")
    else:
        process_user_message(user_text.strip(), modo_selecionado, crews_para_usar)

if st.session_state.pending_research:
    execute_pending_research()

