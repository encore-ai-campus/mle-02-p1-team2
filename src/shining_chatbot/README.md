# Shining chatbot source snapshot

This package is standalone and is not wired into the repository root streamlit_app.py.

The app stores its field data locally. Its document-search bridge also depends on a separate SANUP-P checkout containing src/retriever.py, src/rag_chain.py, the corpus metadata and chunks under data/personal/corpus/, and chroma_db/personal/chroma.sqlite3.

Set SANUP_P_ROOT to the absolute path of that checkout before starting the app. For example, in WSL:

    export SANUP_P_ROOT=/home/lee/workspace/SANUP-P
    PYTHONPATH=src python -m streamlit run src/shining_chatbot/app.py

The external checkout must have its own virtual environment. The bridge uses .venv/bin/python on Linux/WSL and .venv/Scripts/python.exe on Windows. It does not fall back to the system Python. When SANUP_P_ROOT is unset, the historical Windows default C:\SANUP-P is retained.

Run the standalone path tests from the repository root with:

    PYTHONPATH=src python3 -m unittest discover -s src/shining_chatbot/tests -v
