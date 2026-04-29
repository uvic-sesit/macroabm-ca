import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import h5py
import altair as alt
import numpy as np
import pandas as pd
import streamlit as st


# Configuration: Set the output folder path here
OUTPUT_FOLDER = Path(__file__).resolve().parents[1] / "dev" / "output"

# Path to industry names CSV file
INDUSTRY_NAMES_CSV = os.path.join(os.path.dirname(__file__), "can_industries_wnames.csv")


TreeNode = Dict[str, Any]


@st.cache_data(show_spinner=False)
def load_industry_mapping() -> Dict[int, str]:
    """Load industry index to name mapping from CSV file."""
    if not os.path.exists(INDUSTRY_NAMES_CSV):
        return {}
    try:
        df = pd.read_csv(INDUSTRY_NAMES_CSV)
        # Create mapping from Firm_ID (index) to Industry_Name
        mapping = dict(zip(df["Firm_ID"], df["Industry_Name"]))
        return mapping
    except Exception:
        return {}


def _is_dataset(obj: h5py.HLObject) -> bool:
    return isinstance(obj, h5py.Dataset)


def _build_tree(group: h5py.Group) -> TreeNode:
    tree: TreeNode = {}
    for key in group.keys():
        obj = group[key]
        if _is_dataset(obj):
            tree[key] = {"type": "dataset"}
        else:
            tree[key] = {"type": "group", "children": _build_tree(obj)}
    return tree


@st.cache_data(show_spinner=False)
def get_tree(file_path: str) -> TreeNode:
    with h5py.File(file_path, "r") as h5_file:
        return _build_tree(h5_file)


def get_node(tree: TreeNode, path: List[str]) -> Tuple[Optional[TreeNode], Optional[str]]:
    node = tree
    for key in path:
        if key not in node:
            return None, None
        entry = node[key]
        if entry["type"] == "dataset":
            return None, "/".join(path)
        node = entry["children"]
    return node, None


def find_first_dataset_path(tree: TreeNode, target_name: str) -> Optional[List[str]]:
    for key in sorted(tree.keys()):
        entry = tree[key]
        if entry["type"] == "dataset" and key == target_name:
            return [key]
        if entry["type"] == "group":
            sub_path = find_first_dataset_path(entry["children"], target_name)
            if sub_path:
                return [key] + sub_path
    return None


def list_dataset_paths(tree: TreeNode, prefix: str = "") -> List[str]:
    paths: List[str] = []
    for key in sorted(tree.keys()):
        entry = tree[key]
        current_path = f"{prefix}/{key}" if prefix else key
        if entry["type"] == "dataset":
            paths.append(current_path)
        else:
            paths.extend(list_dataset_paths(entry["children"], current_path))
    return paths


def merge_trees(trees: Iterable[TreeNode]) -> TreeNode:
    merged: TreeNode = {}
    for tree in trees:
        for key, entry in tree.items():
            if key not in merged:
                merged[key] = entry
                continue
            existing = merged[key]
            if existing["type"] == "group" or entry["type"] == "group":
                existing_children = existing.get("children", {})
                entry_children = entry.get("children", {})
                merged[key] = {
                    "type": "group",
                    "children": merge_trees([existing_children, entry_children]),
                }
            else:
                merged[key] = {"type": "dataset"}
    return merged


def add_real_gdp_nodes(tree: TreeNode) -> None:
    for entry in tree.values():
        if entry["type"] == "group":
            add_real_gdp_nodes(entry["children"])
    has_gdp = "gdp_output" in tree and tree["gdp_output"]["type"] == "dataset"
    has_cpi = "cpi" in tree and tree["cpi"]["type"] == "dataset"
    if has_gdp and has_cpi and "real_gdp_2014" not in tree:
        tree["real_gdp_2014"] = {"type": "dataset"}


def add_can_region(tree: TreeNode) -> List[str]:
    regions = [
        key
        for key, entry in tree.items()
        if entry["type"] == "group" and key != "CAN" and "CAN" in key
    ]
    if not regions:
        return regions
    can_children = merge_trees([tree[region]["children"] for region in regions])
    tree["CAN"] = {"type": "group", "children": can_children}
    return regions


def get_column_labels(
    h5_file: h5py.File, dataset_path: str, industry_mapping: Optional[Dict[int, str]] = None
) -> Optional[List[str]]:
    columns_path = f"{dataset_path}_columns"
    if columns_path not in h5_file:
        return None
    columns_data = h5_file[columns_path][()]
    columns_array = np.asarray(columns_data)
    
    # Handle 2D array (pairs like [agent_id, industry_id])
    if columns_array.ndim == 2 and columns_array.shape[1] == 2:
        if industry_mapping:
            mapped_labels = []
            for a, b in columns_array:
                # Map both indices if they're in the mapping
                idx1 = int(a)
                idx2 = int(b)
                name1 = industry_mapping.get(idx1, str(idx1))
                name2 = industry_mapping.get(idx2, str(idx2))
                mapped_labels.append(f"[{name1}, {name2}]")
            return mapped_labels
        else:
            return [f"[{int(a)}, {int(b)}]" for a, b in columns_array]
    
    # Handle 1D array of indices (industry indices)
    if columns_array.ndim == 1:
        if industry_mapping:
            # Map integer indices directly to industry names
            mapped_labels = []
            for idx in columns_array:
                idx_int = int(idx)
                mapped_labels.append(industry_mapping.get(idx_int, str(idx_int)))
            return mapped_labels
        else:
            return [str(int(x)) for x in columns_array]
    
    # Fallback: convert to list of strings
    raw_labels = [str(x) for x in columns_array.flatten().tolist()]
    
    # Try to map if we have a mapping and labels look like integers
    if industry_mapping:
        mapped_labels = []
        for label in raw_labels:
            try:
                idx = int(float(label))
                mapped_labels.append(industry_mapping.get(idx, label))
            except (ValueError, TypeError):
                mapped_labels.append(label)
        return mapped_labels
    
    return raw_labels


def load_dataset(file_path: str, dataset_path: str) -> np.ndarray:
    with h5py.File(file_path, "r") as h5_file:
        return h5_file[dataset_path][()]


def render_chart(
    values: np.ndarray,
    scenario_label: str,
    series_label: str,
    scale_note: str,
    y_domain: Optional[Tuple[float, float]] = None,
    show_debug: bool = False,
) -> None:
    series = np.asarray(values, dtype=float).squeeze()
    if series.size == 0:
        st.warning(f"Scenario {scenario_label} has no data to plot.")
        return
    finite_mask = np.isfinite(series)
    if not finite_mask.any():
        st.warning(f"Scenario {scenario_label} has no finite values to plot.")
        return
    series = np.where(finite_mask, series, np.nan)
    if show_debug:
        finite_values = series[finite_mask]
        st.caption(
            "Debug: "
            f"points={series.size}, "
            f"finite={finite_mask.sum()}, "
            f"min={float(finite_values.min()):.4g}, "
            f"max={float(finite_values.max()):.4g}, "
            f"y_domain={y_domain}"
        )
    if series.ndim == 0:
        data = pd.DataFrame({"index": [0], "value": [float(series)]})
    else:
        time_axis = np.arange(series.shape[0])
        data = pd.DataFrame({"index": time_axis, "value": series})

    y_scale = alt.Scale(domain=y_domain) if y_domain else alt.Scale()
    chart = (
        alt.Chart(data)
        .mark_line(point=True)
        .encode(
            x=alt.X("index:Q", title="timestep"),
            y=alt.Y("value:Q", scale=y_scale),
        )
        .properties(height=200)
    )
    st.altair_chart(chart, use_container_width=True)
    st.caption(f"Scenario: {scenario_label} | Series: {series_label}{scale_note}")


def is_real_gdp_path(dataset_path: str) -> bool:
    return dataset_path.split("/")[-1] == "real_gdp_2014"


def build_dataset_path(parent: str, name: str) -> str:
    return f"{parent}/{name}" if parent else name


def compute_real_gdp(h5_file: h5py.File, dataset_path: str) -> Optional[np.ndarray]:
    parent = "/".join(dataset_path.split("/")[:-1])
    gdp_path = build_dataset_path(parent, "gdp_output")
    cpi_path = build_dataset_path(parent, "cpi")
    if gdp_path not in h5_file or cpi_path not in h5_file:
        return None
    gdp_data = h5_file[gdp_path][()]
    cpi_data = h5_file[cpi_path][()]
    return np.divide(
        gdp_data,
        cpi_data,
        out=np.full_like(gdp_data, np.nan, dtype=float),
        where=cpi_data != 0,
    )


def get_labels_for_dataset(
    h5_file: h5py.File,
    dataset_path: str,
    regions: List[str],
    industry_mapping: Optional[Dict[int, str]] = None,
) -> Optional[List[str]]:
    candidates: List[str] = []
    if dataset_path.startswith("CAN/"):
        tail_path = dataset_path[len("CAN/") :]
        for region in regions:
            candidates.append(f"{region}/{tail_path}")
            if is_real_gdp_path(tail_path):
                parent = "/".join(tail_path.split("/")[:-1])
                parent_path = f"{region}/{parent}" if parent else region
                candidates.append(build_dataset_path(parent_path, "gdp_output"))
    else:
        candidates.append(dataset_path)
        if is_real_gdp_path(dataset_path):
            parent = "/".join(dataset_path.split("/")[:-1])
            candidates.append(build_dataset_path(parent, "gdp_output"))

    for candidate in candidates:
        if candidate in h5_file:
            labels = get_column_labels(h5_file, candidate, industry_mapping)
            if labels:
                return labels
            
            # Fallback: if no _columns dataset exists but we have industry mapping,
            # check if the dataset has the right number of columns to be industry-indexed
            if industry_mapping:
                try:
                    dataset = h5_file[candidate]
                    if hasattr(dataset, "shape") and len(dataset.shape) >= 2:
                        n_cols = dataset.shape[-1]  # Last dimension is columns
                        n_industries = len(industry_mapping)
                        # If column count matches number of industries, generate labels
                        if n_cols == n_industries:
                            return [industry_mapping.get(i, str(i)) for i in range(n_cols)]
                except Exception:
                    pass
    
    return None


def get_dataset_for_region(h5_file: h5py.File, region: str, tail_path: str) -> Optional[np.ndarray]:
    full_path = f"{region}/{tail_path}" if region else tail_path
    if is_real_gdp_path(tail_path):
        return compute_real_gdp(h5_file, full_path)
    if full_path not in h5_file:
        return None
    return h5_file[full_path][()]


def sum_regions_dataset(
    h5_file: h5py.File,
    regions: List[str],
    tail_path: str,
) -> Tuple[Optional[np.ndarray], List[str]]:
    warnings: List[str] = []
    total: Optional[np.ndarray] = None
    for region in regions:
        data = get_dataset_for_region(h5_file, region, tail_path)
        if data is None:
            continue
        data = np.asarray(data, dtype=float)
        if total is None:
            total = data.copy()
        elif total.shape == data.shape:
            total += data
        else:
            warnings.append(f"{region} shape {data.shape} != {total.shape}")
    return total, warnings


def parse_file_paths(raw_text: str) -> List[str]:
    if not raw_text:
        return []
    normalized = raw_text.replace(";", "\n")
    entries: List[str] = []
    for line in normalized.splitlines():
        for part in line.split(","):
            path = part.strip().strip('"')
            if path:
                entries.append(os.path.expanduser(path))
    unique_paths: List[str] = []
    seen: set[str] = set()
    for entry in entries:
        if entry not in seen:
            seen.add(entry)
            unique_paths.append(entry)
    return unique_paths


def make_unique_labels(paths: Iterable[str]) -> List[str]:
    labels: List[str] = []
    counts: Dict[str, int] = {}
    for path in paths:
        base = os.path.basename(path) or path
        counts[base] = counts.get(base, 0) + 1
        if counts[base] == 1:
            labels.append(base)
        else:
            labels.append(f"{base} ({counts[base]})")
    return labels


def sample_value(data: np.ndarray) -> float:
    if data.ndim == 0:
        return float(data)
    if data.ndim == 1:
        idx = 1 if data.shape[0] > 1 else 0
        return float(data[idx])
    idx = 1 if data.shape[0] > 1 else 0
    return float(data[idx, 0])


def find_h5_files_in_folder(folder_path: str) -> List[str]:
    """Find all .h5 files in the specified folder."""
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return []
    h5_files = []
    for file in os.listdir(folder_path):
        if file.lower().endswith(".h5"):
            h5_files.append(os.path.join(folder_path, file))
    return sorted(h5_files)


def main() -> None:
    st.set_page_config(page_title="MacroABM Results Explorer", layout="wide")
    st.title("MacroABM Results Explorer")
    
    # Load industry mapping
    industry_mapping = load_industry_mapping()
    
    # Automatically find all H5 files in the output folder
    auto_h5_files = find_h5_files_in_folder(OUTPUT_FOLDER)
    
    # Create default text with auto-discovered files or empty if none found
    if auto_h5_files:
        default_paths_text = "\n".join(auto_h5_files)
    else:
        default_paths_text = ""
    
    st.write("HDF5 files are automatically loaded from the configured output folder.")
    st.write(f"**Output folder:** `{OUTPUT_FOLDER}`")
    if auto_h5_files:
        st.info(f"Found {len(auto_h5_files)} H5 file(s) in the output folder.")
    else:
        st.warning(f"No H5 files found in `{OUTPUT_FOLDER}`. You can manually specify file paths below.")
    
    raw_paths = st.text_area(
        "HDF5 file paths (one per line, or comma-separated). Leave empty to use auto-discovered files.",
        value=default_paths_text,
        height=120,
    )
    
    # Use auto-discovered files if text area is empty, otherwise parse the text
    if raw_paths.strip():
        file_paths = parse_file_paths(raw_paths)
    else:
        file_paths = auto_h5_files
    
    if not file_paths:
        st.error("No HDF5 files found. Please check the output folder path or manually specify file paths.")
        return

    missing_paths = [path for path in file_paths if not os.path.exists(path)]
    valid_paths = [path for path in file_paths if os.path.exists(path)]
    if missing_paths:
        st.warning("Missing files:\n" + "\n".join(f"- {path}" for path in missing_paths))
    if not valid_paths:
        st.error("No valid HDF5 files found.")
        return

    trees: Dict[str, TreeNode] = {}
    invalid_files: List[str] = []
    for path in valid_paths:
        try:
            trees[path] = get_tree(path)
        except OSError as exc:
            invalid_files.append(f"{path} ({exc})")
    if invalid_files:
        st.warning("Could not open files:\n" + "\n".join(f"- {entry}" for entry in invalid_files))
    if not trees:
        st.error("No readable HDF5 files available.")
        return

    merged_tree = merge_trees(trees.values())
    regions = add_can_region(merged_tree)
    add_real_gdp_nodes(merged_tree)
    all_dataset_paths = list_dataset_paths(merged_tree)
    if not all_dataset_paths:
        st.info("No datasets found in the selected files.")
        return

    preferred_path = ["economy", "real_gdp_2014"]
    if get_node(merged_tree, preferred_path)[1]:
        default_path = preferred_path
    else:
        default_path = find_first_dataset_path(merged_tree, "real_gdp_2014")
        if not default_path:
            default_path = find_first_dataset_path(merged_tree, "gdp_output")

    path: List[str] = []
    current_tree = merged_tree
    selected_dataset: Optional[str] = None
    level = 1

    while True:
        options = sorted(current_tree.keys())
        if not options:
            break
        default_selection = default_path[level - 1] if default_path and len(default_path) >= level else options[0]
        default_index = options.index(default_selection) if default_selection in options else 0
        selection = st.selectbox(
            f"Level {level}",
            options,
            index=default_index,
            key=f"level_{level}",
        )
        path.append(selection)
        node_entry = current_tree[selection]
        if node_entry["type"] == "dataset":
            selected_dataset = "/".join(path)
            break
        current_tree = node_entry["children"]
        level += 1

    if not selected_dataset:
        st.info("Select a dataset to render the chart.")
        return

    st.caption(f"{len(all_dataset_paths)} variables found across {len(trees)} file(s).")
    with st.expander("Show all variables"):
        st.write(sorted(set(all_dataset_paths)))

    scenario_labels = make_unique_labels(trees.keys())
    scenario_data: List[Dict[str, Any]] = []
    missing_dataset_files: List[str] = []
    can_warnings: List[str] = []

    for path, label in zip(trees.keys(), scenario_labels):
        with h5py.File(path, "r") as h5_file:
            data: Optional[np.ndarray]
            if selected_dataset.startswith("CAN/"):
                tail_path = selected_dataset[len("CAN/") :]
                data, warnings = sum_regions_dataset(h5_file, regions, tail_path)
                if warnings:
                    can_warnings.append(f"{label}: " + "; ".join(warnings))
                shape = data.shape if data is not None else None
                dtype = data.dtype if data is not None else None
            else:
                if is_real_gdp_path(selected_dataset):
                    data = compute_real_gdp(h5_file, selected_dataset)
                else:
                    data = h5_file[selected_dataset][()] if selected_dataset in h5_file else None
                shape = data.shape if data is not None else None
                dtype = data.dtype if data is not None else None

            if data is None:
                missing_dataset_files.append(label)
                continue

            labels = get_labels_for_dataset(h5_file, selected_dataset, regions, industry_mapping)
            scenario_data.append(
                {
                    "label": label,
                    "path": path,
                    "data": data,
                    "shape": shape,
                    "dtype": dtype,
                    "labels": labels,
                }
            )

    if missing_dataset_files:
        st.info(
            "Dataset not found in: " + ", ".join(missing_dataset_files) + ". Showing available scenarios only."
        )
    if can_warnings:
        st.warning("CAN aggregation skipped mismatched shapes:\n" + "\n".join(f"- {msg}" for msg in can_warnings))
    if not scenario_data:
        st.warning("Selected dataset not found in any file.")
        return

    sample_values = [sample_value(entry["data"]) for entry in scenario_data]
    should_scale = max(sample_values) > 1_000_000_000_000
    if st.session_state.get("scale_dataset_path") != selected_dataset:
        st.session_state["scale_to_millions"] = should_scale
        st.session_state["scale_dataset_path"] = selected_dataset

    st.checkbox("Divide values by 1,000,000 (all scenarios)", key="scale_to_millions")
    scale_to_millions = st.session_state["scale_to_millions"]
    scale_note = " (scaled / 1,000,000)" if scale_to_millions else ""
    show_debug = st.checkbox("Show chart debug info", value=False)

    max_columns = 0
    label_source: Optional[List[str]] = None
    for entry in scenario_data:
        data = entry["data"]
        if data.ndim == 2:
            max_columns = max(max_columns, data.shape[1])
            # Use existing labels if available
            if label_source is None and entry["labels"] and len(entry["labels"]) == data.shape[1]:
                label_source = entry["labels"]
            # Fallback: generate labels from industry mapping if column count matches
            elif label_source is None and not entry["labels"] and industry_mapping:
                n_cols = data.shape[1]
                n_industries = len(industry_mapping)
                if n_cols == n_industries:
                    label_source = [industry_mapping.get(i, str(i)) for i in range(n_cols)]

    selected_idx = 0
    if max_columns > 1:
        label_options = list(range(max_columns))
        if label_source and len(label_source) == max_columns:
            label_text = [f"{idx}: {label_source[idx]}" for idx in label_options]
            selected_idx = st.selectbox(
                "Series index",
                label_options,
                format_func=lambda i: label_text[i],
            )
            series_label = label_text[selected_idx]
        else:
            selected_idx = st.selectbox("Series index", label_options)
            series_label = f"column {selected_idx}"
    else:
        series_label = "single series"

    plotted_series: List[Tuple[Dict[str, Any], np.ndarray]] = []
    for idx, entry in enumerate(scenario_data):
        data = entry["data"]
        if data.ndim > 2:
            st.warning(f"Scenario {entry['label']} has {data.ndim}D data; skipping chart.")
            continue
        if data.ndim == 2 and data.shape[1] > 1:
            if selected_idx >= data.shape[1]:
                st.warning(f"Scenario {entry['label']} has only {data.shape[1]} columns; skipping.")
                continue
            series_data = data[:, selected_idx]
        else:
            series_data = data
        if scale_to_millions:
            series_data = series_data.astype(float) / 1_000_000
        plotted_series.append((entry, np.asarray(series_data, dtype=float)))

    if not plotted_series:
        st.warning("No scenarios available to chart.")
        return

    all_values = np.concatenate([series.ravel() for _, series in plotted_series])
    if all_values.size > 0:
        finite_values = all_values[np.isfinite(all_values)]
        y_min = float(finite_values.min()) if finite_values.size else 0.0
        y_max = float(finite_values.max()) if finite_values.size else 0.0
        if y_min == y_max:
            y_min -= 1.0
            y_max += 1.0
        y_domain = (y_min, y_max)
    else:
        y_domain = None

    columns = st.columns(min(len(plotted_series), 3))
    for idx, (entry, series_data) in enumerate(plotted_series):
        target = columns[idx % len(columns)] if columns else st.container()
        with target:
            st.write(f"Dataset: `{selected_dataset}`")
            st.write(f"Shape: `{entry['shape']}`  |  Dtype: `{entry['dtype']}`")
            render_chart(
                series_data,
                entry["label"],
                series_label,
                scale_note,
                y_domain=y_domain,
                show_debug=show_debug,
            )


if __name__ == "__main__":
    main()
