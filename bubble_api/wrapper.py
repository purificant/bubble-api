from __future__ import annotations

import time
import json

import requests

from .constraint import Constraint

API_VERSION = "1.1"


class BubbleWrapper:
    def __init__(
        self, base_url, api_token=None, bubble_version="test", *args, **kwargs
    ):
        if bubble_version != "live":
            base_url = f"{base_url}/version-{bubble_version}"
        self.base_url = f"{base_url}/api/{API_VERSION}/obj"
        self.api_token = api_token

    def _get_headers(self):
        return (
            {
                "Authorization": f"Bearer {self.api_token}",
            }
            if self.api_token is not None
            else None
        )

    @staticmethod
    def _format_constraints(constraints) -> str:
        if constraints is None:
            constraints = list()
        if isinstance(constraints, Constraint):
            constraints = [constraints]
        return json.dumps([constraint.to_dict() for constraint in constraints])

    def make_request(
        self, nb_retries=3, sleep_time=0.2, exponential_backoff=False, **kwargs
    ) -> requests.Response:
        if kwargs.get("headers") is None:
            kwargs["headers"] = self._get_headers()

        response = requests.request(**kwargs)

        if response.status_code // 100 == 2:
            return response

        if nb_retries == 0 or response.status_code // 100 == 4:
            print(response.text)
            response.raise_for_status()

        time.sleep(sleep_time)

        if exponential_backoff:
            sleep_time *= 2

        return self.make_request(
            nb_retries=nb_retries - 1,
            sleep_time=sleep_time,
            **kwargs,
        )

    def get_by_id(self, bubble_type, bubble_id, **kwargs):
        url = f"{self.base_url}/{bubble_type}/{bubble_id}"

        resp = self.make_request(method="GET", url=url, **kwargs)

        return resp.json()["response"]

    def create(self, bubble_type, fields: dict, **kwargs):
        url = f"{self.base_url}/{bubble_type}"

        resp = self.make_request(method="POST", url=url, json=fields, **kwargs)

        return resp.json()["id"]

    def update_object(self, bubble_type, bubble_id, fields: dict, **kwargs):
        url = f"{self.base_url}/{bubble_type}/{bubble_id}"

        self.make_request(method="PATCH", url=url, json=fields, **kwargs)

    def replace_object(self, bubble_type, bubble_id, fields: dict, **kwargs):
        url = f"{self.base_url}/{bubble_type}/{bubble_id}"

        self.make_request(method="PUT", url=url, json=fields, **kwargs)

    def delete_by_id(self, bubble_type, bubble_id, **kwargs):
        url = f"{self.base_url}/{bubble_type}/{bubble_id}"

        self.make_request(method="DELETE", url=url, **kwargs)

    def delete_objects(self, bubble_type, constraints: list[Constraint], **kwargs):
        if constraints is None:
            # TODO Explicit exception
            raise Exception
        for obj in self.get_objects_gen(bubble_type, constraints, **kwargs):
            self.delete_by_id(bubble_type, obj["_id"], **kwargs)

    def delete_all(self, bubble_type, **kwargs):
        self.delete_objects(bubble_type, list(), **kwargs)

    def create_bulk(self, bubble_type, fields: list[dict], **kwargs) -> list:
        url = f"{self.base_url}/{bubble_type}/bulk"
        headers = {
            **self._get_headers(),
            "Content-Type": "text/plain",
        }

        resp = self.make_request(
            method="POST",
            url=url,
            data="\n".join(json.dumps(f) for f in fields),
            headers=headers,
            **kwargs,
        )

        print(resp.text)

        return [json.loads(r) for r in resp.text.split("\n")]

    def count_objects(self, bubble_type, constraints: list[Constraint], **kwargs):
        url = f"{self.base_url}/{bubble_type}"
        constraints = self._format_constraints(constraints)

        params = {
            "constraints": constraints,
            "cursor": 0,
            "limit": 100,
        }

        print(params)

        resp = self.make_request(method="GET", url=url, params=params, **kwargs)
        json_resp = resp.json()["response"]

        return json_resp["count"] + json_resp["remaining"]

    def get_objects_gen(self, bubble_type, constraints=None, **kwargs):
        url = f"{self.base_url}/{bubble_type}"

        constraints = self._format_constraints(constraints)

        params = {
            "constraints": constraints,
            "cursor": 0,
            "limit": 100,
        }

        while True:
            resp = self.make_request(method="GET", url=url, params=params, **kwargs)
            print(resp)
            json_resp = resp.json()["response"]
            print(json_resp)
            print(json_resp["count"])
            yield from json_resp["results"]

            params["cursor"] = json_resp["cursor"] + json_resp["count"]

            if json_resp["remaining"] == 0:
                break

    def get_objects(self, bubble_type, constraints=None):
        return list(self.get_objects_gen(bubble_type, constraints))
