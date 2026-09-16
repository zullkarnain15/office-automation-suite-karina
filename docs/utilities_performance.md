# Utilities performance checks

Run commands from the repository root with the application's Python environment.
The benchmark creates synthetic Excel/TXT inputs and runs complete core jobs for
Attachment Consolidation (Excel and TXT), Comparison Result, and Att Data Repair.
It does not connect to the active database, start the UI, or build an EXE.
Input generation is excluded from job timing. Application logging modules may
initialize their usual logger; benchmark job outputs are temporary.

```powershell
python -m tools.benchmark_utilities --rows 5000 --repeat 3 --compare --output .codex_tmp/utilities-timing.json
python -m tools.benchmark_utilities --rows 1500 --repeat 1 --compare --memory --output .codex_tmp/utilities-memory.json
python -m tools.benchmark_utilities --rows 5000 --repeat 1 --profile --output .codex_tmp/utilities-profile.json
```

Each output filename must be new. Inputs and job outputs are created under a
unique temporary directory and removed afterward. `--work-root` can select an
existing writable folder, including a network share; only a new temporary child
is used. Network performance has not been measured in the local verification.
The default data has distinct synthetic NIKs, valid records, and a repeated date.
It is a reproducible workload, not a representation of every production dataset.

## Reading the results

- `median_seconds` measures core job wall time, including validation within the
  engine, processing, TXT/Excel writes, and file audit artifacts. It excludes UI
  orchestration and database history. Repair also includes discovery and the
  reader call used in preflight, using one content-verified reader.
- `stages_seconds` contains disjoint measured stages. The remaining time is
  reported as `other_including_validation_and_audit_seconds`.
- `--compare` alternates reference and optimized jobs within the same process.
  Reference functions preserve the stage-one style setters and output-path
  mapping. Other code is shared. It does not compare against an old executable.
  Comparison Result uses its existing writer in both variants because the
  candidate style cache did not improve its measured performance.
- `--profile` and `--memory` run additional jobs. Their overhead is excluded from
  the ordinary timing samples. Profile cumulative times overlap and must not be
  added together.
- `peak_python_allocations_mib` is the peak of allocations tracked by
  `tracemalloc` during the separate job. It is **not total process RAM** and does
  not fully account for native allocations in XML/ZIP libraries.
- Python/platform/openpyxl versions and source hashes are recorded. Compare
  equal row counts and comparable environments; inspect individual samples as
  well as medians. Small differences can be timing noise.

## Output equivalence gate

```powershell
python -m pytest tests/test_utilities_report_equivalence.py tests/test_utilities_optimization.py -q
```

These checks compare exact TXT bytes and report values, cell data types, number
formats, fills, fonts, borders, alignments, protection, column widths, freeze
panes, and filters. Worksheet style IDs are workbook-local, so semantic styles
are compared rather than IDs or ZIP bytes. Test jobs fix generated names/times
where necessary; source dates and times are never masked. The consolidation
comparison normalizes only the two output-root paths from isolated test jobs.

Mixed fixtures cover valid rows, leading zeros, repaired data, anomalies, and
multiple TXT files. Separate existing suites cover cancellation, errors,
duplicates, and collisions. Speed is not a pytest assertion: a slower machine
must not cause a correctness test to fail.

The style cache is local to one worksheet, includes each cell's original
date/time style, and copies style arrays before assignment. It uses openpyxl's
internal `_style` representation; rerun the equivalence suite when upgrading
openpyxl. Shared fill constants must remain unchanged during a report write.

## Local measurements, 2026-09-09

5,000 synthetic rows per input, three alternating runs per variant, local disk,
without profiler or tracemalloc overhead in the timing samples:

| Core job | Stage-one reference median | Retained optimization median |
| --- | ---: | ---: |
| Attachment Consolidation, Excel | 2.380 s | 2.140 s |
| Attachment Consolidation, TXT | 1.352 s | 1.357 s |
| Att Data Repair, including discovery/preflight reads | 16.252 s | 14.641 s |

The TXT difference is too small to call an end-to-end improvement. The mapping
stage itself improved in both consolidation modes. Comparison's style-cache
candidate was slower and was removed; its existing writer remains in place.
These results do not establish production or network-share throughput.

A separate 1,500-row tracemalloc run measured approximately 3.50 MiB for the
repair reference and 3.69 MiB with cached styles. The optimization trades some
Python allocation overhead for faster report writing; it is not a memory
reduction. Consolidation measured approximately 1.49 MiB for Excel and 1.24 MiB
for TXT in both variants. Native-library memory is not fully included.
