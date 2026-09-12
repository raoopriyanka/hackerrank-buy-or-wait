import sys
import os
from src.pipeline import PipelineOrchestrator


def main():
    if len(sys.argv) > 1:
        data_dir = sys.argv[1]
    elif os.path.isdir("dataset"):
        data_dir = "dataset"
    else:
        data_dir = "."

    print(f"Executing pipeline with dataset directory: '{data_dir}'")
    orchestrator = PipelineOrchestrator(data_dir=data_dir)
    orchestrator.run(output_csv_path="output.csv", report_md_path="usage_report.md")
    print("Execution complete. 'output.csv' and 'usage_report.md' generated successfully.")


if __name__ == "__main__":
    main()