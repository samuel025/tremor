.PHONY: test fetch-usgs vectors
test:
	python3 -m unittest discover -s tests -v
vectors:
	python3 tests/gen_vectors.py
fetch-usgs:
	python3 scripts/fetch_usgs.py
