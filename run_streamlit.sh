#!/bin/bash
# Script para executar a interface Streamlit

# Ativar ambiente virtual se existir
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Executar Streamlit
streamlit run streamlit_app