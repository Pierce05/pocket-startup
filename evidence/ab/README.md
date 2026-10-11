# Pocket Startup: Stage 2c A/B Experiment Audit & Run Log

> **Reproduce Command:**
> ```bash
> python -m experiments.ab --repeats 4 --seed 42 --sleep 1.0
> ```

> [!NOTE]
> **Statistical Independence Caveat:** The statistical calculations (Wilson score 95% confidence intervals and Fisher's exact tests) treat runs as independent observations. However, each startup idea repeats 4 times and arms are paired by idea across the interleaved schedule. Consequently, reported p-values and confidence intervals are indicative rather than cluster-adjusted inferential tests.

## 1. Provenance & Prompt Verification

- **Model:** `gemini-3.5-flash-lite` `[CONFIG]`
- **Temperature:** `0.2` `[CONFIG]`
- **Random Seed:** `42` `[CONFIG]`
- **Git Commit Hash:** `3b5289639f46aa9e25d44eb530b12cedfd3f14f7` `[CONFIG]`
- **Schedule:** Interleaved arms `(baseline, improved, baseline, improved...)` with deterministic seed shuffle `[CONFIG]`
- **Repeats per Idea:** `4` `[CONFIG]`
- **Autopsy Execution:** Disabled (`autopsy=False`) across all runs `[CONFIG]`

### Exact Prompt SHA-256 Hashes
- **`BUILDER_SYSTEM_V1` SHA-256:** `f6c13a5c36b3b3206252cc7b5146e4afc888a397789377df31ce27d84975a92d`
- **Improved System Prompt (`BUILDER_SYSTEM_V1` + `winner.txt`) SHA-256:** `9e620aee8267cf136eb3b23b3ce51a195d373d26eef7f7f48eb159f088fee69c`
- **`RETRY_USER` SHA-256:** `fcc550840c10f567c41017720f1795271627190477f9b654c1cd2db72bfa14e8`
- **`winner.txt` Patch SHA-256:** `49156a531807280673be59af60163f3f8b5af05a470ab5262a4b74f510c8995c`

## 2. Cell Run ID Manifest

### Cell: HELD_OUT / BASELINE (N=20)
```text
20261011-090227-5cd8
20261011-090328-80a5
20261011-090412-05dc
20261011-090509-87a1
20261011-090540-16e2
20261011-090612-3647
20261011-090647-85b3
20261011-090725-bbed
20261011-090759-b3d6
20261011-090843-b42c
20261011-090923-dba0
20261011-090956-5f75
20261011-091035-1743
20261011-091109-56c7
20261011-091148-136c
20261011-091233-997c
20261011-091256-ce69
20261011-091342-10ce
20261011-091431-28d8
20261011-091506-b8a3
```

### Cell: HELD_OUT / IMPROVED (N=20)
```text
20261011-090258-e5ff
20261011-090359-2a28
20261011-090441-0d61
20261011-090529-67aa
20261011-090601-99dc
20261011-090634-4726
20261011-090709-9de9
20261011-090748-1999
20261011-090832-812d
20261011-090911-6c2b
20261011-090944-6273
20261011-091023-9009
20261011-091055-535a
20261011-091131-634c
20261011-091221-ab21
20261011-091245-56d5
20261011-091315-a55d
20261011-091418-0289
20261011-091453-7aba
20261011-091527-a51a
```

### Cell: TUNING / BASELINE (N=20)
```text
20261011-085146-cf2d
20261011-085235-084f
20261011-085305-3128
20261011-085336-cec5
20261011-085400-2d0b
20261011-085434-ba73
20261011-085505-0473
20261011-085539-f726
20261011-085609-96ef
20261011-085643-71ac
20261011-085715-8b08
20261011-085744-8e3e
20261011-085815-c70c
20261011-085846-308a
20261011-085915-25b5
20261011-085946-cc32
20261011-090017-11df
20261011-090054-6259
20261011-090125-e354
20261011-090157-ac44
```

### Cell: TUNING / IMPROVED (N=20)
```text
20261011-085222-b5c0
20261011-085253-874f
20261011-085324-158b
20261011-085348-25c8
20261011-085422-c163
20261011-085454-ab8a
20261011-085527-3fc0
20261011-085557-c503
20261011-085630-685e
20261011-085704-2073
20261011-085733-254d
20261011-085803-edbd
20261011-085834-17d2
20261011-085903-28e6
20261011-085934-f8d2
20261011-090005-21b4
20261011-090040-4a09
20261011-090113-e520
20261011-090146-25a1
20261011-090216-e1c1
```

## 3. Statistical Verification & Highlights

- Complete tabular comparison, token breakdowns, Wilson 95% intervals, and Fisher exact test values are in [`cost_radar.md`](../cost_radar.md).
- Machine-readable aggregate metrics are in [`metrics.json`](../metrics.json).
