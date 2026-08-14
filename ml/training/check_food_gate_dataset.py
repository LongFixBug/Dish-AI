from datasets import load_dataset
from huggingface_hub import hf_hub_download
from datasets import DatasetDict

PARQUET_PATH = hf_hub_download(
    repo_id="avnishs17/food_not_food",
    repo_type="dataset",
    revision="4d0e6d6e731dd26586e303f8c7f37642fb1da1fe",
    filename="default/train/0000.parquet",
)

dataset = load_dataset(
    "parquet",
    data_files={"train": PARQUET_PATH},
)["train"]

print(dataset)
print(dataset.features["label"].names)
print(dataset[0]["image"].size)
print(dataset[0]["label"])

train_and_holdout = dataset.train_test_split(
    test_size=0.30,
    seed=42,
    stratify_by_column="label",
)

val_and_test = train_and_holdout["test"].train_test_split(
    test_size=0.50,
    seed=42,
    stratify_by_column="label",
)

splits = DatasetDict(
    {
        "train": train_and_holdout["train"],
        "validation": val_and_test["train"],
        "test": val_and_test["test"],
    }
)

print(splits)