import json
from datetime import datetime, timedelta
from enum import IntEnum
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

import pandas as pd
from pydantic import BaseModel, computed_field

if TYPE_CHECKING:
    from pandas import DataFrame


class Alarm(BaseModel):
    type: "AlarmType"
    state: "AlarmState"
    limit: int  # Either C * 32 for Temperatures, or Seconds for Time Estimates


class EstimatorConfig(BaseModel):
    temperatureChangeBeforeReady: int
    secondsDelayBeforeReady: int
    secondsDelayBeforeResting: int
    estimatorType: int


class CookState(IntEnum):
    V2COOK_STATE_NOT_STARTED = 0
    V2COOK_STATE_COOK_CONFIGURED = 1
    V2COOK_STATE_STARTED = 2
    V2COOK_STATE_READY_FOR_RESTING = 3
    V2COOK_STATE_RESTING = 4
    V2COOK_STATE_SLIGHTLY_UNDERDONE = 5
    V2COOK_STATE_FINISHED = 6
    V2COOK_STATE_SLIGHTLY_OVERDONE = 7
    V2COOK_STATE_OVERCOOK = 8


class Setup(BaseModel):
    sequenceNumber: Optional[int]
    state: CookState
    name: str
    targetInternalTemperature: int  # C * 32
    alarms: List[Alarm]
    cookID: str
    cutID: int
    presetID: int
    clipNumber: int
    cookingAppliance: int | None = None
    estimatorConfig: EstimatorConfig

    @computed_field
    @property
    def cut(self) -> "Cut":
        return cuts.get(self.cutID)

    @computed_field
    @property
    def preset(self) -> "TemperatureRange":
        return presets.get(self.presetID)


class HistoryValue(BaseModel):
    ambient: int  # C * 32
    internal: int  # C * 32


class History(BaseModel):
    interval: int
    startTime: int
    values: List[HistoryValue]


class MasterType(IntEnum):
    MASTER_TYPE_BLOCK = 0
    MASTER_TYPE_IOS = 1
    MASTER_TYPE_ANDROID = 2
    MASTER_TYPE_PROBE_SIM = 3
    MASTER_TYPE_BLOCK_V2_2P = 4
    MASTER_TYPE_BLOCK_V2_4P = 5


class ProbeType(IntEnum):
    PROBE = 0
    BLOCK_PROBE_ONE = 1
    BLOCK_PROBE_TWO = 2
    BLOCK_PROBE_THREE = 3
    BLOCK_PROBE_FOUR = 4
    THERMOMIX_PROBE = 5
    TRAEGER_PROBE = 6
    PLUS = 128
    BLOCK = 8
    SECOND_GENERATION_PROBE = 16
    SECOND_GENERATION_BLOCK_PROBE_ONE = 17
    SECOND_GENERATION_BLOCK_PROBE_TWO = 18
    SECOND_GENERATION_BLOCK_PROBE_THREE = 19
    SECOND_GENERATION_BLOCK_PROBE_FOUR = 20
    SECOND_GENERATION_THERMOMIX_PROBE = 21
    SECOND_GENERATION_TRAEGER_PROBE = 22
    SECOND_GENERATION_PLUS = 112
    SECOND_GENERATION_THERMOMIX_PLUS = 80
    SECOND_GENERATION_TRAEGER_PLUS = 144
    SECOND_GENERATION_TWO_PROBE_BLOCK = 162
    SECOND_GENERATION_FOUR_PROBE_BLOCK = 164
    AMBER = 64


class AlarmType(IntEnum):
    ALARM_TYPE_MIN_AMBIENT = 0
    ALARM_TYPE_MAX_AMBIENT = 1
    ALARM_TYPE_MIN_INTERNAL = 2
    ALARM_TYPE_MAX_INTERNAL = 3
    ALARM_TYPE_TIME_FROM_NOW = 4
    ALARM_TYPE_TIME_BEFORE_READY = 5
    ALARM_TYPE_REPEAT_DURATION = 6
    ALARM_TYPE_ESTIMATE_READY = 7


class AlarmState(IntEnum):
    ALARM_STATE_NOT_READY = 0
    ALARM_STATE_READY = 1
    ALARM_STATE_FIRED = 2
    ALARM_STATE_DISMISSED = 3


class Raw(BaseModel):
    masterType: MasterType
    probeID: str
    probeNumber: ProbeType
    probeFirmwareRevision: str
    parentDeviceID: str
    parentDeviceProbeNumber: int
    parentDeviceFirmwareRevision: str
    setup: Setup
    history: History
    deviceInfo: str
    peak: int  # C * 32
    appVersion: str
    osVersion: str
    emailAddress: str
    sendingDeviceCloudID: str


def temp(x: int | pd.DataFrame) -> float | pd.DataFrame:
    return x / 32


class TemperatureRange(BaseModel):
    id: int
    name: str
    animal_id: int
    cut_id: int
    min_temp_c: int
    max_temp_c: int
    target_temp_c: int
    min_temp_f: int
    max_temp_f: int
    target_temp_f: int
    start_hex: str | None = None
    end_hex: str | None = None
    description: str
    image_name: str
    usda_safe: bool


class Cut(BaseModel):
    id: int
    name: str
    name_long: str
    animal_id: int
    cut_type_id: int
    estimated_thickness: float | None = None
    usda_safe_c: int | None = None
    usda_safe_f: int | None = None
    most_popular_temp_range_id: int | None = None
    cut_order: int
    insertion_instruction: str | None = None
    temperature_ranges: List[TemperatureRange]


json_data_meats = json.load(
    (Path(__file__).parent / "meats.json").open("r", encoding="utf-8")
)

cuts: dict[int, Cut] = {}
presets: dict[int, TemperatureRange] = {}

for category in json_data_meats.get("categories", []):
    for animal in category["animals"]:
        for cut_type in animal["cut_types"]:
            for cut in cut_type["cuts"]:
                cuts[cut["id"]] = Cut.model_validate(cut)

                for tr in cuts[cut["id"]].temperature_ranges:
                    presets[tr.id] = tr


class Cook(BaseModel):
    id: str
    totalTime: int  # Seconds
    isFavourite: bool
    isDeleted: bool
    isOwner: bool
    updatedAt: datetime
    feedback: int | None = None
    raw: Raw

    def as_str(self):
        return f"Cook(updated_at={self.updatedAt.strftime('%Y-%m-%d %H:%M')},started_at={self.startedAt.strftime('%Y-%m-%d %H:%M')},\n     cut={self.raw.setup.cut.name_long},preset={self.raw.setup.preset.name},duration={self.duration},peak={temp(self.raw.peak):.1f}°C,target={temp(self.raw.setup.targetInternalTemperature):.1f}°C)"

    @computed_field
    @property
    def startedAt(self) -> datetime:
        return datetime.fromtimestamp(self.raw.history.startTime)

    @computed_field
    @property
    def duration(self) -> timedelta:
        return timedelta(seconds=self.totalTime)

    def history_df(self) -> "DataFrame":
        from pandas import DataFrame

        ix = pd.date_range(
            start=self.startedAt,
            periods=len(self.raw.history.values),
            freq=f"{self.raw.history.interval}s",
        )
        return temp(
            DataFrame.from_records(
                [c.model_dump() for c in self.raw.history.values], index=ix
            )
        )

    def plot(self):
        from matplotlib import pyplot as plt

        df = self.history_df()

        f, ax = plt.subplots(figsize=(8, 6))
        df.plot(grid=True, ax=ax)
        ax.axhline(
            temp(self.raw.setup.targetInternalTemperature), color="black", lw=1, ls="--"
        )
        plt.title(self.as_str())
        plt.show()
