import os
from rest_framework import status as http_status
import requests
from urllib.parse import urljoin
import json

import waffle
from waffle.utils import get_setting

from flask import request
from flask import send_from_directory
from flask import Response
from flask import stream_with_context
from flask import g
from django.conf import settings as api_settings
from django.utils.encoding import smart_str
from werkzeug.http import dump_cookie
from geoip2.database import Reader
from geoip2.errors import AddressNotFoundError

from framework import status
from framework import sentry
from framework.auth import cas
from framework.routing import Rule
from framework.flask import redirect
from framework.routing import WebRenderer
from framework.exceptions import HTTPError
from framework.routing import json_renderer
from framework.routing import process_rules
from framework.auth import views as auth_views
from framework.routing import render_mako_string
from framework.auth.core import _get_current_user

from osf import features
from osf.models import Institution, Preprint
from osf.utils import sanitize
from osf.utils import permissions
from website import util
from website import settings
from website import language
from website.util import metrics
from website.util import paths
from website import maintenance
from website import landing_pages as landing_page_views
from website import views as website_views
from website.citations import views as citation_views
from website.search import views as search_views
from website.oauth import views as oauth_views
from addons.osfstorage import views as osfstorage_views
from website.profile.utils import get_profile_image_url
from website.profile import views as profile_views
from website.project import views as project_views
from addons.base import views as addon_views
from website.discovery import views as discovery_views
from website.conferences import views as conference_views
from website.policies import views as policy_views
from website.preprints import views as preprint_views
from website.registries import views as registries_views
from website.reviews import views as reviews_views
from website.institutions import views as institution_views
from website.ember_osf_web import views as ember_osf_web_views
from website.closed_challenges import views as closed_challenges_views
from website.settings import EXTERNAL_EMBER_APPS, EXTERNAL_EMBER_SERVER_TIMEOUT

from api.waffle.utils import flag_is_active


def set_status_message(user):
    if user and not user.accepted_terms_of_service:
        status.push_status_message(
            message=language.TERMS_OF_SERVICE.format(api_domain=settings.API_DOMAIN,
                                                     user_id=user._id,
                                                     csrf_token=json.dumps(g.get('csrf_token'))),
            kind='default',
            dismissible=True,
            trust=True,
            jumbotron=True,
            id='terms_of_service',
            extra={}
        )


def get_globals():
    """Context variables that are available for every template rendered by
    OSFWebRenderer.
    """
    user = _get_current_user()
    set_status_message(user)
    user_institutions = [{'id': inst._id, 'name': inst.name, 'logo_path': inst.logo_path_rounded_corners} for inst in user.get_affiliated_institutions()] if user else []
    try:
        location = Reader('GeoLite2-City.mmdb').city(request.remote_addr)
        # TODO: replace with adequate error handling during keen removal
    except (FileNotFoundError, AddressNotFoundError):
        location = None

    if request.host_url != settings.DOMAIN:
        try:
            inst_id = Institution.objects.get(domains__icontains=request.host, is_deleted=False)._id
            request_login_url = f'{settings.DOMAIN}institutions/{inst_id}'
        except Institution.DoesNotExist:
            request_login_url = request.url.replace(request.host_url, settings.DOMAIN)
    else:
        request_login_url = request.url

    return {
        'private_link_anonymous': is_private_link_anonymous_view(),
        'user_name': user.username if user else '',
        'user_full_name': user.fullname if user else '',
        'user_id': user._id if user else '',
        'user_locale': user.locale if user and user.locale else '',
        'user_timezone': user.timezone if user and user.timezone else '',
        'user_url': user.url if user else '',
        'user_profile_image': get_profile_image_url(user=user, size=25) if user else '',
        'user_email_verifications': user.unconfirmed_email_info if user else [],
        'user_api_url': user.api_url if user else '',
        'user_entry_point': metrics.get_entry_point(user) if user else '',
        'user_institutions': user_institutions if user else None,
        'display_name': user.fullname if user else '',
        'anon': {
            'continent': (location or {}).get('continent', {}).get('code', None),
            'country': (location or {}).get('country', {}).get('iso_code', None),
        },
        'use_cdn': settings.USE_CDN_FOR_CLIENT_LIBS,
        'sentry_dsn_js': settings.SENTRY_DSN_JS if sentry.enabled else None,
        'dev_mode': settings.DEV_MODE,
        'allow_login': settings.ALLOW_LOGIN,
        'cookie_name': settings.COOKIE_NAME,
        'status': status.pop_status_messages(),
        'domain': settings.DOMAIN,
        'api_domain': settings.API_DOMAIN,
        'disk_saving_mode': settings.DISK_SAVING_MODE,
        'language': language,
        'noteworthy_links_node': settings.NEW_AND_NOTEWORTHY_LINKS_NODE,
        'popular_links_node': settings.POPULAR_LINKS_NODE,
        'web_url_for': util.web_url_for,
        'api_url_for': util.api_url_for,
        'api_v2_url': util.api_v2_url,  # URL function for templates
        'api_v2_domain': settings.API_DOMAIN,
        'api_v2_base': util.api_v2_url(''),  # Base url used by JS api helper
        'sanitize': sanitize,
        'sjson': lambda s: sanitize.safe_json(s),
        'webpack_asset': paths.webpack_asset,
        'osf_url': settings.INTERNAL_DOMAIN,
        'waterbutler_url': settings.WATERBUTLER_URL,
        'login_url': cas.get_login_url(request_login_url),
        'sign_up_url': util.web_url_for('auth_register', _absolute=True, next=request_login_url),
        'reauth_url': util.web_url_for('auth_logout', redirect_url=request.url, reauth=True),
        'profile_url': cas.get_profile_url(),
        'enable_institutions': settings.ENABLE_INSTITUTIONS,
        'page_route_name': request.url_rule.endpoint.replace('__', '.'),
        'keen': {
            'public': {
                'project_id': settings.KEEN['public']['project_id'],
                'write_key': settings.KEEN['public']['write_key'],
            },
            'private': {
                'project_id': settings.KEEN['private']['project_id'],
                'write_key': settings.KEEN['private']['write_key'],
            },
        },
        'institutional_landing_flag': flag_is_active(request, features.INSTITUTIONAL_LANDING_FLAG),
        'maintenance': maintenance.get_maintenance(),
        'recaptcha_site_key': settings.RECAPTCHA_SITE_KEY,
        'custom_citations': settings.CUSTOM_CITATIONS,
        'osf_support_email': settings.OSF_SUPPORT_EMAIL,
        'osf_contact_email': settings.OSF_CONTACT_EMAIL,
        'footer_links': settings.FOOTER_LINKS,
        'features': features,
        'waffle': waffle,
        'csrf_cookie_name': api_settings.CSRF_COOKIE_NAME,
        'permissions': permissions
    }


def is_private_link_anonymous_view():
    # Avoid circular import
    from osf.models import PrivateLink
    view_only = request.args.get('view_only')
    if not view_only:
        return False
    try:
        return PrivateLink.objects.filter(key=view_only).values_list('anonymous', flat=True).get()
    except PrivateLink.DoesNotExist:
        return False

#: Use if a view only redirects or raises error
notemplate = WebRenderer('', renderer=render_mako_string, trust=False)


# Static files (robots.txt, etc.)

def favicon():
    return send_from_directory(
        settings.STATIC_FOLDER,
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )


def robots():
    """Serves the robots.txt file."""
    # Allow local robots.txt
    if os.path.exists(os.path.join(settings.STATIC_FOLDER,
                                   'robots.local.txt')):
        robots_file = 'robots.local.txt'
    else:
        robots_file = 'robots.txt'
    return send_from_directory(
        settings.STATIC_FOLDER,
        robots_file,
        mimetype='html'
    )

def sitemap_file(path):
    """Serves the sitemap/* files."""
    if path.endswith('.xml.gz'):
        mime = 'application/x-gzip'
    elif path.endswith('.xml'):
        mime = 'text/xml'
    else:
        raise HTTPError(http_status.HTTP_404_NOT_FOUND)
    return send_from_directory(
        settings.STATIC_FOLDER + '/sitemaps/',
        path,
        mimetype=mime
    )


def goodbye():
    # Redirect to dashboard if logged in
    redirect_url = util.web_url_for('index')
    if _get_current_user():
        return redirect(redirect_url)
    else:
        return redirect(redirect_url + '?goodbye=true')

def make_url_map(app):
    """Set up all the routes for the OSF app.

    :param app: A Flask/Werkzeug app to bind the rules to.
    """

    # Set default views to 404, using URL-appropriate renderers
    process_rules(app, [
        Rule(
            '/<path:_>',
            ['get', 'post'],
            HTTPError(http_status.HTTP_404_NOT_FOUND),
            WebRenderer('', render_mako_string, trust=False)
        ),
        Rule(
            '/api/v1/<path:_>',
            ['get', 'post'],
            HTTPError(http_status.HTTP_404_NOT_FOUND),
            json_renderer
        ),
    ])

    # Static files
    process_rules(app, [
        Rule('/favicon.ico', 'get', favicon, json_renderer),
        Rule('/robots.txt', 'get', robots, json_renderer),
        Rule('/sitemaps/<path>', 'get', sitemap_file, json_renderer),
    ])


    process_rules(app, [

        Rule(
            '/reproducibility/',
            'get',
            website_views.reproducibility,
            notemplate
        ),
        Rule('/about/', 'get', website_views.redirect_about, notemplate),
        Rule('/help/', 'get', website_views.redirect_help, notemplate),
        Rule('/faq/', 'get', website_views.redirect_faq, notemplate),
        Rule(['/getting-started/', '/getting-started/email/', '/howosfworks/'], 'get', website_views.redirect_getting_started, notemplate),
        Rule(
            '/presentations/',
            'get',
            conference_views.redirect_to_meetings,
            json_renderer,
        ),
        Rule(
            '/news/',
            'get',
            website_views.redirect_to_cos_news,
            notemplate
        ),
        Rule(
            [
                # Legacy routes
                '/rr/',
                '/registeredreports/',
                '/registeredreport/',
                '/prereg/',
            ],
            'get',
            website_views.redirect_to_registration_workflow,
            notemplate
        ),

        Rule(
            '/preprint/',
            'get',
            preprint_views.preprint_redirect,
            notemplate,
        ),
        Rule(
            ['/activity/', '/explore/activity/', '/explore/'],
            'get',
            discovery_views.redirect_activity_to_search,
            notemplate
        ),
        Rule(
            '/files/auth/',
            'get',
            addon_views.get_auth,
            json_renderer,
        ),

        Rule(
            [
                '/project/<pid>/waterbutler/logs/',
                '/project/<pid>/node/<nid>/waterbutler/logs/',
            ],
            'put',
            addon_views.create_waterbutler_log,
            json_renderer,
        ),
        Rule(
            [
                '/registration/<pid>/callbacks/',
            ],
            'put',
            project_views.register.registration_callbacks,
            json_renderer,
        ),
    ], prefix='/api/v1')

    # Set up static routing for addons and providers
    # NOTE: We use nginx to serve static addon assets in production
    addon_base_path = os.path.abspath('addons')
    provider_static_path = os.path.abspath('assets')
    if settings.DEV_MODE:
        @app.route('/static/addons/<addon>/<path:filename>')
        def addon_static(addon, filename):
            addon_path = os.path.join(addon_base_path, addon, 'static')
            return send_from_directory(addon_path, filename)

        @app.route('/assets/<filename>')
        def provider_static(filename):
            return send_from_directory(directory=provider_static_path, path=filename)

        @app.route('/ember-cli-live-reload.js')
        def ember_cli_live_reload():
            req = requests.get(f'{settings.LIVE_RELOAD_DOMAIN}/ember-cli-live-reload.js', stream=True)
            return Response(stream_with_context(req.iter_content()), content_type=req.headers['content-type'])
