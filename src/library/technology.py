# -*- coding: utf-8 -*-
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .database import LibraryDatabase


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:16]}"


class TechnologyRepository:
    def __init__(self, database: Optional[LibraryDatabase] = None):
        self.db = database or LibraryDatabase()

    @staticmethod
    def _decode(row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        result = dict(row)
        result["keywords"] = json.loads(result.pop("keywords_json"))
        result["aliases"] = json.loads(result.pop("aliases_json"))
        return result

    def _path(self, connection, node_id: str) -> List[Dict[str, Any]]:
        rows = connection.execute(
            """WITH RECURSIVE ancestors AS (
                 SELECT node_id,parent_id,level,name,0 depth
                 FROM technology_nodes WHERE node_id=?
                 UNION ALL
                 SELECT n.node_id,n.parent_id,n.level,n.name,a.depth+1
                 FROM technology_nodes n JOIN ancestors a ON a.parent_id=n.node_id
               )
               SELECT node_id,level,name FROM ancestors ORDER BY depth DESC""",
            (node_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _effective_status(connection, node_id: str) -> str:
        row = connection.execute(
            """WITH RECURSIVE ancestors(node_id,parent_id,status) AS (
                 SELECT node_id,parent_id,status FROM technology_nodes WHERE node_id=?
                 UNION ALL
                 SELECT n.node_id,n.parent_id,n.status
                 FROM technology_nodes n JOIN ancestors a ON a.parent_id=n.node_id
               )
               SELECT COUNT(*) total,
                      SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) active
               FROM ancestors""",
            (node_id,),
        ).fetchone()
        return "active" if row and row["total"] == row["active"] else "inactive"

    def affected_descendants(self, node_id: str) -> List[Dict[str, Any]]:
        return [
            item for item in self.descendants(node_id, active_only=False)
            if item["node_id"] != node_id and item.get("effective_status") == "active"
        ]

    def get(self, node_id: str) -> Optional[Dict[str, Any]]:
        with self.db.connect() as connection:
            node = self._decode(connection.execute(
                "SELECT * FROM technology_nodes WHERE node_id=?", (node_id,)
            ).fetchone())
            if not node:
                return None
            node["path"] = self._path(connection, node_id)
            node["path_text"] = " / ".join(item["name"] for item in node["path"])
            node["effective_status"] = self._effective_status(connection, node_id)
            node["children"] = [self._decode(row) for row in connection.execute(
                """SELECT * FROM technology_nodes WHERE parent_id=?
                   ORDER BY sort_order,name""",
                (node_id,),
            ).fetchall()]
            for child in node["children"]:
                child["effective_status"] = self._effective_status(
                    connection, child["node_id"]
                )
            node["relations"] = self.list_relations(node_id)
            return node

    def list_nodes(
        self, level: Optional[int] = None, status: str = "",
        query: str = "",
    ) -> List[Dict[str, Any]]:
        clauses, values = ["1=1"], []
        if level is not None:
            clauses.append("n.level=?")
            values.append(level)
        if status == "active":
            clauses.append("e.effective_active=1")
        elif status:
            clauses.append("n.status=?")
            values.append(status)
        if query:
            clauses.append("(n.name LIKE ? OR n.aliases_json LIKE ? OR n.keywords_json LIKE ?)")
            like = f"%{query}%"
            values.extend([like, like, like])
        with self.db.connect() as connection:
            rows = connection.execute(
                f"""WITH RECURSIVE effective(node_id,effective_active) AS (
                      SELECT node_id,status='active'
                      FROM technology_nodes WHERE parent_id IS NULL
                      UNION ALL
                      SELECT n.node_id,e.effective_active AND n.status='active'
                      FROM technology_nodes n JOIN effective e ON n.parent_id=e.node_id
                    )
                    SELECT n.*,e.effective_active
                    FROM technology_nodes n JOIN effective e ON e.node_id=n.node_id
                    WHERE {' AND '.join(clauses)}
                    ORDER BY n.level,n.sort_order,n.name""",
                values,
            ).fetchall()
            results = []
            for row in rows:
                node = self._decode(row)
                node["effective_status"] = (
                    "active" if node.pop("effective_active") else "inactive"
                )
                node["path"] = self._path(connection, node["node_id"])
                node["path_text"] = " / ".join(item["name"] for item in node["path"])
                results.append(node)
            return results

    def tree(self, include_archived: bool = False, query: str = "") -> List[Dict[str, Any]]:
        nodes = self.list_nodes(status="" if include_archived else "active")
        by_id = {node["node_id"]: {**node, "children": []} for node in nodes}
        roots = []
        for node in by_id.values():
            parent = by_id.get(node["parent_id"])
            if parent:
                parent["children"].append(node)
            elif node["level"] == 1:
                roots.append(node)
        if query:
            lowered = query.lower()

            def keep(node: Dict[str, Any]) -> bool:
                node["children"] = [
                    child for child in node["children"] if keep(child)
                ]
                own = lowered in " ".join([
                    node["name"], *node.get("keywords", []),
                    *node.get("aliases", []),
                ]).lower()
                return own or bool(node["children"])

            roots = [root for root in roots if keep(root)]
        return roots

    def descendants(
        self, node_id: str, level: Optional[int] = None,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        with self.db.connect() as connection:
            clauses = []
            values: List[Any] = [node_id]
            if level is not None:
                clauses.append("n.level=?")
                values.append(level)
            if active_only:
                clauses.append("d.effective_active=1")
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = connection.execute(
                f"""WITH RECURSIVE descendants(node_id,effective_active) AS (
                      SELECT node_id,status='active'
                      FROM technology_nodes WHERE node_id=?
                      UNION ALL
                      SELECT n.node_id,d.effective_active AND n.status='active'
                      FROM technology_nodes n
                      JOIN descendants d ON n.parent_id=d.node_id
                    )
                    SELECT n.*,d.effective_active FROM technology_nodes n
                    JOIN descendants d ON n.node_id=d.node_id
                    {where} ORDER BY n.level,n.sort_order,n.name""",
                values,
            ).fetchall()
            results = []
            for row in rows:
                item = self._decode(row)
                item["effective_status"] = (
                    "active" if item.pop("effective_active") else "inactive"
                )
                item["path"] = self._path(connection, item["node_id"])
                item["path_text"] = " / ".join(
                    part["name"] for part in item["path"]
                )
                results.append(item)
            return results

    def _validate_parent(
        self, connection, parent_id: Optional[str], level: int,
        node_id: str = "",
    ) -> None:
        if level == 1:
            if parent_id:
                raise ValueError("一级技术不能设置父节点")
            return
        parent = connection.execute(
            "SELECT * FROM technology_nodes WHERE node_id=?", (parent_id,)
        ).fetchone()
        if (
            not parent or parent["status"] != "active"
            or self._effective_status(connection, parent_id) != "active"
        ):
            raise ValueError("父技术不存在或已归档")
        if parent["level"] != level - 1:
            raise ValueError("技术父子层级必须连续")
        if node_id:
            descendants = connection.execute(
                """WITH RECURSIVE d(node_id) AS (
                     SELECT node_id FROM technology_nodes WHERE parent_id=?
                     UNION ALL SELECT n.node_id FROM technology_nodes n
                     JOIN d ON n.parent_id=d.node_id
                   ) SELECT node_id FROM d WHERE node_id=?""",
                (node_id, parent_id),
            ).fetchone()
            if parent_id == node_id or descendants:
                raise ValueError("技术节点不能移动到自身或后代节点下")

    @staticmethod
    def _slug(name: str) -> str:
        value = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return value or f"technology-{uuid4().hex[:10]}"

    def _next_version(self, connection) -> int:
        row = connection.execute(
            "SELECT COALESCE(MAX(taxonomy_version),0)+1 value FROM technology_nodes"
        ).fetchone()
        return int(row["value"])

    def _audit(
        self, connection, node_id: str, action: str,
        before: Optional[Dict[str, Any]], after: Optional[Dict[str, Any]],
    ) -> None:
        connection.execute(
            """INSERT INTO technology_change_logs(
                 change_id,node_id,action,before_json,after_json
               ) VALUES (?,?,?,?,?)""",
            (
                _id("change"), node_id, action,
                json.dumps(before or {}, ensure_ascii=False, default=str),
                json.dumps(after or {}, ensure_ascii=False, default=str),
            ),
        )

    def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        name = str(payload.get("name", "")).strip()
        level = int(payload.get("level", 0))
        if not name or level not in {1, 2, 3}:
            raise ValueError("技术名称或层级无效")
        node_id = payload.get("node_id") or _id("technology")
        with self.db.transaction() as connection:
            self._validate_parent(connection, payload.get("parent_id"), level)
            version = self._next_version(connection)
            connection.execute(
                """INSERT INTO technology_nodes(
                     node_id,parent_id,level,name,slug,description,keywords_json,
                     aliases_json,status,sort_order,taxonomy_version
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    node_id, payload.get("parent_id"), level, name,
                    payload.get("slug") or self._slug(name),
                    payload.get("description", ""),
                    json.dumps(payload.get("keywords", []), ensure_ascii=False),
                    json.dumps(payload.get("aliases", []), ensure_ascii=False),
                    payload.get("status", "active"),
                    int(payload.get("sort_order", 0)), version,
                ),
            )
            after = dict(connection.execute(
                "SELECT * FROM technology_nodes WHERE node_id=?", (node_id,)
            ).fetchone())
            self._audit(connection, node_id, "create", None, after)
        return self.get(node_id)

    def update(self, node_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
        allowed = {
            "name", "description", "keywords", "aliases", "sort_order", "status",
            "parent_id",
        }
        with self.db.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM technology_nodes WHERE node_id=?", (node_id,)
            ).fetchone()
            if not row:
                raise ValueError("技术节点不存在")
            before = dict(row)
            if "parent_id" in changes:
                self._validate_parent(
                    connection, changes.get("parent_id"), row["level"], node_id
                )
            fields, values = [], []
            for key, value in changes.items():
                if key not in allowed:
                    continue
                column = key
                if key in {"keywords", "aliases"}:
                    column = f"{key}_json"
                    value = json.dumps(value, ensure_ascii=False)
                fields.append(f"{column}=?")
                values.append(value)
            if fields:
                version = self._next_version(connection)
                fields.extend(["taxonomy_version=?", "updated_at=?"])
                values.extend([version, datetime.now(timezone.utc).isoformat(), node_id])
                connection.execute(
                    f"UPDATE technology_nodes SET {','.join(fields)} WHERE node_id=?",
                    values,
                )
                after = dict(connection.execute(
                    "SELECT * FROM technology_nodes WHERE node_id=?", (node_id,)
                ).fetchone())
                self._audit(connection, node_id, "update", before, after)
        return self.get(node_id)

    def move(self, node_id: str, parent_id: Optional[str], sort_order: int = 0) -> Dict[str, Any]:
        with self.db.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM technology_nodes WHERE node_id=?", (node_id,)
            ).fetchone()
            if not row:
                raise ValueError("技术节点不存在")
            before = dict(row)
            self._validate_parent(connection, parent_id, row["level"], node_id)
            version = self._next_version(connection)
            connection.execute(
                """UPDATE technology_nodes
                   SET parent_id=?,sort_order=?,taxonomy_version=?,updated_at=?
                   WHERE node_id=?""",
                (
                    parent_id, sort_order, version,
                    datetime.now(timezone.utc).isoformat(), node_id,
                ),
            )
            after = dict(connection.execute(
                "SELECT * FROM technology_nodes WHERE node_id=?", (node_id,)
            ).fetchone())
            self._audit(connection, node_id, "move", before, after)
        return self.get(node_id)

    def references(self, node_id: str) -> Dict[str, int]:
        with self.db.connect() as connection:
            queries = {
                "datasets": "SELECT COUNT(*) value FROM datasets WHERE technology_node_id=?",
                "projects": "SELECT COUNT(*) value FROM projects WHERE technology_node_id=?",
                "topics": "SELECT COUNT(*) value FROM project_topic_technologies WHERE technology_node_id=?",
                "jobs": "SELECT COUNT(*) value FROM forecast_jobs WHERE taxonomy_snapshot_json LIKE ?",
            }
            return {
                key: int(connection.execute(
                    sql, (f"%{node_id}%",) if key == "jobs" else (node_id,)
                ).fetchone()["value"])
                for key, sql in queries.items()
            }

    def summary(self, node_id: str) -> Dict[str, Any]:
        node = self.get(node_id)
        if not node:
            raise ValueError("技术节点不存在")
        leaf_ids = [
            item["node_id"] for item in self.descendants(
                node_id, level=3, active_only=True
            )
        ]
        counts = {
            "datasets": 0, "papers": 0, "ipc_records": 0,
            "source_files": 0, "projects": 0,
        }
        if leaf_ids:
            placeholders = ",".join("?" for _ in leaf_ids)
            eligible = (
                "d.status='published' AND d.lifecycle_status='active' "
                "AND d.migration_status='mapped'"
            )
            with self.db.connect() as connection:
                row = connection.execute(
                    f"""SELECT
                          COUNT(DISTINCT d.dataset_id) datasets,
                          COUNT(DISTINCT p.paper_id) papers,
                          COUNT(DISTINCT m.metric_id) ipc_records,
                          COUNT(DISTINCT s.file_id) source_files
                        FROM datasets d
                        LEFT JOIN papers p ON p.dataset_id=d.dataset_id
                        LEFT JOIN ipc_metrics m ON m.dataset_id=d.dataset_id
                        LEFT JOIN source_files s ON s.dataset_id=d.dataset_id
                        WHERE d.technology_node_id IN ({placeholders}) AND {eligible}""",
                    leaf_ids,
                ).fetchone()
                counts.update(dict(row))
                counts["projects"] = int(connection.execute(
                    """SELECT COUNT(*) value FROM projects
                       WHERE technology_node_id=?""",
                    (node_id,),
                ).fetchone()["value"])
        return {
            "node_id": node_id,
            "name": node["name"],
            "path_text": node["path_text"],
            "level": node["level"],
            "status": node["status"],
            "effective_status": node["effective_status"],
            "child_count": len(node.get("children", [])),
            **counts,
            "references": self.references(node_id),
        }

    def archive(
        self, node_id: str, *, confirm_descendants: bool = False
    ) -> Dict[str, Any]:
        affected = self.affected_descendants(node_id)
        if affected and not confirm_descendants:
            raise ValueError("该技术仍有启用下级，需确认级联停用影响")
        return self.update(node_id, {"status": "archived"})

    def restore(self, node_id: str) -> Dict[str, Any]:
        node = self.get(node_id)
        if not node:
            raise ValueError("技术节点不存在")
        if node["parent_id"]:
            parent = self.get(node["parent_id"])
            if (
                not parent or parent["status"] != "active"
                or parent.get("effective_status") != "active"
            ):
                raise ValueError("请先恢复父技术")
        return self.update(node_id, {"status": "active"})

    def delete(self, node_id: str) -> None:
        refs = self.references(node_id)
        with self.db.transaction() as connection:
            child = connection.execute(
                "SELECT 1 FROM technology_nodes WHERE parent_id=? LIMIT 1", (node_id,)
            ).fetchone()
            if child or any(refs.values()):
                raise ValueError("技术已被引用或仍有下级节点，只能归档")
            before = connection.execute(
                "SELECT * FROM technology_nodes WHERE node_id=?", (node_id,)
            ).fetchone()
            if not before:
                raise ValueError("技术节点不存在")
            self._audit(connection, node_id, "delete", dict(before), None)
            connection.execute(
                "DELETE FROM technology_relations WHERE source_node_id=? OR target_node_id=?",
                (node_id, node_id),
            )
            connection.execute("DELETE FROM technology_nodes WHERE node_id=?", (node_id,))

    def create_relation(
        self, source_node_id: str, target_node_id: str,
        relation_type: str, status: str = "confirmed",
    ) -> Dict[str, Any]:
        if relation_type not in {"related", "depends_on", "converges_with"}:
            raise ValueError("技术关系类型无效")
        if source_node_id == target_node_id:
            raise ValueError("技术不能关联自身")
        relation_id = _id("relation")
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO technology_relations(
                     relation_id,source_node_id,target_node_id,relation_type,status
                   ) VALUES (?,?,?,?,?)""",
                (relation_id, source_node_id, target_node_id, relation_type, status),
            )
            return dict(connection.execute(
                "SELECT * FROM technology_relations WHERE relation_id=?",
                (relation_id,),
            ).fetchone())

    def list_relations(self, node_id: str) -> List[Dict[str, Any]]:
        with self.db.connect() as connection:
            return [dict(row) for row in connection.execute(
                """SELECT r.*,s.name source_name,t.name target_name
                   FROM technology_relations r
                   JOIN technology_nodes s ON s.node_id=r.source_node_id
                   JOIN technology_nodes t ON t.node_id=r.target_node_id
                   WHERE r.source_node_id=? OR r.target_node_id=?
                   ORDER BY r.created_at""",
                (node_id, node_id),
            ).fetchall()]

    def delete_relation(self, relation_id: str) -> bool:
        with self.db.transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM technology_relations WHERE relation_id=?", (relation_id,)
            )
            return cursor.rowcount > 0

    def changes(self, node_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM technology_change_logs WHERE node_id=?
                   ORDER BY created_at DESC LIMIT ?""",
                (node_id, limit),
            ).fetchall()
            results = []
            for row in rows:
                item = dict(row)
                item["before"] = json.loads(item.pop("before_json"))
                item["after"] = json.loads(item.pop("after_json"))
                results.append(item)
            return results

    def snapshot(self, root_id: str) -> Dict[str, Any]:
        root = self.get(root_id)
        if not root or root["level"] != 1:
            raise ValueError("项目技术范围必须是一级技术")
        nodes = self.descendants(root_id, active_only=True)
        return {
            "root": {
                "node_id": root["node_id"], "name": root["name"],
                "path": root["path"], "taxonomy_version": root["taxonomy_version"],
            },
            "nodes": [
                {
                    "node_id": node["node_id"], "parent_id": node["parent_id"],
                    "level": node["level"], "name": node["name"],
                    "taxonomy_version": node["taxonomy_version"],
                }
                for node in nodes
            ],
            "taxonomy_version": max(
                (node["taxonomy_version"] for node in nodes), default=1
            ),
        }
