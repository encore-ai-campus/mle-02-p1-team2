# Shining chatbot source snapshot

This package is standalone and is not wired into the repository root streamlit_app.py.

The app's field and CSV features use local project files. SANUP-P document search requires a separate SANUP-P checkout with src/retriever.py, src/rag_chain.py, corpus metadata and chunks under data/personal/corpus/, and chroma_db/personal/chroma.sqlite3. It also needs that checkout's virtual environment. If these files are unavailable, field and CSV features continue to work; the app shows the missing relative paths in a collapsed setup panel.

Set SANUP_P_ROOT to the absolute path of the SANUP-P checkout before starting the app. For example, in WSL:

    export SANUP_P_ROOT=/path/to/SANUP-P
    PYTHONPATH=src python -m streamlit run src/shining_chatbot/app.py

The bridge uses .venv/bin/python on Linux/WSL and .venv/Scripts/python.exe on Windows. It does not fall back to the system Python. When SANUP_P_ROOT is unset, the historical Windows default C:\SANUP-P is retained.

Run the standalone path and setup tests from the repository root with:

    PYTHONPATH=src python3 -m unittest discover -s src/shining_chatbot/tests -v

The AppTest smoke checks are separate from the standard-library tests and require Python 3.12, Streamlit, and pandas. From the repository root, run them with the project virtual environment:

    PYTHONPATH=src .venv/bin/python -m unittest discover -s smoke_tests -v
