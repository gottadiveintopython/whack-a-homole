.PHONY: run build_zipapp run_zipapp download_assets 
ASSETS = ./src/whack_a_homole/assets.sqlite3
ZIPAPP = ./dist/whack-a-homole.pyz

download_assets: $(ASSETS)
$(ASSETS):
	uv run python ./src/download_assets.py

run: $(ASSETS)
	uv run python ./src/main.py

build_zipapp: $(ZIPAPP)
$(ZIPAPP): $(ASSETS)
	mkdir --parents ./dist
	uv run --directory ./src zip --recurse-paths ../dist/whack-a-homole.pyz .

run_zipapp: $(ZIPAPP)
	uv run python $(ZIPAPP)
