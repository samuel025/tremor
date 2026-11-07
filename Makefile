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
sandbox-test:
	cd contract && cargo near build non-reproducible-wasm --no-abi && cd sandbox && cargo test -- --nocapture --test-threads=1
demo:
	python3 scripts/demo.py
replay:
	python3 scripts/replay.py
verify-onchain:
	python3 scripts/verify_onchain.py
