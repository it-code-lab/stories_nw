const puppeteer = require("puppeteer");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

// Commands to run this code : DND
// REF: https://gemini.google.com/app/c90e2976f214a9fe
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

    // ✅ Capture browser console logs
    // page.on('console', msg => {
    // const args = msg.args();
    // Promise.all(args.map(arg => arg.jsonValue())).then(values => {
    //             console.log(`🧠 Browser log:`, ...values);
    // });
    // });    
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
        updateProperties();
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

        "-af", "adelay=500|500", // Add 500ms delay to audio stream(s)
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

    // await page.evaluate(() => {
    //     const video = document.querySelector("video");
    //     video.play();
    // });
    // ffmpeg.stderr.on("data", (data) => {
    //     console.log("FFmpeg:", data.toString());
    // });

    // ffmpeg.on("close", async () => {
    //     console.log(`✅ Recording complete: ${outputPath}`);
    //     await browser.close();
    // });
    let ffmpegReady = false;
    let ffmpegReadyTime;
    const ffmpegPromise = new Promise((resolve, reject) => {
        ffmpeg.stderr.on("data", (data) => {
            const output = data.toString();
            console.log("FFmpeg:", output); // Log all output for debugging

            // Check for a line indicating encoding has started
            // Common patterns include "frame=", "time=", "size="
            // Adjust this pattern if needed based on your FFmpeg version/output
            if (!ffmpegReady && output.includes('frame=') || output.includes('time=')) {
                console.log("✅ FFmpeg seems to have started recording.");
                ffmpegReady = true;
                ffmpegReadyTime = Date.now();
                resolve(); // Signal that FFmpeg is ready
            }
        });

        ffmpeg.on("error", (err) => {
            console.error("❌ FFmpeg error:", err);
            if (!ffmpegReady) reject(err); // Reject if error occurs before ready
        });

        ffmpeg.on("close", (code) => {
             console.log(`✅ FFmpeg process closed with code ${code}`);
             // If FFmpeg closes before we thought it was ready, reject
             if (!ffmpegReady) {
                 reject(new Error(`FFmpeg closed unexpectedly (code ${code}) before indicating readiness.`));
             }
             // The main recording completion logic is outside this specific promise
        });

        // Add a timeout in case FFmpeg never outputs the expected message
        setTimeout(() => {
             if (!ffmpegReady) {
                 reject(new Error("FFmpeg readiness timeout: Did not detect start message."));
             }
        }, 10000); // 10 second timeout - adjust as needed
    });

    let whiteScreenDuration = 0; // Initialize white screen duration
    try {
        console.log("⏳ Waiting for FFmpeg to signal readiness...");
        await ffmpegPromise; // Wait until the stderr listener resolves
        const videoStartTime = Date.now();
        whiteScreenDuration = (videoStartTime - ffmpegReadyTime) / 1000;
        console.log("⏱ Estimated white screen duration:", whiteScreenDuration, "seconds");
        console.log("▶️ Starting video playback...");
        await page.evaluate(() => {
            const video = document.querySelector("video");
            video.currentTime = 0; // Ensure it starts from the beginning
            video.play();
        });
    } catch (error) {
        console.error("❌ Error during FFmpeg readiness wait or video playback start:", error);
        // Handle the error appropriately - maybe kill ffmpeg and exit
        ffmpeg.kill('SIGINT'); // Attempt to gracefully stop FFmpeg
        await browser.close();
        process.exit(1);
    }

    whiteScreenDuration = 1;

    // The existing ffmpeg.on("close", ...) handler for final cleanup remains
    // Note: The 'close' event might fire *after* the main script flow continues
    // if recording finishes successfully. Ensure browser.close() is handled correctly.

    // Refined close handler (ensure it's only defined once)
    ffmpeg.removeAllListeners('close'); // Remove potential listener added in the promise setup
    ffmpeg.on('close', async (code) => {
        console.log(`✅ Recording complete. FFmpeg exited with code ${code}. Output: ${outputPath}`);
        //await browser.close();
        console.log("✅ Browser closed.");
        // Trim the white/mute part using ffmpeg -ss
        const trimmedOutput = outputPath.replace(".mp4", "_trimmed.mp4");
        const trim = spawn("ffmpeg", [
                    "-y",
                    "-ss", whiteScreenDuration.toFixed(2),
                    "-i", outputPath,
                    "-c", "copy",
                    trimmedOutput
        ]);

        trim.stderr.on("data", (data) => {
                    console.log("FFmpeg Trim:", data.toString());
        });

        trim.on("close", (code) => {
                    if (code === 0) {
                            fs.renameSync(trimmedOutput, outputPath);
                            console.log(`✂️ Trimmed video saved as ${outputPath}`);
                    } else {
                            console.error("❌ Trimming failed with code", code);
                    }
        });
        
    });
})();
