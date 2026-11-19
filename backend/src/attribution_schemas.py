import re
from pydantic import BaseModel,Field,field_validator
class EquipmentInput(BaseModel):
    name:str=Field(min_length=2,max_length=40)
    kind:str=Field(default='device',min_length=2,max_length=30)
    note:str=Field(default='',max_length=300)
class CalibrationInput(BaseModel):
    equipment_id:int=Field(gt=0)
    event_id:int=Field(gt=0)
    note:str=Field(default='单台设备启停对照采样，无原始录音',min_length=4,max_length=300)
class LedgerLineInput(BaseModel):
    event_id:int=Field(gt=0)
    amount:float=Field(ge=0)
class LedgerInput(BaseModel):
    equipment_id:int=Field(gt=0)
    client_token:str=Field(min_length=8,max_length=80)
    note:str=Field(default='',max_length=400)
    lines:list[LedgerLineInput]=Field(min_length=1,max_length=200)
    @field_validator('client_token')
    @classmethod
    def token_shape(cls,v):
        if not re.fullmatch(r'[A-Za-z0-9._:-]{8,80}',v):
            raise ValueError('重试令牌只允许字母数字及 . _ : -，用于幂等识别')
        return v
    @field_validator('lines')
    @classmethod
    def no_dup_event(cls,v):
        ids=[x.event_id for x in v]
        if len(ids)!=len(set(ids)):
            raise ValueError('同一笔登记中同一采样只能出现一次')
        return v
