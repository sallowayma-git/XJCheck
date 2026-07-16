# Topology ground truth v1

This validation-only subset was frozen from project `P003` in `benchmark_split_v1.csv`.
It contains explicit connection-marker intersections, unmarked internal crossings, and exact
endpoint merges. Labels are based on local geometry plus marker evidence, not on Pair/Issue
counts. Held-out projects are excluded.

Matching identity is `sheet_id + decision_kind + reason_code + sorted source entity handles`.
Coordinates are review evidence and are not production branching inputs. Any label change must
record a manual review basis and increment the fixture version.
