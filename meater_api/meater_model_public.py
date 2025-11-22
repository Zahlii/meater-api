from datetime import timedelta

from pydantic import BaseModel, computed_field


class Temperature(BaseModel):
    internal: float
    ambient: float


class CookTemperature(BaseModel):
    target: float
    peak: float


class CookTime(BaseModel):
    elapsed: int
    remaining: int

    @computed_field
    @property
    def elapsed_time(self) -> timedelta:
        return timedelta(seconds=self.elapsed)

    @computed_field
    @property
    def remaining_time(self) -> timedelta:
        return timedelta(seconds=self.remaining)


class V1Cook(BaseModel):
    id: str
    name: str
    state: str
    temperature: CookTemperature
    time: CookTime


class Device(BaseModel):
    id: str
    temperature: Temperature
    cook: V1Cook
    updated_at: int
