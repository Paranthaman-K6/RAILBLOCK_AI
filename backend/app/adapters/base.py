import csv, io
from typing import List, Dict, Tuple

class BaseAdapter:
    source_name: str = "base"
    expected_columns: List[str] = []

    def __init__(self, content: str = None, rows: List[Dict] = None):
        self.content = content
        self.rows = rows or []
        self.errors = []
        self.warnings = []

    def load(self) -> List[Dict]:
        if self.rows:
            return self.rows
        if not self.content:
            return []
        f = io.StringIO(self.content)
        reader = csv.DictReader(f)
        # normalize header: strip, lower?
        if reader.fieldnames:
            reader.fieldnames = [h.strip() for h in reader.fieldnames]
        return list(reader)

    def normalize(self, records: List[Dict]) -> List[Dict]:
        # header and field normalization: strip, upper for IDs, dept normalization
        normalized = []
        for r in records:
            nr = {}
            for k, v in r.items():
                nk = k.strip().lower()  # keep lower for internal
                # also keep original case handling
                if isinstance(v, str):
                    v = v.strip()
                # map lower to canonical lower
                nr[nk] = v
            # normalize ID fields to upper
            for id_field in ["corridor_id","section_id","line_id","asset_id","task_id","resource_id","train_id","corridor","asset","window_id"]:
                if id_field in nr and isinstance(nr[id_field], str):
                    nr[id_field] = nr[id_field].strip().upper() if nr[id_field] else nr[id_field]
            # department normalization
            if "department" in nr and isinstance(nr["department"], str):
                nr["department"] = nr["department"].strip().upper().replace(" ","_").replace("&","_")
                # map S&T variants
                if nr["department"] in ["S&T","SANDT","S_AND_T","SIGNAL"]:
                    nr["department"] = "S_AND_T"
            normalized.append(nr)
        return normalized

    def validate(self, records: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        # to be overridden
        return records, []

    def to_canonical(self, records: List[Dict]) -> List[Dict]:
        return records
