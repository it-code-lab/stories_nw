const puppeteer = require("puppeteer");
const { spawn } = require("child_process");
const path = require("path");

// Commands to run this code : DND
// //Command Line
// node puppeteer-recorder.js captured_video.mp4 10 landscape 5 style2 story-classical-3-710.mp3 0.05 1

// //Python Code
// import subprocess

// subprocess.run([
//     "node", "puppeteer-recorder.js",
//     "captured_video.mp4", "10", "portrait", "4", "style1", "story-classical-3-710.mp3", "0.05", "1"
// ])


// Extract arguments from command line
const [,, outputFileName, recordingDuration, videoOrientation, wordsPerCaption, captionStyle, backgroundMusic, backgroundMusicVolume, soundEffectVolume] = process.argv;

if (!outputFileName) {
    console.error("❌ Please provide at least the output file name as the first argument.");
    process.exit(1);
}

const isLandscape = videoOrientation === "landscape";
const width = isLandscape ? 1280 : 720;
const height = isLandscape ? 720 : 1280;
const captureWidth = isLandscape ? 1664 : 720;
const captureHeight = isLandscape ? 936 : 1280;
const offsetX = isLandscape ? 12 : 720;
const offsetY = isLandscape ? 130 : 130;

(async () => {
    const videoUrl = "file:///C:/0.data/4.SM-WSpace/6B.Python/1.Create_Video_From_Readernook_Story/application/index.html";
    //const recordingDuration = 10; // seconds

    const browser = await puppeteer.launch({
        headless: false,
        defaultViewport: { width, height },
        args: [
            '--start-maximized',
            '--autoplay-policy=no-user-gesture-required'
        ]
    });

    const [page] = await browser.pages();
    await page.goto(videoUrl);

    console.log("✅ Browser opened. Waiting for video to load...");
    await page.waitForSelector("video");

    // Set values in browser before playing
    await page.evaluate(({ wordsPerCaption, captionStyle, backgroundMusic, backgroundMusicVolume, soundEffectVolume }) => {
        if (document.getElementById("videoOrientation"))
            document.getElementById("videoOrientation").value = videoOrientation;
        if (document.getElementById("captionLength"))
            document.getElementById("captionLength").value = wordsPerCaption;
        if (document.getElementById("captionStyle"))
            document.getElementById("captionStyle").value = captionStyle;
        if (document.getElementById("bgMusicSelect"))

            document.getElementById("bgMusicSelect").value = backgroundMusic;
            const selectedMusic = backgroundMusic;
            if (selectedMusic !== "none") {
                const audioBackground = new Audio();
                audioBackground.src = `sounds/${selectedMusic}`;
                audioBackground.loop = true;
                audioBackground.volume = bgMusicVolume.value;
                audioBackground.play();
            }
        if (document.getElementById("bgMusicVolume"))
            document.getElementById("bgMusicVolume").value = backgroundMusicVolume;
        if (document.getElementById("effectVolume"))
            document.getElementById("effectVolume").value = soundEffectVolume;

        const video = document.querySelector("video");
        video.currentTime = 0;
        video.muted = false;
        video.volume = 1.0;
        // video.play();
        video.pause();
        video.currentTime = 0;
        video.muted = false;
        video.volume = 1.0;
    }, { wordsPerCaption, captionStyle, backgroundMusic, backgroundMusicVolume, soundEffectVolume });

    // await page.waitForFunction(() => {
    //     const video = document.querySelector("video");
    //     return !video.paused && video.currentTime > 0;
    // }, { timeout: 5000 });

    // const delayMs = 1000;
    // console.log(`⏳ Waiting ${delayMs}ms before starting recording...`);
    // await new Promise(res => setTimeout(res, delayMs));

    const outputPath = path.resolve(__dirname, outputFileName.endsWith(".mp4") ? outputFileName : outputFileName + ".mp4");

    const ffmpeg = spawn("ffmpeg", [
        "-y",
        "-f", "gdigrab",
        "-framerate", "24",
        "-offset_x", offsetX,
        "-offset_y", offsetY,
        "-video_size", `${captureWidth}x${captureHeight}`,
        "-i", "desktop",

        "-f", "dshow",
        "-i", "audio=Stereo Mix (Realtek(R) Audio)",

        "-af", "adelay=400|400", // Add 200ms delay to audio stream(s)
        "-c:v", "libx264",
        "-c:a", "aac",
        "-b:a", "192k",
        "-preset", "ultrafast",
        "-async", "1",
        "-vsync", "cfr", // Add this
        "-t", `${recordingDuration}`,
        "-pix_fmt", "yuv420p",
        outputPath
    ]);

    await new Promise(resolve => setTimeout(resolve, 500)); // give FFmpeg time to initialize

    await page.evaluate(() => {
        const video = document.querySelector("video");
        video.play();
    });
    ffmpeg.stderr.on("data", (data) => {
        console.log("FFmpeg:", data.toString());
    });

    ffmpeg.on("close", async () => {
        console.log(`✅ Recording complete: ${outputPath}`);
        await browser.close();
    });

})();
