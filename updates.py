"""Check public GitHub releases without downloading or replacing the executable."""
from dataclasses import dataclass
from http.client import HTTPException
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app_version import APP_VERSION

REPOSITORY_URL = 'https://github.com/MrDerekib/tm-app'
RELEASES_URL = REPOSITORY_URL + '/releases'
LATEST_RELEASE_API = 'https://api.github.com/repos/MrDerekib/tm-app/releases/latest'
CACHE_SECONDS = 24 * 60 * 60


class UpdateError(Exception):
    """An update lookup failed; automatic checks can ignore this quietly."""


def version_tuple(value):
    # Accept the original v1.0 tag as well as v1.1.0, comparing numbers, not text.
    match = re.fullmatch(r'[vV]?(\d+)\.(\d+)(?:\.(\d+))?', value) if isinstance(value, str) else None
    if match is None:
        raise ValueError('Formato de versión no reconocido.')
    return tuple(int(part or 0) for part in match.groups())


@dataclass(frozen=True)
class Release:
    tag: str

    def __post_init__(self):
        version_tuple(self.tag)

    @property
    def version(self):
        return '.'.join(map(str, version_tuple(self.tag)))

    @property
    def url(self):
        # Build the link from our own repository and a validated version tag.
        return RELEASES_URL + '/tag/' + self.tag

    def is_newer(self, current=APP_VERSION):
        return version_tuple(self.tag) > version_tuple(current)


def fetch_latest_release():
    request = Request(LATEST_RELEASE_API, headers={
        'Accept': 'application/vnd.github+json',
        'User-Agent': f'TM-App/{APP_VERSION}',
        'X-GitHub-Api-Version': '2026-03-10',
    })
    try:
        with urlopen(request, timeout=6) as response:
            raw = response.read(512 * 1024 + 1)
        if len(raw) > 512 * 1024:
            raise ValueError('Respuesta demasiado grande.')
        payload = json.loads(raw.decode('utf-8'))
        if not isinstance(payload, dict):
            raise ValueError('Respuesta no válida.')
        if payload.get('draft') or payload.get('prerelease'):
            return None
        return Release(payload.get('tag_name'))
    except HTTPError as exc:
        if exc.code == 404:
            return None
        if exc.code in (403, 429):
            raise UpdateError('GitHub ha limitado las consultas. Inténtalo más tarde.') from exc
        raise UpdateError('GitHub no ha podido responder. Inténtalo más tarde.') from exc
    except (OSError, URLError, HTTPException) as exc:
        raise UpdateError('No se pudo contactar con GitHub. Comprueba la conexión a Internet.') from exc
    except (ValueError, UnicodeError) as exc:
        raise UpdateError('No se pudo interpretar la versión publicada en GitHub.') from exc


def latest_release(cache_path, *, force=False):
    path = Path(cache_path)
    now = time.time()
    if not force:
        try:
            cache = json.loads(path.read_text(encoding='utf-8'))
            if cache['format'] == 1 and 0 <= now - cache['checked_at'] < CACHE_SECONDS:
                return Release(cache['latest_tag']) if cache['latest_tag'] is not None else None
        except (OSError, ValueError, TypeError, KeyError):
            pass
    release = fetch_latest_release()
    cache = {'format': 1, 'checked_at': now, 'latest_tag': release.tag if release else None}
    try:
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(cache, indent=2), encoding='utf-8')
        temporary.replace(path)
    except OSError:
        # The online result is still useful if saving the optional cache fails.
        pass
    return release
