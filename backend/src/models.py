from datetime import datetime
from sqlalchemy import String,Text,Float,Integer,Boolean,DateTime,ForeignKey,JSON,UniqueConstraint,CheckConstraint
from sqlalchemy.orm import Mapped,mapped_column
from .database import Base
class User(Base):
    __tablename__='users'
    id:Mapped[int]=mapped_column(primary_key=True)
    username:Mapped[str]=mapped_column(String(60),unique=True)
    password_hash:Mapped[str]=mapped_column(String(160))
    role:Mapped[str]=mapped_column(String(20))
class Audit(Base):
    __tablename__='audit'
    id:Mapped[int]=mapped_column(primary_key=True)
    actor:Mapped[str]=mapped_column(String(60))
    action:Mapped[str]=mapped_column(String(100))
    subject:Mapped[str]=mapped_column(String(100))
    detail:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(default=datetime.utcnow)
class DemoClock(Base):
    __tablename__='demo_clock'
    id:Mapped[int]=mapped_column(primary_key=True)
    at:Mapped[datetime]=mapped_column(DateTime)
class Complaint(Base):
    __tablename__='complaints'
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(40),unique=True)
    alias:Mapped[str]=mapped_column(String(40))
    building:Mapped[str]=mapped_column(String(40))
    summary:Mapped[str]=mapped_column(String(400))
    consent:Mapped[bool]=mapped_column(Boolean,default=False)
    consent_note:Mapped[str]=mapped_column(String(300),default='')
    status:Mapped[str]=mapped_column(String(20),default='monitoring')
    created_at:Mapped[datetime]=mapped_column(default=datetime.utcnow)
class NoiseEvent(Base):
    __tablename__='noise_events'
    __table_args__=(UniqueConstraint('complaint_id','measured_at','position',name='event_same_window'),CheckConstraint('duration_s > 0',name='duration_positive'))
    id:Mapped[int]=mapped_column(primary_key=True)
    complaint_id:Mapped[int]=mapped_column(ForeignKey('complaints.id'))
    measured_at:Mapped[datetime]=mapped_column(DateTime)
    position:Mapped[str]=mapped_column(String(60))
    duration_s:Mapped[int]=mapped_column(Integer)
    energies:Mapped[list]=mapped_column(JSON)
    total:Mapped[float]=mapped_column(Float)
    note:Mapped[str]=mapped_column(String(300),default='合成频带，无原始录音')
class Separation(Base):
    __tablename__='separations'
    id:Mapped[int]=mapped_column(primary_key=True)
    complaint_id:Mapped[int]=mapped_column(ForeignKey('complaints.id'))
    state:Mapped[str]=mapped_column(String(20),default='queued')
    event_ids:Mapped[list]=mapped_column(JSON)
    result:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    error:Mapped[str]=mapped_column(String(400),default='')
class Attribution(Base):
    __tablename__='attributions'
    id:Mapped[int]=mapped_column(primary_key=True)
    complaint_id:Mapped[int]=mapped_column(ForeignKey('complaints.id'))
    separation_id:Mapped[int]=mapped_column(ForeignKey('separations.id'),unique=True)
    source:Mapped[str]=mapped_column(String(30))
    evidence:Mapped[str]=mapped_column(String(500))
    reviewer:Mapped[str]=mapped_column(String(60))
class Agreement(Base):
    __tablename__='agreements'
    __table_args__=(CheckConstraint('threshold > 0',name='positive_threshold'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    complaint_id:Mapped[int]=mapped_column(ForeignKey('complaints.id'))
    attribution_id:Mapped[int]=mapped_column(ForeignKey('attributions.id'))
    energy_ledger_id:Mapped[int|None]=mapped_column(ForeignKey('energy_ledgers.id'),nullable=True)
    party_a:Mapped[str]=mapped_column(String(40))
    party_b:Mapped[str]=mapped_column(String(40))
    quiet_from:Mapped[int]=mapped_column(Integer)
    quiet_to:Mapped[int]=mapped_column(Integer)
    threshold:Mapped[float]=mapped_column(Float)
    observation_days:Mapped[int]=mapped_column(Integer)
    state:Mapped[str]=mapped_column(String(20),default='draft')
    activated_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    observation_from:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    observation_until:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
class Signature(Base):
    __tablename__='signatures'
    __table_args__=(UniqueConstraint('agreement_id','party',name='one_signature'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    agreement_id:Mapped[int]=mapped_column(ForeignKey('agreements.id'))
    party:Mapped[str]=mapped_column(String(40))
    proof:Mapped[str]=mapped_column(String(300))
class Remedy(Base):
    __tablename__='remedies'
    id:Mapped[int]=mapped_column(primary_key=True)
    agreement_id:Mapped[int]=mapped_column(ForeignKey('agreements.id'))
    instruction:Mapped[str]=mapped_column(String(400))
    responsible:Mapped[str]=mapped_column(String(40))
    state:Mapped[str]=mapped_column(String(20),default='open')
    receipt:Mapped[str]=mapped_column(String(300),default='')
    completed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
class Recheck(Base):
    __tablename__='rechecks'
    id:Mapped[int]=mapped_column(primary_key=True)
    agreement_id:Mapped[int]=mapped_column(ForeignKey('agreements.id'))
    event_id:Mapped[int]=mapped_column(ForeignKey('noise_events.id'),unique=True)
    passed:Mapped[bool]=mapped_column(Boolean)
    note:Mapped[str]=mapped_column(String(300))
class Breach(Base):
    __tablename__='breaches'
    id:Mapped[int]=mapped_column(primary_key=True)
    agreement_id:Mapped[int]=mapped_column(ForeignKey('agreements.id'))
    event_id:Mapped[int]=mapped_column(ForeignKey('noise_events.id'),unique=True)
    resolved:Mapped[bool]=mapped_column(Boolean,default=False)
    resolution:Mapped[str]=mapped_column(String(300),default='')
class Closure(Base):
    __tablename__='closures'
    id:Mapped[int]=mapped_column(primary_key=True)
    complaint_id:Mapped[int]=mapped_column(ForeignKey('complaints.id'))
    agreement_id:Mapped[int]=mapped_column(ForeignKey('agreements.id'),unique=True)
    note:Mapped[str]=mapped_column(String(400))
    closed_at:Mapped[datetime]=mapped_column(DateTime)
class Equipment(Base):
    __tablename__='equipment'
    __table_args__=(UniqueConstraint('complaint_id','name',name='equipment_name_unique'),CheckConstraint("name <> ''",name='equipment_name_present'))
    id:Mapped[int]=mapped_column(primary_key=True)
    complaint_id:Mapped[int]=mapped_column(ForeignKey('complaints.id'))
    name:Mapped[str]=mapped_column(String(40))
    kind:Mapped[str]=mapped_column(String(30),default='device')
    note:Mapped[str]=mapped_column(String(300),default='')
    active:Mapped[bool]=mapped_column(Boolean,default=True)
class Calibration(Base):
    """单台设备启停时的采样标记：同一条采样只标定单台设备，避免把混合样本当模板。"""
    __tablename__='calibrations'
    __table_args__=(UniqueConstraint('event_id',name='one_calibration_per_event'),UniqueConstraint('equipment_id','event_id',name='calibration_natural_key'))
    id:Mapped[int]=mapped_column(primary_key=True)
    complaint_id:Mapped[int]=mapped_column(ForeignKey('complaints.id'))
    equipment_id:Mapped[int]=mapped_column(ForeignKey('equipment.id'))
    event_id:Mapped[int]=mapped_column(ForeignKey('noise_events.id'))
    note:Mapped[str]=mapped_column(String(300),default='')
class EnergyLedger(Base):
    """主管跨多条采样一次登记的一笔能量归因；client_token保证重试不重复扣减。"""
    __tablename__='energy_ledgers'
    __table_args__=(UniqueConstraint('client_token',name='energy_ledger_idempotent'),CheckConstraint('amount >= 0',name='ledger_amount_non_negative'))
    id:Mapped[int]=mapped_column(primary_key=True)
    complaint_id:Mapped[int]=mapped_column(ForeignKey('complaints.id'))
    equipment_id:Mapped[int]=mapped_column(ForeignKey('equipment.id'))
    client_token:Mapped[str]=mapped_column(String(80))
    amount:Mapped[float]=mapped_column(Float)
    note:Mapped[str]=mapped_column(String(400),default='')
    reviewer:Mapped[str]=mapped_column(String(60))
    created_at:Mapped[datetime]=mapped_column(default=datetime.utcnow)
class EnergyLine(Base):
    """一笔归因在各采样上的明细；同一笔内(采样,设备)唯一，跨笔累计超额由应用层余额校验拦截。"""
    __tablename__='energy_lines'
    __table_args__=(UniqueConstraint('ledger_id','event_id','equipment_id',name='line_unique_within_ledger'),CheckConstraint('amount >= 0',name='line_amount_non_negative'))
    id:Mapped[int]=mapped_column(primary_key=True)
    ledger_id:Mapped[int]=mapped_column(ForeignKey('energy_ledgers.id'))
    complaint_id:Mapped[int]=mapped_column(ForeignKey('complaints.id'))
    equipment_id:Mapped[int]=mapped_column(ForeignKey('equipment.id'))
    event_id:Mapped[int]=mapped_column(ForeignKey('noise_events.id'))
    amount:Mapped[float]=mapped_column(Float)
