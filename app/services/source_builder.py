"""Mutate a source tarball to inject/replace a Procfile at the archive root."""

import io
import tarfile


def inject_procfile(tarball_bytes: bytes, process_type: str, start_command: str) -> bytes:
    """Return a new tarball with a Procfile injected (or replaced) at the root.

    GitHub tarballs have a single top-level directory; the Procfile is placed
    inside it (the archive root). An existing Procfile at the root is replaced.
    """
    procfile_content = f"{process_type}: {start_command}\n".encode()

    src = tarfile.open(fileobj=io.BytesIO(tarball_bytes), mode="r:gz")
    out_buf = io.BytesIO()
    out = tarfile.open(fileobj=out_buf, mode="w:gz")

    top_dir: str | None = None
    for member in src.getmembers():
        name = member.name
        if top_dir is None:
            top_dir = name.split("/")[0]
        # Skip existing root Procfile — we replace it
        if name == f"{top_dir}/Procfile" or name == "Procfile":
            continue
        f = src.extractfile(member) if member.isfile() else None
        out.addfile(member, f)

    root = top_dir or "."
    info = tarfile.TarInfo(name=f"{root}/Procfile")
    info.size = len(procfile_content)
    out.addfile(info, io.BytesIO(procfile_content))

    src.close()
    out.close()
    return out_buf.getvalue()
