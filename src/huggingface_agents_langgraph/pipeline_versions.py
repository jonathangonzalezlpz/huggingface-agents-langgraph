"""Version identities and presentation metadata for historical experiments."""

from copy import deepcopy

PIPELINE_VERSION = "2"
V2_REFERENCE_ID = "89ff5842-b1bc-4be3-b9c0-3291e97f4afa"
V2_REFERENCE_REVISION = "a9125ee963fa23614409e0928dd260c071394500"
V2_REFERENCE_NAME = "V2 · Completo · referencia"


def experiment_presentation(record: dict) -> dict:
    """Label the verified reference without changing its recorded configuration."""
    if record.get("id") != V2_REFERENCE_ID:
        return record
    result = deepcopy(record)
    result.update(
        display_name=V2_REFERENCE_NAME,
        verified_pipeline_version="2",
        reference_revision=V2_REFERENCE_REVISION,
        is_reference=True,
    )
    return result
