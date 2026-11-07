"""Local adapter for retained receipt artifacts, with no network or registry writes.

A matching digest proves byte identity, not execution. Review the actual receipt
contents and source/derivation/output bindings before accepting any tier claim.
"""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit


def canonical_base(public_base):
    parsed = urlsplit(public_base)
    if (any(c.isspace() or c in '<>"|' for c in public_base)
            or parsed.scheme != 'https' or not parsed.netloc or parsed.query or parsed.fragment
            or parsed.username or parsed.password or '%' in parsed.path
            or any(part in ('.', '..') for part in parsed.path.split('/'))):
        raise ValueError('explicit canonical HTTPS receipt directory required')
    return public_base.rstrip('/') + '/'


def retain(source, destination, public_base):
    """Copy existing JSON bytes; return a planned publication reference.

    public_base is supplied by the integrator from the actual site destination.
    Publication and registry integration are deliberately separate operations.
    """
    base = canonical_base(public_base)
    raw = Path(source).read_bytes()
    if not isinstance(json.loads(raw), dict):
        raise ValueError('receipt artifact must be an existing JSON object')
    digest = hashlib.sha256(raw).hexdigest()
    directory = Path(destination)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (digest + '.json')
    # Exclusive creation avoids following an existing symlink or replacing bytes.
    try:
        with target.open('xb') as stream:
            stream.write(raw)
    except FileExistsError:
        if target.is_symlink() or target.read_bytes() != raw:
            raise ValueError('receipt artifact collision or unsafe destination') from None
    return {'receipt': base + target.name, 'artifactSha256': digest}


def verify_local(directory, public_base, reference):
    """Check the exact local artifact bound by a planned canonical HTTPS URL."""
    base = canonical_base(public_base)
    digest = reference.get('artifactSha256')
    if (not isinstance(digest, str) or len(digest) != 64
            or any(c not in '0123456789abcdef' for c in digest)
            or reference.get('receipt') != base + digest + '.json'):
        raise ValueError('artifact reference must bind its canonical content-addressed path')
    path = Path(directory) / (digest + '.json')
    if path.is_symlink():
        raise ValueError('receipt artifacts must be regular retained files')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('retained receipt bytes do not match artifact SHA256')
    artifact = json.loads(raw)
    if not isinstance(artifact, dict):
        raise ValueError('receipt artifact must be a JSON object')
    return artifact
