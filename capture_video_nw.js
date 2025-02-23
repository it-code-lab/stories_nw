const puppeteer = require('puppeteer');
const ffmpeg = require('fluent-ffmpeg');
const fs = require('fs');

// Set FFmpeg paths
ffmpeg.setFfmpegPath('C:\\ffmpeg\\bin\\ffmpeg.exe');
ffmpeg.setFfprobePath('C:\\ffmpeg\\bin\\ffprobe.exe');

(async () => {
  // Launch the browser
  const browser = await puppeteer.launch({ headless: false });
  const page = await browser.newPage();

  // Navigate to the page with the video
  await page.goto('file://' + __dirname + '/index.html');

  // Wait for the video container to load
  await page.waitForSelector('#video-container');

  // Start playing the video
  await page.evaluate(() => {
    const video = document.getElementById('video');
    video.currentTime = 0; // Restart video
    video.play(); // Start playback
  });

  // Ensure the "frames" folder exists
  if (!fs.existsSync('frames')) fs.mkdirSync('frames');

  // Capture frames at regular intervals
  const frameRate = 30; // Frames per second
  const duration = 10; // Recording duration in seconds
  const totalFrames = frameRate * duration;

  for (let i = 0; i < totalFrames; i++) {
    await page.screenshot({
      path: `frames/frame_${i.toString().padStart(4, '0')}.png`,
      clip: await page.evaluate(() => {
        const videoElement = document.querySelector('#video-container');
        const rect = videoElement.getBoundingClientRect();
        return {
          x: rect.x,
          y: rect.y,
          width: rect.width,
          height: rect.height,
        };
      }),
    });
    await new Promise((resolve) => setTimeout(resolve, 1000 / frameRate));
  }

  console.log('Finished capturing frames.');

  // Combine frames into a video using FFmpeg
  const ffmpegProcess = ffmpeg()
    .input('frames/frame_%04d.png')
    .inputFPS(frameRate)
    .output('output.mp4')
    .videoCodec('libx264')
    .on('end', () => {
      console.log('Video created successfully.');
      browser.close(); // Close the browser after FFmpeg finishes
    })
    .on('error', (err) => {
      console.error('Error creating video:', err);
      browser.close(); // Close the browser if FFmpeg fails
    })
    .run();

  // Handle script termination gracefully
  process.on('SIGINT', () => {
    console.log('Terminating script...');
    ffmpegProcess.kill('SIGINT'); // Stop FFmpeg gracefully
    browser.close(); // Close the browser
    process.exit(); // Exit the script
  });
})();