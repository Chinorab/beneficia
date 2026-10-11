.PHONY: run build test eval offline-test replay stop clean

IMAGE ?= beneficia:latest
NAME  ?= beneficia
PORT  ?= 8080
DATA  := $(CURDIR)/data
# Optional: limit the evaluation to some cases, e.g. make eval CASES="case01_direct_de case04_pact_de"
CASES ?=
ONLY  := $(if $(CASES),--only $(CASES),)

# Build the image (downloads the model once, about 5 GB) and start the local interface.
# The interface is published on 127.0.0.1 only. Case folders and results live in ./data.
run: build
	@echo "Beneficia will be available on http://127.0.0.1:$(PORT) once the model has loaded."
	docker run --rm --name $(NAME) -p 127.0.0.1:$(PORT):8080 -v "$(DATA):/data" $(IMAGE) web

build:
	docker build --load -t $(IMAGE) .

# Unit and integration tests inside the image (no model needed).
test: build
	docker run --rm --network none $(IMAGE) test

# Batch evaluation of data/cases, results in data/output/eval/summary.json.
eval: build
	docker run --rm -v "$(DATA):/data" $(IMAGE) eval $(ONLY)

# Air-gap proof: the whole pipeline runs in a container without any network interface.
offline-test: build
	docker run --rm --network none -v "$(DATA):/data" $(IMAGE) offline-check $(ONLY)

# Reproduce the reported scores in seconds from the recorded model outputs in data/results (no model, no network).
replay: build
	docker run --rm --network none -v "$(DATA):/data" $(IMAGE) replay

stop:
	-docker stop $(NAME)

clean:
	-docker rmi $(IMAGE)
