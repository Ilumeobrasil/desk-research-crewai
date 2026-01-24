import streamlit as st
from datetime import datetime
import os
import sys
import logging
import traceback
from pathlib import Path
from typing import Any
import markdown2
import re
import html as html_module
import warnings

logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("crewai.telemetry").setLevel(logging.CRITICAL)
logging.getLogger("crewai").setLevel(logging.WARNING)

os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["ANONYMIZED_TELEMETRY"] = "False"

warnings.filterwarnings("ignore", category=RuntimeWarning)

from desk_research.system.research_system import DeskResearchSystem
from desk_research.constants import MODE_CONFIG, DEFAULT_MAX_PAPERS, DEFAULT_MAX_WEB_RESULTS
    
_current_dir = Path(__file__).resolve().parent
_src_dir = _current_dir / "src"

if _src_dir.exists() and str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

_parent_dir = _current_dir.parent
if (_parent_dir / "src" / "desk_research").exists():
    _parent_src = _parent_dir / "src"
    if str(_parent_src) not in sys.path:
        sys.path.insert(0, str(_parent_src))

DEFAULT_CHAT_NAME = "Nova Pesquisa"
MAX_TITLE_LENGTH = 28
MODO_PESQUISA = "integrated"

st.set_page_config(
    page_title="Desk Research System",
    page_icon="💬",
    layout="wide",
)


def clean_html_content(html: str) -> str:
    """Remove divs vazios e outros elementos desnecessários do HTML"""
    if not html:
        return html
    
    while True:
        new_html = re.sub(
            r'<div[^>]*>\s*</div>',
            '',
            html,
            flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
        )
        if new_html == html:
            break
        html = new_html
    
    html = re.sub(
        r'<div[^>]*style="[^"]*background-color:\s*transparent[^"]*"[^>]*>\s*</div>',
        '',
        html,
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
    )
    
    html = re.sub(
        r'<div[^>]*>\s*(<div[^>]*>\s*</div>\s*)+</div>',
        '',
        html,
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL
    )
    
    html = re.sub(r'\n\s*\n\s*\n+', '\n\n', html)
    
    return html.strip()


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


def format_result_for_chat(result: Any) -> str:
    """Formata o resultado para exibição no chat."""
    return extract_result_text(result)


def execute_research(user_text: str, selected_crews: list) -> str:
    """Executa a pesquisa usando o modo integrated."""
    try:
        system = DeskResearchSystem()
        
        if not selected_crews:
            return "❌ Erro: É necessário selecionar pelo menos um agente para executar a pesquisa."
        
        params = {
            "topic": user_text,
            "selected_modos": selected_crews,
            "params": {
                "max_papers": DEFAULT_MAX_PAPERS,
                "max_web_results": DEFAULT_MAX_WEB_RESULTS
            }
        }
        
        executor = system._executors.get(MODO_PESQUISA)
        if not executor:
            return f"❌ Executor para modo '{MODO_PESQUISA}' não encontrado."
        
        resultado = executor(**params)
        return format_result_for_chat(resultado)
        
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
        color: #1f77b5 !important;
    }

    /* ===== Container do chat ===== */
    .chat-wrap {
        max-width: 900px;
        margin: 0 auto;
        padding: 16px 12px 96px 12px;
    }

    /* ===== Bolhas ===== */
    .bubble {
        padding: 20px 20px;
        border-radius: 11px;
        margin: 0px 0;
        line-height: 1.5;
        font-size: 15px;
        max-width: 85%;
        border: 1px solid #e5e7eb;
        background-color: #ffffff;
    }
    
    /* ===== Formatação de Markdown dentro das bolhas ===== */
    .bubble h1, .bubble h2, .bubble h3, .bubble h4 {
        margin-top: 5px;
        margin-bottom: 5px;
        font-weight: bold;
        color: #0f172a;
    }
    
    .bubble h2 {
        font-size: 18px;
        border-bottom: 1px solid #e5e7eb;
        padding-bottom: 1px;
        margin-top: 12px;
    }
    
    .bubble h3 {
        font-size: 16px;
    }
    
    .bubble h4 {
        font-size: 15px;
    }
    
    .bubble p {
        margin-top: 1px;
        margin-bottom: 1px;
    }
    
    .bubble ul, .bubble ol {
        margin-top: 1px;
        margin-bottom: 1px;
        padding-left: 20px;
    }
    
    .bubble li {
        margin-top: 2px;
        margin-bottom: 2px;
    }
    
    .bubble strong {
        font-weight: 600;
    }
    
    .bubble em {
        font-style: italic;
    }
    
    /* Ocultar divs vazios que possam aparecer */
    .bubble div:empty,
    .bubble div[style*="background-color: transparent"]:empty {
        display: none !important;
    }
    
    .bubble div:has(> div:empty:only-child) {
        display: none !important;
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
        margin-bottom: 1px;
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
        border-radius: 11px;
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

    if "chat_order" not in st.session_state:
        st.session_state.chat_order = list(st.session_state.chats.keys())

    if "pending_research" not in st.session_state:
        st.session_state.pending_research = None

    if "system" not in st.session_state:
        st.session_state.system = DeskResearchSystem()
    
    if "selected_crews" not in st.session_state:
        st.session_state.selected_crews = ['web', 'consumer_hours']


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

st.markdown("---")
st.markdown("### Desk research (BETA) v.0.0.4")
st.caption("Selecione quais agentes deseja ativar para a pesquisa integrada")

modos_disponiveis = [k for k in MODE_CONFIG.keys() if k != "integrated"]

selected_crews = st.multiselect(
    "🤖 Selecione os agentes:",
    options=modos_disponiveis,
    default=st.session_state.selected_crews,
    format_func=lambda x: f"{MODE_CONFIG[x]['emoji']} {MODE_CONFIG[x]['nome']}",
    key=f"crews_select_{active}",
    help="Selecione pelo menos um agente para executar a pesquisa integrada"
)

if not selected_crews:
    st.warning("⚠️ Por favor, selecione pelo menos um agente para continuar.")

st.session_state.selected_crews = selected_crews
st.markdown("---")

st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)

for m in messages:
    role = m["role"]
    content = m["content"]

    who = "Você" if role == "user" else "Assistente"
    css_class = "user" if role == "user" else "assistant"
    meta = f'<div class="meta">{who} • {datetime.now().strftime("%H:%M")}</div>'

    try:
        html_content = markdown2.markdown(
            content,
            extras=['fenced-code-blocks', 'tables', 'strike']
        )
        html_content = clean_html_content(html_content)
    except Exception:
        escaped = html_module.escape(content)
        html_content = escaped.replace('\n', '<br>')

    st.markdown(
        f"""
        <div>
            {meta}
            <div class="bubble {css_class}">
                {html_content}
            </div>
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


def process_user_message(message: str, selected_crews: list) -> None:
    """Processa uma mensagem do usuário e adiciona resposta ao chat."""
    if not message.strip():
        return
    
    active_before = st.session_state.active_chat
    
    if not selected_crews:
        st.session_state.chats[active_before].append({
            "role": "assistant",
            "content": "❌ Erro: É necessário selecionar pelo menos um agente para executar a pesquisa."
        })
        st.rerun()
        return
    
    st.session_state.chats[active_before].append({"role": "user", "content": message.strip()})
    
    st.session_state.pending_research = {
        "message": message.strip(),
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
    selected_crews = pesquisa.get("selected_crews", [])
    
    if not selected_crews:
        st.session_state.chats[active_before].append({
            "role": "assistant", 
            "content": "❌ Erro: É necessário selecionar pelo menos um agente para executar a pesquisa integrada."
        })
        st.rerun()
        return
    
    with st.spinner("🔄 Processando pesquisa... Isso pode levar alguns minutos."):
        resposta = execute_research(message, selected_crews)
    
    active_after = maybe_autoname_chat(active_before, message)
    st.session_state.chats[active_after].append({"role": "assistant", "content": resposta})
    
    bump_chat_to_top(active_after)
    st.rerun()


if send and user_text.strip():
    if not selected_crews:
        st.error("⚠️ Por favor, selecione pelo menos um agente antes de enviar.")
    else:
        process_user_message(user_text.strip(), selected_crews)

if st.session_state.pending_research:
    execute_pending_research()
