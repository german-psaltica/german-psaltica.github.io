HUGO ?= hugo
PYTHON ?= python3
JOBS ?= 6
PORT ?= 1414

.PHONY: all build generate serve clean

all: build

generate:
	$(PYTHON) scripts/build_library.py --jobs $(JOBS)

build: generate
	$(HUGO) --minify --cleanDestinationDir

serve: generate
	$(HUGO) server --bind 127.0.0.1 --port $(PORT) --disableFastRender

clean:
	rm -rf public resources .hugo_build.lock
