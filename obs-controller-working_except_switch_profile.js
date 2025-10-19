const OBSWebSocket = require('obs-websocket-js').default;
const obs = new OBSWebSocket();

let isConnected = false;

async function connectOBS() {
  if (!isConnected) {
    await obs.connect('ws://localhost:4455', 'your_password'); // Replace with your password
    isConnected = true;
  }
}

async function switchProfile(profileName) {
  await connectOBS();
  await obs.call('SetProfileParameter', {
    parameterCategory: "General",
    parameterName: "ProfileName",
    parameterValue: profileName
  });
  console.log(`🔁 Requested switch to OBS profile: ${profileName}`);
}

async function startOBSRecording(sceneName, profileName) {
  await switchProfile(profileName);

  await new Promise(res => setTimeout(res, 1000)); // allow time for profile switch

  await obs.call('SetCurrentProgramScene', { sceneName });
  await obs.call('StartRecord'); // ✅ Correct for OBS WebSocket v5+
  console.log(`🎥 OBS recording started (Profile: ${profileName}, Scene: ${sceneName})`);
}

async function stopOBSRecording() {
  if (!isConnected) return;
  await obs.call('StopRecord'); // ✅ Correct for OBS WebSocket v5+
  await obs.disconnect();
  isConnected = false;
  console.log("🛑 OBS recording stopped and disconnected.");
}

module.exports = {
  startOBSRecording,
  stopOBSRecording
};
