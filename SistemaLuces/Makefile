PYTHON := python3.11
LOCAL_UV_CACHE := $(CURDIR)/.cache/uv
LOCAL_TMP := $(CURDIR)/.tmp

.PHONY: verify
verify:
	@mkdir -p $(LOCAL_UV_CACHE) $(LOCAL_TMP)
	@UV_CACHE_DIR=$(LOCAL_UV_CACHE) uv lock --check --offline
	@TMPDIR=$(LOCAL_TMP) TZ=UTC LC_ALL=C PYTHONHASHSEED=0 $(PYTHON) -B -m unittest discover -s tests -t . -v
	@TMPDIR=$(LOCAL_TMP) TZ=UTC LC_ALL=C PYTHONHASHSEED=0 $(PYTHON) -B -m compileall -q src tests
	@TMPDIR=$(LOCAL_TMP) TZ=UTC LC_ALL=C PYTHONHASHSEED=0 $(PYTHON) -B -m tabnanny src tests
