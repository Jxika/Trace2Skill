<div align="center">
<h1>Trace2Skill: Distill Trajectory-Local Lessons into Transferable Agent Skills</h1>

<!-- Badges -->
<a href="https://github.com/Qwen-Applications">
  <img src="https://img.shields.io/badge/Qwen-Applications-4433FF?style=for-the-badge" alt="Qwen Applications">
</a>
<a href="https://arxiv.org/abs/2603.25158">
  <img src="https://img.shields.io/badge/arXiv-2603.25158-b31b1b.svg?style=for-the-badge" alt="arXiv">
</a>
<a href="https://github.com/Qwen-Applications/Trace2Skill">
  <img src="https://img.shields.io/badge/Github-Code-black?style=for-the-badge&logo=github" alt="Github">
</a>

<p align="center">
  <i><b>Qwen Large Model Application Team, Alibaba</b></i>
</p>

In this project, we provide the official code and released spreadsheet skills for Trace2Skill. Trace2Skill automatically adapts and creates agent skills from execution traces. Instead of updating skills sequentially from individual trajectories, it analyzes a pool of traces in parallel, proposes trajectory-local patches with multiple analysts, and hierarchically consolidates them into a unified, conflict-free skill directory.

The paper studies two evolution modes: <b>skill deepening</b> from an existing human-written skill, and <b>skill creation from scratch</b> from a weak initial draft. In addition to spreadsheet tasks, the paper also studies math reasoning and visual question answering.

<p align="center">
  <b>Trace2Skill pipeline:</b> trajectory generation -> parallel multi-agent patch proposal -> conflict-free patch consolidation
</p>

</div>

## 1. Setup and Installation

Clone this repository and install the lightweight runtime dependencies:

```bash
git clone https://github.com/Qwen-Applications/Trace2Skill.git
cd Trace2Skill
python -m pip install openai tqdm openpyxl requests diskcache
```

The runners use OpenAI-compatible chat APIs by default. Set the API credentials for your provider:

```bash
export OPENAI_API_KEY=<your_api_key>
export OPENAI_BASE_URL=<optional_openai_compatible_endpoint>
```

For local OpenAI-compatible serving, pass `--api-key EMPTY` and `--base-url http://localhost:8000/v1` to the analysis or skill-evolution entrypoints.

## 2. Data and Released Skills

Prepare a SpreadsheetBench dataset directory or JSONL file and pass it with `--data_path` when running evaluation. The benchmark runner uses the preloaded spreadsheet skills under `spreadsheet_agent/skills/`.

We release the top-performing spreadsheet skills referenced in the paper under `released_skills/`:

| Skill | Setting | Source traces | Location |
|-------|---------|---------------|----------|
| `trace2skill-xlsx-35B-combined` | Self-deepen | 35B combined success/error traces | `released_skills/trace2skill-xlsx-35B-combined/` |
| `xlsx-35B` | Self-create | 35B error traces | `released_skills/xlsx-35B/` |
| `trace2skill-xlsx-122B-combined` | Self-deepen | 122B combined success/error traces | `released_skills/trace2skill-xlsx-122B-combined/` |
| `xlsx-122B` | Self-create | 122B error traces | `released_skills/xlsx-122B/` |

The runtime skill tree in `spreadsheet_agent/skills/` includes the released `xlsx-35B` and `xlsx-122B` variants directly. The full paper release set is preserved separately in `released_skills/`.

## 3. Running and Skill Evolution

From the repository root, run the SpreadsheetBench agent, evaluate outputs, analyze trajectories, and evolve skills with the following entrypoints:

| Workflow | Command | Output |
|----------|---------|--------|
| Run SpreadsheetBench | `python run_spreadsheetbench.py --data_path <dataset> --model <model>` | Spreadsheet outputs and optional trajectory logs |
| Evaluate outputs | `python evaluate_with_official.py --data_path <dataset> --output_dir <outputs>` | Official-compatible evaluation results |
| Match results and logs | `python analyze_results.py --help` | Failure triage records |
| Agentic error analysis | `python analysis/run_error_analysis.py --help` | `parsed_error_records.json` |
| Single-call error analysis | `python analysis/run_error_analysis_llm.py --help` | `parsed_error_records.json` |
| Single-call success analysis | `python analysis/run_success_analysis_llm.py --help` | `parsed_success_records.json` |
| Parallel error-driven skill evolution | `python -m skill_evolver.run_parallel_skill_evolution --help` | Updated skill directory |
| Parallel combined skill evolution | `python -m skill_evolver.run_parallel_combined_skill_evolution --help` | Updated skill directory |

Example benchmark run:

```bash
python run_spreadsheetbench.py \
  --data_path <dataset> \
  --model <model> \
  --output_dir outputs/spreadsheetbench \
  --log_dir outputs/logs
```

Example parallel skill evolution from parsed error records:

```bash
python -m skill_evolver.run_parallel_skill_evolution \
  --input-json <analysis_output_or_parsed_error_records.json> \
  --skill-dir spreadsheet_agent/skills/xlsx/ \
  --model <model> \
  --max-workers 4 \
  --save-intermediates
```

The skill-evolver entrypoints accept either parsed JSON files or the corresponding analysis output directories directly.

## Repository Structure

```text
Trace2Skill/
├── README.md
├── analysis/                           # Error/success trajectory analysis scripts and prompts
│   ├── run_error_analysis.py           # Agentic error analyst
│   ├── run_error_analysis_llm.py       # Single-call error analyst
│   └── run_success_analysis_llm.py     # Single-call success analyst
├── released_skills/                    # Released paper skill artifacts
│   ├── trace2skill-xlsx-35B-combined/
│   ├── trace2skill-xlsx-122B-combined/
│   ├── xlsx-35B/
│   └── xlsx-122B/
├── skill_evolver/                      # Parallel Trace2Skill patch proposal and consolidation
│   ├── run_parallel_skill_evolution.py
│   └── run_parallel_combined_skill_evolution.py
├── spreadsheet_agent/                  # SpreadsheetBench agent and runtime skills
│   ├── agents/
│   ├── skills/
│   └── tools/
├── src/react_agent/                    # ReAct agent and OpenAI-compatible model clients
├── run_spreadsheetbench.py             # SpreadsheetBench runner
├── evaluate_with_official.py           # Official-compatible scorer wrapper
├── analyze_results.py                  # Result/log matching and triage
└── spreadsheetbench_support.py         # Shared SpreadsheetBench utilities
```

Core implementations:

- `skill_evolver/parallel_evolving_agent.py`
- `skill_evolver/parallel_success_evolving_agent.py`
- `skill_evolver/skill_evolving_agent.py`
- `analysis/error_analysis_agent.py`
- `spreadsheet_agent/agents/cli_skill_preloaded_agent.py`

## Acknowledgements

This repository focuses on the spreadsheet setting and released skills discussed in the paper, while keeping the core Trace2Skill evolution pipeline runnable. We thank the developers and communities behind the tools used by this release:

- [Qwen](https://github.com/QwenLM) and the Qwen application ecosystem
- [SpreadsheetBench](https://arxiv.org/abs/2406.14991) for spreadsheet-agent evaluation
- [openpyxl](https://openpyxl.readthedocs.io/) for spreadsheet manipulation support

## Citation

If you find our work useful in your research, please consider citing our paper:

```bibtex
@misc{ni2026trace2skilldistilltrajectorylocallessons,
      title={Trace2Skill: Distill Trajectory-Local Lessons into Transferable Agent Skills},
      author={Jingwei Ni and Yihao Liu and Xinpeng Liu and Yutao Sun and Mengyu Zhou and Pengyu Cheng and Dexin Wang and Erchao Zhao and Xiaoxi Jiang and Guanjun Jiang},
      year={2026},
      eprint={2603.25158},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2603.25158},
}
```
