import json
import logging
import uuid
from functools import lru_cache
from pathlib import Path
from typing import List

import requests

from meater_api.meater_model import Cook
from meater_api.meater_model_public import Device


class MEATERAPI:
    def __init__(self, email: str, password: str, device_id: str = None):
        self._email = email
        self._password = password

        self._config_path = Path("config.json")
        self._sess = requests.Session()
        self._base = "https://api.cloud.meater.com"

        self._sess_v1 = requests.Session()
        self._base_v1 = "https://public-api.cloud.meater.com"

        self._app_version = "4.4.2"
        self._app_build = "12305"

        self._sess.headers.update(
            {
                "User-Agent": f"MEATER/{self._app_build} CFNetwork/1568.300.101 Darwin/24.2.0"
            }
        )
        self._sess.hooks = {"response": lambda r, *args, **kwargs: self._raise(r)}
        self._sess_v1.hooks = {"response": lambda r, *args, **kwargs: self._raise(r)}

        self._device_id = device_id
        self._token = self._token_v1 = None

        self.load_config()

        if self._device_id is None:
            self._device_id = str(uuid.uuid4()).upper()
            logging.info("Using device id %s", self._device_id)

        self.login()
        self.login_v1()

    def save_config(self):
        with self._config_path.open("w", encoding="utf8") as f:
            json.dump(
                {
                    "token": self._token,
                    "device_id": self._device_id,
                    "token_v1": self._token_v1,
                },
                f,
                indent=4,
            )
            logging.info("Saved config for device %s", self._device_id)

    def load_config(self):
        if self._config_path.exists():
            with self._config_path.open("r", encoding="utf8") as f:
                config = json.load(f)
                self._token = config["token"]
                self._token_v1 = config["token_v1"]
                self._device_id = config["device_id"]
                logging.info("Loaded config for device %s", self._device_id)
                self.set_token(self._token)
                self.set_token(self._token_v1)

    def set_token(self, token: str):
        self._sess.headers.update(
            {
                "Authorization": f"Bearer {token}",
            }
        )

    def set_token_v1(self, token: str):
        self._sess_v1.headers.update(
            {
                "Authorization": f"Bearer {token}",
            }
        )

    @staticmethod
    def _raise(res: requests.Response):
        try:
            logging.info(
                "%s %s [%d]", res.request.method, res.request.url, res.status_code
            )
            res.raise_for_status()

            return res
        except requests.HTTPError as e:
            logging.error("Invalid response from Meater API: %s\n%s", e, res.content)

    @lru_cache(maxsize=1)
    def login_v1(self):
        if self._token_v1 is not None:
            return
        logging.info("Attempting login public API")
        res = self._sess_v1.post(
            self._base_v1 + "/v1/login",
            json={"email": self._email, "password": self._password},
        ).json()
        self.set_token_v1(res["data"]["token"])
        self.save_config()

    @lru_cache(maxsize=1)
    def login(self):
        if self._token is not None:
            return

        logging.info("Attempting login as device %s", self._device_id)

        res = self._sess.post(
            self._base + "/login",
            json={
                "check_terms": 1,
                "password": self._password,
                "email": self._email,
                "clientVersion": f"MEATER-iOS-v{self._app_version}",
                "device": {
                    "model": "iPhone",
                    "locale": "de_DE",
                    "os_version": "18.2",
                    "os_name": "iOS",
                    "app_version": self._app_version,
                    "app_build": self._app_build,
                    "id": self._device_id,
                },
            },
        ).json()
        self.set_token(res["accessToken"])
        self.save_config()

    def get_cooks(self) -> List[Cook]:
        data = self._sess.get(self._base + "/v2/cooks").json()["data"]
        return [Cook.model_validate(c) for c in data]

    def get_live_devices(self) -> List[Device]:
        data = self._sess_v1.get(self._base_v1 + "/v1/devices").json()["data"][
            "devices"
        ]
        return [Device.model_validate(c) for c in data]
