import numpy as np
import requests
import io
import pandas as pd
from typing import Union, List
import datetime
import time
from threading import Thread


class EconomicCalendar:
    __slots__ = (
        "startHorizon",
        "endHorizon",
        "ecocal",
        "details",
        "URL",
        "hasCollectedTable",
        "hasCollectedDetails",
        "SOURCE_URL"
    )

    def __init__(self,
                 startHorizon: Union[datetime.datetime, str] = None,
                 endHorizon: Union[datetime.datetime, str] = None,
                 preBuildCalendar: bool = True) -> None:

        if isinstance(startHorizon, (datetime.datetime, datetime.date)):
            startHorizon = startHorizon.strftime("%Y-%m-%d")
        if isinstance(endHorizon, (datetime.datetime, datetime.date)):
            endHorizon = endHorizon.strftime("%Y-%m-%d")

        self.startHorizon: str = startHorizon if startHorizon is not None else "2023-10-08"
        self.endHorizon: str = endHorizon if startHorizon is not None else "2023-10-10"
        self.hasCollectedTable: bool = False
        self.hasCollectedDetails: bool = False
        self.ecocal: pd.DataFrame = None
        self.details: pd.DataFrame = None

        self.SOURCE_URL: str = "https://calendar-api.fxstreet.com/en/api/v1/eventDates"
        if preBuildCalendar:
            try:
                r_ = self._buildCalendar()
                if not r_:
                    raise Exception(f"An error occured.")
            except Exception as e:
                raise Exception(f"An error occured ({e})")

    def _buildCalendar(self) -> bool:

        self.URL = f"{self.SOURCE_URL}/{self.startHorizon}T00:00:00Z/{self.endHorizon}T23:59:59Z" \
                   f"?&volatilities=NONE" \
                   f"&volatilities=LOW" \
                   f"&volatilities=MEDIUM" \
                   f"&volatilities=HIGH" \
                   f"&countries=US&countries=UK&countries=EMU&countries=DE&countries=CN&countries=JP&countries=CA&countries=AU" \
                   f"&countries=NZ&countries=CH&countries=FR&countries=IT&countries=ES&countries=UA" \
                   f"&categories=8896AA26-A50C-4F8B-AA11-8B3FCCDA1DFD" \
                   f"&categories=FA6570F6-E494-4563-A363-00D0F2ABEC37" \
                   f"&categories=C94405B5-5F85-4397-AB11-002A481C4B92" \
                   f"&categories=E229C890-80FC-40F3-B6F4-B658F3A02635" \
                   f"&categories=24127F3B-EDCE-4DC4-AFDF-0B3BD8A964BE" \
                   f"&categories=DD332FD3-6996-41BE-8C41-33F277074FA7" \
                   f"&categories=7DFAEF86-C3FE-4E76-9421-8958CC2F9A0D" \
                   f"&categories=1E06A304-FAC6-440C-9CED-9225A6277A55" \
                   f"&categories=33303F5E-1E3C-4016-AB2D-AC87E98F57CA" \
                   f"&categories=9C4A731A-D993-4D55-89F3-DC707CC1D596" \
                   f"&categories=91DA97BD-D94A-4CE8-A02B-B96EE2944E4C" \
                   f"&categories=E9E957EC-2927-4A77-AE0C-F5E4B5807C16"

        try:
            start_clock = time.time_ns()
            r = requests.get(url=self.URL,
                             headers={
                                 "Accept": "text/csv",
                                 "Content-Type": "text/csv",
                                 "Referer": "https://www.fxstreet.com/",
                                 "Connection": "keep-alive",
                                 "User-Agent": "EcoCal script",
                             })
            end_clock = time.time_ns()
            dur_clock = end_clock - start_clock
            print(f"Duration: {dur_clock}")
        except Exception as e:
            raise Exception(f"An error just occurred (Error: {e})")
        if r.status_code != 200:
            raise Exception(f"An error just occurred")
        df = pd.read_csv(
            filepath_or_buffer=io.StringIO(r.content.decode("utf-8")),
            na_values=np.NaN
        )
        self.ecocal: pd.DataFrame = df
        self.hasCollectedTable = True
        return self.hasCollectedTable

    def getCalendar(self, withDetails: bool = True) -> pd.DataFrame:
        if not self.hasCollectedTable: self._buildCalendar()
        if withDetails:
            if not self.hasCollectedDetails:
                self._getDetails()
                return self._mergeTableDetails()
        return self.ecocal

    def saveCalendar(self) -> None:
        if not self.hasCollectedTable: self._buildCalendar()
        try:
            self.ecocal.to_csv(path_or_buf=f"ecocal_{datetime.datetime.now().isoformat()}.csv",
                               index_label="ID")
        except OSError as e:
            raise Exception(f"An error has occurred ({e}")

    def _getDetails(self) -> pd.DataFrame:
        if not self.hasCollectedTable: self._buildCalendar()

        cg = 0
        LIMIT_ROW_GROUPING: int = 10
        resources: List[str] = []
        output: dict = {}
        for index, row in self.ecocal.iterrows():
            cg += 1
            r_id = row["Id"]
            resources.append(r_id)

            if cg % LIMIT_ROW_GROUPING == 0:
                cg = 0
                threads = []
                for i, res_id in enumerate(resources):
                    t = Thread(target=self._requestDetails, args=(res_id, output))
                    t.start()
                    threads.append(t)

                for res_id, t in zip(resources, threads):
                    t.join()
                del threads
                resources = []
        df_ = pd.DataFrame(data=output).T
        df_.rename(columns={"id": "Id"}, inplace=True)
        self.hasCollectedDetails = True
        self.details = df_
        return self.details

    def _requestDetails(self, resource_id: str = "", output: dict = {}) -> Union[dict, None]:
        if not isinstance(resource_id, str) or str(resource_id) == "":
            raise Exception("Please enter a valid resource id")
        URL = f"{self.SOURCE_URL}/{resource_id}"

        r = requests.get(url=URL,
                         headers={
                             "Accept": "application/json",
                             "Content-Type": "application/json",
                             "Referer": "https://www.fxstreet.com/",
                             "Connection": "keep-alive",
                             "User-Agent": "EcoCal script",
                         })
        if r.status_code == 200:
            output[resource_id] = r.json()
            return output[resource_id]
        return None

    def _mergeTableDetails(self) -> pd.DataFrame:
        if not self.hasCollectedTable: self._buildCalendar()
        if not self.hasCollectedDetails: self._getDetails()
        df = pd.merge(left=self.ecocal, right=self.details, how="left", on="Id")
        return df