from __future__ import annotations

import io
import zipfile
from xml.etree import ElementTree

import requests


class OpenDartClient:
    BASE_URL = "https://opendart.fss.or.kr/api"

    def __init__(self, api_key: str, timeout: int = 20):
        self.api_key = api_key
        self.timeout = timeout

    def _json_get(self, endpoint: str, params: dict) -> dict:
        query = {"crtfc_key": self.api_key, **params}
        response = requests.get(
            f"{self.BASE_URL}/{endpoint}",
            params=query,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        status = str(payload.get("status", ""))
        if status not in {"000", "013"}:
            raise RuntimeError(
                f"OpenDART API 오류: {status} {payload.get('message', '')}".strip()
            )
        return payload

    def company_codes(self) -> dict[str, str]:
        response = requests.get(
            f"{self.BASE_URL}/corpCode.xml",
            params={"crtfc_key": self.api_key},
            timeout=self.timeout,
        )
        response.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            xml_name = next(name for name in archive.namelist() if name.endswith(".xml"))
            root = ElementTree.fromstring(archive.read(xml_name))

        mapping = {}
        for item in root.findall("list"):
            name = (item.findtext("corp_name") or "").strip()
            code = (item.findtext("corp_code") or "").strip()
            if name and code:
                mapping[name] = code
        return mapping

    def financial_statement_all(
        self,
        corp_code: str,
        year: int,
        report_code: str = "11011",
        fs_div: str = "CFS",
    ) -> list[dict]:
        payload = self._json_get(
            "fnlttSinglAcntAll.json",
            {
                "corp_code": corp_code,
                "bsns_year": str(year),
                "reprt_code": report_code,
                "fs_div": fs_div,
            },
        )
        return payload.get("list", []) if payload.get("status") == "000" else []
