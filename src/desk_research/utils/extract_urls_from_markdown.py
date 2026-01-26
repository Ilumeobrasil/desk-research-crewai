import re

def extract_urls_from_markdown(markdown_text: str) -> list[str]:
    urls = []
    pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    matches = re.findall(pattern, markdown_text)
    
    for _, url in matches:
        if url.startswith('http://') or url.startswith('https://'):
            urls.append(url)
    
    return urls