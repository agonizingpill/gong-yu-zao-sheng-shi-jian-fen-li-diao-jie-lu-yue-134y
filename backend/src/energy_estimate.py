"""用单台设备启停采样估计每台设备在各采样上可解释的能量。

模板只来自单台设备单独运行（或单独停机对照）的标定采样；混合采样不能作为模板。
对每条采样做非负最小二乘 x ≈ Σ a_j·t_j（Σt_j=1，a_j≥0），a_j 即设备 j 可解释
的能量份额；拟合不上的正残差计入“待核实”，不允许任何登记占用。
本模块只处理相对频带能量，不识别声源身份、不提供分贝或法律结论。
"""
import hashlib,json

try:
    from scipy.optimize import nnls as _scipy_nnls
except Exception:  # 本地无科学计算栈时使用纯Python实现，结果口径一致
    _scipy_nnls=None


def _solve_square(M,y):
    """高斯-若尔当解小型线性方程组（正规方程），带轻微对角扰动防奇异。"""
    n=len(M)
    scale=max((abs(M[i][j]) for i in range(n) for j in range(n)),default=1.0) or 1.0
    A=[row[:]+[y[i]] for i,row in enumerate(M)]
    for i in range(n):
        A[i][i]+=1e-12*scale
    for col in range(n):
        pivot=max(range(col,n),key=lambda r:abs(A[r][col]))
        if abs(A[pivot][col])<1e-14*scale:
            A[col][col]+=1e-10*scale;pivot=col
        A[col],A[pivot]=A[pivot],A[col]
        div=A[col][col]
        A[col]=[v/div for v in A[col]]
        for r in range(n):
            if r==col:continue
            factor=A[r][col]
            if factor:
                A[r]=[a-factor*b for a,b in zip(A[r],A[col])]
    return [A[i][n] for i in range(n)]


def _lstsq(A,b):
    """列满秩假设下的最小二乘：(AᵀA)x=Aᵀb。"""
    m=len(A);n=len(A[0])
    At=[[A[i][j] for i in range(m)] for j in range(n)]
    M=[[sum(At[r][k]*At[s][k] for k in range(m)) for s in range(n)] for r in range(n)]
    y=[sum(At[r][k]*b[k] for k in range(m)) for r in range(n)]
    return _solve_square(M,y)


def _nnls_pure(A,b):
    """Lawson-Hanson 非负最小二乘（Lawson & Hanson 1974 经典主动集算法）。"""
    m=len(A);n=len(A[0]);eps=1e-12
    x=[0.0]*n;P=set();R=set(range(n))
    def residual():return [b[i]-sum(A[i][j]*x[j] for j in range(n)) for i in range(m)]
    def grad():
        r=residual();return [sum(A[i][j]*r[i] for i in range(m)) for j in range(n)]
    scale=(max(map(abs,b)) or 1.0)*max((abs(v) for row in A for v in row),default=1.0)
    tol=10*eps*max(m,n)*scale
    w=grad()
    while R and max(w[j] for j in R)>tol:
        j=max(R,key=lambda k:w[k]);P.add(j);R.remove(j)
        idx=sorted(P)
        sub=[[A[i][k] for k in idx] for i in range(m)]
        s_full=[0.0]*n
        for k,v in zip(idx,_lstsq(sub,b)):s_full[k]=v
        guard=0
        while min(s_full[k] for k in P)<=0 and guard<1000:
            guard+=1
            alpha=min(x[k]/(x[k]-s_full[k]) for k in P if s_full[k]<=0 and x[k]-s_full[k]!=0)
            x=[xk+alpha*(sk-xk) for xk,sk in zip(x,s_full)]
            P={k for k in P if x[k]>1e-14*scale}
            R=set(range(n))-P
            idx=sorted(P)
            sub=[[A[i][k] for k in idx] for i in range(m)]
            s_full=[0.0]*n
            for k,v in zip(idx,_lstsq(sub,b)):s_full[k]=v
        x=s_full
        w=grad()
    return [v if v>0 else 0.0 for v in x]


def nnls(A,b):
    if _scipy_nnls is not None:
        cols=[[A[i][j] for i in range(len(A))] for j in range(len(A[0]))]
        x,_=_scipy_nnls(cols,b)
        return [float(v) for v in x]
    return _nnls_pure(A,b)


def _norm(v):return sum(x*x for x in v)**0.5


def build_templates(calibrations):
    """calibrations: [{'equipment_id','event_id','energies':[8]}] → 设备模板（和为1）。"""
    grouped={}
    for c in calibrations:
        grouped.setdefault(c['equipment_id'],[]).append(c['energies'])
    templates={}
    for equip_id,spectra in grouped.items():
        bands=len(spectra[0])
        profile=[0.0]*bands
        for spec in spectra:
            total=sum(spec)
            for k,v in enumerate(spec):profile[k]+=v/total
        s=sum(profile)
        templates[equip_id]=[v/s for v in profile]
    return templates


def estimate_event(spectrum,templates):
    """返回每台设备可解释能量与待核实残差；可解释之和不超过采样总能量。"""
    total=sum(spectrum)
    equip_ids=sorted(templates)
    if not equip_ids or total<=0:
        return {'explainable':{eid:0.0 for eid in equip_ids},'undetermined':total,
                'residual_norm':_norm(spectrum),'fit_rmse':_norm(spectrum)/max(1,len(spectrum))**0.5}
    A=[[templates[eid][k] for eid in equip_ids] for k in range(len(spectrum))]
    raw=nnls(A,spectrum)
    fit=[sum(A[k][j]*raw[j] for j in range(len(raw))) for k in range(len(spectrum))]
    residual=[spectrum[k]-fit[k] for k in range(len(spectrum))]
    explainable={eid:max(0.0,raw[j]) for j,eid in enumerate(equip_ids)}
    over=sum(explainable.values())-total
    if over>0:  # NNLS无总量约束，过冲时按比例收回到总能量以内
        shrink=total/sum(explainable.values())
        explainable={eid:v*shrink for eid,v in explainable.items()}
    undetermined=max(0.0,total-sum(explainable.values()))
    return {'explainable':explainable,'undetermined':undetermined,
            'residual_norm':_norm(residual),'fit_rmse':_norm(residual)/max(1,len(spectrum))**0.5}


def estimate_all(events,calibrations):
    """events: [{'event_id','energies'}]；无标定模板的设备不会出现在结果中。"""
    templates=build_templates(calibrations)
    digest=hashlib.sha256(json.dumps(
        {'calibrations':sorted(calibrations,key=lambda c:(c['equipment_id'],c['event_id'])),
         'event_ids':sorted(e['event_id'] for e in events)},sort_keys=True).encode()).hexdigest()
    rows=[]
    for e in events:
        r=estimate_event(e['energies'],templates)
        rows.append({'event_id':e['event_id'],'total':sum(e['energies']),
                     'explainable':r['explainable'],'undetermined':r['undetermined'],
                     'fit_rmse':r['fit_rmse']})
    return {'calibration_checksum':digest,'templates':templates,'events':rows,
            'limitation':'模板仅来自单台设备启停采样；拟合残差为待核实能量，频带能量不能证明真实声源。'}
