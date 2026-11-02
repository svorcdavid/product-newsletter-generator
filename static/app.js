const form = document.querySelector('#job-form');
const status = document.querySelector('#status');
const statusText = document.querySelector('#status-text');
const result = document.querySelector('#result');
const errorBox = document.querySelector('#error');

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  status.hidden = false;
  result.hidden = true;
  errorBox.hidden = true;
  statusText.textContent = 'Queueing the scraper…';

  try {
    const apiKey = document.querySelector('#api-key')?.value || '';
    const response = await fetch('/api/jobs', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-API-Key': apiKey},
      body: JSON.stringify({
        raw_data: document.querySelector('#raw-data').value,
        header_image_url: document.querySelector('#header-image-url').value || null,
        email_to: document.querySelector('#email-to').value || null
      })
    });
    if (!response.ok) throw new Error((await response.json()).detail || 'Could not create job');
    await poll((await response.json()).id, apiKey);
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.hidden = false;
    status.hidden = true;
  }
});

async function poll(jobId, apiKey) {
  const response = await fetch(`/api/jobs/${jobId}`, {headers: {'X-API-Key': apiKey}});
  const job = await response.json();
  const previewLink = document.querySelector('#preview');
  const downloadLink = document.querySelector('#download');

  previewLink.classList.remove('is-disabled');
  downloadLink.classList.remove('is-disabled');
  previewLink.removeAttribute('aria-disabled');
  downloadLink.removeAttribute('aria-disabled');
  previewLink.setAttribute('href', '#');
  downloadLink.setAttribute('href', '#');

  if (job.status === 'queued' || job.status === 'running') {
    statusText.textContent = job.status === 'queued'
      ? 'Čekání na aplikaci…'
      : job.phase === 'finalizing'
        ? 'Dokončování newsletteru…'
        : job.phase === 'emailing'
          ? 'Odesílání e-mailu…'
          : `Zpracování produktu ${job.current || 0} z ${job.total || '?'} (${job.product_code || 'začíná'})…`;
    previewLink.classList.add('is-disabled');
    downloadLink.classList.add('is-disabled');
    previewLink.setAttribute('aria-disabled', 'true');
    downloadLink.setAttribute('aria-disabled', 'true');
    previewLink.removeAttribute('href');
    downloadLink.removeAttribute('href');
    window.setTimeout(() => poll(jobId, apiKey), 1500);
    return;
  }
  if (job.status === 'failed') throw new Error(job.error || 'Generation failed');
  statusText.textContent = 'Newsletter připraven.';
  previewLink.href = job.preview_url;
  downloadLink.href = job.download_url;
  document.querySelector('#email-status').textContent = job.email_status || '';
  result.hidden = false;
}
