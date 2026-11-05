"""
MIA (Mail Intelligence Assistant) Storage Module.
Provides full Cloud MongoDB Atlas synchronization and local persistence for emails,
structured metadata, vector embeddings, and ingestion jobs.
"""

import json
import sqlite3
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
DB_PATH = DATA_DIR / "atlas_logs.db"

try:
    import pymongo
    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False


class MIAStorage:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_sqlite()
        self._mongo_client = None
        self._cached_mongo_uri = None

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def init_sqlite(self):
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            cursor = conn.cursor()

            # 1. Emails table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS emails (
                    email_id TEXT PRIMARY KEY,
                    thread_id TEXT,
                    sender_name TEXT,
                    sender_email TEXT,
                    sender_domain TEXT,
                    subject TEXT,
                    body TEXT,
                    received_at TEXT,
                    summary TEXT,
                    main_topic TEXT,
                    purpose TEXT,
                    events TEXT,
                    organizations TEXT,
                    locations TEXT,
                    activities TEXT,
                    keywords TEXT,
                    search_descriptions TEXT,
                    processing_status TEXT DEFAULT 'completed'
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_sender_email ON emails(sender_email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_sender_name ON emails(sender_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_received_at ON emails(received_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_thread_id ON emails(thread_id)")

            # 2. Email Embeddings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS email_embeddings (
                    email_id TEXT PRIMARY KEY,
                    model TEXT,
                    embedding TEXT,
                    created_at TEXT,
                    FOREIGN KEY (email_id) REFERENCES emails(email_id) ON DELETE CASCADE
                )
            """)

            # 3. Processing Jobs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processing_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email_id TEXT,
                    status TEXT,
                    attempts INTEGER DEFAULT 0,
                    last_attempt TEXT,
                    error_msg TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_proc_jobs_email_id ON processing_jobs(email_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_proc_jobs_status ON processing_jobs(status)")

            conn.commit()

    def get_mongo_client(self):
        """Returns active pymongo database if configured in mia.mongodb_uri."""
        if not HAS_PYMONGO:
            return None
        from backend.config import config_manager
        uri = config_manager.get("mia.mongodb_uri", "")
        if not uri or not isinstance(uri, str) or not uri.strip():
            return None

        clean_uri = uri.strip()
        if self._mongo_client is not None and self._cached_mongo_uri == clean_uri:
            try:
                return self._mongo_client
            except Exception:
                pass

        # Try to resolve TLS CA bundle via certifi for Windows compatibility
        ca_file = None
        try:
            import certifi
            ca_file = certifi.where()
        except Exception:
            pass

        client = None
        try:
            kwargs = {
                "serverSelectionTimeoutMS": 6000,
                "connectTimeoutMS": 6000,
                "socketTimeoutMS": 10000,
            }
            if ca_file:
                kwargs["tlsCAFile"] = ca_file
            else:
                kwargs["tlsAllowInvalidCertificates"] = True

            client = pymongo.MongoClient(clean_uri, **kwargs)
            client.admin.command('ping')
        except Exception as e:
            # Fallback attempt with tlsAllowInvalidCertificates if certifi fails
            try:
                client = pymongo.MongoClient(clean_uri, serverSelectionTimeoutMS=6000, tlsAllowInvalidCertificates=True)
                client.admin.command('ping')
            except Exception as e2:
                print(f"[MIA Storage] MongoDB Atlas connection error: {e2}")
                return None

        self._mongo_client = client
        self._cached_mongo_uri = clean_uri
        try:
            db_name = config_manager.get("mia.mongodb_db", "atlas_mia")
            db = client[db_name]
            # Ensure indexes
            db.emails.create_index("email_id", unique=True)
            db.emails.create_index("sender_email")
            db.emails.create_index("received_at")
            db.email_embeddings.create_index("email_id", unique=True)
            db.mia_config.create_index("_id")
        except Exception:
            pass
        return client

    def get_backend_type(self) -> str:
        from backend.config import config_manager
        uri = config_manager.get("mia.mongodb_uri", "")
        if uri and isinstance(uri, str) and uri.strip() and self.get_mongo_client() is not None:
            return "mongodb_atlas"
        return "sqlite"

    def test_mongodb(self, uri: str) -> Tuple[bool, str]:
        if not HAS_PYMONGO:
            return False, "pymongo package not installed."
        if not uri or not uri.strip():
            return False, "MongoDB URI cannot be empty."

        ca_file = None
        try:
            import certifi
            ca_file = certifi.where()
        except Exception:
            pass

        try:
            kwargs = {"serverSelectionTimeoutMS": 6000}
            if ca_file:
                kwargs["tlsCAFile"] = ca_file
            else:
                kwargs["tlsAllowInvalidCertificates"] = True
            client = pymongo.MongoClient(uri.strip(), **kwargs)
            client.admin.command('ping')
            return True, "Successfully connected to MongoDB Atlas Cloud."
        except Exception:
            try:
                client = pymongo.MongoClient(uri.strip(), serverSelectionTimeoutMS=6000, tlsAllowInvalidCertificates=True)
                client.admin.command('ping')
                return True, "Successfully connected to MongoDB Atlas Cloud (TLS Fallback)."
            except Exception as e:
                return False, f"Connection failed: {str(e)}"

    def sync_config_to_cloud(self, config_data: Dict[str, Any]) -> bool:
        """Synchronizes MIA settings to MongoDB Atlas Cloud collection."""
        mongo_client = self.get_mongo_client()
        if not mongo_client:
            return False
        try:
            from backend.config import config_manager
            db_name = config_manager.get("mia.mongodb_db", "atlas_mia")
            db = mongo_client[db_name]
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            db.mia_config.update_one(
                {"_id": "active_config"},
                {"$set": {"config": config_data, "updated_at": now}},
                upsert=True
            )
            print("[MIA Storage] Synced active settings to MongoDB Atlas Cloud.")
            return True
        except Exception as e:
            print(f"[MIA Storage] Cloud config sync error: {e}")
            return False

    def get_cloud_config(self) -> Optional[Dict[str, Any]]:
        """Retrieves active configuration synced in MongoDB Atlas Cloud."""
        mongo_client = self.get_mongo_client()
        if not mongo_client:
            return None
        try:
            from backend.config import config_manager
            db_name = config_manager.get("mia.mongodb_db", "atlas_mia")
            doc = mongo_client[db_name].mia_config.find_one({"_id": "active_config"})
            return doc.get("config") if doc else None
        except Exception as e:
            print(f"[MIA Storage] Cloud config fetch error: {e}")
            return None

    def save_email(self, email_data: Dict[str, Any], embedding: Optional[List[float]] = None, model_name: str = "tfidf-dense-v1") -> bool:
        """Atomically saves email and embedding to SQLite and MongoDB Atlas (if configured)."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        def serialize_list(val):
            if isinstance(val, (list, tuple, dict)):
                return json.dumps(val, ensure_ascii=False)
            return val or "[]"

        # 1. Save to SQLite
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO emails (
                    email_id, thread_id, sender_name, sender_email, sender_domain,
                    subject, body, received_at, summary, main_topic, purpose,
                    events, organizations, locations, activities, keywords,
                    search_descriptions, processing_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email_id) DO UPDATE SET
                    thread_id = excluded.thread_id,
                    sender_name = excluded.sender_name,
                    sender_email = excluded.sender_email,
                    sender_domain = excluded.sender_domain,
                    subject = excluded.subject,
                    body = excluded.body,
                    received_at = excluded.received_at,
                    summary = excluded.summary,
                    main_topic = excluded.main_topic,
                    purpose = excluded.purpose,
                    events = excluded.events,
                    organizations = excluded.organizations,
                    locations = excluded.locations,
                    activities = excluded.activities,
                    keywords = excluded.keywords,
                    search_descriptions = excluded.search_descriptions,
                    processing_status = excluded.processing_status
            """, (
                email_data["email_id"],
                email_data.get("thread_id", email_data["email_id"]),
                email_data.get("sender_name", ""),
                email_data.get("sender_email", ""),
                email_data.get("sender_domain", ""),
                email_data.get("subject", ""),
                email_data.get("body", ""),
                email_data.get("received_at", now),
                email_data.get("summary", ""),
                email_data.get("main_topic", ""),
                email_data.get("purpose", ""),
                serialize_list(email_data.get("events")),
                serialize_list(email_data.get("organizations")),
                serialize_list(email_data.get("locations")),
                serialize_list(email_data.get("activities")),
                serialize_list(email_data.get("keywords")),
                serialize_list(email_data.get("search_descriptions")),
                email_data.get("processing_status", "completed")
            ))

            if embedding is not None:
                cursor.execute("""
                    INSERT INTO email_embeddings (email_id, model, embedding, created_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(email_id) DO UPDATE SET
                        model = excluded.model,
                        embedding = excluded.embedding,
                        created_at = excluded.created_at
                """, (
                    email_data["email_id"],
                    model_name,
                    json.dumps(embedding),
                    now
                ))

            cursor.execute("""
                INSERT INTO processing_jobs (email_id, status, attempts, last_attempt, error_msg)
                VALUES (?, 'completed', 1, ?, NULL)
            """, (email_data["email_id"], now))
            conn.commit()

        # 2. Sync to MongoDB Atlas Cloud if active
        mongo_client = self.get_mongo_client()
        if mongo_client:
            try:
                from backend.config import config_manager
                db_name = config_manager.get("mia.mongodb_db", "atlas_mia")
                db = mongo_client[db_name]
                mongo_doc = dict(email_data)
                mongo_doc["updated_at"] = now
                db.emails.update_one({"email_id": email_data["email_id"]}, {"$set": mongo_doc}, upsert=True)
                if embedding is not None:
                    db.email_embeddings.update_one(
                        {"email_id": email_data["email_id"]},
                        {"$set": {"email_id": email_data["email_id"], "model": model_name, "embedding": embedding, "created_at": now}},
                        upsert=True
                    )
            except Exception as ex:
                print(f"[MIA Storage] MongoDB sync error: {ex}")

        return True

    def _parse_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        for field in ("events", "organizations", "locations", "activities", "keywords", "search_descriptions"):
            if field in d and isinstance(d[field], str):
                try:
                    d[field] = json.loads(d[field])
                except Exception:
                    d[field] = []
        return d

    def get_email(self, email_id: str) -> Optional[Dict[str, Any]]:
        mongo_client = self.get_mongo_client()
        if mongo_client:
            try:
                from backend.config import config_manager
                db_name = config_manager.get("mia.mongodb_db", "atlas_mia")
                doc = mongo_client[db_name].emails.find_one({"email_id": email_id}, {"_id": 0})
                if doc:
                    return doc
            except Exception:
                pass

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM emails WHERE email_id = ?", (email_id,))
            row = cursor.fetchone()
            return self._parse_row(row) if row else None

    def get_all_emails(self) -> List[Dict[str, Any]]:
        mongo_client = self.get_mongo_client()
        if mongo_client:
            try:
                from backend.config import config_manager
                db_name = config_manager.get("mia.mongodb_db", "atlas_mia")
                docs = list(mongo_client[db_name].emails.find({}, {"_id": 0}).sort("received_at", -1))
                if docs:
                    return docs
            except Exception:
                pass

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM emails ORDER BY received_at DESC")
            return [self._parse_row(r) for r in cursor.fetchall()]

    def get_recent_emails(self, limit: int = 5) -> List[Dict[str, Any]]:
        mongo_client = self.get_mongo_client()
        if mongo_client:
            try:
                from backend.config import config_manager
                db_name = config_manager.get("mia.mongodb_db", "atlas_mia")
                docs = list(mongo_client[db_name].emails.find({}, {"_id": 0}).sort("received_at", -1).limit(limit))
                if docs:
                    return docs
            except Exception as e:
                print(f"[MIA Storage] get_recent_emails error: {e}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM emails ORDER BY received_at DESC LIMIT ?", (limit,))
            return [self._parse_row(r) for r in cursor.fetchall()]

    def search_by_sender(self, query: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        """
        Searches sender_name, sender_email, and sender_domain with case-insensitivity,
        whitespace normalization, and partial/exact matching.
        """
        q = " ".join(query.strip().lower().split())
        if not q:
            return [], []

        mongo_client = self.get_mongo_client()
        if mongo_client:
            try:
                from backend.config import config_manager
                db_name = config_manager.get("mia.mongodb_db", "atlas_mia")
                filter_q = {
                    "$or": [
                        {"sender_name": {"$regex": q, "$options": "i"}},
                        {"sender_email": {"$regex": q, "$options": "i"}},
                        {"sender_domain": {"$regex": q, "$options": "i"}}
                    ]
                }
                docs = list(mongo_client[db_name].emails.find(filter_q, {"_id": 0}).sort("received_at", -1))
                if docs:
                    senders_map: Dict[str, Dict[str, str]] = {}
                    for e in docs:
                        key = (e.get("sender_email") or "").lower().strip() or (e.get("sender_name") or "").lower().strip()
                        if key not in senders_map:
                            senders_map[key] = {
                                "name": e.get("sender_name", ""),
                                "email": e.get("sender_email", ""),
                                "domain": e.get("sender_domain", "")
                            }
                    return docs, list(senders_map.values())
            except Exception as ex:
                print(f"[MIA Storage] MongoDB search error: {ex}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM emails
                WHERE LOWER(sender_name) LIKE ?
                   OR LOWER(sender_email) LIKE ?
                   OR LOWER(sender_domain) LIKE ?
                ORDER BY received_at DESC
            """, (f"%{q}%", f"%{q}%", f"%{q}%"))
            rows = cursor.fetchall()
            emails = [self._parse_row(r) for r in rows]

            senders_map = {}
            for e in emails:
                key = (e.get("sender_email") or "").lower().strip() or (e.get("sender_name") or "").lower().strip()
                if key not in senders_map:
                    senders_map[key] = {
                        "name": e.get("sender_name", ""),
                        "email": e.get("sender_email", ""),
                        "domain": e.get("sender_domain", "")
                    }

            return emails, list(senders_map.values())

    def get_emails_since(self, since_iso: str) -> List[Dict[str, Any]]:
        mongo_client = self.get_mongo_client()
        if mongo_client:
            try:
                from backend.config import config_manager
                db_name = config_manager.get("mia.mongodb_db", "atlas_mia")
                docs = list(mongo_client[db_name].emails.find({"received_at": {"$gte": since_iso}}, {"_id": 0}).sort("received_at", -1))
                if docs:
                    return docs
            except Exception:
                pass

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM emails
                WHERE received_at >= ?
                ORDER BY received_at DESC
            """, (since_iso,))
            return [self._parse_row(r) for r in cursor.fetchall()]

    def get_all_embeddings(self) -> Dict[str, List[float]]:
        mongo_client = self.get_mongo_client()
        if mongo_client:
            try:
                from backend.config import config_manager
                db_name = config_manager.get("mia.mongodb_db", "atlas_mia")
                docs = list(mongo_client[db_name].email_embeddings.find({}, {"_id": 0}))
                res = {}
                for doc in docs:
                    res[doc["email_id"]] = doc["embedding"]
                if res:
                    return res
            except Exception:
                pass

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT email_id, embedding FROM email_embeddings")
            res = {}
            for row in cursor.fetchall():
                try:
                    res[row["email_id"]] = json.loads(row["embedding"])
                except Exception:
                    pass
            return res

    def get_stats(self) -> Dict[str, Any]:
        backend_type = self.get_backend_type()
        mongo_client = self.get_mongo_client()
        mongo_connected = mongo_client is not None

        if mongo_connected:
            try:
                from backend.config import config_manager
                db_name = config_manager.get("mia.mongodb_db", "atlas_mia")
                db = mongo_client[db_name]
                total_emails = db.emails.count_documents({})
                total_embeddings = db.email_embeddings.count_documents({})
                return {
                    "total_emails": total_emails,
                    "total_embeddings": total_embeddings,
                    "completed_jobs": total_emails,
                    "backend": backend_type,
                    "cloud_connected": True
                }
            except Exception as e:
                print(f"[MIA Storage] Stats from MongoDB Atlas error: {e}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM emails")
            total_emails = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM email_embeddings")
            total_embeddings = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM processing_jobs WHERE status = 'completed'")
            completed_jobs = cursor.fetchone()[0]

            return {
                "total_emails": total_emails,
                "total_embeddings": total_embeddings,
                "completed_jobs": completed_jobs,
                "backend": backend_type,
                "cloud_connected": mongo_connected
            }

    def clear_all(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM email_embeddings")
            cursor.execute("DELETE FROM emails")
            cursor.execute("DELETE FROM processing_jobs")
            conn.commit()

        mongo_client = self.get_mongo_client()
        if mongo_client:
            try:
                from backend.config import config_manager
                db_name = config_manager.get("mia.mongodb_db", "atlas_mia")
                db = mongo_client[db_name]
                db.emails.delete_many({})
                db.email_embeddings.delete_many({})
            except Exception as e:
                print(f"[MIA Storage] MongoDB clear error: {e}")


mia_storage = MIAStorage()
