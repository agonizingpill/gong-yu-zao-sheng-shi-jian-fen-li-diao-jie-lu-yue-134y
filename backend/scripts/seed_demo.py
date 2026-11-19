from datetime import datetime,timedelta
from sqlalchemy import select,func
from src.database import Base,engine,Session
from src.models import User,DemoClock,Complaint,NoiseEvent,Equipment,Calibration
from src.auth import password_hash

def seed():
    Base.metadata.create_all(engine)
    with Session() as db:
        for role in ('operator','supervisor','viewer'):
            if not db.scalar(select(User).where(User.username==role)):
                db.add(User(username=role,role=role,password_hash=password_hash('Quiet2026!')))
        if not db.get(DemoClock,1):db.add(DemoClock(id=1,at=datetime(2026,11,18,16,0)))
        items=[('QT031','访客青叶','3栋北侧','22:30设备低频持续，申请协调减振时段',True),('QT032','访客杉木','6栋东侧','午间装修冲击频带，尚未授权监测',False),('QT033','访客白榆','1栋走廊','晚间人声频带事件，希望双方协调安静时段',True)]
        for code,alias,building,summary,consent in items:
            if not db.scalar(select(Complaint).where(Complaint.code==code)):
                c=Complaint(code=code,alias=alias,building=building,summary=summary,consent=consent,consent_note='书面授权QTC-031' if consent else '待取得授权');db.add(c);db.flush()
                if consent:
                    for j in range(6):
                        energy=[8+j*.1,6,1.6,.5,.3,.2,.1,.05] if code=='QT031' else [.2,.3,.8,3,6+j*.1,7,4,1]
                        db.add(NoiseEvent(complaint_id=c.id,measured_at=datetime(2026,11,17,22,30)+timedelta(minutes=j*5),position='窗台测点A',duration_s=60,energies=energy,total=sum(energy),note='合成频带示例，无录音及真实住户信息'))
        qt031=db.scalar(select(Complaint).where(Complaint.code=='QT031'))
        if qt031:
            # 单台设备启停对照：风机偏63/125Hz，水泵偏250/500Hz；两条标定均为单独运行采样。
            single=[('屋顶风机','单启风机',datetime(2026,11,17,21,40),[9,7,1.2,.3,.2,.1,.05,.02]),
                    ('地下水泵','单开水泵',datetime(2026,11,17,21,50),[1.5,2.5,6,4,.6,.3,.1,.05])]
            for name,tag,when,energy in single:
                equip=db.scalar(select(Equipment).where(Equipment.complaint_id==qt031.id,Equipment.name==name))
                if not equip:
                    equip=Equipment(complaint_id=qt031.id,name=name,kind='device',note='设备台账示例');db.add(equip);db.flush()
                ev=db.scalar(select(NoiseEvent).where(NoiseEvent.complaint_id==qt031.id,NoiseEvent.measured_at==when,NoiseEvent.position=='设备间测点B'))
                if not ev:
                    ev=NoiseEvent(complaint_id=qt031.id,measured_at=when,position='设备间测点B',duration_s=60,energies=energy,total=sum(energy),note=f'{tag}启停对照采样，无录音')
                    db.add(ev);db.flush()
                if not db.scalar(select(Calibration).where(Calibration.event_id==ev.id)):
                    db.add(Calibration(complaint_id=qt031.id,equipment_id=equip.id,event_id=ev.id,note=f'{tag}，单台运行时采集'))
        db.commit()
        counts={m.__tablename__:db.scalar(select(func.count()).select_from(m)) for m in (User,Complaint,NoiseEvent,DemoClock,Equipment,Calibration)}
        print(counts)
        return counts
if __name__=='__main__':seed()
