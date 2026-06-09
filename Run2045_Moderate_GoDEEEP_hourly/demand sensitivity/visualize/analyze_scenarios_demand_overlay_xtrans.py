"""
analyze_scenarios_demand_overlay_xtrans.py

Compare Base xtrans scenarios against Demand +10% xtrans scenarios.

Inputs:
  results/A_co2_*_hourly_xtrans.{json,nc}
  results/Sensitivity_demand/S_demandp10_co2_*_xtrans.{json,nc}

Outputs:
  figures/Sensitivity_demand_overlay_xtrans/
"""

import json
import os
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pypsa

warnings.filterwarnings("ignore")

# Directories default to relative paths; override via environment variables.
BASE_RESULTS_DIR = Path(os.environ.get("BASE_RESULTS_DIR", "results"))
DEMAND_RESULTS_DIR = Path(os.environ.get("DEMAND_RESULTS_DIR", "results/Sensitivity_demand"))
FIGURES_DIR = Path(os.environ.get("FIGURES_DIR", "figures/Sensitivity_demand_overlay_xtrans"))
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

CA_BUSES = ["p8", "p9", "p10", "p11"]

# IMPORTANT: this version uses xtrans only. It does NOT use xtrans2.
FAMILIES = [
    {
        "family": "Base xtrans",
        "results_dir": BASE_RESULTS_DIR,
        "color": "#1565c0",
        "marker": "o",
        "linestyle": "-",
        "scenarios": [
            ("A_co2_100_hourly_xtrans", "100%"),
            ("A_co2_50_hourly_xtrans", "50%"),
            ("A_co2_20_hourly_xtrans", "20%"),
            ("A_co2_05_hourly_xtrans", "5%"),
            ("A_co2_00_hourly_xtrans", "0%"),
        ],
    },
    {
        "family": "Demand +10% xtrans",
        "results_dir": DEMAND_RESULTS_DIR,
        "color": "#d95f02",
        "marker": "s",
        "linestyle": "--",
        "scenarios": [
            ("S_demandp10_co2_100_xtrans", "100%"),
            ("S_demandp10_co2_50_xtrans", "50%"),
            ("S_demandp10_co2_20_xtrans", "20%"),
            ("S_demandp10_co2_05_xtrans", "5%"),
            ("S_demandp10_co2_00_xtrans", "0%"),
        ],
    },
]

CARRIER_COLORS = {
    "onwind": "#4575b4",
    "solar": "#f9a825",
    "offwind_floating": "#74add1",
    "nuclear": "#9c27b0",
    "hydro": "#26c6da",
    "CCGT": "#ef5350",
    "OCGT": "#ff7043",
    "CCGT-95CCS": "#ab47bc",
    "hydrogen_ct": "#26a69a",
    "coal": "#5d4037",
    "geothermal": "#66bb6a",
    "biomass": "#8d6e63",
    "oil": "#bdbdbd",
    "waste": "#e0e0e0",
}

CARRIER_LABELS = {
    "onwind": "Onshore Wind",
    "solar": "Solar PV",
    "offwind_floating": "Offshore Wind",
    "nuclear": "Nuclear",
    "hydro": "Hydro",
    "CCGT": "CCGT (Gas)",
    "OCGT": "OCGT (Gas)",
    "CCGT-95CCS": "CCGT w/ CCS",
    "hydrogen_ct": "Hydrogen CT",
    "coal": "Coal",
    "geothermal": "Geothermal",
    "biomass": "Biomass",
    "oil": "Oil",
    "waste": "Waste",
}


def get_weights(n):
    if "generators" in n.snapshot_weightings.columns:
        return n.snapshot_weightings["generators"]
    if "objective" in n.snapshot_weightings.columns:
        return n.snapshot_weightings["objective"]
    return pd.Series(1.0, index=n.snapshots)


def compute_bus_intensity(n):
    co2_factors = n.generators.carrier.map(n.carriers.co2_emissions).fillna(0)
    efficiency = n.generators["efficiency"].replace(0, np.nan).fillna(1.0)
    gen_intensity = co2_factors / efficiency

    gen_dispatch = n.generators_t.p
    gen_emissions_t = gen_dispatch.multiply(gen_intensity, axis=1)

    bus_generation = pd.DataFrame(0.0, index=n.snapshots, columns=n.buses.index)
    bus_emissions = pd.DataFrame(0.0, index=n.snapshots, columns=n.buses.index)

    for g in gen_dispatch.columns:
        bus = n.generators.loc[g, "bus"]
        bus_generation[bus] += gen_dispatch[g]
        bus_emissions[bus] += gen_emissions_t[g]

    bus_intensity = bus_emissions.div(bus_generation.replace(0, np.nan)).fillna(0.0)
    return bus_intensity, gen_emissions_t


def get_ca_metrics(n):
    bus_intensity, gen_emissions_t = compute_bus_intensity(n)
    weights = get_weights(n)

    ca_gens = n.generators[n.generators.bus.isin(CA_BUSES)]
    local_ts = gen_emissions_t[ca_gens.index].sum(axis=1)

    imp_em = pd.Series(0.0, index=n.snapshots)
    exp_em = pd.Series(0.0, index=n.snapshots)
    net_mwh = pd.Series(0.0, index=n.snapshots)

    if not n.links.empty and not n.links_t.p0.empty:
        for lk in n.links_t.p0.columns:
            b0 = n.links.loc[lk, "bus0"]
            b1 = n.links.loc[lk, "bus1"]
            flow = n.links_t.p0[lk]

            if b1 in CA_BUSES and b0 not in CA_BUSES:
                imp_em += flow.clip(lower=0) * bus_intensity[b0]
                net_mwh += flow.clip(lower=0)
            elif b0 in CA_BUSES and b1 not in CA_BUSES:
                exp_em += flow.clip(lower=0) * bus_intensity[b0]
                net_mwh -= flow.clip(lower=0)

    prod_em = (local_ts * weights).sum() / 1e6
    cons_em = ((local_ts + imp_em - exp_em) * weights).sum() / 1e6
    net_twh = (net_mwh * weights).sum() / 1e6

    new_builds = ca_gens[ca_gens.p_nom == 0]
    gen_mwh = n.generators_t.p[ca_gens.index].multiply(weights, axis=0).sum()
    ca_capex = (new_builds.capital_cost * new_builds.p_nom_opt.clip(lower=0)).sum()
    ca_opex = (gen_mwh * ca_gens.marginal_cost).sum()

    return {
        "ca_prod_mt": prod_em,
        "ca_cons_mt": cons_em,
        "ca_net_import_twh": net_twh,
        "ca_imp_em_mt": (imp_em * weights).sum() / 1e6,
        "ca_exp_em_mt": (exp_em * weights).sum() / 1e6,
        "ca_cost_b": (ca_capex + ca_opex) / 1e9,
    }


def load_one_scenario(results_dir, scenario_id, cap_label, family_label):
    json_path = results_dir / f"{scenario_id}.json"
    nc_path = results_dir / f"{scenario_id}.nc"

    if not json_path.exists():
        print(f"  Skipping {scenario_id}: JSON not found at {json_path}")
        return None

    with open(json_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    row = {
        "family": family_label,
        "scenario_id": scenario_id,
        "cap_label": cap_label,
        "co2_cap_mt": None if summary.get("co2_cap_tonnes") is None else summary["co2_cap_tonnes"] / 1e6,
        "western_emissions_mt": summary["co2_emissions_tonnes"] / 1e6,
        "western_cost_b": summary["objective_total_annual_system_cost"] / 1e9,
        "western_gen_twh": pd.Series({k: v / 1e6 for k, v in summary.get("generation_MWh_by_carrier", {}).items()}),
        "generator_added_gw": summary.get("generator_added_capacity_MW", np.nan) / 1000,
        "storage_added_gw": summary.get("storage_added_capacity_MW", np.nan) / 1000,
        "transmission_added_gw": summary.get("transmission_link_added_capacity_MW", np.nan) / 1000,
        "load_scale": summary.get("load_scale", 1.0),
        "extendable_transmission": summary.get("extendable_transmission", None),
        "ca_prod_mt": None,
        "ca_cons_mt": None,
        "ca_net_import_twh": None,
        "ca_imp_em_mt": None,
        "ca_exp_em_mt": None,
        "ca_cost_b": None,
    }

    if nc_path.exists():
        print(f"  Loading {scenario_id}")
        n = pypsa.Network(str(nc_path))
        row.update(get_ca_metrics(n))
    else:
        print(f"  JSON only, CA metrics unavailable: {scenario_id}")

    return row


def load_all_rows():
    rows = []
    print("\nLoading xtrans scenario families...")

    for fam in FAMILIES:
        print(f"\nFamily: {fam['family']}")
        for scenario_id, cap_label in fam["scenarios"]:
            row = load_one_scenario(fam["results_dir"], scenario_id, cap_label, fam["family"])
            if row is not None:
                rows.append(row)

    if not rows:
        raise RuntimeError("No scenarios loaded. Check file names and directories.")
    return rows


def rows_to_summary_df(rows):
    records = []
    for r in rows:
        records.append({
            "family": r["family"],
            "cap_label": r["cap_label"],
            "scenario_id": r["scenario_id"],
            "co2_cap_mt": r["co2_cap_mt"],
            "western_emissions_mt": r["western_emissions_mt"],
            "western_cost_b": r["western_cost_b"],
            "ca_prod_mt": r["ca_prod_mt"],
            "ca_cons_mt": r["ca_cons_mt"],
            "ca_net_import_twh": r["ca_net_import_twh"],
            "ca_cost_b": r["ca_cost_b"],
            "generator_added_gw": r["generator_added_gw"],
            "storage_added_gw": r["storage_added_gw"],
            "transmission_added_gw": r["transmission_added_gw"],
            "load_scale": r["load_scale"],
            "extendable_transmission": r["extendable_transmission"],
        })
    return pd.DataFrame(records)


def plot_western_cost_overlay(rows):
    fig, ax = plt.subplots(figsize=(9.5, 5.5))

    for fam in FAMILIES:
        fam_rows = [r for r in rows if r["family"] == fam["family"]]
        x = [r["western_emissions_mt"] for r in fam_rows]
        y = [r["western_cost_b"] for r in fam_rows]
        labs = [r["cap_label"] for r in fam_rows]

        ax.plot(
            x, y,
            marker=fam["marker"],
            linestyle=fam["linestyle"],
            color=fam["color"],
            linewidth=2.5,
            markersize=8,
            markerfacecolor="white",
            markeredgewidth=2,
            label=fam["family"],
        )

        for xx, yy, lab in zip(x, y, labs):
            ax.annotate(f" {lab}", (xx, yy), fontsize=9, color=fam["color"], va="center")

    ax.set_xlabel("Annual CO₂ Emissions — Western Interconnection (Mt)")
    ax.set_ylabel("Total System Cost ($B/year)")
    ax.set_title("Western Cost vs Emissions\nBase xtrans vs Demand +10% xtrans")
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.set_xlim(left=-2)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "xtrans_overlay_western_cost_vs_emissions.png", dpi=150, bbox_inches="tight")
    print("  Saved xtrans_overlay_western_cost_vs_emissions.png")
    plt.close(fig)


def plot_generation_mix_overlay(rows):
    all_carriers = set()
    for r in rows:
        all_carriers.update(r["western_gen_twh"].index)

    carriers = [
        c for c in CARRIER_COLORS
        if c in all_carriers and any(r["western_gen_twh"].get(c, 0) > 0.5 for r in rows)
    ]

    cap_order = ["100%", "50%", "20%", "5%", "0%"]
    x_base = np.arange(len(cap_order))
    bar_width = 0.36

    fig, ax = plt.subplots(figsize=(12.5, 6.5))

    for j, fam in enumerate(FAMILIES):
        fam_rows = {r["cap_label"]: r for r in rows if r["family"] == fam["family"]}
        x = x_base + (j - 0.5) * bar_width
        bottoms = np.zeros(len(cap_order))

        for carrier in carriers:
            values = [fam_rows[cap]["western_gen_twh"].get(carrier, 0) if cap in fam_rows else 0 for cap in cap_order]
            ax.bar(
                x, values, bar_width,
                bottom=bottoms,
                color=CARRIER_COLORS.get(carrier, "#999999"),
                edgecolor="white",
                linewidth=0.25,
                label=CARRIER_LABELS.get(carrier, carrier) if j == 0 else None,
            )
            bottoms += np.array(values)

        for xx, total in zip(x, bottoms):
            short = "Base" if fam["family"].startswith("Base") else "D+10"
            ax.text(xx, total + max(bottoms.max(), 1) * 0.01, short, ha="center", va="bottom", fontsize=8, rotation=90)

    ax.set_xticks(x_base)
    ax.set_xticklabels(cap_order)
    ax.set_xlabel("CO₂ cap scenario")
    ax.set_ylabel("Annual Generation (TWh)")
    ax.set_title("Western Generation Mix\nBase xtrans vs Demand +10% xtrans")
    ax.grid(True, alpha=0.3, axis="y")
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1), fontsize=9)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "xtrans_overlay_western_generation_mix.png", dpi=150, bbox_inches="tight")
    print("  Saved xtrans_overlay_western_generation_mix.png")
    plt.close(fig)


def plot_ca_emissions_overlay(rows):
    fig, ax = plt.subplots(figsize=(9.5, 5.5))

    for fam in FAMILIES:
        fam_rows = [
            r for r in rows
            if r["family"] == fam["family"] and r["ca_cons_mt"] is not None and r["ca_prod_mt"] is not None
        ]

        if not fam_rows:
            continue

        cons = [r["ca_cons_mt"] for r in fam_rows]
        prod = [r["ca_prod_mt"] for r in fam_rows]
        cost = [r["western_cost_b"] for r in fam_rows]
        labs = [r["cap_label"] for r in fam_rows]

        ax.plot(
            cons, cost,
            marker=fam["marker"],
            linestyle=fam["linestyle"],
            color=fam["color"],
            linewidth=2.3,
            markersize=8,
            markerfacecolor="white",
            markeredgewidth=2,
            label=f"{fam['family']} — CA consumption",
        )

        ax.plot(
            prod, cost,
            marker="x",
            linestyle=":",
            color=fam["color"],
            linewidth=1.8,
            markersize=7,
            label=f"{fam['family']} — CA production",
        )

        for xx, yy, lab in zip(cons, cost, labs):
            ax.annotate(f" {lab}", (xx, yy), fontsize=8, color=fam["color"], va="center")

    ax.set_xlabel("CA Annual CO₂ Emissions (Mt)")
    ax.set_ylabel("Western System Cost ($B/year)")
    ax.set_title("California Emissions vs Western Cost\nBase xtrans vs Demand +10% xtrans")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    ax.set_xlim(left=-0.3)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "xtrans_overlay_ca_emissions_vs_western_cost.png", dpi=150, bbox_inches="tight")
    print("  Saved xtrans_overlay_ca_emissions_vs_western_cost.png")
    plt.close(fig)


def plot_ca_trade_overlay(rows):
    valid = [r for r in rows if r["ca_net_import_twh"] is not None]
    if not valid:
        print("  Skipping xtrans_overlay_ca_trade.png — no CA data")
        return

    cap_order = ["100%", "50%", "20%", "5%", "0%"]
    x_base = np.arange(len(cap_order))
    width = 0.36

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.6))

    for j, fam in enumerate(FAMILIES):
        fam_rows = {r["cap_label"]: r for r in valid if r["family"] == fam["family"]}
        x = x_base + (j - 0.5) * width

        net_import = [fam_rows.get(cap, {}).get("ca_net_import_twh", np.nan) for cap in cap_order]
        imp_em = [fam_rows.get(cap, {}).get("ca_imp_em_mt", np.nan) for cap in cap_order]
        exp_em = [fam_rows.get(cap, {}).get("ca_exp_em_mt", np.nan) for cap in cap_order]

        ax1.bar(x, net_import, width, label=fam["family"], color=fam["color"], alpha=0.75)
        ax2.bar(x, imp_em, width, label=f"{fam['family']} imported", color=fam["color"], alpha=0.75)
        ax2.scatter(x, exp_em, marker="x", color=fam["color"], s=45, label=f"{fam['family']} exported")

    ax1.axhline(0, color="black", linewidth=0.8)
    ax1.set_xticks(x_base)
    ax1.set_xticklabels(cap_order)
    ax1.set_ylabel("Net imports (TWh/year)")
    ax1.set_title("CA Net Electricity Imports\n(+ = importer, − = exporter)")
    ax1.grid(True, alpha=0.3, axis="y")
    ax1.legend(fontsize=9)

    ax2.set_xticks(x_base)
    ax2.set_xticklabels(cap_order)
    ax2.set_ylabel("Mt CO₂/year")
    ax2.set_title("Carbon Embodied in CA Trade")
    ax2.grid(True, alpha=0.3, axis="y")
    ax2.legend(fontsize=8)

    fig.suptitle("California Electricity Trade\nBase xtrans vs Demand +10% xtrans", fontsize=13, y=1.03)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "xtrans_overlay_ca_trade.png", dpi=150, bbox_inches="tight")
    print("  Saved xtrans_overlay_ca_trade.png")
    plt.close(fig)


def main():
    rows = load_all_rows()
    summary_df = rows_to_summary_df(rows)

    print("\nLoaded scenarios:")
    print(summary_df[[
        "family",
        "cap_label",
        "scenario_id",
        "co2_cap_mt",
        "western_emissions_mt",
        "western_cost_b",
        "ca_prod_mt",
        "ca_cons_mt",
        "ca_net_import_twh",
        "transmission_added_gw",
        "storage_added_gw",
    ]].to_string(index=False))

    out_csv = FIGURES_DIR / "xtrans_overlay_summary.csv"
    summary_df.to_csv(out_csv, index=False)
    print(f"\nSaved summary CSV: {out_csv}")

    print("\nGenerating xtrans overlay plots...")
    plot_western_cost_overlay(rows)
    plot_generation_mix_overlay(rows)
    plot_ca_emissions_overlay(rows)
    plot_ca_trade_overlay(rows)

    print(f"\nDone. Xtrans overlay figures saved to: {FIGURES_DIR}")


if __name__ == "__main__":
    main()
