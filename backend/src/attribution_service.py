from sqlalchemy import select
from .models import (Complaint,NoiseEvent,Equipment,Calibration,EnergyLedger,EnergyLine)
from .common import require,lock_case,get,record,dump
from .energy_estimate import estimate_all

# 浮点累计的容差：允许极少量舍入误差，超出即判定超额。
EPS=1e-6


def _equipment(db,caseid,eid):
    item=get(db,Equipment,eid)
    require(item.complaint_id==caseid,'设备不属于当前卷宗')
    require(item.active,'该设备已停用，不能再登记能量')
    return item


def create_equipment(db,user,caseid,data):
    case=lock_case(db,caseid)
    require(case.status!='closed','已结案卷宗请先由主管重开')
    require(not db.scalar(select(Equipment).where(Equipment.complaint_id==caseid,Equipment.name==data.name.strip())),'该设备名称已存在')
    row=Equipment(complaint_id=caseid,name=data.name.strip(),kind=data.kind,note=data.note)
    db.add(row);db.flush();record(db,user,'equipment.create',row.id,data.name);db.commit()
    return dump(row)


def mark_calibration(db,user,caseid,data):
    case=lock_case(db,caseid)
    require(case.status!='closed','已结案卷宗请先由主管重开')
    equip=_equipment(db,caseid,data.equipment_id)
    event=get(db,NoiseEvent,data.event_id)
    require(event.complaint_id==caseid,'采样不属于当前卷宗')
    require(not db.scalar(select(Calibration).where(Calibration.event_id==event.id)),'该采样已用于单台设备标定；一条采样只能标定一台设备')
    row=Calibration(complaint_id=caseid,equipment_id=equip.id,event_id=event.id,note=data.note)
    db.add(row);db.flush();record(db,user,'calibration.mark',row.id,f'equipment={equip.id};event={event.id}')
    db.commit();return dump(row)


def _overview_locked(db,caseid):
    """调用方必须已持有投诉行锁，保证余额与登记串行化在同一事务口径内。"""
    events=db.scalars(select(NoiseEvent).where(NoiseEvent.complaint_id==caseid).order_by(NoiseEvent.id)).all()
    calibrations=[{'equipment_id':c.equipment_id,'event_id':c.event_id,
                   'energies':get(db,NoiseEvent,c.event_id).energies}
                  for c in db.scalars(select(Calibration).where(Calibration.complaint_id==caseid))]
    estimate=estimate_all([{'event_id':e.id,'energies':e.energies} for e in events],calibrations)
    explain={row['event_id']:row['explainable'] for row in estimate['events']}
    lines=db.scalars(select(EnergyLine).where(EnergyLine.complaint_id==caseid)).all()
    allocated={}
    for line in lines:
        allocated.setdefault(line.event_id,{})
        allocated[line.event_id][line.equipment_id]=allocated[line.event_id].get(line.equipment_id,0)+line.amount
    rows=[]
    for e in events:
        cap=explain.get(e.id,{})
        used=allocated.get(e.id,{})
        per=[]
        for equip in db.scalars(select(Equipment).where(Equipment.complaint_id==caseid,Equipment.active==True).order_by(Equipment.id)):
            ceiling=cap.get(equip.id,0.0)
            spent=used.get(equip.id,0.0)
            per.append({'equipment_id':equip.id,'name':equip.name,
                        'explainable_energy':ceiling,'allocated_energy':spent,
                        'remaining_energy':max(0.0,ceiling-spent-EPS)})
        rows.append({'event_id':e.id,'measured_at':e.measured_at,'total':e.total,
                     'undetermined_energy':next((r['undetermined'] for r in estimate['events'] if r['event_id']==e.id),e.total),
                     'per_equipment':per})
    return {'calibration_checksum':estimate['calibration_checksum'],'events':rows}


def energy_overview(db,caseid):
    lock_case(db,caseid)  # 余额查询也走同一把锁，避免读到锁等待前的旧聚合
    return _overview_locked(db,caseid)


def register_ledger(db,user,caseid,data):
    case=lock_case(db,caseid)
    require(case.status!='closed','已结案卷宗不能登记能量归因，请先由主管重开')
    equip=_equipment(db,caseid,data.equipment_id)
    # 幂等：同一client_token的重复提交直接回放原结果，不再次扣减；令牌全局唯一但须归属本卷本设备。
    existing=db.scalar(select(EnergyLedger).where(EnergyLedger.client_token==data.client_token))
    if existing:
        require(existing.complaint_id==caseid and existing.equipment_id==equip.id,
                '重试令牌已被其他卷宗或设备使用，请更换令牌后提交')
        lines=db.scalars(select(EnergyLine).where(EnergyLine.ledger_id==existing.id).order_by(EnergyLine.id)).all()
        return {'replayed':True,'ledger':dump(existing),'lines':[dump(x) for x in lines]}
    event_ids=[x.event_id for x in data.lines]
    events={e.id:e for e in db.scalars(select(NoiseEvent).where(NoiseEvent.complaint_id==caseid,NoiseEvent.id.in_(event_ids)))}
    require(len(events)==len(set(event_ids)),'存在不属于本卷或重复的采样')
    overview=_overview_locked(db,caseid)
    caps={row['event_id']:{p['equipment_id']:p for p in row['per_equipment']} for row in overview['events']}
    # 整笔校验：任何一条超额/无可解释余量都整笔退回，不写入任何明细。
    for line in data.lines:
        slot=caps[line.event_id].get(equip.id)
        require(slot is not None,'设备与采样不匹配，无法登记')
        require(slot['explainable_energy']>EPS,f'采样#{line.event_id}缺少该设备的单台启停标定，可解释能量为0，留待核实')
        require(line.amount<=slot['remaining_energy']+EPS,
                f"采样#{line.event_id}可登记余量{slot['remaining_energy']:.4f}不足，本笔登记整笔退回")
        require(line.amount>=0,'明细能量不可为负')
    total=sum(x.amount for x in data.lines)
    ledger=EnergyLedger(complaint_id=caseid,equipment_id=equip.id,
                        client_token=data.client_token,
                        amount=total,note=data.note,reviewer=user.username)
    db.add(ledger);db.flush()
    for line in data.lines:
        db.add(EnergyLine(ledger_id=ledger.id,complaint_id=caseid,equipment_id=equip.id,
                          event_id=line.event_id,amount=line.amount))
    record(db,user,'energy.register',ledger.id,f'equipment={equip.id};lines={len(data.lines)};total={total:.4f};token={data.client_token}')
    db.commit()
    db.refresh(ledger)
    lines=db.scalars(select(EnergyLine).where(EnergyLine.ledger_id==ledger.id).order_by(EnergyLine.id)).all()
    return {'replayed':False,'ledger':dump(ledger),'lines':[dump(x) for x in lines]}


def list_ledgers(db,caseid):
    lock_case(db,caseid)
    ledgers=db.scalars(select(EnergyLedger).where(EnergyLedger.complaint_id==caseid).order_by(EnergyLedger.id.desc())).all()
    out=[]
    for l in ledgers:
        lines=db.scalars(select(EnergyLine).where(EnergyLine.ledger_id==l.id).order_by(EnergyLine.id)).all()
        equip=db.get(Equipment,l.equipment_id)
        out.append({**dump(l),'equipment_name':equip.name if equip else '',
                    'lines':[dump(x) for x in lines]})
    return out
