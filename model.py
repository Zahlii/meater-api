import pandas as pd
from pydantic import BaseModel
from typing import List, Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from pandas import DataFrame


class Alarm(BaseModel):
    type: int
    state: int
    limit: int


class EstimatorConfig(BaseModel):
    temperatureChangeBeforeReady: int
    secondsDelayBeforeReady: int
    secondsDelayBeforeResting: int
    estimatorType: int


class Setup(BaseModel):
    sequenceNumber: Optional[int]
    state: int
    name: str
    targetInternalTemperature: int
    alarms: List[Alarm]
    cookID: str
    cutID: int
    presetID: int
    clipNumber: int
    estimatorConfig: EstimatorConfig


class HistoryValue(BaseModel):
    ambient: int
    internal: int


class History(BaseModel):
    interval: int
    startTime: int
    values: List[HistoryValue]


class Raw(BaseModel):
    masterType: int
    probeID: str
    probeNumber: int
    probeFirmwareRevision: str
    parentDeviceID: str
    parentDeviceProbeNumber: int
    parentDeviceFirmwareRevision: str
    setup: Setup
    history: History
    deviceInfo: str
    peak: int
    appVersion: str
    osVersion: str
    emailAddress: str
    sendingDeviceCloudID: str


class Cook(BaseModel):
    id: str
    totalTime: int
    isFavourite: bool
    isDeleted: bool
    isOwner: bool
    updatedAt: datetime
    feedback: int
    raw: Raw

    def history_df(self) -> "DataFrame":
        from pandas import DataFrame

        ix = pd.date_range(
            start=datetime.fromtimestamp(self.raw.history.startTime),
            periods=len(self.raw.history.values),
            freq=f"{self.raw.history.interval}s",
        )
        return DataFrame.from_records([c.model_dump() for c in self.raw.history.values], index=ix) / 32

    def plot(self):
        from matplotlib import pyplot as plt

        df = self.history_df()

        f, ax = plt.subplots(figsize=(8, 6))
        df.plot(grid=True, ax=ax)
        ax.axhline(self.raw.setup.targetInternalTemperature / 32, color="black", lw=1, ls="--")
        plt.show()
