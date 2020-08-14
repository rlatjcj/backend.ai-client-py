from pathlib import Path
from unittest import mock

from typing import (
    Mapping
)


from datetime import datetime
from dateutil.tz import tzutc
from yarl import URL

import pytest
from aioresponses import aioresponses

from ai.backend.client.config import API_VERSION
from ai.backend.client.session import Session
from ai.backend.client.test_utils import AsyncMock
from ai.backend.client.request import Request

import aiohttp
import asyncio


def build_url(config, path: str):
    base_url = config.endpoint.path.rstrip('/')
    query_path = path.lstrip('/') if len(path) > 0 else ''
    path = '{0}/{1}'.format(base_url, query_path)
    canonical_url = config.endpoint.with_path(path)
    return canonical_url


@pytest.fixture(scope='module', autouse=True)
def api_version():
    mock_nego_func = AsyncMock()
    mock_nego_func.return_value = API_VERSION
    with mock.patch('ai.backend.client.session._negotiate_api_version', mock_nego_func):
        yield


def test_create_vfolder():
    with Session() as session, aioresponses() as m:
        payload = {
            'id': 'fake-vfolder-id',
            'name': 'fake-vfolder-name',
            'host': 'local',
        }
        m.post(build_url(session.config, '/folders'), status=201,
               payload=payload)
        resp = session.VFolder.create('fake-vfolder-name')
        assert resp == payload


def test_create_vfolder_in_other_host():
    with Session() as session, aioresponses() as m:
        payload = {
            'id': 'fake-vfolder-id',
            'name': 'fake-vfolder-name',
            'host': 'fake-vfolder-host',
        }
        m.post(build_url(session.config, '/folders'), status=201,
               payload=payload)
        resp = session.VFolder.create('fake-vfolder-name', 'fake-vfolder-host')
        assert resp == payload


def test_list_vfolders():
    with Session() as session, aioresponses() as m:
        payload = [
            {
                'name': 'fake-vfolder1',
                'id': 'fake-vfolder1-id',
                'host': 'fake-vfolder1-host',
                'is_owner': True,
                'permissions': 'wd',
            },
            {
                'name': 'fake-vfolder2',
                'id': 'fake-vfolder2-id',
                'host': 'fake-vfolder2-host',
                'is_owner': True,
                'permissions': 'wd',
            }
        ]
        m.get(build_url(session.config, '/folders'), status=200,
              payload=payload)
        resp = session.VFolder.list()
        assert resp == payload


def test_delete_vfolder():
    with Session() as session, aioresponses() as m:
        vfolder_name = 'fake-vfolder-name'
        m.delete(build_url(session.config, '/folders/{}'.format(vfolder_name)),
                 status=204)
        resp = session.VFolder(vfolder_name).delete()
        assert resp == {}


def test_vfolder_get_info():
    with Session() as session, aioresponses() as m:
        vfolder_name = 'fake-vfolder-name'
        payload = {
            'name': vfolder_name,
            'id': 'fake-vfolder-id',
            'host': 'fake-vfolder-host',
            'numFiles': 5,
            'created': '2018-06-02 09:04:15.585917+00:00',
            'is_owner': True,
            'permission': 'wd',
        }
        m.get(build_url(session.config, '/folders/{}'.format(vfolder_name)),
              status=200, payload=payload)
        resp = session.VFolder(vfolder_name).info()
        assert resp == payload


def test_vfolder_upload(tmp_path: Path):
    tmp_path = Path.cwd()

    with Session() as session:
        mock_file = tmp_path / 'test_request.py'
        vfolder_name = 'fake-vfolder-name'

        base_path = Path.cwd()
        mock_file = base_path / Path(mock_file)

        file_size = Path(mock_file).stat().st_size
        file_path = base_path / mock_file

        config = session.config
        base_url = config.endpoint

        session_create_url = base_url / 'folders/{}/create_upload_session' \
                                        .format(vfolder_name)

        params: Mapping = {'path': "{}".format(str(Path(file_path).relative_to(base_path))),
                            'size': int(file_size)}
        rqst = Request(session,
                       'POST',
                       '/folders/{}/create_upload_session'
                       .format(vfolder_name), params=params)

        rqst.content_type = "application/octet-stream"
        date = datetime.now(tzutc())
        rqst.date = date

        rqst._sign(URL("/folders/{}/create_upload_session?path={}&size={}"
                        .format(vfolder_name, params['path'], params['size'])))
        rqst.headers["Date"] = date.isoformat()
        rqst.headers["content-type"] = "application/octet-stream"

        params = {'path': "{}".format(str(Path(file_path).relative_to(base_path))),
                  'size': int(file_size)}

        session.VFolder(vfolder_name).delete()
        session.VFolder.create(vfolder_name)
        jwt_token_from_api = session.VFolder(vfolder_name).upload([mock_file], basedir=tmp_path)

        loop = asyncio.get_event_loop()

        try:
            jwt_token = loop.run_until_complete(get_jwt_token(session_create_url, rqst.headers, params))
        finally:
            loop.close()

        header_1, payload_1, _ = jwt_token_from_api.split(".")
        header_2, payload_2, _ = jwt_token.split(".")

        if ((header_1 == header_2) & (payload_1[0:10] == payload_2[0:10]) &
           (payload_1[-10:] == payload_2[-10:])):
            assert True
        else:
            assert False


async def get_jwt_token(session_create_url, headers, params):
    async with aiohttp.ClientSession() as sess:
        params['size'] = int(params['size'])
        headers['method'] = 'POST'
        async with sess.post(session_create_url, headers=headers, params=params) as resp:
            jwt_token = await resp.json()
            jwt_token = jwt_token['token']
            return jwt_token


def test_vfolder_delete_files():
    with Session() as session, aioresponses() as m:
        vfolder_name = 'fake-vfolder-name'
        files = ['fake-file1', 'fake-file2']
        m.delete(build_url(session.config,
                           '/folders/{}/delete_files'.format(vfolder_name)),
                 status=200, payload={})
        resp = session.VFolder(vfolder_name).delete_files(files)
        assert resp == '{}'


def test_vfolder_download(mocker):
    mock_reader = AsyncMock()
    mock_from_response = mocker.patch(
        'ai.backend.client.func.vfolder.aiohttp.MultipartReader.from_response',
        return_value=mock_reader)
    mock_reader.next = AsyncMock()
    mock_reader.next.return_value = None
    with Session() as session, aioresponses() as m:
        vfolder_name = 'fake-vfolder-name'
        m.get(build_url(session.config,
                        '/folders/{}/download'.format(vfolder_name)),
              status=200,
              headers={'X-TOTAL-PAYLOADS-LENGTH': '0'}, body='')
        session.VFolder(vfolder_name).download(['fake-file1'])
        assert mock_from_response.called == 1
        assert mock_reader.next.called == 1


def test_vfolder_list_files():
    with Session() as session, aioresponses() as m:
        vfolder_name = 'fake-vfolder-name'
        payload = {
            "files": [
                {
                    "mode": "-rw-r--r--",
                    "size": 4751244,
                    "ctime": 1528277299.2744732,
                    "mtime": 1528277299.2744732,
                    "atime": 1528277300.7658687,
                    "filename": "bigtxt.txt",
                },
                {
                    "mode": "-rw-r--r--",
                    "size": 200000,
                    "ctime": 1528333257.6576185,
                    "mtime": 1528288069.625786,
                    "atime": 1528332829.692922,
                    "filename": "200000",
                }
            ],
            "folder_path": "/mnt/local/1f6bd27fde1248cabfb50306ea83fc0a",
        }
        m.get(build_url(session.config,
                        '/folders/{}/files'.format(vfolder_name)),
              status=200, payload=payload)
        resp = session.VFolder(vfolder_name).list_files('.')
        assert resp == payload


def test_vfolder_invite():
    with Session() as session, aioresponses() as m:
        vfolder_name = 'fake-vfolder-name'
        user_ids = ['user1@lablup.com', 'user2@lablup.com']
        payload = {'invited_ids': user_ids}
        m.post(build_url(session.config,
                         '/folders/{}/invite'.format(vfolder_name)),
               status=201, payload=payload)
        resp = session.VFolder(vfolder_name).invite('rw', user_ids)
        assert resp == payload


def test_vfolder_invitations():
    with Session() as session, aioresponses() as m:
        payload = {
            'invitations': [
                {
                    'id': 'fake-invitation-id',
                    'inviter': 'inviter@lablup.com',
                    'perm': 'ro',
                    'vfolder_id': 'fake-vfolder-id',
                }
            ]
        }
        m.get(build_url(session.config, '/folders/invitations/list'),
              status=200, payload=payload)
        resp = session.VFolder.invitations()
        assert resp == payload


def test_vfolder_accept_invitation():
    with Session() as session, aioresponses() as m:
        payload = {
            'msg': ('User invitee@lablup.com now can access'
                    ' vfolder fake-vfolder-id'),
        }
        m.post(build_url(session.config, '/folders/invitations/accept'),
               status=200, payload=payload)
        resp = session.VFolder.accept_invitation('inv-id')
        assert resp == payload


def test_vfolder_delete_invitation():
    with Session() as session, aioresponses() as m:
        payload = {'msg': 'Vfolder invitation is deleted: fake-inv-id.'}
        m.delete(build_url(session.config, '/folders/invitations/delete'),
                 status=200, payload=payload)
        resp = session.VFolder.delete_invitation('inv-id')
        assert resp == payload
