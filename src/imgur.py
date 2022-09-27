from IniParser import IniParser
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from logging.config import fileConfig
import requests
import json
import base64
import logging
import time
import math


fileConfig('logging_config.ini')
log = logging.getLogger()

RATE_LIMITING_ERROR = 429
MAX_UPLOADS_PER_DAY = 1250
MAX_UPLOADS_PER_HOUR = 1250
SUPPORTED_ALBUM_KEYS = ("ids",
                        "deletehashes",
                        "title",
                        "description",
                        "privacy",
                        "layout",
                        "cover")
SUPPORTED_IMAGE_KEYS = ("image",
                        "album",
                        "type",
                        "name",
                        "title",
                        "description")
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'\
             'AppleWebKit/537.36 (KHTML, like Gecko)'\
             'Chrome/101.0.4951.67 Safari/537.36'


class Imgur():
    def __init__(self,
                 username,
                 client_id,
                 client_secret,
                 refresh_token,
                 access_token):
        self.USERNAME = username
        self.CLIENT_ID = client_id
        self.CLIENT_SECRET = client_secret
        self.REFRESH_TOKEN = refresh_token
        self.API_URL = 'https://api.imgur.com'
        self.CURRENT_ACCESS_TOKEN = access_token
        self.SESSION = None
        self.RATE_LIMIT_USER_LIMIT = None
        self.RATE_LIMIT_USER_REMAINING = None
        self.RATE_LIMIT_USER_REST = None
        self.RATE_LIMIT_CLIENT_LIMIT = None
        self.RATE_LIMIT_CLIENT_REMAINING = None
        self.POST_RATE_LIMIT_LIMIT = None
        self.POST_RATE_LIMIT_REMAINING = None
        self.POST_RATE_LIMIT_RESET = None
        self.HEADERS = {'User-Agent': USER_AGENT,
                        'accept': 'application/json',
                        'Authorization': f'Bearer {self.CURRENT_ACCESS_TOKEN}'}

    # Python doesn't support multiple constructors it will always use the latest
    # i.e. this one since it's the latest one.
    def __init__(self):
        ip = IniParser('imgur-config.ini')
        self.API_URL = 'https://api.imgur.com'
        self.CLIENT_ID = ip.get_imgur_properties('CLIENT_ID')
        self.CLIENT_SECRET = ip.get_imgur_properties('CLIENT_SECRET')
        self.REFRESH_TOKEN = ip.get_imgur_properties('REFRESH_TOKEN')
        self.CURRENT_ACCESS_TOKEN = ip.get_imgur_properties('ACCESS_TOKEN')
        self.SESSION = None
        self.RATE_LIMIT_USER_LIMIT = None
        self.RATE_LIMIT_USER_REMAINING = None
        self.RATE_LIMIT_USER_REST = None
        self.RATE_LIMIT_CLIENT_LIMIT = None
        self.RATE_LIMIT_CLIENT_REMAINING = None
        self.POST_RATE_LIMIT_LIMIT = None
        self.POST_RATE_LIMIT_REMAINING = None
        self.POST_RATE_LIMIT_RESET = None
        self.USERNAME = ip.get_imgur_properties('USERNAME')
        self.HEADERS = {'User-Agent': USER_AGENT,
                        'accept': 'application/json',
                        'Authorization': "Bearer {}".format(
                            self.CURRENT_ACCESS_TOKEN)}
        self.start_session()
        self.test_and_update_access_token()

    def _post(self, url, data, headers, sleep=False):
        time_elapsed = 0
        r = self.SESSION.post(url, data=data, headers=headers)
        headers = r.headers

        self.POST_RATE_LIMIT_LIMIT = int(headers['X-Post-Rate-Limit-Limit'])
        self.POST_RATE_LIMIT_REMAINING = int(headers['X-Post-Rate-Limit-Remaining'])
        self.POST_RATE_LIMIT_RESET = int(headers['X-Post-Rate-Limit-Reset']) + 60

        if sleep and int(r.status_code) == 400:
            if r.json()['data']['error']['code'] == RATE_LIMITING_ERROR:
                log.info('Imgur API upload limit reached.')
                # Update user every minute
                while time_elapsed <= self.POST_RATE_LIMIT_RESET:
                    time.sleep(60)
                    time_elapsed += 60
                    time_elapsed_min = int(time_elapsed / 60)
                    minutes_remaining = math.ceil(self.POST_RATE_LIMIT_RESET / 60)
                    log.info(
                        f'Slept for {time_elapsed_min}/{minutes_remaining} min.')
                # Retry after waiting
                r = self.SESSION.post(url, data=data, headers=headers)

                if r.status_code != 200:
                    log.debug(r.status_code)
                    r.raise_for_status()
                    # raise Exception(f'{r.status_code} status code returned.')
        return r

    def start_session(self):
        # https://findwork.dev/blog/advanced-usage-python-requests-timeouts-retries-hooks/#request-hooks
        self.SESSION = requests.Session()
        retry = Retry(connect=3,
                      backoff_factor=0.5,
                      status_forcelist=[502],
                      allowed_methods=['POST'])
        adapter = HTTPAdapter(max_retries=retry)
        self.SESSION.mount('http://', adapter)
        self.SESSION.mount('https://', adapter)

    def refresh(self):
        data = {
            'refresh_token': self.REFRESH_TOKEN,
            'client_id': self.CLIENT_ID,
            'client_secret': self.CLIENT_SECRET,
            'grant_type': 'refresh_token'
        }

        url = "/".join([self.API_URL, "oauth2", "token"])
        response = self.SESSION.post(url, data=data)

        if response.status_code != 200:
            raise Exception('Error refreshing access token!',
                            response.status_code)

        response_data = response.json()
        self.CURRENT_ACCESS_TOKEN = response_data['access_token']

    """
    Returns:
            {
            "data": {
                "account_id": 1234,
                "account_url": null,
                "ad_type": 0,
                "ad_url": "",
                "animated": false,
                "bandwidth": 0,
                "datetime": 1654572054,
                "deletehash": "W1gH9JldrBr9eVl",
                "description": null,
                "edited": "0",
                "favorite": false,
                "has_sound": false,
                "height": 257,
                "id": "PLMnX48",
                "in_gallery": false,
                "in_most_viral": false,
                "is_ad": false,
                "link": "https://i.imgur.com/PLMnX48.png",
                "name": "",
                "nsfw": null,
                "section": null,
                "size": 88753,
                "tags": [],
                "title": null,
                "type": "image/png",
                "views": 0,
                "vote": null,
                "width": 406
            },
            "status": 200,
            "success": true
        }
    """

    def upload_image(self, **kwargs):
        url = "/".join([self.API_URL, "3", "image"])
        data = {}
        will_sleep = False

        for k, v in kwargs.items():
            if k == "sleep":
                will_sleep = v
                continue
            if k not in SUPPORTED_IMAGE_KEYS:
                log.debug(f'"{k}" not a supported API option.')
            if "image" not in kwargs:
                raise Exception("'image' key is required.")
            if k == "image":
                data[k] = base64.b64encode(open(v, "rb").read())
            else:
                data[k] = v

        r = self._post(url, data, self.HEADERS, will_sleep)

        # if r.status_code != 200 and r.json()["success"] == "true":
        #     raise Exception("{} status code returned.".format(r.status_code))
        return r.json()

    """
    Description: A convenience method to upload images by
    only specifying a list of image locations.
    """

    def upload_images(self, images):
        responses = []
        for img in images:
            responses.append(self.upload_image(image=img))
        return responses

    """
    Description: Create an imgur album.
    Returns:
            {
            "data": {
                "deletehash": "W84i9h3fWX5bQCQ",
                "id": "KvHzfrN"
            },
            "status": 200,
            "success": true
        }
    """

    def create_album(self, **kwargs):
        url = "/".join([self.API_URL, "3", "album"])
        data = {}
        for k, v in kwargs.items():
            if k not in SUPPORTED_ALBUM_KEYS:
                log.debug("'{}' not a supported API option.".format(k))
            if k == "ids" or k == "deletehashes":
                if not isinstance(v, list):
                    raise Exception("'{}' provided is not a list.".format(k))
            data[k] = v
        r = self._post(url, data, self.HEADERS)
        # r = requests.post(url, data=data, headers=self.HEADERS)
        if r.status_code != 200 and r.json()["success"] == "true":
            raise Exception("{} status code returned.".format(r.status_code))
        # return json.dumps(r.json(), indent=4, sort_keys=True)
        return r.json()

    def get_key_from_image_album(self, id, key):
        '''
            Return a list of values of the given key
            from an image object.
        '''
        data = self.get_images_from_album(id)
        return [image[key] for image in data if key in image]

    def get_images_from_album(self, id):
        '''
           Using the album_id return all the images associated
           to the album.
        '''
        url = "/".join([self.API_URL, "3", "account",
                        self.USERNAME, "album", id, 'images'])
        r = self.SESSION.get(url, headers=self.HEADERS)
        if r.status_code != 200:
            r.raise_for_status()
        return r.json()['data']

    """
    Returns: A list of the album hashes.
    """

    def get_albums(self, page=0):
        url = "/".join([self.API_URL, "3", "account",
                        self.USERNAME, "albums", "ids", str(page)])
        r = self.SESSION.get(url, headers=self.HEADERS)
        if r.status_code != 200:
            r.raise_for_status()
        return r.json()["data"]

    def download_album(self, directory="."):
        pretty_json_string = json.dumps(
            self.SESSION.json(), indent=4, sort_keys=True)
        actual_json = json.loads(pretty_json_string)
        for image in actual_json['data']['images']:
            r = self.SESSION.get(image['link'], allow_redirects=True)
            file_name = image['link'].split("/")[-1]
            absolute_path = "\\".join([directory, file_name])
            with open(absolute_path, 'wb') as f:
                f.write(r.content)

    def test_and_update_access_token(self):
        # Putting this here instead of creating a wrapper method
        # for requests methods means the token could expire after
        # this was run. This is just easier now.
        log.debug("Checking access_token is still valid.")
        url = "/".join([self.API_URL, "3", "account", self.USERNAME])
        r = self.SESSION.get(url, headers=self.HEADERS)
        if r.status_code == 401:
            log.debug("access_token was invalid. Updating it.")
            self.refresh()
        else:
            log.debug("access_token is still valid.")

    def get_credits(self):
        url = "/".join([self.API_URL, "3", "credits"])
        r = self.SESSION.get(url, headers=self.HEADERS)
        return r.json()

    def run(self):
        self.start_session()
        self.test_and_update_access_token()
        # self.get_credits()
        # self.refresh()
        # self.download_album()
        # self.create_album(title="MyFancyAlbum")
        # log.debug(self.get_albums())


if __name__ == "__main__":
    ip = IniParser('imgur-config.ini')
    client_id = ip.get_imgur_properties('CLIENT_ID')
    client_secret = ip.get_imgur_properties('CLIENT_SECRET')
    refresh_token = ip.get_imgur_properties('REFRESH_TOKEN')
    access_token = ip.get_imgur_properties('ACCESS_TOKEN')
    # Can get username during token creation.
    username = ip.get_imgur_properties('USERNAME')
    imgur = Imgur(username,
                  client_id,
                  client_secret,
                  refresh_token,
                  access_token)
    imgur.run()
