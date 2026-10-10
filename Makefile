.PHONY: run build test eval offline-test replay stop clean

# The project lives in track_2b/ (HackApertus template). This file only forwards the targets.
run build test eval offline-test replay stop clean:
	$(MAKE) -C track_2b $@
