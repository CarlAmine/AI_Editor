import uuid
from typing import Dict, Optional

from pipeline.runner import run_job


def Assemble_Pipeline(
    primary_url: str,
    sources: list = None,
    prompt: str = "",
    music_mode: str = "original",
    custom_music_url: str = None,
    requirements_state: dict = None,
    job_id: str = None,
    gdrive_folder_id: str = None,
) -> Dict:
    """
    Backwards-compatible entrypoint.
    Delegates execution to the new stage-based pipeline runner.
    """
    payload = {
        "primary_url": primary_url,
        "sources": sources or [],
        "prompt": prompt,
        "music_mode": music_mode,
        "custom_music_url": custom_music_url,
        "requirements_state": requirements_state or {},
        "gdrive_folder_id": gdrive_folder_id,
    }
    jid = job_id or str(uuid.uuid4())[:8]
    return run_job(jid, payload)


def main():
    print("This module is a compatibility wrapper around pipeline.runner.run_job().")


if __name__ == "__main__":
    main()
