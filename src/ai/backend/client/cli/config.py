import getpass
import json
import sys

import click
import colorama

from . import main
from .pretty import print_done, print_error, print_fail, print_warn
from .. import __version__
from ..config import get_config, local_state_path
from ..exceptions import BackendClientError
from ..session import Session


@main.command()
def config():
    '''
    Shows the current configuration.
    '''
    config = get_config()
    click.echo('API endpoint: {0} (mode: {1})'.format(
        click.style(str(config.endpoint), bold=True),
        click.style(str(config.endpoint_type), fg='cyan', bold=True)))
    if sys.stdout.isatty():
        click.echo('Server version: ...')
    else:
        with Session() as sess:
            try:
                versions = sess.System.get_versions()
            except BackendClientError:
                click.echo('Server version: (failed to fetch)')
            else:
                click.echo('Server version: {0} (API: {1})'.format(
                    versions.get('manager', '(unavailable)'),
                    versions['version'],
                ))
    nrows = 1
    click.echo('Client version: {0} (API: {1})'.format(
        click.style(__version__, bold=True),
        click.style(config.version, bold=True),
    ))
    nrows += 1
    if config.domain:
        click.echo('Domain name: "{0}"'.format(click.style(config.domain, bold=True)))
        nrows += 1
    if config.group:
        click.echo('Group name: "{0}"'.format(click.style(config.group, bold=True)))
        nrows += 1
    if config.is_anonymous:
        click.echo('Access key: (this is an anonymous session)')
        nrows += 1
    elif config.endpoint_type == 'docker':
        pass
    elif config.endpoint_type == 'session':
        if (local_state_path / 'cookie.dat').exists() and \
                (local_state_path / 'config.json').exists():
            sess_config = json.loads((local_state_path / 'config.json').read_text())
            click.echo('Username: "{0}"'.format(click.style(sess_config.get('username', ''), bold=True)))
            nrows += 1
    else:
        click.echo('Access key: "{0}"'.format(click.style(config.access_key, bold=True)))
        nrows += 1
        masked_skey = config.secret_key[:6] + ('*' * 24) + config.secret_key[-10:]
        click.echo('Secret key: "{0}"'.format(click.style(masked_skey, bold=True)))
        nrows += 1
    click.echo('Signature hash type: {0}'.format(
        click.style(config.hash_type, bold=True)))
    nrows += 1
    click.echo('Skip SSL certificate validation? {0}'.format(
        click.style(str(config.skip_sslcert_validation), bold=True)))
    nrows += 1
    if sys.stdout.isatty():
        sys.stdout.flush()
        with Session() as sess:
            click.echo('\u001b[{0}A\u001b[2K'.format(nrows), nl=False)
            try:
                versions = sess.System.get_versions()
            except BackendClientError:
                click.echo('Server version: {0}'.format(
                    click.style('(failed to fetch)', fg='red', bold=True),
                ))
            else:
                click.echo('Server version: {0} (API: {1})'.format(
                    click.style(versions.get('manager', '(unavailable)'), bold=True),
                    click.style(versions['version'], bold=True),
                ))
            click.echo('\u001b[{0}B'.format(nrows), nl=False)
            sys.stdout.flush()


@main.command()
def login():
    '''
    Log-in to the console API proxy.
    It stores the current session cookie in the OS-default
    local application data location.
    '''
    user_id = input('User ID: ')
    password = getpass.getpass()

    config = get_config()
    if config.endpoint_type != 'session':
        print_warn('To use login, your endpoint type must be "session".')
        raise click.Abort()

    with Session() as session:
        try:
            result = session.Auth.login(user_id, password)
            if not result['authenticated']:
                print_fail('Login failed.')
                sys.exit(1)
            print_done('Login succeeded.')

            local_state_path.mkdir(parents=True, exist_ok=True)
            session.aiohttp_session.cookie_jar.update_cookies(result['cookies'])
            session.aiohttp_session.cookie_jar.save(local_state_path / 'cookie.dat')
            (local_state_path / 'config.json').write_text(json.dumps(result.get('config', {})))
        except Exception as e:
            print_error(e)


@main.command()
def logout():
    '''
    Log-out from the console API proxy and clears the local cookie data.
    '''
    config = get_config()
    if config.endpoint_type != 'session':
        print_warn('To use logout, your endpoint type must be "session".')
        raise click.Abort()

    with Session() as session:
        try:
            session.Auth.logout()
            print_done('Logout done.')
            try:
                (local_state_path / 'cookie.dat').unlink()
                (local_state_path / 'config.json').unlink()
            except (IOError, PermissionError):
                pass
        except Exception as e:
            print_error(e)


@main.command()
@click.argument('old_password', metavar='OLD_PASSWORD')
@click.argument('new_password', metavar='NEW_PASSWORD')
@click.argument('new_password2', metavar='NEW_PASSWORD2')
def update_password(old_password, new_password, new_password2):
    '''
    Update user's password.
    '''
    config = get_config()
    if config.endpoint_type != 'session':
        print_warn('To update password, your endpoint type must be "session".')
        raise click.Abort()

    with Session() as session:
        try:
            session.Auth.update_password(old_password, new_password, new_password2)
            print_done('Password updated.')
        except Exception as e:
            print_error(e)
