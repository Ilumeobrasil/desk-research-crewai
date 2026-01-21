# sitecustomize.py
import os

os.environ["LITELLM_DISABLE_LOGGING"] = "true"
os.environ["LITELLM_DISABLE_SPEND_TRACKING"] = "true"
os.environ["LITELLM_DISABLE_COLD_STORAGE"] = "true"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGCHAIN_CALLBACKS"] = "false"
