# Crew baseline metrics

Closed crew PRs in `mw-ding/eng-crew`, closed 2026-11-03 to 2026-11-07 (UTC), closing issue in milestone #38 M25 — Integration tests (features delivered 2026-11-01..03). Generated 2026-11-07 07:45 UTC by
`scripts/metrics-baseline.py`. Definitions: [README.md](README.md#baseline-report).

## Medians

| Metric | Median | PRs | How derived |
|---|---|---|---|
| Issue to PR (min) | 2022 | 44 | Closing issue created to PR opened |
| PR to first verdict (min) | 6 | 44 | PR opened to the first reviewer-validator `pass=verdict` review |
| Verdict to land (min) | 13.5 | 44 | Last verdict before merge to merge; merged PRs only |
| Handoff ack latency (min) | 2 | 44 | PR opened to the first reviewer-validator `pass=ack` review before any verdict |
| Rounds per PR | 1 | 44 | Distinct reviewer-validator verdicts |
| Defects caught per PR | 0 | 44 | Distinct `verdict=changes` verdicts (review or validation) |
| Engine cost per PR (runs) | 1 | 44 | Recorded engine runs, where recorded; a run proxy, not tokens |

PRs: 44 (44 merged). Defects caught in total: 15.

## Per PR

| pr | issue | state | issue_to_pr_min | pr_to_first_verdict_min | verdict_to_land_min | ack_latency_min | rounds | defects | engine_runs |
|---|---|---|---|---|---|---|---|---|---|
| 810 | 783 | merged | 23 | 4 | 2 | 3 | 2 | 1 | 2 |
| 815 | 784 | merged | 105 | 3 | 1 | 2 | 2 | 1 | 2 |
| 816 | 785 | merged | 128 | 3 | 1 | 2 | 2 | 1 | 2 |
| 820 | 817 | merged | 11 | 3 | 4 | 2 | 2 | 1 | 2 |
| 1063 | 814 | merged | 2504 | 4 | 31 | 2 | 2 | 1 | 2 |
| 1065 | 811 | merged | 2596 | 9 | 27 | 3 | 2 | 1 | 2 |
| 1066 | 787 | merged | 2619 | 4 | 24 | 2 | 2 | 1 | 2 |
| 1067 | 786 | merged | 2633 | 4 | 11 | 2 | 2 | 1 | 2 |
| 1069 | 1064 | merged | 61 | 3 | 102 | 2 | 2 | 1 | 2 |
| 1071 | 788 | merged | 2689 | 10 | 5 | 2 | 1 | 0 | 1 |
| 1073 | 789 | merged | 2770 | 3 | 18 | 1 | 3 | 2 | 3 |
| 1075 | 790 | merged | 2784 | 6 | 23 | 2 | 1 | 0 | 1 |
| 1077 | 798 | merged | 2820 | 5 | 14 | 1 | 2 | 0 | 3 |
| 1080 | 791 | merged | 2837 | 5 | 33 | 4 | 3 | 2 | 3 |
| 1081 | 1072 | merged | 73 | 11 | 29 | 3 | 1 | 0 | 1 |
| 1083 | 801 | merged | 2846 | 13 | 18 | 1 | 1 | 0 | 1 |
| 1084 | 1078 | merged | 33 | 14 | 26 | 3 | 1 | 0 | 1 |
| 1085 | 1079 | merged | 34 | 13 | 28 | 2 | 1 | 0 | 1 |
| 1091 | 796 | merged | 2875 | 9 | 29 | 2 | 4 | 0 | 4 |
| 1094 | 799 | merged | 2897 | 6 | 2 | 2 | 2 | 0 | 2 |
| 1097 | 800 | merged | 2945 | 10 | 31 | 2 | 4 | 0 | 4 |
| 1104 | 1103 | merged | 3 | 4 | 26 | 2 | 1 | 0 | 1 |
| 1105 | 803 | merged | 2976 | 4 | 15 | 2 | 2 | 0 | 2 |
| 1107 | 802 | merged | 2978 | 9 | 32 | 1 | 2 | 0 | 3 |
| 1108 | 792 | merged | 2980 | 3 | 2 | 1 | 2 | 0 | 2 |
| 1110 | 1102 | merged | 31 | 14 | 13 | 2 | 1 | 0 | 1 |
| 1113 | 1112 | merged | 6 | 5 | 39 | 2 | 1 | 0 | 1 |
| 1115 | 793 | merged | 3037 | 3 | 38 | 1 | 1 | 0 | 1 |
| 1117 | 743 | merged | 3501 | 5 | 25 | 2 | 1 | 0 | 1 |
| 1119 | 794 | merged | 3096 | 4 | 20 | 2 | 1 | 0 | 1 |
| 1121 | 795 | merged | 3141 | 4 | 8 | 2 | 1 | 0 | 1 |
| 1148 | 1087 | merged | 755 | 7 | 2 | 3 | 1 | 0 | 1 |
| 1149 | 1098 | merged | 668 | 8 | 13 | 2 | 1 | 0 | 1 |
| 1150 | 1050 | merged | 1286 | 9 | 9 | 2 | 1 | 0 | 1 |
| 1152 | 1106 | merged | 731 | 7 | 3 | 2 | 1 | 0 | 1 |
| 1153 | 1088 | merged | 850 | 39 | 8 | 10 | 1 | 0 | 1 |
| 1154 | 1118 | merged | 638 | 33 | 9 | 20 | 1 | 0 | 1 |
| 1159 | 1089 | merged | 891 | 56 | 3 | 2 | 1 | 0 | 1 |
| 1160 | 1156 | merged | 19 | 8 | 3 | 3 | 1 | 0 | 1 |
| 1162 | 1042 | merged | 1540 | 17 | 4 | 10 | 1 | 0 | 1 |
| 1163 | 1124 | merged | 277 | 22 | 29 | 2 | 1 | 0 | 1 |
| 1165 | 818 | merged | 3221 | 10 | 3 | 3 | 1 | 0 | 2 |
| 1169 | 1168 | merged | 3 | 5 | 2 | 2 | 1 | 0 | 1 |
| 1186 | 806 | merged | 4108 | 3 | 2 | 2 | 2 | 2 | 2 |
