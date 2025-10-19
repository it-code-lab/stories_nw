// Requires: npm i obs-websocket-js@^5
const OBSWebSocket = require('obs-websocket-js').default;
const obs = new OBSWebSocket();

let isConnected = false;

// ---- Tunables ----
const TIMEOUT_PROFILE_MS = 8000;
const TIMEOUT_EVENT_MS   = 8000;
const POLL_INTERVAL_MS   = 150;
// -------------------

async function connectOBS() {
  if (isConnected) return;

  const url = process.env.OBS_WS_URL || 'ws://localhost:4455';
  const password = process.env.OBS_WS_PASSWORD || undefined; // leave undefined if auth disabled

  if (password) await obs.connect(url, password);
  else          await obs.connect(url);

  isConnected = true;

  // Optional debug
  obs.on('CurrentProfileChanged', (e) => console.log('🔔 CurrentProfileChanged:', e));
  obs.on('RecordStateChanged',   (e) => console.log('🔔 RecordStateChanged:', e));
}

function waitForEvent(eventName, timeoutMs = TIMEOUT_EVENT_MS) {
  return new Promise((resolve, reject) => {
    const handler = (data) => { clearTimeout(t); obs.off(eventName, handler); resolve(data); };
    const t = setTimeout(() => { obs.off(eventName, handler); reject(new Error(`Timed out waiting for ${eventName}`)); }, timeoutMs);
    obs.once(eventName, handler); // <-- subscribe BEFORE the call that triggers it
  });
}

async function waitUntil(condFn, timeoutMs, intervalMs = POLL_INTERVAL_MS) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    // eslint-disable-next-line no-await-in-loop
    if (await condFn()) return true;
    // eslint-disable-next-line no-await-in-loop
    await new Promise(r => setTimeout(r, intervalMs));
  }
  return false;
}

function normalizeProfileNames(list) {
  const raw = list?.profiles ?? [];
  return raw.map(p => (typeof p === 'string' ? p : p?.profileName)).filter(Boolean);
}

async function ensureOutputsStopped() {
  const { outputActive } = await obs.call('GetRecordStatus');
  if (outputActive) await obs.call('StopRecord');
}

async function switchProfile(profileName) {
  await connectOBS();
  await ensureOutputsStopped();

  const list1   = await obs.call('GetProfileList'); // { profiles: [...], currentProfileName: "..." }
  const names   = normalizeProfileNames(list1);
  const current = list1.currentProfileName || list1.currentProfile || null;

  console.log('📄 Profiles:', names.join(', ') || '(none)'); 
  console.log('➡️  Current:', current);

  if (!names.includes(profileName)) {
    throw new Error(`Profile "${profileName}" not found. Available: ${names.join(', ')}`);
  }
  if (current === profileName) {
    console.log(`✅ Already on profile: ${profileName}`);
    return;
  }

  // Arm listener BEFORE switching to avoid races
  const eventWait = waitForEvent('CurrentProfileChanged', TIMEOUT_PROFILE_MS).catch(() => null);

  await obs.call('SetCurrentProfile', { profileName });

  // Event or polling will confirm the change
  const ok = await Promise.race([
    eventWait.then(() => true),
    waitUntil(async () => {
      const l = await obs.call('GetProfileList');
      const cur = l.currentProfileName || l.currentProfile || null;
      return cur === profileName;
    }, TIMEOUT_PROFILE_MS)
  ]);

  if (!ok) {
    const l2  = await obs.call('GetProfileList');
    const now = l2.currentProfileName || l2.currentProfile || null;
    if (now !== profileName) throw new Error('Profile change did not apply within timeout.');
  }

  console.log(`🔁 Switched to profile: ${profileName}`);
}

async function startOBSRecording(profileName) {
  await connectOBS();
  await switchProfile(profileName);

  // Settle briefly; encoders/settings may reload
  await new Promise(r => setTimeout(r, 500));

  // If a recording is already active, restart it cleanly
  const { outputActive } = await obs.call('GetRecordStatus');
  if (outputActive) await obs.call('StopRecord');

  await obs.call('StartRecord');
  console.log(`🎥 Recording started (Profile: ${profileName}).`);
}

async function stopOBSRecording({ disconnect = true } = {}) {
  if (!isConnected) return;
  const { outputActive } = await obs.call('GetRecordStatus');
  if (outputActive) await obs.call('StopRecord');
  if (disconnect) {
    await obs.disconnect();
    isConnected = false;
    console.log('🛑 Recording stopped and disconnected.');
  } else {
    console.log('🛑 Recording stopped.');
  }
}

module.exports = {
  connectOBS,
  switchProfile,
  startOBSRecording,
  stopOBSRecording,
};
