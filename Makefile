.PHONY: test fetch-usgs vectors
test:
	python3 -m unittest discover -s tests -v
vectors:
	python3 tests/gen_vectors.py
fetch-usgs:
	python3 scripts/fetch_usgs.py
sim:
	python3 sim/run_all.py && python3 sim/report.py
conformance-vectors:
	python3 tests/gen_conformance.py 200
conformance:
	cd contract && cargo test --test conformance -- --nocapture
test-rust:
	cd contract && cargo test -- --nocapture
build-wasm:
	cd contract && cargo build --target wasm32-unknown-unknown --release
