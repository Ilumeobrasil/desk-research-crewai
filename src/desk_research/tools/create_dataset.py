import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY") or os.getenv("ASIMOV_API_KEY")
BASE_URL = (os.getenv("BASE_URL") or os.getenv("ASIMOV_API_BASE") or "").rstrip("/")
DATASET = os.getenv("ASIMOV_DATASET", "consumer-hours-flow-dev")
MODEL = os.getenv("ASIMOV_DATASET_MODEL", "openai/text-embedding-ada-002")

if not API_KEY or not BASE_URL:
    raise SystemExit("Faltando API_KEY/BASE_URL (ou ASIMOV_API_KEY/ASIMOV_API_BASE).")

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Ocp-Apim-Subscription-Key": API_KEY,
    "x-api-key": API_KEY,
    "Content-Type": "application/json",
}

resp = requests.get(f"{BASE_URL}/api/application/datasets", headers=headers, timeout=60)
if resp.status_code != 200:
    raise SystemExit(1)

data = resp.json()
for it in data.get("items", []):
    if it.get("name") == DATASET:
        raise SystemExit(0)

payload = {"name": DATASET, "model": MODEL}
resp2 = requests.post(f"{BASE_URL}/api/application/datasets", headers=headers, json=payload, timeout=60)
