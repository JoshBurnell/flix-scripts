#
# Copyright (C) Foundry 2020
#

import base64
import binascii
import hashlib
import hmac
import json
import time
import urllib.request

from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Tuple

import requests


class flix:
    """Flix will handle the login and expose functions to get,
    create shows etc.
    """

    def __init__(self):
        self.reset()

    def authenticate(self, hostname: str, login: str, password: str) -> Dict:
        """authenticate will authenticate a user

        Arguments:
            hostname {str} -- Hostname of the server

            login {str} -- Login of the user

            password {str} -- Password of the user

        Returns:
            Dict -- Authenticate
        """
        authdata = base64.b64encode((login + ':' + password).encode('UTF-8'))
        response = None
        header = {
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + authdata.decode('UTF-8'),
        }
        try:
            r = requests.post(hostname + '/authenticate', headers=header,
                              verify=False)
            r.raise_for_status()
            response = json.loads(r.content)
            self.hostname = hostname
            self.login = login
            self.password = password
        except requests.exceptions.RequestException as err:
            print('Authentification failed', err)
            return None

        self.key = response['id']
        self.secret = response['secret_access_key']
        self.expiry = datetime.strptime(
            response['expiry_date'].split('.')[0], '%Y-%m-%dT%H:%M:%S')
        return response

    def __get_token(self) -> Tuple[str, str]:
        """__get_token will request a token and will reset it
        if it is too close to the expiry date

        Returns:
            Tuple[str, str] -- Key and Secret
        """
        if (self.key is None or self.secret is None or self.expiry is None or
                datetime.now() + timedelta(hours=2) > self.expiry):
            authentificationToken = self.authenticate(
                self.hostname, self.login, self.password)
            auth_id = authentificationToken['id']
            auth_secret_token = authentificationToken['secret_access_key']
            auth_expiry_date = authentificationToken['expiry_date']
            auth_expiry_date = auth_expiry_date.split('.')[0]
            self.key = auth_id
            self.secret = auth_secret_token
            self.expiry = datetime.strptime(auth_expiry_date,
                                            '%Y-%m-%dT%H:%M:%S')
        return self.key, self.secret

    def __fn_sign(self,
                  access_key_id: str,
                  secret_access_key: str,
                  url: str,
                  content: object,
                  http_method: str,
                  content_type: str,
                  dt: str) -> str:
        """After being logged in, you will have a token.

        Arguments:
            access_key_id {str} -- Access key ID from your token

            secret_access_key {str} -- Secret access key from your token

            url {str} -- Url of the request

            content {object} -- Content of your request

            http_method {str} -- Http Method of your request

            content_type {str} -- Content Type of your request

            dt {str} -- Datetime

        Raises:
            ValueError: 'You must specify a secret_access_key'

        Returns:
            str -- Signed header
        """
        raw_string = http_method.upper() + '\n'
        content_md5 = ''
        if content:
            if isinstance(content, str):
                content_md5 = hashlib.md5(content).hexdigest()
            elif isinstance(content, bytes):
                hx = binascii.hexlify(content)
                content_md5 = hashlib.md5(hx).hexdigest()
            elif isinstance(content, dict):
                jsoned = json.dumps(content)
                content_md5 = hashlib.md5(jsoned.encode('utf-8')).hexdigest()
        if content_md5 != '':
            raw_string += content_md5 + '\n'
            raw_string += content_type + '\n'
        else:
            raw_string += '\n\n'
        raw_string += dt.isoformat().split('.')[0] + 'Z' + '\n'
        url_bits = url.split('?')
        url_without_query_params = url_bits[0]
        raw_string += url_without_query_params
        if len(secret_access_key) == 0:
            raise ValueError('You must specify a secret_access_key')
        digest_created = base64.b64encode(
            hmac.new(secret_access_key.encode('utf-8'),
                     raw_string.encode('utf-8'),
                     digestmod=hashlib.sha256).digest()
        )
        return 'FNAUTH ' + access_key_id + ':' + digest_created.decode('utf-8')

    def __get_headers(
            self, content: object, url: str, method: str = 'POST') -> object:
        """__get_headers will generate the header to make any request
        containing the authorization with signature

        Arguments:
            content {object} -- Content of the request

            url {str} -- Url to make the request

            method {str} -- Request method (default: {'POST'})

        Returns:
            object -- Headers
        """
        dt = datetime.utcnow()
        key, secret = self.__get_token()
        return {
            'Authorization': self.__fn_sign(
                key,
                secret,
                url,
                content,
                method,
                'application/json',
                dt),
            'Content-Type': 'application/json',
            'Date': dt.strftime('%a, %d %b %Y %H:%M:%S GMT'),
        }

    def reset(self):
        """reset will reset the user info
        """
        self.hostname = None
        self.secret = None
        self.expiry = None
        self.login = None
        self.password = None
        self.key = None

    # SHIVA
    def get_sequence_revision_by_id(self,
                                    show_id: int,
                                    seq_id: int,
                                    episode_id: int = None,
                                    revision_id: int = 1
                                    ) -> Dict:
        """get_sequence_revisions retrieve the list of sequence revisions

        Arguments:
            show_id {int} -- Show ID

            seq_id {int} -- Sequence ID

            episode_id {int} -- Episode ID (default: {None})

            revision_id {int} -- Revision ID (default: {1})

        Returns:
            Dict -- Sequence revisions
        """
        url = '/show/{0}/sequence/{1}/revision/{2}'.format(
            show_id, seq_id, revision_id)
        if episode_id is not None:
            url = '/show/{0}/episode/{1}/sequence/{2}/revision/{3}'.format(
                show_id, episode_id, seq_id, revision_id)
        headers = self.__get_headers(None, url, 'GET')
        response = None
        try:
            r = requests.get(self.hostname + url, headers=headers,
                             verify=False)
            response = json.loads(r.content)
        except requests.exceptions.RequestException as err:
            if r is not None and r.status_code == 401:
                print('Your token has been revoked')
            else:
                print('Could not retrieve sequence revisions', err)
            return None
        return response

    def get_sequence_revision_panels(self,
                                     show_id: int,
                                     seq_id: int,
                                     episode_id: int = None,
                                     revision_id: int = 1
                                     ) -> Dict:
        """get_sequence_revisions retrieve the list of sequence revisions

        Arguments:
            show_id {int} -- Show ID

            seq_id {int} -- Sequence ID

            episode_id {int} -- Episode ID (default: {None})

            revision_id {int} -- Revision ID (default: {1})

        Returns:
            Dict -- Sequence revisions
        """
        url = '/show/{0}/sequence/{1}/revision/{2}/panels'.format(
            show_id, seq_id, revision_id)
        if episode_id is not None:
            url = '/show/{0}/episode/{1}/sequence/{2}/revision/{3}/panels'.format(
                show_id, episode_id, seq_id, revision_id)
        headers = self.__get_headers(None, url, 'GET')
        response = None
        try:
            r = requests.get(self.hostname + url, headers=headers,
                             verify=False)
            response = json.loads(r.content)
            response = response.get('panels')
        except requests.exceptions.RequestException as err:
            if r is not None and r.status_code == 401:
                print('Your token has been revoked')
            else:
                print('Could not retrieve sequence revisions', err)
            return None
        return response

    def get_revision_dialogues(self,
                               show_id: int,
                               seq_id: int,
                               episode_id: int = None,
                               revision_id: int = 1
                               ) -> Dict:
        """get_sequence_revisions retrieve the list of sequence revisions

        Arguments:
            show_id {int} -- Show ID

            seq_id {int} -- Sequence ID

            episode_id {int} -- Episode ID (default: {None})

            revision_id {int} -- Revision ID (default: {1})

        Returns:
            Dict -- Sequence revisions
        """
        url = '/show/{0}/sequence/{1}/revision/{2}/dialogues'.format(
            show_id, seq_id, revision_id)
        if episode_id is not None:
            url = '/show/{0}/episode/{1}/sequence/{2}/revision/{3}/dialogues'.format(
                show_id, episode_id, seq_id, revision_id)
        headers = self.__get_headers(None, url, 'GET')
        response = None
        try:
            r = requests.get(self.hostname + url, headers=headers,
                             verify=False)
            response = json.loads(r.content)
            response = response.get('dialogues')
        except requests.exceptions.RequestException as err:
            if r is not None and r.status_code == 401:
                print('Your token has been revoked')
            else:
                print('Could not retrieve sequence revisions', err)
            return None
        return response

    def get_panel_dialogues(self,
                            show_id: int,
                            seq_id: int,
                            episode_id: int = None,
                            panel_id: int = 1
                            ) -> Dict:
        """get_sequence_revisions retrieve the list of sequence revisions

        Arguments:
            show_id {int} -- Show ID

            seq_id {int} -- Sequence ID

            episode_id {int} -- Episode ID (default: {None})

            revision_id {int} -- Revision ID (default: {1})

        Returns:
            Dict -- Sequence revisions
        """
        url = '/show/{0}/sequence/{1}/panel/{2}/dialogues'.format(
            show_id, seq_id, panel_id)
        if episode_id is not None:
            url = '/show/{0}/episode/{1}/sequence/{2}/panel/{3}/dialogues'.format(
                show_id, episode_id, seq_id, panel_id)
        headers = self.__get_headers(None, url, 'GET')
        response = None
        try:
            r = requests.get(self.hostname + url, headers=headers,
                             verify=False)
            response = json.loads(r.content)
            response = response.get('dialogues')
        except requests.exceptions.RequestException as err:
            if r is not None and r.status_code == 401:
                print('Your token has been revoked')
            else:
                print('Could not retrieve sequence revisions', err)
            return None
        return response

    def format_panel_for_revision(self, panels, dialogue):
        """format_panel_for_revision will format the panels as
        revisioned panels

        Arguments:
            panels {List} -- List of panels

        Returns:
            List -- Formatted list of panels
        """
        revisioned_panels = []
        for p in panels:
            revisioned_panels.append({
                'dialogue': dialogue,
                'duration': p.get('duration'),
                'id': p.get('panel_id'),
                'revision_number': p.get('revision_number')
            })
        return revisioned_panels

    def create_new_sequence_revision(
            self, show_id, sequence_id, revisioned_panels, revision,
            comment='From AUTO Dialogue Relink'):
        """new_sequence_revision will create a new sequence revision

        Arguments:
            show_id {int} -- Show ID

            sequence_id {int} -- Sequence ID

            revisioned_panels {List} -- List of revisionned panels

            markers {List} -- List of Markers

            comment {str} -- Comment (default: {'From Hiero'})

        Returns:
            Dict -- Sequence Revision
        """
        url = '/show/{0}/sequence/{1}/revision'.format(show_id, sequence_id)

        # print('*******')
        print(url)
        # print('*******')

        meta = revision.get('meta_data')

        content = {
            'comment': comment,
            'imported': False,
            'meta_data': {
                'movie_asset_id': 0,
                'audio_asset_id': 0,
                'annotations': meta.get('annotations'),
                'audio_timings': meta.get('audio_timings'),
                'highlights': meta.get('highlights'),
                'markers': meta.get('markers')
            },
            'revisioned_panels': revisioned_panels
        }

        data = urllib.parse.urlencode(content).encode("utf-8")

        headers = self.__get_headers(data, url, 'POST')

        response = None
        # try:
        req = urllib.request.Request(self.hostname + url,
                                     headers=headers, data=json.dumps(data))

        response = urllib.request.urlopen(req).read()
        response = json.loads(response)
        # except BaseException:
        #     print('Could not create sequence revision')
        #     return None
        return response
