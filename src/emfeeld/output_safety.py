"""Preflight output admission without writing into existing evidence namespaces.

This is local path safety, not a lock or protection from a concurrent hostile
writer. New artifacts may be assembled inside an unsealed in-progress workflow;
finished inventories, model stores and frozen question locks are not outputs.
"""
from pathlib import Path


def protect_saved_evidence(output: str | Path, *, new_directory: bool = False) -> None:
    """Reject destinations within recognizable saved evidence or model stores.

    Resolve ordinary symlink aliases before checking ancestors. This function
    performs no writes and does not replace a caller's fresh-output or input-
    overwrite checks. Existing ordinary report files outside evidence remain
    governed by that caller's established replacement policy.
    """
    path = Path(output)
    if new_directory and (path.exists() or path.is_symlink()):
        raise FileExistsError('output must be a new directory; previous evidence is never overwritten')
    destination = path.resolve()
    for root in (destination, *destination.parents):
        sealed = (root / 'integrity.json').is_file()
        store = ((root / 'model.json').is_file()
                 and (root / 'revisions').is_dir()
                 and (root / 'proposals').is_dir())
        question = ((root / 'question.json').is_file()
                    and (root / 'receipt.json').is_file())
        study = ((root / 'study.json').is_file()
                 and (root / 'summary.json').is_file())
        replay = ((root / 'manifest.json').is_file()
                  and (root / 'summary.json').is_file())
        attempt = ((root / 'started.json').is_file()
                   and (root / 'outcome.json').is_file())
        if sealed or store or question or study or replay or attempt:
            raise ValueError('output must be outside existing saved evidence and model stores')
