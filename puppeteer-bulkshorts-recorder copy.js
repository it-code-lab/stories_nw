// puppeteer-bulkshorts-recorder.js

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

async function recordShort(shortIndex, outputPath) {
    const browser = await puppeteer.launch({
        headless: false,
        defaultViewport: { width: 1080, height: 1920 },
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const page = await browser.newPage();
    
    const shortUrl = `http://localhost:8080/bulkShortMaker.html?shortIndex=${shortIndex}`;
    console.log(`Opening ${shortUrl}`);

    await page.goto(shortUrl);

    // Wait for user interaction simulation if needed
    await page.evaluate(() => {
        const overlay = document.getElementById('startOverlay');
        if (overlay) {
            overlay.click();
        }
    });

    // Wait for page and animations to complete
    await page.waitForTimeout(1000);

    const client = await page.target().createCDPSession();
    await client.send('Page.enable');
    const { windowId } = await client.send('Browser.getWindowForTarget');

    // Start recording
    await client.send('Page.startScreencast', {
        format: 'png',
        quality: 100,
        maxWidth: 1080,
        maxHeight: 1920,
        everyNthFrame: 1
    });

    const frames = [];

    client.on('Page.screencastFrame', async (frame) => {
        frames.push(frame.data);
        await client.send('Page.screencastFrameAck', { sessionId: frame.sessionId });
    });

    // Record for 20 seconds (adjust as needed)
    await page.waitForTimeout(recordingDuration * 1000);

    await client.send('Page.stopScreencast');
    await browser.close();

    // Save frames as video using ffmpeg (alternative: write raw images)
    const tempFolder = path.join(__dirname, 'temp_frames', `short_${shortIndex}`);
    fs.mkdirSync(tempFolder, { recursive: true });

    frames.forEach((frame, idx) => {
        const filePath = path.join(tempFolder, `frame_${String(idx).padStart(5, '0')}.png`);
        fs.writeFileSync(filePath, Buffer.from(frame, 'base64'));
    });

    // Run ffmpeg to convert frames to video
    const { execSync } = require('child_process');

    const ffmpegCmd = `ffmpeg -r 30 -i ${tempFolder}/frame_%05d.png -vcodec libx264 -pix_fmt yuv420p -y ${outputPath}`;

    console.log(`Running: ${ffmpegCmd}`);
    execSync(ffmpegCmd, { stdio: 'inherit' });

    // Cleanup temp frames
    fs.rmSync(tempFolder, { recursive: true, force: true });

    console.log(`🎬 Short ${shortIndex} recorded successfully at ${outputPath}`);
}

(async () => {
    const args = process.argv.slice(2);
    if (args.length < 2) {
        console.error('Usage: node puppeteer-recorder.js <shortIndex> <outputPath>');
        process.exit(1);
    }
    const [shortIndex, outputPath, recordingDuration] = args;

    await recordShort(shortIndex, outputPath);
})();
