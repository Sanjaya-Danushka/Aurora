#!/usr/bin/env python3
"""
Supabase-backed Community Plugin Store for Aurora/NeoArch
- Real CRUD with Storage uploads (icon, plugin file)
- Auth (email/password)
- Public discovery
- Real download counter via RPC 'increment_downloads'

Reads config from env:
  SUPABASE_URL
  SUPABASE_ANON_KEY
Falls back to provided defaults if present here.
"""
from __future__ import annotations

import os
import re
import json
import mimetypes
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Third-party
try:
    from supabase import create_client, Client
except Exception:
    create_client = None  # type: ignore
    Client = object  # type: ignore

try:
    import requests
except Exception:
    requests = None  # type: ignore


class SupabasePluginStore:
    def __init__(self,
                 url: Optional[str] = None,
                 anon_key: Optional[str] = None,
                 config_dir: Optional[Path] = None) -> None:
        self.url = url or os.getenv("SUPABASE_URL") or "https://rmliylcskqdlooftgwtc.supabase.co"
        self.anon_key = anon_key or os.getenv("SUPABASE_ANON_KEY") or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJtbGl5bGNza3FkbG9vZnRnd3RjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjIyMzY1MTksImV4cCI6MjA3NzgxMjUxOX0.lTsyJDrX5HpOicXNrFaKxYQaWE1MONQqOmkFdN7d76o"
        self.config_dir = config_dir or (Path.home() / ".config" / "aurora")
        self.plugins_dir = self.config_dir / "plugins"
        self._client: Optional[Client] = None
        self._session = None

        if create_client is not None and self.url and self.anon_key:
            try:
                self._client = create_client(self.url, self.anon_key)
            except Exception:
                self._client = None

    # ---------------- Basic helpers ----------------
    def is_configured(self) -> bool:
        return self._client is not None

    def _ensure_requests(self) -> None:
        if requests is None:
            raise RuntimeError("'requests' is required. Install with: pip install requests")

    def _slug_ok(self, slug: str) -> bool:
        return bool(re.match(r"^[a-z0-9_]+$", slug))

    def _mimetype(self, path: str) -> str:
        m, _ = mimetypes.guess_type(path)
        return m or "application/octet-stream"

    # ---------------- Auth ----------------
    def sign_in(self, email: str, password: str) -> Dict:
        if not self._client:
            raise RuntimeError("Supabase client not configured")
        try:
            res = self._client.auth.sign_in_with_password({"email": email, "password": password})
            self._session = getattr(res, "session", None) or getattr(res, "user", None)
            return {"ok": True, "user": getattr(res, "user", None)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def sign_up(self, email: str, password: str) -> Dict:
        if not self._client:
            raise RuntimeError("Supabase client not configured")
        try:
            res = self._client.auth.sign_up({"email": email, "password": password})
            return {"ok": True, "user": getattr(res, "user", None)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def sign_out(self) -> Dict:
        if not self._client:
            return {"ok": True}
        try:
            self._client.auth.sign_out()
            self._session = None
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def current_user_id(self) -> Optional[str]:
        if not self._client:
            return None
        try:
            u = self._client.auth.get_user()
            if hasattr(u, "user") and u.user is not None:
                return getattr(u.user, "id", None)
            # older returns might already be user
            return getattr(u, "id", None)
        except Exception:
            return None

    # ---------------- Discovery / Install ----------------
    def discover_plugins(self) -> List[Dict]:
        if not self._client:
            return []
        try:
            res = self._client.table("plugins").select("*").order("updated_at", desc=True).execute()
            data = getattr(res, "data", None)
            if data is None:
                # supabase-py sometimes returns dict
                data = getattr(res, "model_dump", lambda: {})()
                data = data.get("data", [])
            # Normalize keys expected by UI
            items: List[Dict] = []
            for r in data or []:
                items.append({
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "description": r.get("description") or r.get("desc", ""),
                    "author": r.get("author", "Unknown"),
                    "version": r.get("version", "1.0.0"),
                    "downloads": r.get("downloads", 0),
                    "last_updated": r.get("updated_at", ""),
                    "features": r.get("features", []),
                    "icon_url": r.get("icon_url"),
                    "file_url": r.get("file_url"),
                })
            return items
        except Exception:
            return []

    def _get_plugin_row(self, plugin_id: str) -> Optional[Dict]:
        if not self._client:
            return None
        try:
            res = self._client.table("plugins").select("*").eq("id", plugin_id).limit(1).execute()
            data = getattr(res, "data", None) or []
            return data[0] if data else None
        except Exception:
            return None

    def install_community_plugin(self, plugin_id: str) -> bool:
        if not self._client:
            return False
        self._ensure_requests()
        row = self._get_plugin_row(plugin_id)
        if not row:
            return False
        url = row.get("file_url")
        if not url:
            return False
        try:
            r = requests.get(url, timeout=30)
            if r.status_code != 200:
                return False
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
            path = self.plugins_dir / f"{plugin_id}.py"
            with open(path, "w", encoding="utf-8") as f:
                f.write(r.text)
            # Increment downloads via RPC (best-effort)
            try:
                self._client.rpc("increment_downloads", {"p_id": plugin_id}).execute()
            except Exception:
                pass
            return True
        except Exception:
            return False

    # ---------------- Manage My Plugins ----------------
    def list_my_plugins(self) -> List[Dict]:
        if not self._client:
            return []
        uid = self.current_user_id()
        if not uid:
            return []
        try:
            res = self._client.table("plugins").select("*").eq("created_by", uid).order("updated_at", desc=True).execute()
            return getattr(res, "data", None) or []
        except Exception:
            return []

    def _upload_to_bucket(self, bucket: str, object_path: str, local_path: str) -> Optional[str]:
        if not self._client:
            return None
        try:
            storage = self._client.storage.from_(bucket)
            with open(local_path, "rb") as fh:
                mime = self._mimetype(local_path)
                # upsert to overwrite if exists
                storage.upload(object_path, fh, file_options={"content-type": mime, "upsert": "true"})
            # public url
            pub = storage.get_public_url(object_path)
            # supabase-py returns dict-like or object; normalize
            if isinstance(pub, dict):
                return pub.get("public_url") or pub.get("publicURL") or pub.get("publicUrl")
            return str(pub)
        except Exception:
            return None

    def create_plugin(self,
                      plugin_id: str,
                      name: str,
                      description: str,
                      version: str,
                      author: str,
                      categories: Optional[List[str]] = None,
                      icon_path: Optional[str] = None,
                      file_path: Optional[str] = None) -> Dict:
        if not self._client:
            return {"ok": False, "error": "Supabase not configured"}
        if not self._slug_ok(plugin_id):
            return {"ok": False, "error": "id must be lowercase [a-z0-9_]"}
        uid = self.current_user_id()
        if not uid:
            return {"ok": False, "error": "Not authenticated"}
        # Ensure unique id
        try:
            exists = self._get_plugin_row(plugin_id)
            if exists:
                return {"ok": False, "error": "Plugin id already exists"}
        except Exception:
            pass
        icon_url = None
        file_url = None
        # Upload assets first (so we can store URLs)
        if icon_path:
            ext = Path(icon_path).suffix.lower() or ".png"
            icon_obj = f"{uid}/{plugin_id}{ext}"
            icon_url = self._upload_to_bucket("plugin-icons", icon_obj, icon_path)
        if file_path:
            file_obj = f"{uid}/{plugin_id}{Path(file_path).suffix or '.py'}"
            file_url = self._upload_to_bucket("plugin-files", file_obj, file_path)
            if not file_url:
                return {"ok": False, "error": "Failed to upload plugin file"}
        try:
            payload = {
                "id": plugin_id,
                "name": name,
                "description": description,
                "version": version or "1.0.0",
                "author": author or "Unknown",
                "categories": categories or [],
                "icon_url": icon_url,
                "file_url": file_url,
                "downloads": 0,
                "created_by": uid,
            }
            res = self._client.table("plugins").insert(payload).execute()
            return {"ok": True, "data": getattr(res, "data", None)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def update_plugin(self,
                      plugin_id: str,
                      name: Optional[str] = None,
                      description: Optional[str] = None,
                      version: Optional[str] = None,
                      author: Optional[str] = None,
                      categories: Optional[List[str]] = None,
                      icon_path: Optional[str] = None,
                      file_path: Optional[str] = None) -> Dict:
        if not self._client:
            return {"ok": False, "error": "Supabase not configured"}
        uid = self.current_user_id()
        if not uid:
            return {"ok": False, "error": "Not authenticated"}
        # prepare updates
        updates: Dict[str, object] = {}
        if name is not None:
            updates["name"] = name
        if description is not None:
            updates["description"] = description
        if version is not None:
            updates["version"] = version
        if author is not None:
            updates["author"] = author
        if categories is not None:
            updates["categories"] = categories
        if icon_path:
            ext = Path(icon_path).suffix.lower() or ".png"
            icon_obj = f"{uid}/{plugin_id}{ext}"
            icon_url = self._upload_to_bucket("plugin-icons", icon_obj, icon_path)
            if icon_url:
                updates["icon_url"] = icon_url
        if file_path:
            file_obj = f"{uid}/{plugin_id}{Path(file_path).suffix or '.py'}"
            file_url = self._upload_to_bucket("plugin-files", file_obj, file_path)
            if file_url:
                updates["file_url"] = file_url
        if not updates:
            return {"ok": True, "data": None}
        try:
            res = self._client.table("plugins").update(updates).eq("id", plugin_id).execute()
            return {"ok": True, "data": getattr(res, "data", None)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def delete_plugin(self, plugin_id: str) -> Dict:
        if not self._client:
            return {"ok": False, "error": "Supabase not configured"}
        uid = self.current_user_id()
        if not uid:
            return {"ok": False, "error": "Not authenticated"}
        # Best-effort: remove storage items with common paths
        try:
            # Try to infer stored paths by listing (optional). For simplicity, remove typical locations.
            icons = [f"{uid}/{plugin_id}.png", f"{uid}/{plugin_id}.svg"]
            files = [f"{uid}/{plugin_id}.py"]
            try:
                self._client.storage.from_("plugin-icons").remove(icons)
            except Exception:
                pass
            try:
                self._client.storage.from_("plugin-files").remove(files)
            except Exception:
                pass
        except Exception:
            pass
        try:
            self._client.table("plugins").delete().eq("id", plugin_id).execute()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ---------------- Diagnostics ----------------
    def get_setup_status(self) -> Dict:
        """
        Return diagnostics about required Supabase objects.
        Keys:
          - has_plugins_table: bool
          - has_increment_fn: bool
          - plugins_error: optional str
          - increment_error: optional str
        """
        status = {
            "has_plugins_table": False,
            "has_increment_fn": False,
        }
        if not self._client:
            status["plugins_error"] = "Client not configured"
            status["increment_error"] = "Client not configured"
            return status
        # Check table
        try:
            self._client.table("plugins").select("id").limit(1).execute()
            status["has_plugins_table"] = True
        except Exception as e:
            status["plugins_error"] = str(e)
        # Check function
        try:
            # Safe call; will no-op if id doesn't exist
            self._client.rpc("increment_downloads", {"p_id": "__noop__"}).execute()
            status["has_increment_fn"] = True
        except Exception as e:
            status["increment_error"] = str(e)
        return status
