# California Grid Decarbonization and Costs — PyPSA-USA 2045

A capacity expansion modeling study of the Western Interconnection under varying CO₂ emissions caps in 2045, with California-specific analysis of generation mix, transmission build-out, and decarbonization costs. Developed as a course project for ER 254 (Energy and Society) at UC Berkeley, Spring 2026.

---

## Research Question

What are the costs of decarbonizing the California electric grid at different emissions levels while meeting projected 2045 demand?

---

## Key Findings

**Cost curve is nonlinear.** System costs for the Western Interconnection run $10–16 billion USD to achieve a fully decarbonized grid. The first 50% of emission reduction is achievable at relatively low cost; the last 5% toward net zero is the most cost-intensive. This suggests increased policy incentives may be needed to close the final gap.

**Transmission expansion reduces net-zero cost by ~37%.** Allowing transmission infrastructure to expand enables cheaper renewables in high-resource states to serve neighboring load centers. Without it, nodes must build local generation, which shifts the mix toward nuclear and drives up total cost.

**Onshore wind dominates in all scenarios.** Wind is the primary generation technology across every emissions cap level, particularly when transmission is extendable. This contrasts with prior California-specific studies that projected solar to dominate. The model favors wind because it is cost-effective to build in high-resource regions and export via transmission.

**No new battery storage is built by the optimizer.** Across all 10 scenarios, the model adds zero battery capacity beyond the 18 existing units. Wind generation's relative dispatchability appears to reduce the marginal value of storage under these assumptions.

**California is a net energy exporter but a net carbon importer.** The state exports low-carbon renewable electricity while importing fossil-based power from neighboring states — primarily Arizona (CCGT gas) and Oregon, with smaller contributions from Utah and Nevada.

**Demand growth of 10% raises costs 25–40%.** A sensitivity analysis shows that moderate demand growth significantly offsets decarbonization gains, highlighting the importance of demand-side management alongside supply-side investment.

---

## Scenarios

Two families of scenarios, each run at five CO₂ cap levels:

| Scenario family | Description |
|---|---|
| **Family A — Extendable transmission** | Transmission infrastructure can be expanded by the optimizer |
| **Family B — Fixed transmission** | Transmission is held at current capacity |

CO₂ cap levels: **100%** (baseline BAU), **50%**, **20%**, **5%**, **0%** of baseline emissions.

A demand sensitivity analysis (+10% load) was applied to the extendable transmission family.

---

## Model

Built on [PyPSA-USA](https://github.com/PyPSA/pypsa-usa), an open-source capacity expansion model for the Western Interconnection.

- **Network:** Reeds Western network, 33 buses (4 in California)
- **Optimization horizon:** 2045, 12 representative days (15th of each month), hourly resolution (288 snapshots)
- **Solver:** HiGHS
- **Demand forecast:** NREL Electrification Futures Study 2021, moderate electrification scenario
- **Cost assumptions:** NREL Annual Technology Baseline (ATB) 2024, moderate projections
- **Renewable profiles:** GODEEEP hourly renewable generation data for the Western US
- **Generator data:** EIA Form 860

CCS is excluded. Carbon tax is not modeled. Batteries are modeled as 4-hour and 8-hour units.

---

## Project Structure

```
pypsa-ca-grid-2045/
├── scripts/
│   ├── run_scenario.py              # Main entry point — applies CO₂ cap to baseline network
│   ├── scenario_comparison.py       # Cross-scenario analysis
│   ├── summary_*.py                 # KPI and generation summary scripts
│   ├── plot_*.py                    # Visualization scripts
│   ├── build_*.py                   # PyPSA-USA network build scripts (Snakemake)
│   ├── retrieve_*.py                # Data retrieval scripts
│   ├── patch_config_2045_*.py       # 2045 config patches
│   └── opts/                        # Policy constraint modules
├── config/
│   └── policy_constraints/          # Emissions limits, RPS, PRM, transmission limits
├── results/
│   ├── A_co2_00.nc / .json          # 0% emissions cap results
│   ├── A_co2_05.nc / .json          # 5% cap
│   ├── A_co2_20.nc / .json          # 20% cap
│   ├── A_co2_50.nc / .json          # 50% cap
│   ├── A_co2_100.nc / .json         # Baseline (100%)
│   ├── baseline.nc                  # Pre-optimization network
│   ├── cost_dictionary.xlsx         # Technology cost inputs
│   └── cost_sourcing_memo.md        # Cost and fuel price assumptions
├── data_analysis_testing.py         # Post-processing and visualization (Colab export)
└── requirements.txt
```

---

## Quickstart

**Run a scenario against the baseline network:**

```bash
python scripts/run_scenario.py \
    --scenario A_co2_50 \
    --baseline results/baseline.nc \
    --cap-frac 0.50 \
    --reference-json results/A_co2_100.json \
    --solver highs
```

Default output directory is `results/`. Use `--dry-run` to validate inputs without solving.

**Rebuild the full network** (requires Snakemake and the PyPSA-USA workflow files — not included here):

```bash
snakemake -j4
```

**Post-processing and figures:**

Set the `DATA_ROOT_DIR` environment variable to point at your local data directory, then run `data_analysis_testing.py`.

---

## Data Sources

| Data | Source |
|---|---|
| Demand forecast | NREL Electrification Futures Study (EFS) 2021 |
| Technology costs | NREL ATB 2024 |
| Renewable generation profiles | GODEEEP (Zenodo, 2024) |
| Existing generators | EIA Form 860 |
| Fuel prices | PyPSA-USA processed (NERC, CAISO, EIA, NREL) |

---

## Dependencies

```bash
pip install -r requirements.txt
```

Key packages: `pypsa`, `atlite`, `linopy`, `xarray`, `pandas`, `numpy`, `matplotlib`, `cartopy`, `highspy`.

A linear solver is required. HiGHS is the default (`pip install highspy`); GLPK is used by the test suite.

---

## References

- California Executive Order B-55-18: Carbon Neutrality by 2045
- NREL ATB 2024: [atb.nrel.gov](https://atb.nrel.gov/electricity/2024b/data)
- NREL Electrification Futures Study (EFS) 2021
- GODEEEP renewable generation data: [doi.org/10.5281/zenodo.13717258](https://doi.org/10.5281/zenodo.13717258)
- EIA Form 860: [eia.gov/electricity/data/eia860](https://www.eia.gov/electricity/data/eia860/)
- PyPSA-USA: [github.com/PyPSA/pypsa-usa](https://github.com/PyPSA/pypsa-usa)
