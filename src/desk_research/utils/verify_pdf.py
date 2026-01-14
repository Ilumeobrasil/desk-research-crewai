
import sys
import os
from pathlib import Path

# Add src to pythonpath
sys.path.append(os.path.abspath("src"))

try:
    print("1. Testing Imports...")
    # Skip direct WeasyPrint import check here because we know it will fail on Windows without GTK
    # and we want to test the FALLBACK mechanism.
    import markdown2
    print(f"   [OK] markdown2 version: {markdown2.__version__}")
    from desk_research.utils.pdf_exporter import markdown_to_pdf
    print("   [OK] pdf_exporter imported")
except ImportError as e:
    # ... handle logic ...
    pass
except OSError as e:
    print(f"   [WARNING] WeasyPrint dependencies missing: {e}")
    print("   -> Continuing to test fallback logic...")

print("\n2. Testing PDF Generation (with Fallback)...")
try:
    dummy_md = "# Title\n\n## Subtitle\n\nTest content."
    md_path = Path("test_report.md")
    
    # We call export_report which has the fallback logic
    from desk_research.utils.reporting import export_report
    
    # Needs a mock result object or string
    result = dummy_md
    
    paths = export_report(result, "Debug Topic", prefix="debug")
    pdf_path = paths.get('pdf_path')
    
    if pdf_path and os.path.exists(pdf_path):
        print(f"   [OK] PDF Generated at: {pdf_path}")
    else:
        print(f"   [ERROR] PDF file not found at: {pdf_path}")
    
except Exception as e:
    print(f"   [ERROR] PDF Generation failed: {e}")
    import traceback
    traceback.print_exc()
