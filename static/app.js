const $=s=>document.querySelector(s);const api=async(url,opts={})=>{const r=await fetch(url,{credentials:'same-origin',cache:'no-store',...opts,headers:opts.body instanceof FormData?opts.headers:{'Content-Type':'application/json',...(opts.headers||{})}});if(r.status===401){location.assign('/login?next='+encodeURIComponent(location.pathname));throw Error('Your login session expired. Please sign in again.')}const d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.error||'Request failed');return d};const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const money=n=>'₹'+Number(n||0).toFixed(2);function notify(e){alert(e.message||e)}
$('#nav').addEventListener('click',e=>{const b=e.target.closest('button[data-tab]');if(!b)return;document.querySelectorAll('#nav button').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.panel').forEach(x=>x.classList.toggle('active',x.id===b.dataset.tab));const h=document.getElementById('current-section');if(h)h.textContent=b.textContent.trim();loadTab(b.dataset.tab)});
async function loadDoctors(){
 const d=await api('/api/doctors');
 $('#doctors-list').innerHTML=d.doctors.map(x=>'<article class="doctor-profile"><div class="doctor-profile-head"><div class="doctor-avatar">'+esc((x.name||'D').replace(/^Dr\\.?\\s*/,'').slice(0,1).toUpperCase())+'</div><div><h3>'+esc(x.name)+'</h3><b>'+esc(x.department)+'</b></div><span class="experience-badge">'+Number(x.experience_years||0)+' yrs experience</span></div><p class="doctor-summary">'+esc(x.profile_summary||'Specialist consultation and patient care.')+'</p><div class="doctor-credentials"><div><small>QUALIFICATION</small><strong>'+esc(x.qualification)+'</strong></div><div><small>CERTIFICATION</small><strong>'+esc(x.certifications||x.qualification)+'</strong></div><div><small>CONSULTATION HOURS</small><strong>'+esc(x.days)+' · '+esc(x.start_time)+'–'+esc(x.end_time)+'</strong></div><div><small>CONSULTATION FEE</small><strong>'+money(x.consultation_fee)+'</strong></div></div></article>').join('')||'<p>No doctors listed.</p>';
 if($('#doctor_id'))$('#doctor_id').innerHTML=d.doctors.map(x=>'<option value="'+x.id+'">'+esc(x.name)+' — '+esc(x.department)+'</option>').join('');
}
function renderAppointments(rows){
 const box=$('#appointments-list');if(!box)return;
 const isDoctor=window.clinic_ROLE==='doctor';
 box.innerHTML=rows.map(x=>`<article><div><b>${esc(x.doctor_name)}</b><small>${esc(x.department)} · ${esc(x.appointment_date)} at ${esc(x.appointment_time)}${x.patient_name?' · Patient: '+esc(x.patient_name):''}</small><small>${esc(x.reason||'No reason supplied')} · ${esc(x.status)}</small>${isDoctor&&x.status==='Booked'?'<div class="reschedule-fields"><label>New date<input type="date" id="reschedule-date-'+x.id+'" min="'+new Date().toISOString().slice(0,10)+'" value="'+esc(x.appointment_date)+'"></label><label>New time<input type="time" id="reschedule-time-'+x.id+'" value="'+esc(x.appointment_time)+'"></label><button type="button" onclick="rescheduleAppointment('+x.id+')">Reschedule</button></div>':''}</div>${!isDoctor&&x.status==='Booked'&&['patient','admin','reception'].includes(window.clinic_ROLE)?'<button class="danger" onclick="cancelAppointment('+x.id+')">Cancel</button>':''}</article>`).join('')||'<p>No appointments yet.</p>';
}
async function loadAppointments(){const d=await api('/api/appointments');window.appointmentCache=d.appointments;const filter=$('#appointment-filter')?.value||'all';renderAppointments(filter==='all'?d.appointments:d.appointments.filter(x=>x.status===filter))}
window.cancelAppointment=async id=>{if(!confirm('Cancel this appointment?'))return;try{await api('/api/appointments/'+id,{method:'PATCH'});await loadAppointments()}catch(e){notify(e)}};
window.rescheduleAppointment=async id=>{
 const day=$('#reschedule-date-'+id)?.value,slot=$('#reschedule-time-'+id)?.value;
 if(!day||!slot){alert('Choose both a new date and time.');return}
 if(!confirm('Reschedule this appointment to '+day+' at '+slot+'?'))return;
 try{const d=await api('/api/appointments/'+id+'/reschedule',{method:'POST',body:JSON.stringify({appointment_date:day,appointment_time:slot})});alert(d.message);await loadAppointments()}catch(e){notify(e)}
};
$('#book-form')?.addEventListener('submit',async e=>{e.preventDefault();try{const d=await api('/api/appointments',{method:'POST',body:JSON.stringify({doctor_id:$('#doctor_id').value,appointment_date:$('#appointment_date').value,appointment_time:$('#appointment_time').value,reason:$('#reason').value})});e.target.reset();await Promise.all([loadAppointments(),loadBills()]);alert(d.message+(d.bill_id?' Bill #'+d.bill_id+' · '+money(d.amount)+'. Go to Due payments and select Generate QR.':''))}catch(x){notify(x)}});
async function loadMedicines(){const d=await api('/api/medicines?q='+encodeURIComponent($('#medicine-search').value));const icon=x=>({tablet:'💊',capsule:'💊',drinkable:'🥤',sachet:'🧃',other:'🧴'}[String(x.dosage_form||'Other').toLowerCase()]||'🧴');if($('#order-medicine'))$('#order-medicine').innerHTML=d.medicines.filter(x=>Number(x.stock)>0).map(x=>'<option value="'+x.id+'">'+esc(x.name)+' '+esc(x.strength)+' — '+money(x.price)+' ('+Number(x.stock)+' available)</option>').join('');$('#medicines-list').innerHTML=d.medicines.length?`<table class="inventory-table"><thead><tr><th>Item</th><th>Form</th><th>Strength</th><th>Available stock</th><th>Listed price</th></tr></thead><tbody>${d.medicines.map(x=>`<tr><td><span class="medicine-icon">${icon(x)}</span><b>${esc(x.name)}</b></td><td>${esc(x.dosage_form||'Other')}</td><td>${esc(x.strength)}</td><td><span class="stock-pill ${Number(x.stock)>0?'in-stock':'out-stock'}">${Number(x.stock)>0?Number(x.stock)+' available':'Out of stock'}</span></td><td>${money(x.price)}</td></tr>`).join('')}</tbody></table>`:'<p>No matching medicines.</p>'}$('#medicine-search').addEventListener('input',()=>loadMedicines());if($('#medicine-form'))$('#medicine-form').addEventListener('submit',async e=>{e.preventDefault();try{await api('/api/medicines',{method:'POST',body:JSON.stringify({name:$('#med_name').value,strength:$('#med_strength').value,price:$('#med_price').value,stock:$('#med_stock').value,dosage_form:$('#med_form').value})});e.target.reset();loadMedicines()}catch(x){notify(x)}});
async function loadMedicineOrders(){const box=$('#medicine-orders-list');if(!box)return;const d=await api('/api/medicine-orders');box.innerHTML=(d.orders||[]).map(o=>'<article><div><b>Order #'+o.id+' · '+esc(o.medicine_name)+' '+esc(o.strength||'')+'</b><small>'+(o.patient_name?'Patient: '+esc(o.patient_name)+' · ':'')+'Qty: '+o.quantity+' · Pickup: '+esc(o.pickup_date)+' at '+esc(o.pickup_time)+'</small><small>Status: '+esc(o.status)+' · '+esc(o.created_at)+'</small></div></article>').join('')||'<p>No pickup requests yet.</p>'}
$('#medicine-order-form')?.addEventListener('submit',async e=>{e.preventDefault();try{const d=await api('/api/medicine-orders',{method:'POST',body:JSON.stringify({medicine_id:$('#order-medicine').value,quantity:$('#order-quantity').value,pickup_date:$('#pickup-date').value,pickup_time:$('#pickup-time').value})});alert(d.message+(d.bill_id?' Bill #'+d.bill_id+' has been added to Due payments.':''));e.target.reset();$('#order-quantity').value=1;await Promise.all([loadMedicines(),loadMedicineOrders(),loadBills()])}catch(x){notify(x)}});
const pickupDate=$('#pickup-date');if(pickupDate)pickupDate.min=new Date().toISOString().slice(0,10);
async function loadRecords(){const d=await api('/api/records');$('#records-list').innerHTML=d.records.map(x=>`<article><div><b>${esc(x.record_type)}</b><small>${x.patient_name?'Patient: '+esc(x.patient_name)+' · ':''}${esc(x.created_at)}</small><small>${esc(x.notes)}</small>${x.file_name?`<a href="/uploads/${encodeURIComponent(x.file_name)}">Download attachment</a>`:''}</div></article>`).join('')||'<p>No records available.</p>'}
if($('#record-form'))$('#record-form').addEventListener('submit',async e=>{e.preventDefault();try{const r=await fetch('/api/records',{method:'POST',credentials:'same-origin',body:new FormData(e.target)});const d=await r.json();if(!r.ok)throw Error(d.error);e.target.reset();loadRecords()}catch(x){notify(x)}});
if($('#chat-form'))$('#chat-form').addEventListener('submit',async e=>{e.preventDefault();const q=$('#chat-question').value.trim();if(!q)return;const log=$('#chat-log');log.insertAdjacentHTML('beforeend',`<div class="mine">${esc(q)}</div>`);$('#chat-question').value='';try{const d=await api('/ask',{method:'POST',body:JSON.stringify({question:q})});log.insertAdjacentHTML('beforeend',`<div class="bot">${esc(d.answer)}</div>`);if(d.action)await Promise.all([loadAppointments(),loadMedicines(),loadMedicineOrders(),loadBills()]);loadChatHistory().catch(()=>{})}catch(x){log.insertAdjacentHTML('beforeend',`<div class="bot">${esc(x.message)}</div>`)}log.scrollTop=log.scrollHeight});
async function loadChatContext(){
  const log=$('#chat-log');if(!log)return;
  const d=await api('/api/chat-context');
  log.innerHTML=(d.messages||[]).map(x=>`<div class="mine">${esc(x.question)}</div><div class="bot">${esc(x.answer)}</div>`).join('')||'<div class="bot">Welcome to Clinic FAQ Project. Ask about clinic services, doctors, appointments, or available medicines.</div>';
  log.scrollTop=log.scrollHeight;
}
async function loadChatHistory(){const box=$('#history-list');if(!box)return;const d=await api('/api/chat-history');box.innerHTML=(d.history||[]).map(x=>{const category=String(x.classification||'UNAVAILABLE').toUpperCase();const cls=category.toLowerCase();return `<article class="history-entry"><div class="history-topline"><small>${esc(x.created_at)} · ${esc(x.topic)}</small><span class="classification-badge ${cls}">${esc(category)}</span></div><div class="history-label">USER QUESTION</div><b class="history-text">${esc(x.question)}</b><div class="history-label">ASSISTANT RESPONSE</div><p class="history-text">${esc(x.answer)}</p></div></article>`}).join('')||'<p>No saved conversations yet. Start a conversation in Patient help desk.</p>'}
async function loadAuditLogs(){
 const box=$('#audit-history-list');if(!box)return;
 const d=await api('/api/audit-logs');
 const rows=d.logs||[];
 box.innerHTML=rows.length?'<table class="audit-table"><thead><tr><th>Date / time</th><th>Changed by</th><th>Action</th><th>Record</th><th>Change details</th><th>Old value</th><th>New value</th></tr></thead><tbody>'+rows.map(x=>'<tr><td>'+esc(x.created_at)+'</td><td>'+esc(x.actor_name||'Unknown')+'<small>'+esc(x.actor_email||'')+'</small></td><td>'+esc(x.action)+'</td><td>'+esc(x.entity_type)+' #'+esc(x.entity_id)+'</td><td>'+esc(x.details)+'</td><td>'+esc(x.old_value||'—')+'</td><td>'+esc(x.new_value||'—')+'</td></tr>').join('')+'</tbody></table>':'<p>No administrative changes have been recorded yet.</p>';
}
$('#refresh-audit-logs')?.addEventListener('click',()=>loadAuditLogs().catch(notify));
async function loadManagedPrices(){
 const box=$('#managed-prices-list');if(!box)return;
 const d=await api('/api/price-list');
 const groups=[
  ['Clinic services','service',d.services||[]],
  ['Doctor consultation fees','doctor',d.doctors||[]],
  ['Medicine prices','medicine',d.medicines||[]]
 ];
 box.innerHTML=groups.map(([title,kind,items])=>'<section class="managed-price-group"><h3>'+title+'</h3>'+items.map(x=>'<form class="managed-price-row" data-price-kind="'+kind+'" data-price-id="'+x.id+'"><div><b>'+esc(x.name)+(x.strength?' '+esc(x.strength):'')+'</b><small>'+esc(x.department||'Pharmacy')+(x.stock!==undefined?' · Stock: '+Number(x.stock):'')+'</small></div><label>Price (₹)<input type="number" min="0" max="10000000" step="0.01" name="price" value="'+Number(x.price).toFixed(2)+'" required></label><button type="submit">Save price</button></form>').join('')+'</section>').join('')||'<p>No catalogue items found.</p>';
}
$('#managed-prices-list')?.addEventListener('submit',async e=>{
 const form=e.target.closest('form[data-price-kind]');if(!form)return;
 e.preventDefault();
 const kind=form.dataset.priceKind,id=form.dataset.priceId,price=form.elements.price.value;
 try{const d=await api('/api/prices/'+kind+'/'+id,{method:'PATCH',body:JSON.stringify({price})});alert(d.message);await Promise.all([loadManagedPrices(),loadPriceList(),loadDoctors(),loadMedicines()])}catch(err){notify(err)}
});
$('#reload-managed-prices')?.addEventListener('click',()=>loadManagedPrices().catch(notify));
async function loadPriceList(){const box=$('#assistant-price-list');if(!box)return;const d=await api('/api/price-list');const serviceCards=(d.services||[]).map(x=>`<article class="price-card"><span>${esc(x.department)}</span><b>${esc(x.name)}</b><strong>${money(x.price)}</strong><small>${esc(x.description)}</small></article>`).join('');const doctorCards=(d.doctors||[]).map(x=>`<article class="price-card doctor-price"><span>${esc(x.department)}</span><b>${esc(x.name)}</b><strong>${money(x.price)}</strong><small>Consultation fee</small></article>`).join('');const medicineCards=(d.medicines||[]).map(x=>`<article class="price-card medicine-price"><span>Pharmacy</span><b>${esc(x.name)} ${esc(x.strength)}</b><strong>${money(x.price)}</strong><small>${Number(x.stock)>0?'Listed stock: '+Number(x.stock):'Out of stock'}</small></article>`).join('');box.innerHTML=serviceCards+doctorCards+medicineCards||'<p>No prices have been configured.</p>'}
$('#refresh-history')?.addEventListener('click',()=>loadChatHistory().catch(notify));
$('#reload-prices')?.addEventListener('click',()=>loadPriceList().catch(notify));
async function loadAnalytics(){const d=await api('/api/analytics');$('#analytics-summary').innerHTML=[['Total chatbot queries',d.total_queries],['Appointments',d.appointments],['Registered patients',d.patients]].map(x=>`<article><span>${x[0]}</span><strong>${x[1]}</strong></article>`).join('');$('#topic-list').innerHTML=d.topics.map(x=>`<article><b>${esc(x.label)}</b><strong>${x.count}</strong></article>`).join('')||'<p>No query data yet.</p>';$('#category-list').innerHTML=d.categories.map(x=>`<article><b>${esc(x.label)}</b><strong>${x.count}</strong></article>`).join('')||'<p>No classifications yet.</p>'}
function loadTab(id){const map={doctors:loadDoctors,appointments:loadAppointments,records:loadRecords,medicines:()=>Promise.all([loadMedicines(),loadMedicineOrders()]),analytics:loadAnalytics,history:loadChatHistory,assistant:loadPriceList,'manage-prices':()=>Promise.all([loadManagedPrices(),loadAuditLogs()]),payments:loadBills,emergency:loadEmergencies};if(map[id])map[id]().catch(notify)}

// Executive dashboard enhancements: live KPIs, workspace search and theme controls.
async function loadDashboardMetrics(){
  try{const [a,d]=await Promise.all([api('/api/appointments'),api('/api/doctors')]);
    const ka=$('#kpi-appointments'),kd=$('#kpi-doctors');if(ka)ka.textContent=a.appointments.length;if(kd)kd.textContent=d.doctors.length;
    }catch(e){console.warn('Dashboard metrics:',e.message)}
  if(['admin','reception'].includes(window.clinic_ROLE)){try{const x=await api('/api/analytics');$('#kpi-queries').textContent=x.total_queries}catch(e){$('#kpi-queries').textContent='—'}}else{$('#kpi-queries').textContent='Private'}
}
$('#appointment-filter')?.addEventListener('change',()=>{const rows=window.appointmentCache||[];const v=$('#appointment-filter').value;renderAppointments(v==='all'?rows:rows.filter(x=>x.status===v))});
$('#global-search')?.addEventListener('input',e=>{const q=e.target.value.trim().toLowerCase();document.querySelectorAll('.panel').forEach(panel=>{panel.querySelectorAll('.list article,.cards article,.overview-card').forEach(item=>{item.hidden=!!q&&!item.textContent.toLowerCase().includes(q)})})});
$('#theme-toggle')?.addEventListener('click',()=>{document.body.classList.toggle('dark-mode');try{localStorage.setItem('greenfield-theme',document.body.classList.contains('dark-mode')?'dark':'light')}catch(_){}});
try{if(localStorage.getItem('greenfield-theme')==='dark')document.body.classList.add('dark-mode')}catch(_){}

function updateClock(){const el=$('#live-clock');if(el)el.textContent=new Intl.DateTimeFormat(undefined,{weekday:'short',month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date())}
updateClock();setInterval(updateClock,30000);
const dateInput=$('#appointment_date');if(dateInput)dateInput.min=new Date().toISOString().slice(0,10);
loadDashboardMetrics();


// Profile dropdown: logout is shown only after the profile control is clicked.
const profileToggle=$('#profile-toggle'), profileMenu=$('#profile-menu');
async function loadNotifications(){
 const box=$('#profile-notifications');if(!box)return;
 try{
  const d=await api('/api/notifications');
  const count=$('#notification-count');
  if(count){count.textContent=d.unread_count;count.hidden=!d.unread_count}
  box.innerHTML=(d.notifications||[]).map(n=>'<button type="button" class="profile-notification '+(n.is_read?'read':'unread')+'" data-notification-id="'+n.id+'"><b>'+esc(n.title)+'</b><small>'+esc(n.message)+'</small><time>'+esc(n.created_at)+'</time></button>').join('')||'<p class="notification-empty">No notifications yet.</p>';
 }catch(e){box.innerHTML='<p class="notification-empty">Could not load notifications.</p>'}
}
profileToggle?.addEventListener('click',()=>{const open=profileMenu.hidden;profileMenu.hidden=!open;profileToggle.setAttribute('aria-expanded',String(open));if(open)loadNotifications()});
$('#profile-notifications')?.addEventListener('click',async e=>{
 const item=e.target.closest('[data-notification-id]');if(!item)return;
 try{await api('/api/notifications/'+item.dataset.notificationId+'/read',{method:'PATCH'});await loadNotifications()}catch(err){notify(err)}
});
$('#mark-all-notifications')?.addEventListener('click',async()=>{
 try{await api('/api/notifications/read-all',{method:'POST',body:JSON.stringify({})});await loadNotifications()}catch(err){notify(err)}
});
loadNotifications();
setInterval(loadNotifications,30000);
document.addEventListener('click',e=>{if(profileMenu&&!profileMenu.hidden&&!e.target.closest('.profile-wrap')){profileMenu.hidden=true;profileToggle?.setAttribute('aria-expanded','false')}});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&profileMenu&&!profileMenu.hidden){profileMenu.hidden=true;profileToggle?.setAttribute('aria-expanded','false')}});

// Chat quick actions populate the normal chat input, so the same backend handles them.
document.querySelectorAll('[data-chat-prompt]').forEach(button=>button.addEventListener('click',()=>{const input=$('#chat-question');input.value=button.dataset.chatPrompt;input.focus();}));

// Workspace utilities are real actions, not decorative controls.
const refreshButton = $('#refresh-workspace');
refreshButton?.addEventListener('click', async () => {
  const active = document.querySelector('.panel.active')?.id || 'overview';
  const loaders = {
    overview: loadDashboardMetrics,
    assistant: loadPriceList,
    history: loadChatHistory,
    appointments: loadAppointments,
    doctors: loadDoctors,
    
    records: loadRecords,
    medicines: loadMedicines,
    analytics: loadAnalytics
  };
  const loader = loaders[active];
  if (!loader) { notify(new Error('There is nothing to refresh in this section.')); return; }
  refreshButton.disabled = true;
  refreshButton.textContent = '…';
  try { await loader(); }
  catch (error) { notify(error); }
  finally { refreshButton.disabled = false; refreshButton.textContent = '↻'; }
});

// Only load modules the signed-in role is allowed to access.
(async function initialLoad() {
  const tasks = [loadDoctors(), loadAppointments(), loadMedicines(), loadMedicineOrders(), loadPriceList(), loadChatContext(), loadBills()]; if(['admin','reception'].includes(window.clinic_ROLE)) tasks.push(loadEmergencies());
  
  if (['patient', 'doctor', 'admin'].includes(window.clinic_ROLE)) tasks.push(loadRecords());
  try { await Promise.all(tasks); }
  catch (error) { notify(error); }
})();


let currentTestBill=null;
async function loadBills(){if(!document.getElementById('bills-list'))return;const d=await api('/api/bills');$('#bills-list').innerHTML=(d.bills||[]).map(b=>{const paid=String(b.status).toLowerCase().startsWith('paid');return '<article class="bill-row"><div><b>Bill #'+b.id+' · '+esc(b.description)+'</b><small>'+(b.patient_name?'Patient: '+esc(b.patient_name)+' · ':'')+money(b.amount)+'</small><small>'+esc(b.created_at)+'</small></div><span class="stock-pill '+(paid?'in-stock':'out-stock')+'">'+(paid?'✓ PAYMENT PROCESSED':'! PAYMENT PENDING')+'</span>'+(paid?'<small class="bill-status-detail">'+esc(b.status)+(b.paid_at?' · '+esc(b.paid_at):'')+'</small>':'<button onclick="showPaymentQR('+b.id+','+Number(b.amount)+')">Generate QR to pay</button>')+'</article>'}).join('')||'<p>No bills found.</p>'}
window.showPaymentQR=async(id,amount)=>{currentTestBill=id;$('#qr-payload').textContent='Preparing secure payment link…';$('#qr-code').innerHTML='';$('#payment-qr-modal').hidden=false;try{const d=await api('/api/bills/'+id+'/qr',{method:'POST',body:JSON.stringify({})});const payload=window.location.origin+d.url;$('#qr-payload').textContent=payload;if(window.QRCode)new QRCode($('#qr-code'),{text:payload,width:210,height:210});else $('#qr-code').textContent='QR generator unavailable';}catch(e){$('#qr-payload').textContent=e.message;notify(e)}};
$('#close-qr')?.addEventListener('click',()=>{$('#payment-qr-modal').hidden=true;loadBills().catch(()=>{})});
$('#confirm-test-payment')?.addEventListener('click',async()=>{if(!currentTestBill)return;try{const d=await api('/api/bills/'+currentTestBill+'/test-payment',{method:'POST',body:JSON.stringify({})});alert(d.message);$('#payment-qr-modal').hidden=true;loadBills()}catch(e){notify(e)}});
$('#bill-form')?.addEventListener('submit',async e=>{e.preventDefault();try{await api('/api/bills',{method:'POST',body:JSON.stringify({patient_id:$('#bill-patient').value,description:$('#bill-description').value,amount:$('#bill-amount').value})});e.target.reset();loadBills()}catch(x){notify(x)}});
async function loadEmergencies(){if(!$('#emergency-list'))return;const d=await api('/api/emergencies');$('#emergency-list').innerHTML=d.cases.map(x=>'<article><div><b>Case #'+x.id+' · '+esc(x.patient_name)+'</b><small>'+esc(x.urgency)+' · '+esc(x.phone)+' · '+esc(x.created_at)+'</small><small>'+esc(x.description)+'</small></div><span class="stock-pill out-stock">'+esc(x.status)+'</span></article>').join('')||'<p>No cases recorded.</p>'}
$('#emergency-form')?.addEventListener('submit',async e=>{e.preventDefault();try{await api('/api/emergencies',{method:'POST',body:JSON.stringify({patient_name:$('#em-name').value,phone:$('#em-phone').value,urgency:$('#em-urgency').value,description:$('#em-description').value})});e.target.reset();loadEmergencies()}catch(x){notify(x)}});


$('#stock-purchase-form')?.addEventListener('submit',async e=>{e.preventDefault();try{await api('/api/medicines/'+$('#purchase-med').value+'/purchase',{method:'POST',body:JSON.stringify({quantity:$('#purchase-qty').value,supplier:$('#purchase-supplier').value,cost:$('#purchase-cost').value})});e.target.reset();alert('Purchase saved; stock increased.');loadMedicines()}catch(x){notify(x)}});
