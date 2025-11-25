import csv
import json
import os
from typing import List
from models import Listing

class Storage:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def save_json(self, listings: List[Listing], filename: str) -> str:
        path = os.path.join(self.output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump([l.to_dict() for l in listings], f, ensure_ascii=False, indent=2)
        return path

    def save_csv(self, listings: List[Listing], filename: str) -> str:
        path = os.path.join(self.output_dir, filename)
        if not listings:
            headers = [
                "external_id",
                "title",
                "price",
                "url",
                "address",
                "area",
                "rooms",
                "property_type",
                "source",
                "parsed_at",
                "description",
                "floor",
                "total_floors",
                "images",
            ]
            with open(path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
            return path

        with open(path, "w", encoding="utf-8", newline="") as f:
            dicts = [l.to_dict() for l in listings]
            for d in dicts:
                if isinstance(d.get("images"), list):
                    d["images"] = ",".join(d["images"])
            writer = csv.DictWriter(f, fieldnames=dicts[0].keys())
            writer.writeheader()
            writer.writerows(dicts)
        return path
