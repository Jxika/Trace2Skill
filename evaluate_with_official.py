#!/usr/bin/env python3
"""
Evaluation script that uses the official SpreadsheetBench evaluation logic.

This script imports and calls the official SpreadsheetBench evaluation functions
to ensure 100% compatibility with their evaluation methodology.

Usage:
    python evaluate_with_official.py --data_path data/sample_data_200 --output_dir outputs/spreadsheetbench
"""

import argparse
import json
import os
import sys
from collections import defaultdict

from tqdm import tqdm
from simple_log import SimpleLog

from spreadsheetbench_support import (
    compare_guige_row,
    compare_workbooks as local_compare_workbooks,
    find_output_dir,
    find_spreadsheet_dir,
    load_dataset,
)

try:
    from evaluation_official import compare_workbooks as official_compare_workbooks
except ImportError:
    official_compare_workbooks = None

'''
   是Trace2Skill 项目中用于自动化评估 Agent 执行结果脚本。它的主要作用是将 Agent 输出的表格与SpreadsheetBench 数据集中的标准答案
   （Ground Truth）进行自动化比对，并生成测评报告。
'''

'''
   1.双模式比对机制
   脚本设计了兼容与降级处理：
     · 优先尝试导入 SpreadsheetBench 官方的比对逻辑，以保证论文评测对齐。
     · 如果本地缺少官方测评包，则自动回退使用项目中自带的本地比对函数。
'''
def compare_workbooks(
    gt_path,
    output_path,
    instruction_type,
    answer_position,
    gt_sheet=None,
    output_sheet=None,
):
    if official_compare_workbooks is not None:
        return official_compare_workbooks(
            gt_path, output_path, instruction_type, answer_position
        )
    return local_compare_workbooks(
        gt_path,
        output_path,
        answer_position,
        gt_sheet=gt_sheet,
        output_sheet=output_sheet,
    )

'''
   2.核心评估流程
   遍历指定的数据集，执行以下步骤：
      · 文件匹配：自动在输出目录中巽宅Agent 生成的 _output.xlsx,并在数据目录寻找对应的标准答案字典（_answer.xlsx 或 _golden.xlsx）。
      · 计算两类得分：
         · Soft Score(软得分)：反映单个测试用例中答对测试点的比例（0.0 ~ 1.0）
         · Hard Score(硬得分)：只有当该任务所有测试点 100% 对齐时，才记为 1（完全正确），否则为0。
'''
def evaluate(data_path, output_dir, start_idx=0, end_idx=None, verbose=False):
    """
    Evaluate outputs against ground truth using official SpreadsheetBench logic.

    Returns:
        dict with evaluation results
    """
    dataset = load_dataset(data_path)

    if end_idx is None:
        end_idx = len(dataset)
    dataset = dataset[start_idx:end_idx]

    print(f"Evaluating {len(dataset)} instances using official SpreadsheetBench evaluation...")

    results = []
    total_test_cases = 0
    passed_test_cases = 0
    fully_correct = 0

    # Track by instruction type (like official eval)
    type_results = defaultdict(lambda: {"soft": [], "hard": []})
    log=SimpleLog("simple/simple_log.txt")
    #从 dataset.json 读取关键字段
    for instance in tqdm(dataset):
        instance_id = str(instance["id"])
        spreadsheet_path = str(instance.get("spreadsheet_path", instance_id))
        instruction_type = instance.get("instruction_type", "")
        answer_position = instance.get("answer_position", "")
        gt_sheet = instance.get("golden_sheet")
        output_sheet = instance.get("answer_sheet")

        if not answer_position:
            if verbose:
                print(f"Warning: No answer_position for {instance_id}, skipping")
            continue

        if instance.get("task_type") == "guige_row":
            spreadsheet_dir = find_spreadsheet_dir(data_path, instance)
            if spreadsheet_dir is None:
                results.append({
                    "id": instance_id,
                    "success": False,
                    "error": "Spreadsheet directory not found",
                    "test_cases": [],
                })
                continue

            golden_file = instance.get("golden_file")
            if not golden_file:
                results.append({
                    "id": instance_id,
                    "success": False,
                    "error": "No golden_file in dataset entry",
                    "test_cases": [],
                })
                continue

            output_instance_dir = find_output_dir(output_dir, instance)
            gt_path = os.path.join(spreadsheet_dir, golden_file)
            output_path = os.path.join(output_instance_dir, "output.xlsx")
            golden_row = int(instance.get("golden_row", instance.get("source_row", 1)))
            gt_sheet = instance.get("golden_sheet")
            output_sheet = instance.get("answer_sheet", "sheet")
            output_cell = answer_position.split(",")[0].strip()
            if "!" in output_cell:
                output_cell = output_cell.split("!")[-1]

            total_test_cases += 1
            try:
                result, msg = compare_guige_row(
                    gt_path,
                    output_path,
                    gt_sheet,
                    golden_row,
                    output_sheet,
                    output_cell,
                )
            except Exception as e:
                result = False
                msg = str(e)

            test_case_results = [{
                "gt_file": golden_file,
                "output_file": "output.xlsx",
                "passed": result,
                "message": msg,
            }]
            if result:
                passed_test_cases += 1
                fully_correct += 1
            elif verbose:
                print(f"  {instance_id}: {msg}")

            soft_score = 1.0 if result else 0.0
            hard_score = 1 if result else 0
            type_results[instruction_type]["soft"].append(soft_score)
            type_results[instruction_type]["hard"].append(hard_score)
            results.append({
                "id": instance_id,
                "success": result,
                "soft_score": soft_score,
                "hard_score": hard_score,
                "test_cases": test_case_results,
            })
            continue

        # Find spreadsheet directory (contains ground truth) 找到数据目录
        spreadsheet_dir = find_spreadsheet_dir(data_path, instance)
        log.write(f"evaluate_with_official.py|evaluate|spreadsheet_dir:{spreadsheet_dir}")
        if spreadsheet_dir is None:
            results.append({
                "id": instance_id,
                "success": False,
                "error": "Spreadsheet directory not found",
                "test_cases": [],
            })
            continue

        # Find output directory for this instance 找到输出目录
        output_instance_dir = find_output_dir(output_dir, instance)
        log.write(f"evaluate_with_official.py|evaluate|output_instance_dir:{output_instance_dir}")
        # Find all test cases (ground truth files)
        # Standard format: *_answer.xlsx, Verified format: *_golden.xlsx
        try:
            all_files = os.listdir(spreadsheet_dir)
        except FileNotFoundError:
            results.append({
                "id": instance_id,
                "success": False,
                "error": f"Cannot list spreadsheet directory: {spreadsheet_dir}",
                "test_cases": [],
            })
            continue

        gt_files = sorted([f for f in all_files if f.endswith("_answer.xlsx")])
        log.write(f"evaluate_with_official.py|evaluate|gt_files:{gt_files}")
        if not gt_files:
            # Try verified dataset format
            gt_files = sorted([f for f in all_files if f.endswith("_golden.xlsx")])
        log.write(f"evaluate_with_official.py|evaluate|gt_files:{gt_files}")
        #找Ground Truth文件
        if not gt_files:
            # Try exact match for simple naming: golden.xlsx
            if "golden.xlsx" in all_files:
                gt_files = ["golden.xlsx"]

        if not gt_files:
            results.append({
                "id": instance_id,
                "success": False,
                "error": "No ground truth files found (expected *_answer.xlsx or *_golden.xlsx)",
                "test_cases": [],
            })
            continue

        test_case_results = []
        log.close()
        for gt_file in gt_files:
            # Derive output filename from ground truth filename
            if gt_file.endswith("_answer.xlsx"):
                output_file = gt_file.replace("_answer.xlsx", "_output.xlsx")
            elif gt_file == "golden.xlsx":
                # Simple naming: golden.xlsx -> initial_output.xlsx
                output_file = "initial_output.xlsx"
            else:  # _golden.xlsx
                output_file = gt_file.replace("_golden.xlsx", "_output.xlsx")

            gt_path = os.path.join(spreadsheet_dir, gt_file)
            output_path = os.path.join(output_instance_dir, output_file)

            total_test_cases += 1

            # Use official SpreadsheetBench comparison function
            #对每个(gt_path,output_path)调用compare_workbooks().
            try:
                result, msg = compare_workbooks(
                    gt_path,
                    output_path,
                    instruction_type,
                    answer_position,
                    gt_sheet=gt_sheet,
                    output_sheet=output_sheet,
                )
            except Exception as e:
                result = False
                msg = str(e)

            test_case_results.append({
                "gt_file": gt_file,
                "output_file": output_file,
                "passed": result,
                "message": msg,
            })

            if result:
                passed_test_cases += 1
            elif verbose:
                print(f"  {instance_id}/{output_file}: {msg}")

        # Calculate metrics for this instance (matching official eval)
        passed_count = sum(1 for tc in test_case_results if tc["passed"])
        total_count = len(test_case_results)
        soft_score = passed_count / total_count if total_count > 0 else 0
        hard_score = 1 if passed_count == total_count else 0

        if hard_score == 1:
            fully_correct += 1

        # Track by instruction type
        type_results[instruction_type]["soft"].append(soft_score)
        type_results[instruction_type]["hard"].append(hard_score)

        results.append({
            "id": instance_id,
            "instruction_type": instruction_type,
            "success": hard_score == 1,
            "test_cases": test_case_results,
            "passed_count": passed_count,
            "total_count": total_count,
            "soft_score": soft_score,  #部分正确
            "hard_score": hard_score,  #完全正确
        })

    # Calculate overall metrics
    total_instances = len(results)

    soft_scores = [r.get("soft_score", 0) for r in results if "soft_score" in r]
    hard_scores = [r.get("hard_score", 0) for r in results if "hard_score" in r]

    avg_soft_score = sum(soft_scores) / len(soft_scores) if soft_scores else 0
    avg_hard_score = sum(hard_scores) / len(hard_scores) if hard_scores else 0

    # Calculate per-type metrics
    type_metrics = {}
    for inst_type, scores in type_results.items():
        type_metrics[inst_type] = {
            "count": len(scores["soft"]),
            "avg_soft_score": sum(scores["soft"]) / len(scores["soft"]) if scores["soft"] else 0,
            "avg_hard_score": sum(scores["hard"]) / len(scores["hard"]) if scores["hard"] else 0,
        }

    summary = {
        "total_instances": total_instances, #评测实例数
        "fully_correct_instances": fully_correct, #hard_score=1的提数
        "instance_accuracy": fully_correct / total_instances if total_instances > 0 else 0, #完全正确实例占比
        "total_test_cases": total_test_cases, #全部test case总数
        "passed_test_cases": passed_test_cases, #通过的 test case数
        "test_case_accuracy": passed_test_cases / total_test_cases if total_test_cases > 0 else 0,#test case级别准确率
        "avg_soft_score": avg_soft_score,#各题soft的平均
        "avg_hard_score": avg_hard_score,#各题hard的平均
        "by_instruction_type": type_metrics,#按题型分组统计
    }

    return {
        "summary": summary,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate SpreadsheetBench outputs using official evaluation logic")
    parser.add_argument("--data_path",type=str,required=True,help="Path to SpreadsheetBench data directory",)
    parser.add_argument("--output_dir",type=str,required=True,help="Directory containing agent outputs",)
    parser.add_argument("--results_file",type=str,default=None,
        help="Path to save evaluation results JSON (default: output_dir/eval_official_results.json)",
    )
    parser.add_argument("--start_idx",type=int,default=0,help="Start index for evaluation",)
    parser.add_argument("--end_idx",type=int,default=None,help="End index for evaluation (exclusive)",)
    #在 evaluate_with_official.py 里是一个开关(action="store_true"),默认关闭。打开后会在终端多打印一些调试、诊断信息。
    parser.add_argument("--verbose",action="store_true",help="Print detailed error messages",)
    parser.add_argument("--repeat",type=int,default=1,
        help="Number of seed runs to evaluate. When > 1, scans output_dir for seed_*/ "
             "subdirectories and evaluates each independently (default: 1).",
    )
    args = parser.parse_args()
    
    '''
    默认情况下，repeat=1，脚本只测评指定的单个output_dir 目录。
    当你在运行命令时传入 --repeat N 时，它的作用如下：
       1.自动扫描子集：脚本不再直接读取 output_dir ，而是去扫描该目录下命名格式为 seed_* 的子文件夹。
       repeat>1时，不再读 output_dir 根目录下的输出，而是扫描其下所有seed_* 子目录，每个seed单独评一遍：
       outputs/spreadsheetbench/
       |-seed_42/
       |   |——spreadsheet/13-1/...
       |-seed_123/
       |   |——spreadsheet/13-1/...
    '''
    if args.repeat > 1:
        _run_repeat_evaluation(args)
        return

    # Run evaluation
    eval_result = evaluate(
        data_path=args.data_path,
        output_dir=args.output_dir,
        start_idx=args.start_idx,
        end_idx=args.end_idx,
        verbose=args.verbose,
    )

    # Print summary
    _print_summary(eval_result["summary"])

    # Save results
    results_file = args.results_file or os.path.join(args.output_dir, "eval_official_results.json")
    with open(results_file, "w") as f:
        json.dump(eval_result, f, indent=2)
    print(f"Results saved to: {results_file}")


def _print_summary(summary: dict, label: str = "") -> None:
    """Print a formatted evaluation summary."""
    header = f"EVALUATION RESULTS{' (' + label + ')' if label else ''} (Official SpreadsheetBench Logic)"
    print("\n" + "=" * 60)
    print(header)
    print("=" * 60)
    print(f"Total Instances:        {summary['total_instances']}")
    print(f"Fully Correct:          {summary['fully_correct_instances']}")
    print(f"Instance Accuracy:      {summary['instance_accuracy']*100:.1f}%")
    print(f"Total Test Cases:       {summary['total_test_cases']}")
    print(f"Passed Test Cases:      {summary['passed_test_cases']}")
    print(f"Test Case Accuracy:     {summary['test_case_accuracy']*100:.1f}%")
    print(f"Avg Soft Score:         {summary['avg_soft_score']*100:.1f}%")
    print(f"Avg Hard Score:         {summary['avg_hard_score']*100:.1f}%")

    if summary["by_instruction_type"]:
        print("-" * 60)
        print("By Instruction Type:")
        for inst_type, metrics in sorted(summary["by_instruction_type"].items()):
            print(f"  {inst_type or '(unknown)'}:")
            print(f"    Count: {metrics['count']}")
            print(f"    Soft:  {metrics['avg_soft_score']*100:.1f}%")
            print(f"    Hard:  {metrics['avg_hard_score']*100:.1f}%")

    print("=" * 60)

'''
多轮/随机数聚合统计(_run_repeat_evaluation)
为了衡量 Agent 表现的稳定性，脚本支持通过 --repeat 参数统计多次不同随机种子（Seed）的并集结果：
    · pass@any:在这N次运行中，只要有一次跑通了该测试例，就算通过。
    · pass@all:在这N次运行中，该测试每一次都必须跑通，衡量稳定性。
'''
def _run_repeat_evaluation(args) -> None:
    """Evaluate all seed_* subdirectories under args.output_dir."""
    seed_dirs = sorted(
        d for d in os.scandir(args.output_dir)
        if d.is_dir() and d.name.startswith("seed_")
    )
    if not seed_dirs:
        print(f"No seed_* subdirectories found in {args.output_dir}", file=__import__("sys").stderr)
        __import__("sys").exit(1)

    print(f"Found {len(seed_dirs)} seed run(s): {[d.name for d in seed_dirs]}")
    all_seed_results = {}

    for seed_dir in seed_dirs:
        seed_name = seed_dir.name
        print(f"\nEvaluating {seed_name} ...")
        result = evaluate(
            data_path=args.data_path,
            output_dir=seed_dir.path,
            start_idx=args.start_idx,
            end_idx=args.end_idx,
            verbose=args.verbose,
        )
        all_seed_results[seed_name] = result
        per_seed_file = os.path.join(seed_dir.path, "eval_official_results.json")
        with open(per_seed_file, "w") as f:
            json.dump(result, f, indent=2)
        _print_summary(result["summary"], label=seed_name)
        print(f"Results saved to: {per_seed_file}")

    # Aggregate summary: pass@k = fraction of seeds where instance passed
    _print_aggregate_summary(all_seed_results)


def _print_aggregate_summary(all_seed_results: dict) -> None:
    """Print aggregate pass@k statistics across all seeds."""
    if not all_seed_results:
        return

    # Collect per-instance pass/fail across seeds
    instance_seeds: dict[str, list[bool]] = {}
    for seed_name, result in all_seed_results.items():
        for r in result.get("results", []):
            iid = str(r["id"])
            instance_seeds.setdefault(iid, []).append(r.get("success", False))

    total_instances = len(instance_seeds)
    # pass@1: fraction that passed in at least one seed
    passed_any = sum(1 for v in instance_seeds.values() if any(v))
    # pass@all: fraction that passed in all seeds
    passed_all = sum(1 for v in instance_seeds.values() if all(v))

    n_seeds = len(all_seed_results)
    print("\n" + "=" * 60)
    print(f"AGGREGATE SUMMARY ({n_seeds} seeds)")
    print("=" * 60)
    print(f"Unique instances:       {total_instances}")
    print(f"pass@any (>=1 seed):    {passed_any}/{total_instances} "
          f"({passed_any/total_instances*100:.1f}%)" if total_instances else "N/A")
    print(f"pass@all (all seeds):   {passed_all}/{total_instances} "
          f"({passed_all/total_instances*100:.1f}%)" if total_instances else "N/A")
    print("=" * 60)

'''
   最终在终端中打印包全局通过率、分类准确率等信息的统计报告，并将每一题成功与否的明细保存到 eval_official_results.json 中。
'''
if __name__ == "__main__":
    import sys
    sys.argv=[
        "evaluate_with_official.py",
        "--data_path","data",
        "--output_dir","outputs/spreadsheetbench",
        "--start_idx","0",
        "--end_idx","10",
        "--verbose",
    ]
    main()
