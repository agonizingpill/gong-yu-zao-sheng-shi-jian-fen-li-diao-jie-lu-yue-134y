import {api,post} from '../api.js';import {store} from '../store.js';import {esc,fields,stamp,token} from '../utils.js';import {empty,note} from '../components/common.js';
async function load(caseid){const [equipment,overview,ledgers]=await Promise.all([api(`/complaints/${caseid}/equipment`),api(`/complaints/${caseid}/energy-overview`),api(`/complaints/${caseid}/energy-ledgers`)]);return {equipment,overview,ledgers}}
function remainingSum(overview,equipmentId){return overview.events.reduce((s,e)=>s+(e.per_equipment.find(p=>p.equipment_id===equipmentId)?.remaining_energy||0),0)}
export async function render(){
  const caseid=store.selected;const {equipment,overview,ledgers}=await load(caseid);
  const calibratable=equipment.filter(e=>e.active);
  return `<section class="energy-desk">
  <div class="section-tools"><h2>设备能量台账 <small>单台启停采样估计 · 主管登记</small></h2><button class="secondary" data-action="energy-refresh">刷新余额</button></div>
  ${note('分不清的部分留待核实','每台设备可解释的能量只由单台启停采样拟合得到；拟合不上的残差计入“待核实”，不能登记给任何设备。同一采样的能量不会重复划给同一设备。')}
  <div class="energy-equip">${equipment.length?equipment.map(e=>`<div class="equip-chip"><b>${esc(e.name)}</b><small>${esc(e.kind)} · 标定采样 ${e.calibration_event_ids.length} 条</small><span>总可登记余量 ${remainingSum(overview,e.id).toFixed(3)}</span></div>`).join(''):empty('还没有设备台账','先登记风机、水泵等设备，再把单台启停采样标记为标定。')}</div>
  <h2>各采样能量余额</h2>
  ${overview.events.length?`<div class="energy-table"><table><thead><tr><th>采样</th><th>时刻</th><th>总能量</th><th>待核实</th>${calibratable.map(e=>`<th>${esc(e.name)}<small>可解释/已划/剩余</small></th>`).map(x=>x).join('')}</tr></thead><tbody>${overview.events.map(e=>`<tr><td>#${e.event_id}</td><td>${stamp(e.measured_at)}</td><td>${e.total.toFixed(3)}</td><td class="undetermined">${e.undetermined_energy.toFixed(3)}</td>${calibratable.map(q=>{const p=e.per_equipment.find(x=>x.equipment_id===q.id);return `<td class="${p.remaining_energy<=1e-6?'spent':''}">${p.explainable_energy.toFixed(3)} / ${p.allocated_energy.toFixed(3)} / <b>${p.remaining_energy.toFixed(3)}</b></td>`}).join('')}</tr>`).join('')}</tbody></table></div><p class="checksum">标定输入SHA256 ${overview.calibration_checksum}</p>`:empty('没有可估计的采样','先在事件页登记频带事件，并至少完成一台设备的单台标定。')}
  <div class="split">
  <form data-action="add-equipment" class="paper-form"><h2>登记设备</h2><label>设备名称<input name="name" value="屋顶风机" required minlength="2" maxlength="40"></label><label>类型<input name="kind" value="device" required minlength="2" maxlength="30"></label><label>说明<input name="note" value="风机与水泵同时运行，需分开归因" maxlength="300"></label><button>保存设备</button></form>
  <form data-action="mark-calibration" class="paper-form"><h2>标记单台启停采样</h2><label>设备<select name="equipment_id" required>${calibratable.map(e=>`<option value="${e.id}">${esc(e.name)}</option>`).join('')}</select></label><label>采样事件ID<input name="event_id" type="number" min="1" required placeholder="单台运行时的事件编号"></label><label>标定说明<textarea name="note" minlength="4" maxlength="300">单台设备启停对照采样，混合采样不可作为标定。</textarea></label><button>标记为标定采样</button></form>
  </div>
  <form data-action="register-ledger" class="paper-form ledger-form"><h2>主管跨采样登记一笔归因</h2><input type="hidden" name="client_token" value="${token()}"><label>归因设备<select name="equipment_id" required>${calibratable.map(e=>`<option value="${e.id}">${esc(e.name)}（总余量 ${remainingSum(overview,e.id).toFixed(3)}）</option>`).join('')}</select></label><label>各采样划给该设备的能量，每行 “事件ID:能量”，留空行忽略<textarea name="lines_text" rows="4" placeholder="1:1.2&#10;2:0.8"></textarea></label><label>现场证据<textarea name="note" minlength="4" maxlength="400">现场核对设备启停时间与各采样一致，仅登记单台可解释能量。</textarea></label><button>主管提交登记（超额整笔退回）</button><small class="token-hint">失败后可直接重试，隐藏令牌保证重试不重复扣减；登记成功后页面刷新会自动换新令牌。</small></form>
  <h2>已登记归因（调解仅可引用这些记录）</h2>
  ${ledgers.length?ledgers.map(l=>`<article class="ledger-card"><b>QEL-${l.id} · ${esc(l.equipment_name)} · ${l.lines.length}条采样 · 合计${l.amount.toFixed(3)}</b><small>${esc(l.reviewer)} · ${stamp(l.created_at)} · 令牌 ${esc(l.client_token)}</small><p>${esc(l.note)}</p><div class="ledger-lines">${l.lines.map(x=>`<span>事件#${x.event_id}：${x.amount.toFixed(3)}</span>`).join('')}</div></article>`).join(''):empty('尚无成功登记的归因','登记成功后，时段协议起草时才能选择能量归因记录。')}
  </section>`
}
export async function action(name,form,button){
  const caseid=store.selected;
  if(name==='energy-refresh'||name==='refresh'){return null}
  if(name==='add-equipment'){const v=fields(form);await post(`/complaints/${caseid}/equipment`,v);return '设备已登记'}
  if(name==='mark-calibration'){const v=fields(form);await post(`/complaints/${caseid}/calibrations`,{...v,equipment_id:Number(v.equipment_id),event_id:Number(v.event_id)});return '标定采样已标记，能量估计已纳入该设备模板'}
  if(name==='register-ledger'){
    const v=fields(form);
    const lines=String(v.lines_text||'').split('\n').map(s=>s.trim()).filter(Boolean).map(pair=>{const [eid,amount]=pair.split(':').map(s=>s&&s.trim());if(!eid||!amount)throw new Error('每行格式须为 事件ID:能量，例如 1:1.2');return {event_id:Number(eid),amount:Number(amount)}});
    if(!lines.length)throw new Error('请至少填写一行 事件ID:能量');
    if(lines.some(x=>!Number.isFinite(x.amount)||x.amount<0))throw new Error('能量须为非负有限数');
    const res=await post(`/complaints/${caseid}/energy-ledgers`,{equipment_id:Number(v.equipment_id),client_token:v.client_token,note:v.note,lines});
    return res.replayed?'重复请求已识别，返回原登记，未重复扣减':'能量归因已登记，可在调解页引用'
  }
  return null
}
