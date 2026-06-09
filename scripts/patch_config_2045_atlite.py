from pathlib import Path
import yaml

cfg_path = Path("config/config.2045.atlite.yaml")

with cfg_path.open("r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

# Use a separate run folder so old GoDEEEP/Moderate outputs are not mixed
cfg.setdefault("run", {})
cfg["run"]["name"] = "Run2045_Conservative_ERA5"

# Scenario settings
cfg.setdefault("scenario", {})
cfg["scenario"]["interconnect"] = ["western"]
cfg["scenario"]["planning_horizons"] = [2045]
cfg["scenario"]["simpl"] = [75]
cfg["scenario"]["clusters"] = [33]

# Cost setting: ATB Conservative
cfg.setdefault("costs", {})
cfg["costs"].setdefault("atb", {})
cfg["costs"]["atb"]["scenario"] = "Conservative"

# Solver setting
cfg.setdefault("solving", {})
cfg["solving"].setdefault("solver", {})
cfg["solving"]["solver"]["name"] = "appsi_highs"
cfg["solving"]["solver"]["options"] = "highs-default"

# Switch renewable profile generation to atlite
# These are the technologies that normally use weather-based CF profiles.
target_renewables = [
    "solar",
    "onwind",
    "offwind",
    "offwind_floating",
    "offwind_fixed",
]

renewable = cfg.get("renewable", {})
changed = []

for tech in target_renewables:
    if tech in renewable and isinstance(renewable[tech], dict):
        renewable[tech]["dataset"] = "atlite"
        changed.append(tech)

cfg["renewable"] = renewable

with cfg_path.open("w", encoding="utf-8") as f:
    yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)

print(f"Updated config written to: {cfg_path}")
print("Renewable technologies set to dataset='atlite':", changed)

if not changed:
    print("WARNING: No renewable technology blocks were changed.")
    print("Check the structure of config/config.2045.atlite.yaml manually.")
