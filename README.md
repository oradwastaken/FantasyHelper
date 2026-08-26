# FantasyHelper


Based on Coreyjs's [nhl-api-py](https://github.com/coreyjs/nhl-api-py) package and mattdodge's [yahoofantasy](https://github.com/mattdodge/yahoofantasy) packages. All package dependencies are managed using uv.

---

## Installation

1. **Install uv**  
   Follow instructions at [uv installation](https://docs.astral.sh/uv/getting-started/installation/).

2. **Sync dependencies**  
   From the project root, run:
   ```bash
   uv sync
   ```
   This installs all dependencies and links the project (fantasyhelper) in editable mode.
3. **Start Jupyter**
    Launch with:
    ```bash
    uv run jupyter notebook
    ```
   
    Make sure the notebook kernel is set to the `uv` environment created for this project (usually located in .venv/). If you don’t see it, you can add it manually:
    ```bash
    uv run python -m ipykernel install --user --name=fantasyhelper
   ```

    Then, open jupyter notebook:
    ```
    uv run jupyter notebook
    ```

    The app's core functionality is in [main.ipynb](main.ipynb).

## Rankings workflow

Edit [config.yaml](config.yaml) with the current Yahoo league, season, schedule, and
Google projections-sheet details. Build CSV reports from the local HDF5 snapshot with:

```bash
uv run fantasyhelper build
```

To include projections, create a Google OAuth desktop client JSON file at the configured
credentials path and run `uv run fantasyhelper build --with-projections`. The first use
opens a browser sign-in flow. Publish all reports to a new (or configured existing) Google
Sheet with `uv run fantasyhelper publish --with-projections`.
