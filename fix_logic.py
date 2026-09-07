import re

with open('backend/squad_logic.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r'@st\.cache_data[^\n]*\n', '', text)
text = text.replace('import streamlit as st\n', '')
text = text.replace('st.error', 'print')
text = text.replace('from betting_engine', 'from backend.betting_engine')
text = text.replace('from data import', 'from backend.data import')

import re
text = re.sub(r'from theme import \([\s\S]*?\)', 'def fmt_num(val, fmt=".1f"):\n    try:\n        return format(float(val), fmt)\n    except (ValueError, TypeError):\n        return str(val)\n', text)

with open('backend/squad_logic.py', 'w', encoding='utf-8') as f:
    f.write(text)

