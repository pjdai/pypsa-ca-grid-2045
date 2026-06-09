# Cost and Technology Assumptions Memo

## Scope

This memo documents the cost, fuel price, and CO2 emissions factor assumptions for the final PyPSA-USA baseline network.

## Final baseline network

- Baseline network: results/baseline.nc
- Source network: resources/Run2045/western/elec_s75_c33_ec_lv1.0_REM-3h_E.nc
- Model framework: PyPSA-USA
- Interconnect: Western
- Planning horizon: 2045
- Spatial aggregation: simpl=75, clusters=33
- Temporal resolution: 3-hourly snapshots, 2920 snapshots per year

## Cost data

The model-ready carrier-level cost summary is:

- results/costs_overrides.csv

This table summarizes generator-level cost attributes from the final 2045 PyPSA-USA baseline network:

- capital_cost
- marginal_cost
- efficiency
- lifetime
- existing capacity
- extendability

The current values are extracted from the PyPSA-USA generated 2045 network and cost files.

For final reporting, these values should be compared against:

- NREL ATB 2024
- Moderate scenario
- 2045 vintage, or the nearest available ATB projection year

## Fuel prices

Fuel price summaries are saved as:

- results/fuel_prices_summary.csv

The source files are:

- resources/Run2045/western/state_ng_power_prices.csv
- resources/Run2045/western/ba_ng_power_prices.csv
- resources/Run2045/western/state_coal_power_prices.csv

## CO2 emissions factors

CO2 emissions factors are saved as:

- results/emissions_factors.csv

These values are extracted from the PyPSA carrier table using the `co2_emissions` column where available.

## Notes

PyPSA `capital_cost` is generally an annualized model cost, often closer to USD/MW-year. NREL ATB CAPEX is commonly reported as overnight CAPEX, often USD/kW. Therefore, ATB CAPEX should be converted to USD/MW and annualized using a capital recovery factor before comparing with PyPSA capital_cost.
