# Phase 1: Bug Fixes

**Status:** Complete  
**Dependencies:** None  
**Deliverables:** Fixed `save_json` method, removed dead `filter_stopwords` call

---

## Overview

Fix two bugs that cause runtime errors:
1. `save_json` in `LocalFileHandler` is missing function call parentheses
2. `AreaRagAggregator` calls undefined `filter_stopwords` function

---

## Task 1: Fix `save_json` Missing Parentheses

### Problem

In `utils/local_file_handler.py` line 41, `self.make_directory` is referenced but not called (missing `()`). This means directories are never created before saving JSON files.

### File to Edit

`utils/local_file_handler.py`

### Current Code (lines 39-43)

```python
    def save_json(self, file_path: str, data: str):
        self.make_directory
        with open(file_path, "w") as f:
            json.dump(data, f)
```

### Required Change

Change line 41 from:
```python
        self.make_directory
```

To:
```python
        self.make_directory(Path(file_path).parent)
```

### Verification

After change, grep for `self.make_directory` in the file. All occurrences should have `(Path(file_path).parent)` as the argument. There should be 5 total occurrences, all with proper function calls.

---

## Task 2: Comment Out Undefined `filter_stopwords` Call

### Problem

In `review_aggregator/area_review_aggregator.py` line 117, `filter_stopwords(x)` is called but:
- The import on line 12 is commented out
- The file `utils/nlp_functions.py` does not exist

This will cause a `NameError` at runtime.

### File to Edit

`review_aggregator/area_review_aggregator.py`

### Current Code (lines 114-120)

```python
    def clean_single_item_reviews(self, ratings: dict) -> list:
        df = pd.DataFrame(ratings)[["rating", "review"]]

        df["review"] = df["review"].replace(r"[^A-Za-z0-9 ]+", "", regex=True)
        df["review"] = df["review"].str.lower().apply(lambda x: filter_stopwords(x))

        # remove all special characters from combined_review
        df["combined_review"] = df["rating"].astype("string") + " " + df["review"]
```

### Required Change

Comment out lines 117-118 (the two lines that process `df["review"]`):

```python
    def clean_single_item_reviews(self, ratings: dict) -> list:
        df = pd.DataFrame(ratings)[["rating", "review"]]

        # df["review"] = df["review"].replace(r"[^A-Za-z0-9 ]+", "", regex=True)
        # df["review"] = df["review"].str.lower().apply(lambda x: filter_stopwords(x))

        # remove all special characters from combined_review
        df["combined_review"] = df["rating"].astype("string") + " " + df["review"]
```

### Note

This matches how `PropertyRagAggregator` handles the same method (lines 112-115 in `property_review_aggregator.py`), where stopword filtering is already commented out.

---

## Success Criteria

1. [x] `save_json` in `local_file_handler.py` properly calls `self.make_directory(Path(file_path).parent)`
2. [x] `filter_stopwords` call in `area_review_aggregator.py` is commented out
3. [x] No new linting/syntax errors: run `python -m py_compile utils/local_file_handler.py review_aggregator/area_review_aggregator.py`
4. [x] Existing tests still pass: run `python test_openai_implementation.py`

---

## Commit Message

```
fix: correct save_json directory creation and remove undefined filter_stopwords

- Add missing () to self.make_directory call in LocalFileHandler.save_json
- Comment out filter_stopwords usage in AreaRagAggregator (function doesn't exist)
```
