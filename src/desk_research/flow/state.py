from typing import Dict, Any, List
from pydantic import BaseModel


class DeskResearchState(BaseModel):
    topic: str = ""
    selected_crews: List[str] = []
    params: Dict[str, Any] = {}
    results: Dict[str, Any] = {}
    final_report: str = ""
    retry_count: int = 0
    feedback: str = ""


