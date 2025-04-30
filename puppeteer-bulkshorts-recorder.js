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
const [,, shortIndex, outputPath, recordingDuration] = process.argv;

if (!outputPath) {
    console.error("❌ Please provide at least the output file name as the first argument.");
    process.exit(1);
}

const isLandscape = false;
const width = isLandscape ? 1280 : 720;
const height = isLandscape ? 720 : 1280;
const captureWidth = isLandscape ? 1664 : 540;
const captureHeight = isLandscape ? 936 : 960;
const offsetX = isLandscape ? 12 : 0;           //605 for middle
const offsetY = isLandscape ? 130 : 130;

(async () => {
    const videoUrl = `http://localhost:8080/bulkShortMaker.html?shortIndex=${shortIndex}`;
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

    // console.log("✅ Browser opened. Waiting for video to load...");
    // await page.waitForSelector("video");

    // Wait for user interaction simulation if needed
    await page.evaluate(() => {
        const overlay = document.getElementById('startOverlay');
        if (overlay) {
            overlay.click();
        }
    });
 
    const ffmpeg = spawn("ffmpeg", [
        "-y",
        "-f", "gdigrab",
        "-framerate", "18",
        "-offset_x", offsetX,
        "-offset_y", offsetY,
        "-video_size", `${captureWidth}x${captureHeight}`,
        "-i", "desktop",

        "-f", "dshow",
        "-i", "audio=Stereo Mix (Realtek(R) Audio)",

        "-af", "adelay=400|400", // Add 1000ms delay to audio stream(s)
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

    await new Promise(resolve => setTimeout(resolve, 2500)); // give FFmpeg time to initialize


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

    let whiteScreenDuration = 1.2;

    // The existing ffmpeg.on("close", ...) handler for final cleanup remains
    // Note: The 'close' event might fire *after* the main script flow continues
    // if recording finishes successfully. Ensure browser.close() is handled correctly.

    // Refined close handler (ensure it's only defined once)
    ffmpeg.removeAllListeners('close'); // Remove potential listener added in the promise setup
    ffmpeg.on('close', async (code) => {
        console.log(`✅ Recording complete. FFmpeg exited with code ${code}. Output: ${outputPath}`);

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
        await browser.close();
        console.log("✅ Browser closed.");
        
    });
})();
