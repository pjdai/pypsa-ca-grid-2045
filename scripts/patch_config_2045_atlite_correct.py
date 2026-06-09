from pathlib import Path
import yaml

cfg_path = Path("config/config.2045.atlite.yaml")

with cfg_path.open("r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

# Separate run name
cfg.setdefault("run", {})
cfg["run"]["name"] = "Run2045_Conservative_ERA5"

# Scenario settings
cfg.setdefault("scenario", {})
cfg["scenario"]["interconnect"] = ["western"]
cfg["scenario"]["planning_horizons"] = [2045]
cfg["scenario"]["simpl"] = [75]
cfg["scenario"]["clusters"] = [33]

# ATB Conservative
cfg.setdefault("costs", {})
cfg["costs"].setdefault("atb", {})
cfg["costs"]["atb"]["scenario"] = "Conservative"

# Solver
cfg.setdefault("solving", {})
cfg["solving"].setdefault("solver", {})
cfg["solving"]["solver"]["name"] = "appsi_highs"
cfg["solving"]["solver"]["options"] = "highs-default"

# Correct renewable dataset switch
cfg.setdefault("renewable", {})
cfg["renewable"]["dataset"] = "atlite"

# Weather year for atlite / ERA5
cfg["renewable_weather_years"] = [2019]

# GoDEEEP scenarios are irrelevant for atlite, but keep historical harmlessly
cfg["renewable_scenarios"] = ["historical"]

with cfg_path.open("w", encoding="utf-8") as f:
    yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)

print("Updated:", cfg_path)
print("run.name =", cfg["run"]["name"])
print("renewable.dataset =", cfg["renewable"]["dataset"])
print("renewable_weather_years =", cfg["renewable_weather_years"])
print("costs.atb.scenario =", cfg["costs"]["atb"]["scenario"])
print("solver =", cfg["solving"]["solver"]["name"])
