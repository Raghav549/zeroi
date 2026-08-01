import os
import pathlib
import tempfile

temp_dir = pathlib.Path(tempfile.mkdtemp(prefix="zeroi-test-"))

os.environ["ZEROI_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{temp_dir / 'zeroi_test.db'}"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["ARTIFACT_BACKEND"] = "local"
os.environ["ARTIFACT_LOCAL_DIR"] = str(temp_dir / "artifacts")
os.environ["AUTH_DISABLED"] = "true"
os.environ["LLM_BASE_URL"] = ""
os.environ["LOG_LEVEL"] = "WARNING"
