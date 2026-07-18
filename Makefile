.PHONY: test demo clean

PYTHONPATH := src

test:
	PYTHONPATH=$(PYTHONPATH) python3 -m unittest discover -s tests -v

demo:
	PYTHONPATH=$(PYTHONPATH) python3 -m rewrite_converter generate-all examples/google-redirect.json -o generated

clean:
	find generated -type f -delete 2>/dev/null || true

