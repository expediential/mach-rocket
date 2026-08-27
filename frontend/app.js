/* Local client for the Mission Validation Platform. It communicates only with the local API. */
const content = document.querySelector('#content');
const pageTitle = document.querySelector('#page-title');
const crumb = document.querySelector('#crumb');
let currentPage = 'Dashboard';

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || 'The local service could not complete this request.');
  return response.json();
}
function esc(value) { return String(value).replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[char]); }
function badge(status) { const tone = /FAIL|SIGNIFICANT|HIGH/.test(status) ? 'fail' : /WARNING|WITHIN|MEDIUM/.test(status) ? 'warning' : 'pass'; return `<span class="badge ${tone}">${esc(status)}</span>`; }
function setActive(page) { document.querySelectorAll('.nav').forEach(button => button.classList.toggle('active', button.dataset.page === page)); pageTitle.textContent = page === 'Dashboard' ? 'Mission overview' : page; crumb.textContent = page.toUpperCase(); }

async function dashboardPage() {
  const data = await api('/api/dashboard');
  content.innerHTML = document.querySelector('#dashboard-template').innerHTML;
  document.querySelector('#health-grid').innerHTML = data.health.items.map(item => `<div class="health"><div><strong>${esc(item.name)}</strong>${badge(item.status)}</div><small>${item.status === 'WARNING' ? 'Review evidence' : 'Ready for review'}</small></div>`).join('');
  content.querySelector('[data-go="Test"]').addEventListener('click', () => navigate('Test'));
}

async function vehiclePage() {
  const vehicle = await api('/api/vehicle');
  content.innerHTML = `<div class="workspace"><article class="panel"><span class="eyebrow">2D TECHNICAL REPRESENTATION</span><h2>${esc(vehicle.name)}</h2><p class="muted">A procedural vehicle view based on available dimensions. It is not a CAD substitute.</p><div class="technical-vehicle"><div class="rocket" title="Simplified Falcon-X vehicle"></div></div></article><aside class="panel"><span class="eyebrow">IMPORTED VEHICLE</span><h3>OpenRocket artifact</h3><ul class="detail-list"><li>Source <span>${esc(vehicle.source)}</span></li><li>Mass <span>${vehicle.mass_kg} kg</span></li><li>Length <span>${vehicle.length_m} m</span></li><li>Stages <span>${vehicle.stages}</span></li><li>Motor <span>${esc(vehicle.motor)}</span></li></ul><p class="muted">${esc(vehicle.view)}</p></aside></div>`;
}

async function missionPage() {
  const data = await api('/api/dashboard');
  content.innerHTML = `<div class="workspace"><article class="panel"><span class="eyebrow">CENTRAL SOURCE OF TRUTH</span><h2>Mission configuration</h2><p>Values below are the readable mission configuration used by simulation and testing.</p><pre class="config">mission:
  target_altitude_m: ${data.mission.target_altitude_m}
  allowed_altitude_error_m: ${data.mission.allowed_error_m}
telemetry:
  rate_hz: ${data.mission.telemetry_rate_hz}
sensors:
  pressure: true
  temperature: true
  gps: true
  battery: true
flight:
  expected_duration_s: ${data.mission.expected_duration_s}</pre></article><aside class="panel"><span class="eyebrow">VERSION</span><h3>v1.7</h3><p>Configuration is tracked separately from source artifacts for reproducible runs.</p><button class="secondary" data-go="Settings">View history</button></aside></div>`;
  content.querySelector('[data-go]').addEventListener('click', () => navigate('Settings'));
}

function simulatePage() {
  content.innerHTML = `<div class="workspace"><article class="panel"><span class="eyebrow">SOFTWARE-ONLY FLIGHT SIMULATOR</span><h2>Run a scenario</h2><p>Creates synthetic telemetry for mission-software verification. It is not a high-fidelity flight-dynamics model.</p><form id="simulation-form"><div class="form-row"><div class="field"><label for="scenario-name">SCENARIO NAME</label><input id="scenario-name" value="Normal mission" maxlength="80" /></div><div class="field"><label for="fault">FAULT INJECTION</label><select id="fault"><option value="none">None — Normal mission</option><option value="gps_loss">GPS unavailable</option><option value="radio_loss">5-second radio interruption</option><option value="malformed_packet">Malformed telemetry</option><option value="packet_delay">Delayed packets</option><option value="battery_anomaly">Battery anomaly</option></select></div></div><div class="form-row"><div class="field"><label for="start">START TIME (SECONDS)</label><input id="start" type="number" value="40" min="0" max="90" /></div><div class="field"><label for="duration">DURATION (SECONDS)</label><input id="duration" type="number" value="5" min="1" max="60" /></div></div><button class="primary">Run simulation</button></form><div id="simulation-result"></div></article><aside class="panel"><span class="eyebrow">REPRODUCIBILITY</span><h3>Every run records</h3><ul class="detail-list"><li>Scenario <span>Saved</span></li><li>Random seed <span>2026</span></li><li>Configuration <span>v1.7</span></li><li>Software <span>demo-a81f29</span></li><li>Input source <span>Demo</span></li></ul></aside></div>`;
  content.querySelector('#simulation-form').addEventListener('submit', async event => { event.preventDefault(); const resultBox = content.querySelector('#simulation-result'); resultBox.innerHTML = '<p class="muted">Generating deterministic telemetry…</p>'; try { const result = await api('/api/simulate', { method: 'POST', body: JSON.stringify({ name: content.querySelector('#scenario-name').value, fault: content.querySelector('#fault').value, start_s: Number(content.querySelector('#start').value), duration_s: Number(content.querySelector('#duration').value), seed: 2026 }) }); const isFail = result.verdict === 'FAIL'; resultBox.innerHTML = `<div class="run-result ${isFail ? 'fail-result' : ''}">${badge(result.verdict)} <strong>${esc(result.id)}</strong><p>Generated ${result.telemetry.length} validated synthetic packets. ${result.validation.rejected_packets} packet(s) rejected; ${result.validation.gps_unavailable_samples} GPS-unavailable sample(s).</p><small>Seed 2026 · v1.7 · ${esc(result.software_version)}</small></div>`; } catch (error) { resultBox.innerHTML = `<div class="run-result fail-result">${esc(error.message)}</div>`; } });
}

async function testPage() {
  content.innerHTML = '<div class="empty">Loading MissionTest evidence…</div>';
  const tests = await api('/api/tests/run', { method: 'POST', body: '{}' });
  content.innerHTML = `<div class="grid split"><article class="panel"><span class="eyebrow">MISSIONTEST</span><h2>Reusable scenario evidence</h2><div class="health-grid test-summary"><div class="health"><strong>${tests.total}</strong><small>Tests</small></div><div class="health"><strong class="pass-text">${tests.passed}</strong><small>Passed</small></div><div class="health"><strong class="warning-text">${tests.warnings}</strong><small>Warnings</small></div><div class="health"><strong style="color:var(--red)">${tests.failed}</strong><small>Failed</small></div></div><table class="table"><thead><tr><th>ID</th><th>TEST</th><th>RESULT</th><th>EVIDENCE</th></tr></thead><tbody>${tests.cases.map(test => `<tr><td>${test.id}</td><td><strong>${esc(test.name)}</strong></td><td>${badge(test.result)}</td><td>${esc(test.detail)}</td></tr>`).join('')}</tbody></table></article><aside class="panel"><span class="eyebrow">FAILED SCENARIO</span><h3>Radio-loss recovery</h3><p>${esc(tests.headline)}</p><hr/><span class="eyebrow">TEST CASE BUILDER</span><p class="muted">Choose a failure in Simulate, set when and how long it occurs, then run the scenario.</p><button class="primary" data-go="Simulate">Build a test</button></aside></div>`;
  content.querySelector('[data-go]').addEventListener('click', () => navigate('Simulate'));
}

async function flightsPage() {
  const data = await api('/api/flights');
  content.innerHTML = `<article class="panel"><span class="eyebrow">FLIGHT REPLAY</span><h2>Recorded and synthetic flights</h2><p>Replay controls are local dashboard controls; imported data remains distinct from simulated telemetry.</p><table class="table"><thead><tr><th>FLIGHT</th><th>TYPE</th><th>MAX ALTITUDE</th><th>DURATION</th><th>PACKETS</th><th>REPLAY</th></tr></thead><tbody>${data.flights.map(flight => `<tr><td><strong>${flight.name}</strong></td><td>${badge(flight.type)}</td><td>${flight.max_altitude_m} m</td><td>${flight.duration_s} s</td><td>${flight.packets}</td><td><button class="secondary replay" data-flight="${flight.id}">Play</button></td></tr>`).join('')}</tbody></table><div id="replay-result"></div></article>`;
  content.querySelectorAll('.replay').forEach(button => button.addEventListener('click', () => { content.querySelector('#replay-result').innerHTML = `<div class="run-result">Replay ready for <strong>${esc(button.dataset.flight)}</strong>. Use the time-series dashboard adapter to play, pause, change speed, or jump to a timestamp.</div>`; }));
}

async function comparePage() {
  const data = await api('/api/compare');
  content.innerHTML = `<div class="workspace"><article class="panel"><span class="eyebrow">CONTINUOUS MISSION VALIDATION</span><h2>Simulation #12 vs Flight #03</h2><p>Differences are classified using tolerance bands. They are evidence for investigation, not claims of root cause.</p><table class="table"><thead><tr><th>METRIC</th><th>SIMULATION</th><th>ACTUAL</th><th>DIFFERENCE</th><th>STATUS</th></tr></thead><tbody>${data.metrics.map(metric => `<tr><td><strong>${esc(metric.metric)}</strong></td><td>${metric.simulation} ${metric.unit}</td><td>${metric.actual} ${metric.unit}</td><td>${metric.difference > 0 ? '+' : ''}${metric.difference} ${metric.unit}</td><td>${badge(metric.classification)}</td></tr>`).join('')}</tbody></table></article><aside class="panel"><span class="eyebrow">POTENTIAL CAUSES TO INVESTIGATE</span><h3>Altitude difference</h3><ol>${data.investigation_areas.map(item => `<li>${esc(item)}</li>`).join('')}</ol><p class="muted">${esc(data.note)}</p></aside></div>`;
}

async function reportsPage() {
  content.innerHTML = `<article class="panel"><span class="eyebrow">REPORT GENERATION</span><h2>Mission validation report</h2><p>Produces a self-contained HTML report with summary, test evidence, comparison metrics, configuration version, and scope limits.</p><button class="primary" id="make-report">Generate HTML report</button><div id="report-result"></div></article>`;
  content.querySelector('#make-report').addEventListener('click', async () => { const result = await api('/api/reports', { method: 'POST', body: '{}' }); content.querySelector('#report-result').innerHTML = `<div class="report-success">Report ready. <a href="${result.url}" target="_blank">Open or download report</a> · Formats: ${result.formats.join(', ')}</div>`; });
}

async function filesPage() {
  const artifacts = await api('/api/artifacts');
  content.innerHTML = `<div class="workspace"><article class="panel"><span class="eyebrow">ENGINEERING ARTIFACTS</span><h2>Traceable project files</h2><table class="table"><thead><tr><th>FILE</th><th>TYPE</th><th>STATUS</th><th>PREVIEW</th></tr></thead><tbody>${artifacts.map(file => `<tr><td><strong>${esc(file.name)}</strong></td><td>${esc(file.type)}</td><td>${badge(file.status)}</td><td>${esc(file.preview)}</td></tr>`).join('')}</tbody></table></article><aside class="panel"><span class="eyebrow">IMPORT TELEMETRY</span><h3>CSV confirmation</h3><div class="file-upload"><input id="csv-file" type="file" accept=".csv,text/csv"/><br/><small>Headers are mapped only when unambiguous. Unsupported artifacts can be retained for traceability.</small></div><div id="import-result"></div></aside></div>`;
  content.querySelector('#csv-file').addEventListener('change', async event => { const file = event.target.files[0]; if (!file) return; const target = content.querySelector('#import-result'); target.innerHTML = '<p class="muted">Checking columns…</p>'; const result = await api('/api/telemetry/import', { method: 'POST', body: JSON.stringify({ name: file.name, csv: await file.text() }) }); target.innerHTML = `<div class="run-result">${result.packets} valid packets imported. ${result.errors.length ? `${result.errors.length} invalid row(s): ${result.errors.map(e => e.row).join(', ')}` : 'No invalid rows.'}<br/><small>${esc(result.message)}</small></div>`; });
}

async function securityPage() {
  const findings = await api('/api/security/findings');
  content.innerHTML = `<div class="workspace"><article class="panel"><span class="eyebrow">PRACTICAL SECURITY CHECKS</span><h2>Security evidence</h2><p>Files are scanned as text only. Uploaded content is never executed, and this prototype does not claim production or military-grade security.</p>${findings.map(finding => `<div class="security-card ${finding.severity.toLowerCase()}">${badge(finding.status)} <strong>${esc(finding.title)}</strong><p>${esc(finding.detail)}</p></div>`).join('')}</article><aside class="panel"><span class="eyebrow">SECRET DETECTION</span><h3>Scan text safely</h3><div class="field"><label for="scan-name">FILE NAME</label><input id="scan-name" value="notes.txt" /></div><div class="field"><label for="scan-content">TEXT TO SCAN</label><textarea id="scan-content" placeholder="Paste text; it will not be stored as an artifact."></textarea></div><button class="primary" id="scan-button">Scan</button><div id="scan-result"></div></aside></div>`;
  content.querySelector('#scan-button').addEventListener('click', async () => { const findings = await api('/api/security/scan', { method: 'POST', body: JSON.stringify({ name: content.querySelector('#scan-name').value, content: content.querySelector('#scan-content').value }) }); content.querySelector('#scan-result').innerHTML = findings.length ? `<div class="run-result fail-result">${findings.length} potential secret(s) found. Review before committing.</div>` : '<div class="report-success">No likely secrets detected in the supplied text.</div>'; });
}

async function settingsPage() {
  const [history, audit, runs] = await Promise.all([api('/api/config/history'), api('/api/audit'), api('/api/runs')]);
  content.innerHTML = `<div class="grid two"><article class="panel"><span class="eyebrow">CONFIGURATION HISTORY</span><h2>Traceability</h2><table class="table"><thead><tr><th>VERSION</th><th>CHANGE</th><th>EFFECT</th></tr></thead><tbody>${history.revisions.map(r => `<tr><td><strong>${r.version}</strong></td><td>${esc(r.change)}</td><td>${esc(r.effect)}</td></tr>`).join('')}</tbody></table></article><article class="panel"><span class="eyebrow">RECENT RUNS</span><h2>Reproducible records</h2>${runs.length ? `<table class="table"><thead><tr><th>RUN</th><th>SCENARIO</th><th>VERDICT</th></tr></thead><tbody>${runs.map(run => `<tr><td>${esc(run.id)}</td><td>${esc(run.scenario)}</td><td>${badge(run.verdict)}</td></tr>`).join('')}</tbody></table>` : '<p class="muted">No local simulation runs yet. Run one from Simulate.</p>'}</article></div><article class="panel"><span class="eyebrow">AUDIT LOG</span><h3>Who did what and when</h3><table class="table"><thead><tr><th>TIME</th><th>ACTOR</th><th>ACTION</th><th>RESULT</th><th>DETAIL</th></tr></thead><tbody>${audit.map(event => `<tr><td>${new Date(event.occurred_at).toLocaleString()}</td><td>${esc(event.actor)}</td><td>${esc(event.action)}</td><td>${badge(event.result)}</td><td>${esc(event.detail)}</td></tr>`).join('')}</tbody></table></article>`;
}

async function navigate(page) { currentPage = page; setActive(page); content.innerHTML = '<div class="empty">Loading local workspace…</div>'; try { const pages = { Dashboard: dashboardPage, Vehicle: vehiclePage, Mission: missionPage, Simulate: simulatePage, Test: testPage, Flights: flightsPage, Compare: comparePage, Reports: reportsPage, Files: filesPage, Security: securityPage, Settings: settingsPage }; await pages[page](); } catch (error) { content.innerHTML = `<article class="panel"><h2>Could not load this view</h2><p>${esc(error.message)}</p><p class="muted">Confirm the local API is running and refresh the page. No project source data was modified.</p></article>`; } }

document.querySelectorAll('.nav').forEach(button => button.addEventListener('click', () => navigate(button.dataset.page)));
document.querySelector('#quick-sim').addEventListener('click', () => navigate('Simulate'));
document.querySelector('#report-button').addEventListener('click', () => navigate('Reports'));
navigate(currentPage);
