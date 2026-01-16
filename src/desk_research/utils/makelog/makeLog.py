import json
from pathlib import Path
from typing import Any, Dict

log_path = Path(__file__).parent


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if hasattr(obj, 'raw') or hasattr(obj, 'tasks_output'):
            result = {}
            if hasattr(obj, 'raw'):
                result['raw'] = obj.raw
            if hasattr(obj, 'tasks_output'):
                result['tasks_output'] = [
                    self.default(task) if not isinstance(task, (str, int, float, bool, type(None), list, dict))
                    else (self._process_list(task) if isinstance(task, list) else task)
                    for task in obj.tasks_output
                ]

            for attr in ['pydantic', 'tasks', 'agents']:
                if hasattr(obj, attr):
                    attr_value = getattr(obj, attr)
                    if not isinstance(attr_value, (str, int, float, bool, type(None))):
                        result[attr] = self.default(attr_value)
                    else:
                        result[attr] = attr_value
            return result if result else str(obj)
        
        if hasattr(obj, 'model_dump'):
            try:
                return obj.model_dump()
            except Exception:
                pass
        
        if hasattr(obj, 'dict'):
            try:
                return obj.dict()
            except Exception:
                pass
        
        if hasattr(obj, '__dict__'):
            try:
                return {k: self.default(v) for k, v in obj.__dict__.items()}
            except Exception:
                pass
        
        return str(obj)
    
    def _process_list(self, lst: list) -> list:
        return [
            self.default(item) if not isinstance(item, (str, int, float, bool, type(None), list, dict))
            else (self._process_list(item) if isinstance(item, list) else item)
            for item in lst
        ]


def generate_files(file_path: str, content: str) -> None:
    Path(file_path).write_text(content, encoding='utf-8')


def make_log(props: Dict[str, Any]) -> None:
    content = props.get('content')
    log_name = props.get('logName')
    
    if content is not None and not isinstance(content, str):
        try:
            content = json.dumps(content, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
        except (TypeError, ValueError) as e:
            content = json.dumps({"error": "Failed to serialize", "content": str(content)}, ensure_ascii=False, indent=2)
    elif content is None:
        content = json.dumps(None)
    
    log_file_path = log_path / f"{log_name}.json"
    generate_files(str(log_file_path), content)

