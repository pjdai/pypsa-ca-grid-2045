from pathlib import Path

path = Path("scripts/build_renewable_profiles.py")
text = path.read_text(encoding="utf-8")

old = '''        logger.info("Calculate average distances.")
        layoutmatrix = (layout * availability).stack(spatial=["y", "x"])

        coords = cutout.grid[["x", "y"]]
        bus_coords = regions[["x", "y"]]

        average_distance = []
        centre_of_mass = []
        for bus in buses:
            row = layoutmatrix.sel(bus=bus).data
            nz_b = row != 0
            row = row[nz_b]
            co = coords[nz_b]
            distances = haversine(bus_coords.loc[bus], co)
            average_distance.append((distances * (row / row.sum())).sum())
            centre_of_mass.append(co.values.T @ (row / row.sum()))
'''

new = '''        logger.info("Calculate average distances.")
        layoutmatrix = (layout * availability).stack(spatial=["y", "x"])

        # Use the stacked spatial coordinates from layoutmatrix itself.
        # Do not use cutout.grid here because its length can differ from
        # the stacked layoutmatrix after exclusions / regional aggregation.
        spatial_index = layoutmatrix.indexes["spatial"]
        coords = pd.DataFrame(
            {
                "x": spatial_index.get_level_values("x").astype(float),
                "y": spatial_index.get_level_values("y").astype(float),
            },
            index=spatial_index,
        )

        bus_coords = regions[["x", "y"]]

        average_distance = []
        centre_of_mass = []
        for bus in buses:
            row = layoutmatrix.sel(bus=bus).values
            row = np.asarray(row).reshape(-1)

            nz_b = row != 0
            row = row[nz_b]
            co = coords.iloc[nz_b]

            if row.sum() == 0:
                average_distance.append(0.0)
                centre_of_mass.append(bus_coords.loc[bus].values)
                continue

            weights = row / row.sum()
            distances = haversine(bus_coords.loc[bus], co)
            average_distance.append((distances * weights).sum())
            centre_of_mass.append(co.values.T @ weights)
'''

if old not in text:
    raise SystemExit("Target block not found. Open the file and patch manually.")

path.write_text(text.replace(old, new), encoding="utf-8")
print("Patched:", path)
