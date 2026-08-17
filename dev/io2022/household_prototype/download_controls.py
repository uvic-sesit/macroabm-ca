"""Download the PUBLIC StatCan control tables via the WDS full-table CSV endpoint.
Two-step: getFullTableDownloadCSV/{pid}/en -> {object: zip url} -> download zip -> unzip.
PUMFs (SFS/CIS/SHS) are NOT here -- they require the manual licence portal."""
import io, json, sys, urllib.request, zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent.parent / "raw_data" / "can_2022" / "controls"
OUT.mkdir(parents=True, exist_ok=True)
PIDS = {
    "36100660": "DHEA wealth quarterly by characteristic",
    "36100587": "DHEA income/consumption/saving annual",
    "36100580": "NBSA households aggregate balance sheet",
    "38100238": "household credit mortgage vs consumer",
    "18100205": "NHPI new housing price index",
    "18100004": "CPI",
    "17100009": "population estimates quarterly",
    "11100012": "distribution of total income by census family type",
}

def fetch(pid, desc):
    api = f"https://www150.statcan.gc.ca/t1/wds/rest/getFullTableDownloadCSV/{pid}/en"
    try:
        meta = json.load(urllib.request.urlopen(api, timeout=60))
    except Exception as e:
        return pid, f"WDS-ERROR {e}", 0
    if meta.get("status") != "SUCCESS":
        return pid, f"WDS-STATUS {meta.get('status')}", 0
    zurl = meta["object"]
    try:
        raw = urllib.request.urlopen(zurl, timeout=300).read()
    except Exception as e:
        return pid, f"DL-ERROR {e}", 0
    mb = len(raw) / 1e6
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
        data_names = [n for n in z.namelist() if n.endswith(".csv") and "MetaData" not in n]
        z.extractall(OUT)
    except Exception as e:
        return pid, f"UNZIP-ERROR {e} ({mb:.1f}MB)", mb
    return pid, f"OK {mb:.1f}MB -> {data_names[:1]}", mb

if __name__ == "__main__":
    for pid, desc in PIDS.items():
        p, status, mb = fetch(pid, desc)
        print(f"{pid}  {status:60s}  # {desc}", flush=True)
