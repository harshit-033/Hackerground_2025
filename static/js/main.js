// main.js - updated rendering for structured responses and PDF generation
async function postJSON(url, data){
  const res = await fetch(url, {
    method:'POST',
    headers:{ 'Content-Type':'application/json' },
    body: JSON.stringify(data)
  });
  return res.json();
}

function renderResumeStructured(obj){
  const summaryBox = document.getElementById('summaryBox');
  const detailsBox = document.getElementById('detailsBox');
  summaryBox.innerHTML = '';
  detailsBox.innerHTML = '';

  const score = obj.match_score;
  const summary = obj.summary;
  const missing = obj.missing_skills || [];
  const imps = obj.improvements || [];

  // Score bar
  const scoreWrap = document.createElement('div');
  scoreWrap.className = 'score-wrap';
  scoreWrap.innerHTML = `<div class="score-label">Match Score</div><div class="score-bar"><div class="score-fill" style="width:${score}%"></div></div><div class="score-num">${score}%</div>`;
  summaryBox.appendChild(scoreWrap);

  // Summary
  const sumEl = document.createElement('div');
  sumEl.className = 'summary';
  sumEl.innerText = summary;
  summaryBox.appendChild(sumEl);

  // Missing skills
  const missEl = document.createElement('div');
  missEl.className = 'missing';
  missEl.innerHTML = '<h4>Missing Skills</h4>';
  const ul = document.createElement('ul');
  missing.forEach(s => { const li = document.createElement('li'); li.innerText = s; ul.appendChild(li); });
  missEl.appendChild(ul);
  detailsBox.appendChild(missEl);

  // Improvements
  const impEl = document.createElement('div');
  impEl.className = 'improvements';
  impEl.innerHTML = '<h4>Improvements</h4>';
  const ul2 = document.createElement('ul');
  imps.forEach(s => { const li = document.createElement('li'); li.innerText = s; ul2.appendChild(li); });
  impEl.appendChild(ul2);
  detailsBox.appendChild(impEl);
}

function renderPlainText(text){
  const summaryBox = document.getElementById('summaryBox');
  const detailsBox = document.getElementById('detailsBox');
  summaryBox.textContent = 'Analysis result (raw text)';
  detailsBox.textContent = text;
}

document.addEventListener('DOMContentLoaded', function(){
  // Resume analyzer handlers
  const analyzeBtn = document.getElementById('analyzeBtn');
  const downloadPdfBtn = document.getElementById('downloadPdfBtn');
  if(analyzeBtn){
    analyzeBtn.addEventListener('click', async function(){
      const resume = document.getElementById('resume').value;
      const job_desc = document.getElementById('job_desc').value;
      const summaryBox = document.getElementById('summaryBox');
      const detailsBox = document.getElementById('detailsBox');
      summaryBox.textContent = 'Analyzing...';
      detailsBox.textContent = '';
      try{
        const data = await postJSON('/api/analyze_resume', { resume, job_description: job_desc });
        if(data.error){ summaryBox.textContent = 'Error: ' + data.error; return; }
        if(data.structured){
          renderResumeStructured(data.structured);
          // store structured on element for PDF
          summaryBox.dataset.structured = JSON.stringify(data.structured);
        } else if(data.raw){
          renderPlainText(data.raw);
          detailsBox.textContent = data.raw;
        } else {
          summaryBox.textContent = 'No data returned.';
        }
      }catch(err){
        summaryBox.textContent = 'Network error';
      }
    });
  }

  if(downloadPdfBtn){
    downloadPdfBtn.addEventListener('click', async function(){
      const summaryBox = document.getElementById('summaryBox');
      const detailsBox = document.getElementById('detailsBox');
      let payload = {};
      if(summaryBox.dataset.structured){
        payload.structured = JSON.parse(summaryBox.dataset.structured);
        payload.title = 'Resume Analysis Report';
      } else {
        payload.text = detailsBox.textContent || 'No details';
        payload.title = 'Resume Analysis Report';
      }
      const res = await fetch('/api/generate_pdf', {
        method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)
      });
      if(res.ok){
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = (payload.title || 'report') + '.pdf'; document.body.appendChild(a); a.click(); a.remove();
        URL.revokeObjectURL(url);
      } else {
        const err = await res.json();
        alert('PDF Error: ' + (err.error || res.statusText));
      }
    });
  }

  // Job search handlers
  const searchBtn = document.getElementById('searchBtn');
  const downloadJobsPdfBtn = document.getElementById('downloadJobsPdfBtn');
  if(searchBtn){
    searchBtn.addEventListener('click', async function(){
      const qualifications = document.getElementById('qualifications').value;
      const achievements = document.getElementById('achievements').value;
      const jobsBox = document.getElementById('jobsBox');
      jobsBox.textContent = 'Searching...';
      try{
        const data = await postJSON('/api/search_jobs', { qualifications, achievements });
        if(data.error){ jobsBox.textContent = 'Error: ' + data.error; return; }
        if(data.structured){
          // pretty render list of roles
          jobsBox.innerHTML = '';
          data.structured.forEach(item => {
            const card = document.createElement('div');
            card.className = 'job-card';
            const title = document.createElement('div'); title.className='job-title'; title.innerText = item.role || item.title || 'Role';
            const desc = document.createElement('div'); desc.className='job-desc'; desc.innerText = item.description || '';
            const imps = document.createElement('ul'); (item.improvements||[]).forEach(i=>{const li=document.createElement('li'); li.innerText=i; imps.appendChild(li);});
            card.appendChild(title); card.appendChild(desc); card.appendChild(imps);
            jobsBox.appendChild(card);
          });
          // store structured for PDF
          jobsBox.dataset.structured = JSON.stringify(data.structured);
        } else {
          jobsBox.textContent = data.raw || 'No data';
        }
      }catch(err){ jobsBox.textContent = 'Network error'; }
    });
  }

  if(downloadJobsPdfBtn){
    downloadJobsPdfBtn.addEventListener('click', async function(){
      const jobsBox = document.getElementById('jobsBox');
      let payload = {};
      if(jobsBox.dataset.structured){
        payload.structured = JSON.parse(jobsBox.dataset.structured);
        payload.title = 'Job Recommendations';
      } else {
        payload.text = jobsBox.textContent || 'No recommendations';
        payload.title = 'Job Recommendations';
      }
      const res = await fetch('/api/generate_pdf', {
        method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)
      });
      if(res.ok){
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = (payload.title || 'report') + '.pdf'; document.body.appendChild(a); a.click(); a.remove();
        URL.revokeObjectURL(url);
      } else {
        const err = await res.json();
        alert('PDF Error: ' + (err.error || res.statusText));
      }
    });
  }
});
