# Research Method and Reproducibility Notes

## Scope

The review combined four evidence streams:

1. static inspection of the supplied XJCheck repository;
2. execution of its test suite and a real degraded CLI run;
3. corpus inventory, sidecar parsing and embedded-preview visual sampling over all supplied DWGs;
4. primary vendor documentation and targeted research on vector/graph/neuro-symbolic technical drawing extraction.

## Repository review procedure

- Unpacked the repository and inspected `README.md`, `progress.md`, `task_plan.md`, `docs/`, `src/`, configs and tests.
- Ran the repository test suite using `PYTHONPATH=.:src pytest -q` in a Python 3.12 environment.
- Traced the call chain from scanning/conversion through page routing, extractors, Pair generation, reporting and topology shadow.
- Inspected the location and responsibilities of `wire_topology.py`, `candidates.py`, `pairs.py`, page classifiers and report writers.

## Corpus review procedure

- Discovered project roots from DWG-containing directories.
- Parsed `.prj`, `LdDzbInfo.xml` and `AirSwitchClassSet.xml` sidecars.
- Verified DWG headers and page lists.
- Classified page titles and current route targets.
- Extracted the largest embedded DIB preview from every DWG as visual QC evidence.
- Selected representative pages across legacy wire diagrams, terminal tables, communication pages, backplates, operation-box pages, metering and time synchronization.

## Important boundary

The execution environment used for this review did not contain ODA File Converter,
RealDWG, ODA Drawings SDK or LibreDWG. Therefore, no claim is made that all 502
DWGs were entity-extracted in this environment. The supplied baseline runner is
the reproducible next step in the target ODA environment. Zero-entity results from
the local degraded run are explicitly classified as reader incompleteness, not
recognition accuracy.

## Search strategy

Search terms were grouped around:

- AutoCAD Electrical audit, wire network, signal source/destination, terminal and gap pointers;
- EPLAN check runs, connection update, interruption points and message management;
- Zuken E3 object-oriented connectivity, intelligent libraries, terminal plans and DRC;
- Siemens Capital logical/physical connectivity, topology and correct-by-construction DRC;
- ODA/RealDWG/ezdxf/LibreDWG reader capabilities;
- vector technical drawing graph learning, P&ID graph extraction and neuro-symbolic industrial compliance.

Vendor claims were used only to infer product principles and user-facing capability,
not proprietary implementation details. Dependency recommendations favor official
documentation. Research papers are treated as secondary evidence and are not used
to justify replacing deterministic geometry with an end-to-end model.
