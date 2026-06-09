from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa


def get_snapshot_weights(n):
    if hasattr(n, "snapshot_weightings") and "objective" in n.snapshot_weightings.columns:
        return n.snapshot_weightings["objective"]
    return pd.Series(1.0, index=n.snapshots)


def reduce_snapshots(n, snapshot_step: int):
    if snapshot_step <= 1:
        return n

    original_n = len(n.snapshots)
    selected = n.snapshots[::snapshot_step]

    print(f"Reducing snapshots: {original_n} -> {len(selected)} using snapshot_step={snapshot_step}")

    n.set_snapshots(selected)

    # Keep annual scaling roughly consistent after sampling
    for col in n.snapshot_weightings.columns:
        n.snapshot_weightings[col] = n.snapshot_weightings[col] * snapshot_step

    return n


def add_co2_cap(n, cap_tonnes: float):
    name = "CO2Limit"

    if name in n.global_constraints.index:
        n.remove("GlobalConstraint", name)

    n.add(
        "GlobalConstraint",
        name,
        type="primary_energy",
        carrier_attribute="co2_emissions",
        sense="<=",
        constant=float(cap_tonnes),
    )


def calculate_generator_emissions(n):
    if not hasattr(n, "generators_t") or n.generators_t.p.empty:
        return float("nan")

    if "co2_emissions" not in n.carriers.columns:
        return float("nan")

    weights = get_snapshot_weights(n)
    dispatch_mwh = n.generators_t.p.mul(weights, axis=0)

    carrier_to_co2 = n.carriers["co2_emissions"]
    gen_carrier = n.generators["carrier"]
    gen_eff = n.generators["efficiency"].replace(0, np.nan).fillna(1.0)

    gen_co2_intensity = gen_carrier.map(carrier_to_co2).fillna(0.0) / gen_eff
    gen_co2_intensity = gen_co2_intensity.reindex(dispatch_mwh.columns).fillna(0.0)

    return float(dispatch_mwh.mul(gen_co2_intensity, axis=1).sum().sum())


def generation_by_carrier(n):
    if not hasattr(n, "generators_t") or n.generators_t.p.empty:
        return {}

    weights = get_snapshot_weights(n)
    dispatch_mwh = n.generators_t.p.mul(weights, axis=0)
    carriers = n.generators["carrier"].reindex(dispatch_mwh.columns)

    out = dispatch_mwh.T.groupby(carriers).sum().T.sum(axis=0)

    return {str(k): float(v) for k, v in out.items()}


def expansion_cost(n, table_name, nominal_col="p_nom"):
    df = getattr(n, table_name)

    opt_col = f"{nominal_col}_opt"
    if opt_col not in df.columns or "capital_cost" not in df.columns:
        return 0.0, 0.0

    existing = pd.to_numeric(df[nominal_col], errors="coerce").fillna(0.0)
    optimized = pd.to_numeric(df[opt_col], errors="coerce").fillna(existing)
    added = (optimized - existing).clip(lower=0.0)

    cap_cost = pd.to_numeric(df["capital_cost"], errors="coerce").fillna(0.0)
    added_cost = added * cap_cost

    return float(added.sum()), float(added_cost.sum())


def read_reference_emissions(path):
    with Path(path).open("r", encoding="utf-8") as f:
        data = json.load(f)
    return float(data["co2_emissions_tonnes"])


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--scenario", required=True)
    parser.add_argument("--baseline", default="results/baseline.nc")
    parser.add_argument("--out-dir", default="results")
    parser.add_argument("--solver", default="highs")

    parser.add_argument("--no-co2-cap", action="store_true")
    parser.add_argument("--cap-frac", type=float, default=None)
    parser.add_argument("--reference-json", default=None)
    parser.add_argument("--cap-tonnes", type=float, default=None)

    parser.add_argument("--snapshot-step", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    baseline_path = Path(args.baseline)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading baseline: {baseline_path}")
    n = pypsa.Network(baseline_path)

    n = reduce_snapshots(n, args.snapshot_step)

    cap_tonnes = None

    if args.no_co2_cap:
        print("No CO2 cap will be applied.")
    elif args.cap_tonnes is not None:
        cap_tonnes = float(args.cap_tonnes)
        print(f"Using absolute CO2 cap: {cap_tonnes:,.3f} tonnes")
        add_co2_cap(n, cap_tonnes)
    elif args.cap_frac is not None:
        if args.reference_json is None:
            raise ValueError("--reference-json is required when using --cap-frac")
        ref_emissions = read_reference_emissions(args.reference_json)
        cap_tonnes = ref_emissions * args.cap_frac
        print(f"Reference emissions: {ref_emissions:,.3f} tonnes")
        print(f"CO2 cap fraction: {args.cap_frac}")
        print(f"CO2 cap: {cap_tonnes:,.3f} tonnes")
        add_co2_cap(n, cap_tonnes)
    else:
        raise ValueError("Use one of --no-co2-cap, --cap-tonnes, or --cap-frac with --reference-json")

    if args.dry_run:
        print("Dry run only. No optimization will be solved.")
        print(n)
        print(n.global_constraints)
        return

    solver_options = {}

    if args.solver == "highs":
        solver_options = {
            "solver": "ipm",
            "run_crossover": "on",
            "threads": 4,
            "parallel": "on",
            "primal_feasibility_tolerance": 1e-5,
            "dual_feasibility_tolerance": 1e-5,
            "ipm_optimality_tolerance": 1e-4,
        }

    print(f"Solving scenario {args.scenario} with solver={args.solver}")
    print(f"Solver options: {solver_options}")

    status = n.optimize(
        solver_name=args.solver,
        solver_options=solver_options,
    )

    print("Optimize status:", status)

    out_nc = out_dir / f"{args.scenario}.nc"
    out_json = out_dir / f"{args.scenario}.json"

    n.export_to_netcdf(out_nc)

    gen_added_mw, gen_added_cost = expansion_cost(n, "generators", "p_nom")
    storage_added_mw, storage_added_cost = expansion_cost(n, "storage_units", "p_nom")
    link_added_mw, link_added_cost = expansion_cost(n, "links", "p_nom")

    summary = {
        "scenario": args.scenario,
        "baseline": str(baseline_path),
        "output_nc": str(out_nc),
        "snapshot_step": args.snapshot_step,
        "snapshots": int(len(n.snapshots)),
        "co2_cap_tonnes": cap_tonnes,
        "co2_emissions_tonnes": calculate_generator_emissions(n),
        "objective_total_annual_system_cost": float(getattr(n, "objective", np.nan)),
        "generator_added_capacity_MW": gen_added_mw,
        "generator_added_annualized_cost": gen_added_cost,
        "storage_added_capacity_MW": storage_added_mw,
        "storage_added_annualized_cost": storage_added_cost,
        "transmission_link_added_capacity_MW": link_added_mw,
        "transmission_link_added_annualized_cost": link_added_cost,
        "generation_MWh_by_carrier": generation_by_carrier(n),
        "buses": int(len(n.buses)),
        "generators": int(len(n.generators)),
        "links": int(len(n.links)),
        "storage_units": int(len(n.storage_units)),
        "solver": args.solver,
        "solver_options": solver_options,
    }

    with out_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Saved network: {out_nc}")
    print(f"Saved summary: {out_json}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
