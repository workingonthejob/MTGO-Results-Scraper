from IniParser import IniParser
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import requests
import json
import base64
import random


MAX_UPLOADS_PER_DAY = 1250
MAX_UPLOADS_PER_HOUR = 50
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
        self.HEADERS = {'User-Agent': USER_AGENT,
                        'accept': 'application/json',
                        'Authorization': "Bearer {}".format(
                            self.CURRENT_ACCESS_TOKEN)}

    def __init__(self):
        print("Using the default imgur-config.ini file.")
        ip = IniParser('imgur-config.ini')
        self.API_URL = 'https://api.imgur.com'
        self.CLIENT_ID = ip.get_imgur_properties('CLIENT_ID')
        self.CLIENT_SECRET = ip.get_imgur_properties('CLIENT_SECRET')
        self.REFRESH_TOKEN = ip.get_imgur_properties('REFRESH_TOKEN')
        self.CURRENT_ACCESS_TOKEN = ip.get_imgur_properties('ACCESS_TOKEN')
        self.USERNAME = ip.get_imgur_properties('USERNAME')
        self.HEADERS = {'User-Agent': USER_AGENT,
                        'accept': 'application/json',
                        'Authorization': "Bearer {}".format(
                            self.CURRENT_ACCESS_TOKEN)}
        self.start_session()
        self.test_and_update_access_token()

    def start_session(self):
        self.SESSION = requests.Session()
        retry = Retry(connect=3, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        self.SESSION.mount('http://', adapter)
        self.SESSION.mount('https://', adapter)
        # self.SESSION = session.get(self.URL, headers=self.HEADERS)

    def refresh(self):
        data = {
            'refresh_token': self.REFRESH_TOKEN,
            'client_id': self.CLIENT_ID,
            'client_secret': self.CLIENT_SECRET,
            'grant_type': 'refresh_token'
        }

        url = "/".join([self.API_URL, "oauth2", "token"])

        response = requests.post(url, data=data)

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

        for k, v in kwargs.items():
            if k not in SUPPORTED_IMAGE_KEYS:
                print("[WARN] - '{}' not a supported API option.".format(k))
            if "image" not in kwargs:
                raise Exception("'image' key is required.")
            if k == "image":
                data[k] = base64.b64encode(open(v, "rb").read())
            else:
                data[k] = v
        r = requests.post(url, data=data, headers=self.HEADERS)
        if r.status_code != 200:
            raise Exception("{} status code returned with message {}.".format(r.status_code, r.text))
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
                print("[WARN] - '{}' not a supported API option.".format(k))
            if k == "ids" or k == "deletehashes":
                if not isinstance(v, list):
                    raise Exception("'{}' provided is not a list.".format(k))
            data[k] = v
        r = requests.post(url, data=data, headers=self.HEADERS)
        if r.status_code != 200:
            raise Exception("{} status code returned.".format(r.status_code))
        return r.json()

    """
    Returns: A list of the album hashes.
    """

    def get_albums(self, page=0):
        url = "/".join([self.API_URL, "3", "account",
                        self.USERNAME, "albums", "ids", str(page)])
        r = requests.get(url, headers=self.HEADERS)
        if r.status_code != 200:
            raise Exception("{} status code returned.".format(r.status_code))
        return r.json()["data"]

    def download_album(self, directory="."):
        pretty_json_string = json.dumps(
            self.SESSION.json(), indent=4, sort_keys=True)
        actual_json = json.loads(pretty_json_string)
        for image in actual_json['data']['images']:
            r = requests.get(image['link'], allow_redirects=True)
            file_name = image['link'].split("/")[-1]
            absolute_path = "\\".join([directory, file_name])
            with open(absolute_path, 'wb') as f:
                f.write(r.content)

    def test_and_update_access_token(self):
        # Putting this here instead of creating a wrapper method
        # for requests methods means the token could expire after
        # this was run. This is just easier now.
        print("Checking access_token is still valid.")
        url = "/".join([self.API_URL, "3", "account", self.USERNAME])
        r = requests.get(url, headers=self.HEADERS)
        if r.status_code == 401:
            print("access_token was invalid. Updating it.")
            self.refresh()
        else:
            print("access_token is still valid.")

    def run(self):
        self.start_session()
        self.test_and_update_access_token()
        # self.refresh()
        # self.download_album()
        # self.create_album(title="MyFancyAlbum")
        # print(self.get_albums())


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
