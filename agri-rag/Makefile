.PHONY: install test ingest serve eval eval-retrieval
install:; pip install -r requirements-dev.txt
test:; python -m pytest -q
ingest:; python -m agri_rag.cli ingest --reset
serve:; python -m agri_rag.cli serve
eval:; python -m agri_rag.evaluation.run --judge
eval-retrieval:; python -m agri_rag.evaluation.run --retrieval-only
