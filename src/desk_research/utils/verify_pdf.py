
import sys
import os
from pathlib import Path

sys.path.append(os.path.abspath("src"))

try:
    from desk_research.utils.pdf_exporter import markdown_to_pdf
except ImportError as e:
    pass
except OSError as e:
    print(f"   [WARNING] WeasyPrint dependencies missing: {e}")

try:
    dummy_md = "# Title\n\n## Subtitle\n\nTest content."
    md_path = Path("test_report.md")
    
    from desk_research.utils.reporting import export_report
    
    result = dummy_md
    
    paths = export_report(result, "Debug Topic", prefix="debug")
    pdf_path = paths.get('pdf_path')
    
    if pdf_path and os.path.exists(pdf_path):
        print(f"   [OK] PDF Generated at: {pdf_path}")
    else:
        print(f"   [ERROR] PDF file not found at: {pdf_path}")
    
except Exception as e:
    import traceback
    traceback.print_exc()
