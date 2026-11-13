const $=s=>document.querySelector(s);const api=async(url,opts={})=>{const r=await fetch(url,{credentials:'same-origin',cache:'no-store',...opts,headers:opts.body instanceof FormData?opts.headers:{'Content-Type':'application/json',...(opts.headers||{})}});if(r.status===401){location.assign('/login?next='+encodeURIComponent(location.pathname));throw Error('Your login session expired. Please sign in again.')}const d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.error||'Request failed');return d};const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const money=n=>'₹'+Number(n||0).toFixed(2);function notify(e){alert(e.message||e)}
$('#nav').addEventListener('click',e=>{const b=e.target.closest('button[data-tab]');if(!b)return;document.querySelectorAll('#nav button').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.panel').forEach(x=>x.classList.toggle('active',x.id===b.dataset.tab));const h=document.getElementById('current-section');if(h)h.textContent=b.textContent.trim();loadTab(b.dataset.tab)});
async function loadDoctors(){
 const d=await api('/api/doctors');
 $('#doctors-list').innerHTML=d.doctors.map(x=>'<article class="doctor-profile"><div class="doctor-profile-head"><div class="doctor-avatar">'+esc((x.name||'D').replace(/^Dr\\.?\\s*/,'').slice(0,1).toUpperCase())+'</div><div><h3>'+esc(x.name)+'</h3><b>'+esc(x.department)+'</b></div><span class="experience-badge">'+Number(x.experience_years||0)+' yrs experience</span></div><p class="doctor-summary">'+esc(x.profile_summary||'Specialist consultation and patient care.')+'</p><div class="doctor-credentials"><div><small>QUALIFICATION</small><strong>'+esc(x.qualification)+'</strong></div><div><small>CERTIFICATION</small><strong>'+esc(x.certifications||x.qualification)+'</strong></div><div><small>CONSULTATION HOURS</small><strong>'+esc(x.days)+' · '+esc(x.start_time)+'–'+esc(x.end_time)+'</strong></div><div><small>CONSULTATION FEE</small><strong>'+money(x.consultation_fee)+'</strong></div></div></article>').join('')||'<p>No doctors listed.</p>';
 if($('#doctor_id'))$('#doctor_id').innerHTML=d.doctors.map(x=>'<option value="'+x.id+'">'+esc(x.name)+' — '+esc(x.department)+'</option>').join('');
}
async function loadAppointments(){const d=await api('/api/appointments');window.appointmentCache=d.appointments;const filter=$('#appointment-filter')?.value||'all';const rows=filter==='all'?d.appointments:d.appointments.filter(x=>x.status===filter);$('#appointments-list').innerHTML=rows.map(x=>`<article><div><b>${esc(x.doctor_name)}</b><small>${esc(x.department)} · ${esc(x.appointment_date)} at ${esc(x.appointment_time)}${x.patient_name?' · Patient: '+esc(x.patient_name):''}</small><small>${esc(x.reason||'No reason supplied')} · ${esc(x.status)}</small></div>${x.status==='Booked'?`<button class="danger" onclick="cancelAppointment(${x.id})">Cancel</button>`:''}</article>`).join('')||'<p>No appointments yet.</p>'}
window.cancelAppointment=async id=>{if(!confirm('Cancel this appointment?'))return;try{await api('/api/appointments/'+id,{method:'PATCH'});await loadAppointments()}catch(e){notify(e)}};
$('#book-form').addEventListener('submit',async e=>{e.preventDefault();try{await api('/api/appointments',{method:'POST',body:JSON.stringify({doctor_id:$('#doctor_id').value,appointment_date:$('#appointment_date').value,appointment_time:$('#appointment_time').value,reason:$('#reason').value})});e.target.reset();await loadAppointments();alert('Appointment booked.')}catch(x){notify(x)}});
async function loadMedicines(){const d=await api('/api/medicines?q='+encodeURIComponent($('#medicine-search').value));const icon=x=>({tablet:'💊',capsule:'💊',drinkable:'🥤',sachet:'🧃',other:'🧴'}[String(x.dosage_form||'Other').toLowerCase()]||'🧴');$('#medicines-list').innerHTML=d.medicines.length?`<table class="inventory-table"><thead><tr><th>Item</th><th>Form</th><th>Strength</th><th>Available stock</th><th>Listed price</th></tr></thead><tbody>${d.medicines.map(x=>`<tr><td><span class="medicine-icon">${icon(x)}</span><b>${esc(x.name)}</b></td><td>${esc(x.dosage_form||'Other')}</td><td>${esc(x.strength)}</td><td><span class="stock-pill ${Number(x.stock)>0?'in-stock':'out-stock'}">${Number(x.stock)>0?Number(x.stock)+' available':'Out of stock'}</span></td><td>${money(x.price)}</td></tr>`).join('')}</tbody></table>`:'<p>No matching medicines.</p>'}$('#medicine-search').addEventListener('input',()=>loadMedicines());if($('#medicine-form'))$('#medicine-form').addEventListener('submit',async e=>{e.preventDefault();try{await api('/api/medicines',{method:'POST',body:JSON.stringify({name:$('#med_name').value,strength:$('#med_strength').value,price:$('#med_price').value,stock:$('#med_stock').value,dosage_form:$('#med_form').value})});e.target.reset();loadMedicines()}catch(x){notify(x)}});
async function loadRecords(){const d=await api('/api/records');$('#records-list').innerHTML=d.records.map(x=>`<article><div><b>${esc(x.record_type)}</b><small>${x.patient_name?'Patient: '+esc(x.patient_name)+' · ':''}${esc(x.created_at)}</small><small>${esc(x.notes)}</small>${x.file_name?`<a href="/uploads/${encodeURIComponent(x.file_name)}">Download attachment</a>`:''}</div></article>`).join('')||'<p>No records available.</p>'}
if($('#record-form'))$('#record-form').addEventListener('submit',async e=>{e.preventDefault();try{const r=await fetch('/api/records',{method:'POST',credentials:'same-origin',body:new FormData(e.target)});const d=await r.json();if(!r.ok)throw Error(d.error);e.target.reset();loadRecords()}catch(x){notify(x)}});
if($('#chat-form'))$('#chat-form').addEventListener('submit',async e=>{e.preventDefault();const q=$('#chat-question').value.trim();if(!q)return;const log=$('#chat-log');log.insertAdjacentHTML('beforeend',`<div class="mine">${esc(q)}</div>`);$('#chat-question').value='';try{const d=await api('/ask',{method:'POST',body:JSON.stringify({question:q})});log.insertAdjacentHTML('beforeend',`<div class="bot">${esc(d.answer)}</div>`);loadChatHistory().catch(()=>{})}catch(x){log.insertAdjacentHTML('beforeend',`<div class="bot">${esc(x.message)}</div>`)}log.scrollTop=log.scrollHeight});
async function loadChatContext(){
  const log=$('#chat-log');if(!log)return;
  const d=await api('/api/chat-context');
  log.innerHTML=(d.messages||[]).map(x=>`<div class="mine">${esc(x.question)}</div><div class="bot">${esc(x.answer)}</div>`).join('')||'<div class="bot">Welcome to Clinic FAQ Project. Ask about clinic services, doctors, appointments, or available medicines.</div>';
  log.scrollTop=log.scrollHeight;
}
async function loadChatHistory(){const box=$('#history-list');if(!box)return;const d=await api('/api/chat-history');box.innerHTML=(d.history||[]).map(x=>{const category=String(x.classification||'UNAVAILABLE').toUpperCase();const cls=category.toLowerCase();return `<article class="history-entry"><div class="history-topline"><small>${esc(x.created_at)} · ${esc(x.topic)}</small><span class="classification-badge ${cls}">${esc(category)}</span></div><div class="history-label">USER QUESTION</div><b class="history-text">${esc(x.question)}</b><div class="history-label">ASSISTANT RESPONSE</div><p class="history-text">${esc(x.answer)}</p></div></article>`}).join('')||'<p>No saved conversations yet. Start a conversation in Patient help desk.</p>'}
async function loadPriceList(){const box=$('#assistant-price-list');if(!box)return;const d=await api('/api/price-list');const serviceCards=(d.services||[]).map(x=>`<article class="price-card"><span>${esc(x.department)}</span><b>${esc(x.name)}</b><strong>${money(x.price)}</strong><small>${esc(x.description)}</small></article>`).join('');const doctorCards=(d.doctors||[]).map(x=>`<article class="price-card doctor-price"><span>${esc(x.department)}</span><b>${esc(x.name)}</b><strong>${money(x.price)}</strong><small>Consultation fee</small></article>`).join('');const medicineCards=(d.medicines||[]).map(x=>`<article class="price-card medicine-price"><span>Pharmacy</span><b>${esc(x.name)} ${esc(x.strength)}</b><strong>${money(x.price)}</strong><small>${Number(x.stock)>0?'Listed stock: '+Number(x.stock):'Out of stock'}</small></article>`).join('');box.innerHTML=serviceCards+doctorCards+medicineCards||'<p>No prices have been configured.</p>'}
$('#refresh-history')?.addEventListener('click',()=>loadChatHistory().catch(notify));
$('#reload-prices')?.addEventListener('click',()=>loadPriceList().catch(notify));
async function loadAnalytics(){const d=await api('/api/analytics');$('#analytics-summary').innerHTML=[['Total chatbot queries',d.total_queries],['Appointments',d.appointments],['Registered patients',d.patients]].map(x=>`<article><span>${x[0]}</span><strong>${x[1]}</strong></article>`).join('');$('#topic-list').innerHTML=d.topics.map(x=>`<article><b>${esc(x.label)}</b><strong>${x.count}</strong></article>`).join('')||'<p>No query data yet.</p>';$('#category-list').innerHTML=d.categories.map(x=>`<article><b>${esc(x.label)}</b><strong>${x.count}</strong></article>`).join('')||'<p>No classifications yet.</p>'}
function loadTab(id){const map={doctors:loadDoctors,appointments:loadAppointments,records:loadRecords,medicines:loadMedicines,analytics:loadAnalytics,history:loadChatHistory,assistant:loadPriceList,payments:loadBills,emergency:loadEmergencies};if(map[id])map[id]().catch(notify)}

// Executive dashboard enhancements: live KPIs, workspace search and theme controls.
async function loadDashboardMetrics(){
  try{const [a,d]=await Promise.all([api('/api/appointments'),api('/api/doctors')]);
    const ka=$('#kpi-appointments'),kd=$('#kpi-doctors');if(ka)ka.textContent=a.appointments.length;if(kd)kd.textContent=d.doctors.length;
    }catch(e){console.warn('Dashboard metrics:',e.message)}
  if(['admin','reception'].includes(window.HOSPITAL_ROLE)){try{const x=await api('/api/analytics');$('#kpi-queries').textContent=x.total_queries}catch(e){$('#kpi-queries').textContent='—'}}else{$('#kpi-queries').textContent='Private'}
}
$('#appointment-filter')?.addEventListener('change',()=>{const rows=window.appointmentCache||[];const v=$('#appointment-filter').value;const filtered=v==='all'?rows:rows.filter(x=>x.status===v);$('#appointments-list').innerHTML=filtered.map(x=>`<article><div><b>${esc(x.doctor_name)}</b><small>${esc(x.department)} · ${esc(x.appointment_date)} at ${esc(x.appointment_time)}${x.patient_name?' · Patient: '+esc(x.patient_name):''}</small><small>${esc(x.reason||'No reason supplied')} · ${esc(x.status)}</small></div>${x.status==='Booked'?`<button class="danger" onclick="cancelAppointment(${x.id})">Cancel</button>`:''}</article>`).join('')||'<p>No appointments match this filter.</p>'});
$('#global-search')?.addEventListener('input',e=>{const q=e.target.value.trim().toLowerCase();document.querySelectorAll('.panel').forEach(panel=>{panel.querySelectorAll('.list article,.cards article,.overview-card').forEach(item=>{item.hidden=!!q&&!item.textContent.toLowerCase().includes(q)})})});
$('#theme-toggle')?.addEventListener('click',()=>{document.body.classList.toggle('dark-mode');try{localStorage.setItem('greenfield-theme',document.body.classList.contains('dark-mode')?'dark':'light')}catch(_){}});
try{if(localStorage.getItem('greenfield-theme')==='dark')document.body.classList.add('dark-mode')}catch(_){}

function updateClock(){const el=$('#live-clock');if(el)el.textContent=new Intl.DateTimeFormat(undefined,{weekday:'short',month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date())}
updateClock();setInterval(updateClock,30000);
const dateInput=$('#appointment_date');if(dateInput)dateInput.min=new Date().toISOString().slice(0,10);
loadDashboardMetrics();


// Profile dropdown: logout is shown only after the profile control is clicked.
const profileToggle=$('#profile-toggle'), profileMenu=$('#profile-menu');
profileToggle?.addEventListener('click',()=>{const open=profileMenu.hidden;profileMenu.hidden=!open;profileToggle.setAttribute('aria-expanded',String(open));});
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
  const tasks = [loadDoctors(), loadAppointments(), loadMedicines(), loadPriceList(), loadChatContext(), loadBills()]; if(['admin','reception'].includes(window.clinic_ROLE)) tasks.push(loadEmergencies());
  
  if (['patient', 'doctor', 'admin'].includes(window.HOSPITAL_ROLE)) tasks.push(loadRecords());
  try { await Promise.all(tasks); }
  catch (error) { notify(error); }
})();


let currentDemoBill=null;
async function loadBills(){if(!document.getElementById('bills-list'))return;const d=await api('/api/bills');$('#bills-list').innerHTML=(d.bills||[]).map(b=>'<article><div><b>Bill #'+b.id+' · '+esc(b.description)+'</b><small>'+(b.patient_name?'Patient: '+esc(b.patient_name)+' · ':'')+money(b.amount)+' · '+esc(b.status)+'</small><small>'+esc(b.created_at)+'</small></div>'+(b.status==='Unpaid'?'<button onclick="showDemoQR('+b.id+','+Number(b.amount)+')">Show demo QR</button>':'')+'</article>').join('')||'<p>No bills found.</p>'}
window.showDemoQR=(id,amount)=>{currentDemoBill=id;const payload='CLINIC-FAQ-TEST|BILL:'+id+'|AMOUNT:'+amount.toFixed(2)+'';$('#qr-payload').textContent=payload;$('#qr-code').innerHTML='';if(window.QRCode)new QRCode($('#qr-code'),{text:payload,width:190,height:190});else $('#qr-code').textContent='QR generator unavailable';$('#payment-qr-modal').hidden=false};
$('#close-qr')?.addEventListener('click',()=>$('#payment-qr-modal').hidden=true);
$('#confirm-demo-payment')?.addEventListener('click',async()=>{if(!currentDemoBill)return;try{const d=await api('/api/bills/'+currentDemoBill+'/test-payment',{method:'POST',body:JSON.stringify({})});alert(d.message);$('#payment-qr-modal').hidden=true;loadBills()}catch(e){notify(e)}});
$('#bill-form')?.addEventListener('submit',async e=>{e.preventDefault();try{await api('/api/bills',{method:'POST',body:JSON.stringify({patient_id:$('#bill-patient').value,description:$('#bill-description').value,amount:$('#bill-amount').value})});e.target.reset();loadBills()}catch(x){notify(x)}});
async function loadEmergencies(){if(!$('#emergency-list'))return;const d=await api('/api/emergencies');$('#emergency-list').innerHTML=d.cases.map(x=>'<article><div><b>Case #'+x.id+' · '+esc(x.patient_name)+'</b><small>'+esc(x.urgency)+' · '+esc(x.phone)+' · '+esc(x.created_at)+'</small><small>'+esc(x.description)+'</small></div><span class="stock-pill out-stock">'+esc(x.status)+'</span></article>').join('')||'<p>No cases recorded.</p>'}
$('#emergency-form')?.addEventListener('submit',async e=>{e.preventDefault();try{await api('/api/emergencies',{method:'POST',body:JSON.stringify({patient_name:$('#em-name').value,phone:$('#em-phone').value,urgency:$('#em-urgency').value,description:$('#em-description').value})});e.target.reset();loadEmergencies()}catch(x){notify(x)}});


$('#stock-purchase-form')?.addEventListener('submit',async e=>{e.preventDefault();try{await api('/api/medicines/'+$('#purchase-med').value+'/purchase',{method:'POST',body:JSON.stringify({quantity:$('#purchase-qty').value,supplier:$('#purchase-supplier').value,cost:$('#purchase-cost').value})});e.target.reset();alert('Purchase saved; stock increased.');loadMedicines()}catch(x){notify(x)}});
