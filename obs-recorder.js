//DND - Testing this code with the following command:


// obs-recorder.js
const { startOBSRecording, stopOBSRecording } = require('./obs-controller');
const fs = require("fs");
const path = require("path");

const sceneName = process.argv[2];
const profileName = process.argv[3];
const duration = parseInt(process.argv[4]);
const finalOutputPath = process.argv[5];

const OBS_OUTPUT_FOLDER = "C:/Users/mail2/OneDrive/Desktop/del";
const FILE_EXTENSION = ".mp4";

function listFiles() {
  return fs.readdirSync(OBS_OUTPUT_FOLDER)
    .filter(f => f.endsWith(FILE_EXTENSION))
    .map(f => {
      const full = path.join(OBS_OUTPUT_FOLDER, f);
      return {
        name: f,
        full,
        mtime: fs.statSync(full).mtimeMs,
        size: fs.statSync(full).size
      };
    });
}

function waitForFileUnlock(sourcePath, targetPath, retries = 10, delayMs = 500) {
  return new Promise((resolve, reject) => {
    let attempt = 0;
    const tryRename = () => {
      try {
        fs.renameSync(sourcePath, targetPath);
        console.log(`✅ Recording saved as: ${targetPath}`);
        resolve();
      } catch (err) {
        if (err.code === 'EBUSY' && attempt < retries) {
          attempt++;
          console.log(`⏳ File busy, retrying (${attempt}/${retries})...`);
          setTimeout(tryRename, delayMs);
        } else {
          reject(err);
        }
      }
    };
    tryRename();
  });
}

(async () => {
  try {
    console.log("🚀 Starting obs-recorder.js with args:", process.argv);

    const beforeFiles = listFiles();

    // await startOBSRecording(sceneName, profileName);
    await startOBSRecording( profileName);
    await new Promise(res => setTimeout(res, duration * 1000));
    await stopOBSRecording();

    const afterFiles = listFiles();
    const newFiles = afterFiles.filter(a =>
      !beforeFiles.some(b => b.name === a.name && b.size === a.size)
    );

    if (newFiles.length === 0) {
      throw new Error("No new OBS recording found.");
    }

    const latest = newFiles.sort((a, b) => b.mtime - a.mtime)[0];
    const targetPath = path.resolve(finalOutputPath.endsWith(".mp4") ? finalOutputPath : `${finalOutputPath}.mp4`);

    await waitForFileUnlock(latest.full, targetPath);

  } catch (err) {
    console.error("❌ Error during OBS recording:", err);
  }
})();
