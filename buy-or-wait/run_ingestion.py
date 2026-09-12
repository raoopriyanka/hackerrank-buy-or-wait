import os
import sys
from src.loaders import load_dataset, load_and_validate_csv
from src.models import RequestRecord


def main():
    print("Testing Step 1 Data Ingestion...")

    # Validate requests.csv if present in root
    if os.path.exists("requests.csv"):
        print("Loading requests.csv...")
        records = load_and_validate_csv("requests.csv", RequestRecord)
        print(f"Successfully loaded {len(records)} request records from requests.csv")
        print("Sample Record 0:", records[0].model_dump())

    # Validate whole dataset folder if present
    data_dir = "dataset"
    if os.path.exists(data_dir):
        print(f"\nLoading full dataset from '{data_dir}/'...")
        dataset = load_dataset(data_dir)
        for filename, records in dataset.items():
            print(f"Loaded {len(records)} records from {filename}")
    else:
        print(f"\nNote: Directory '{data_dir}' not found yet. Ready for dataset folder.")

    print("\nStep 1 Ingestion Check Complete.")


if __name__ == "__main__":
    main()