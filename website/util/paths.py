import os
import json
import logging

from website import settings


logger = logging.getLogger(__name__)


def load_asset_paths():
    if settings.DEBUG_MODE:
        logger.warning('Skipping load of "webpack-assets.json" in DEBUG_MODE.')
        return
    asset_paths = None
    try:
        with open(settings.ASSET_HASH_PATH) as fp:
            asset_paths = json.load(fp)
    except OSError:
        logger.error('No "webpack-assets.json" file found. You may need to run webpack.')
        pass
    return asset_paths


asset_paths = load_asset_paths()
base_static_path = '/static/public/js/'
def webpack_asset(path, asset_paths=asset_paths, debug=settings.DEBUG_MODE):
    """Mako filter that resolves a human-readable asset path to its name on disk
    (which may include the hash of the file).
    """
    if not asset_paths:
        logger.warning('webpack-assets.json has not yet been generated. Falling back to non-cache-busted assets')
        return path
    if not debug:
        key = path.replace(base_static_path, '').replace('.js', '')
        hash_path = asset_paths[key]['js']
        return os.path.join(base_static_path, hash_path)
    else:  # We don't cachebust in debug mode, so just return unmodified path
        return path
