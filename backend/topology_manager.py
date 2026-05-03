"""
topology_manager.py
Loads the digital twin from topology_store.json and exposes
graph-navigation helpers used by the correlation engine and
the FastAPI routes.
"""
import json
from pathlib import Path
from typing import Optional


_STORE_PATH = Path(__file__).parent / "topology_store.json"


class TopologyManager:
    def __init__(self, store_path: Path = _STORE_PATH):
        with open(store_path) as f:
            raw = json.load(f)

        self.sites: dict = {}         # site_id -> site dict
        self.nodes: dict = {}         # node_id -> enriched node dict
        self.parent_map: dict = {}    # child_id -> parent_id
        self.pois: dict = {}          # poi_id -> poi dict

        for site in raw["sites"]:
            self.sites[site["site_id"]] = site
            mh = site["main_hub"]
            self._register_node(mh["id"], "main_hub", site["site_id"], None, mh)

            for eh in mh["expansion_hubs"]:
                self._register_node(eh["id"], "expansion_hub", site["site_id"], mh["id"], eh)
                for ru_id in eh["remotes"]:
                    self._register_node(ru_id, "remote", site["site_id"], eh["id"], {})

        for poi in raw.get("pois", []):
            self.pois[poi["id"]] = poi

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _register_node(self, node_id: str, node_type: str, site_id: str,
                       parent_id: Optional[str], extra: dict):
        self.nodes[node_id] = {
            "id": node_id,
            "type": node_type,
            "site_id": site_id,
            "parent_id": parent_id,
            **extra,
        }
        if parent_id:
            self.parent_map[node_id] = parent_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_node(self, node_id: str) -> Optional[dict]:
        return self.nodes.get(node_id)

    def get_parent(self, node_id: str) -> Optional[dict]:
        pid = self.parent_map.get(node_id)
        return self.nodes.get(pid) if pid else None

    def get_children(self, node_id: str) -> list[dict]:
        return [n for n in self.nodes.values() if n.get("parent_id") == node_id]

    def get_siblings(self, node_id: str) -> list[dict]:
        parent = self.get_parent(node_id)
        if not parent:
            return []
        return [n for n in self.get_children(parent["id"]) if n["id"] != node_id]

    def get_hub_health(self, hub_id: str, alarming_ru_ids: list[str]) -> dict:
        """
        Returns health metrics for an expansion hub.
        If alarming_ru_ids >= provisioned_remotes the hub itself is suspect.
        """
        node = self.get_node(hub_id)
        if not node or node["type"] != "expansion_hub":
            return {}

        provisioned = node.get("provisioned_remotes", 0)
        children = self.get_children(hub_id)
        alarming_under_hub = [ru for ru in alarming_ru_ids if ru in [c["id"] for c in children]]
        ratio = len(alarming_under_hub) / provisioned if provisioned else 0

        return {
            "hub_id": hub_id,
            "provisioned": provisioned,
            "alarming_count": len(alarming_under_hub),
            "ratio": round(ratio, 2),
            "hub_is_suspect": ratio >= 1.0,
            "is_critical": node.get("is_critical", False),
        }

    def get_full_topology(self) -> dict:
        return {
            "sites": list(self.sites.values()),
            "nodes": list(self.nodes.values()),
            "pois": list(self.pois.values()),
        }
