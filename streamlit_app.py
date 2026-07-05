# Legacy entrypoint retained for Streamlit Cloud compatibility.
# Use `streamlit run app.py` for the XAU/USD Streamlit Advisor.

from pathlib import Path

APP = Path(__file__).with_name('app.py')
exec(APP.read_text(encoding='utf-8'), globals())
