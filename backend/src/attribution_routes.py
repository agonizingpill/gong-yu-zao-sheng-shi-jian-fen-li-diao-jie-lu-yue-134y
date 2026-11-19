from fastapi import APIRouter,Depends
from sqlalchemy import select
from .database import session
from .auth import current,operator,supervisor
from .models import Equipment,Calibration
from .common import dump
from .attribution_schemas import EquipmentInput,CalibrationInput,LedgerInput
from . import attribution_service as service
router=APIRouter()
@router.get('/complaints/{id}/equipment')
def equipment(id:int,db=Depends(session),u=Depends(current)):
    rows=db.scalars(select(Equipment).where(Equipment.complaint_id==id).order_by(Equipment.id)).all()
    out=[]
    for e in rows:
        calibrations=db.scalars(select(Calibration).where(Calibration.equipment_id==e.id)).all()
        out.append({**dump(e),'calibration_event_ids':[c.event_id for c in calibrations]})
    return out
@router.post('/complaints/{id}/equipment')
def add_equipment(id:int,data:EquipmentInput,db=Depends(session),u=Depends(operator)):
    return service.create_equipment(db,u,id,data)
@router.post('/complaints/{id}/calibrations')
def calibrate(id:int,data:CalibrationInput,db=Depends(session),u=Depends(operator)):
    return service.mark_calibration(db,u,id,data)
@router.get('/complaints/{id}/energy-overview')
def energy_overview(id:int,db=Depends(session),u=Depends(current)):
    return service.energy_overview(db,id)
@router.get('/complaints/{id}/energy-ledgers')
def energy_ledgers(id:int,db=Depends(session),u=Depends(current)):
    return service.list_ledgers(db,id)
@router.post('/complaints/{id}/energy-ledgers')
def register_energy(id:int,data:LedgerInput,db=Depends(session),u=Depends(supervisor)):
    return service.register_ledger(db,u,id,data)
