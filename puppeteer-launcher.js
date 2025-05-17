//DND - to test it run below command:
//node puppeteer-launcher.js test.mp4 10 portrait 4 style2 story-classical-3-710.mp3 0.05 1 

//node puppeteer-launcher.js test.mp4 10 landscape 4 style2 story-classical-3-710.mp3 0.05 1 


// puppeteer-launcher.js
const puppeteer = require("puppeteer");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

// Log file
const logPath = path.join(__dirname, "puppeteer-obs.log");
fs.writeFileSync(logPath, "🚀 New session started\n", "utf-8");

function log(msg) {
  fs.appendFileSync(logPath, msg + "\n");
  console.log(msg);
}

// Extract args
const [,, outputFile, recordingDuration, videoOrientationVal, wordsPerCaption, captionStyle, backgroundMusic, backgroundMusicVolume, soundEffectVolume] = process.argv;

if (!recordingDuration || !videoOrientationVal || !outputFile) {
  log("❌ Usage: node puppeteer-launcher.js <duration> <orientation> <words> <style> <music> <musicVol> <fxVol> <outputFile>");
  process.exit(1);
}

const isLandscape = videoOrientationVal === "landscape";
const width = isLandscape ? 1280 : 720;
const height = isLandscape ? 720 : 1280;

(async () => {
  const browser = await puppeteer.launch({
    headless: false,
    defaultViewport: { width, height },
    args: ['--start-maximized', '--autoplay-policy=no-user-gesture-required']
  });

  const [page] = await browser.pages();
  const videoUrl = "file:///" + __dirname + "/index.html";
  // const videoUrl = "file:///C:/0.data/4.SM-WSpace/6B.Python/1.Create_Video_From_Readernook_Story/application/index.html";
  await page.goto(videoUrl);

  log("✅ Browser opened. Preparing video setup...");
  await page.waitForSelector("video");

  await page.evaluate((params) => {
    const { wordsPerCaption, captionStyle, backgroundMusic, backgroundMusicVolume, soundEffectVolume, videoOrientationVal } = params;

    if (document.getElementById("videoOrientation"))
      document.getElementById("videoOrientation").value = videoOrientationVal;
    if (document.getElementById("captionLength"))
      document.getElementById("captionLength").value = wordsPerCaption;
    if (document.getElementById("captionStyle"))
      document.getElementById("captionStyle").value = captionStyle;
    if (document.getElementById("bgMusicSelect"))
      document.getElementById("bgMusicSelect").value = backgroundMusic;
    if (document.getElementById("bgMusicVolume"))
      document.getElementById("bgMusicVolume").value = backgroundMusicVolume;
    if (document.getElementById("effectVolume"))
      document.getElementById("effectVolume").value = soundEffectVolume;

    const selectedMusic = backgroundMusic;
    if (selectedMusic !== "none") {
        const audioBackground = new Audio();
        audioBackground.src = `sounds/${selectedMusic}`;
        audioBackground.loop = true;
        audioBackground.volume = bgMusicVolume.value;
        audioBackground.play();
    }
    const video = document.querySelector("video");
    video.currentTime = 0;
    video.muted = false;
    video.volume = 1.0;
    updateProperties();
    setTimeout(() => {
        video.play();
      }, 1000); // delay 1 second to let OBS settle
      
  }, { wordsPerCaption, captionStyle, backgroundMusic, backgroundMusicVolume, soundEffectVolume, videoOrientationVal });

  log("🎬 Video setup done. Launching OBS Recorder...");

  const sceneName = isLandscape ? "LandscapeScene" : "PortraitScene";
  const profileName = isLandscape ? "LandscapeProfile" : "PortraitProfile";
  const duration = parseInt(recordingDuration);

  const obsCmd = ["node", "obs-recorder.js", sceneName, profileName, duration.toString(), outputFile];
  const obsProcess = spawn("node", obsCmd.slice(1), { stdio: "inherit" });

  obsProcess.on("close", async (code) => {
    log(`🎥 OBS recording finished with code ${code}`);
    await browser.close();
    log("✅ Browser closed after recording.");
  });
})();
