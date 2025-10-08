const { chromium } = require('playwright');
const fs = require('fs').promises;
const { spawn } = require('child_process');

// Get the number of iterations from command line arguments
const getIterationCount = () => {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.log('⚠️  No iteration count provided. Using default: 1');
    return 1;
  }
  
  const count = parseInt(args[0]);
  if (isNaN(count) || count <= 0) {
    console.log('⚠️  Invalid iteration count. Using default: 1');
    return 1;
  }
  
  return count;
};

// Function to change IP using Python script
const changeIP = () => {
  return new Promise((resolve, reject) => {
    console.log('🔄 Changing IP address...');
    
    const pythonProcess = spawn('py', ['changeip.py']);
    
    pythonProcess.stdout.on('data', (data) => {
      console.log(`🐍 Python stdout: ${data}`);
    });
    
    pythonProcess.stderr.on('data', (data) => {
      console.error(`🐍 Python stderr: ${data}`);
    });
    
    pythonProcess.on('close', (code) => {
      if (code === 0) {
        console.log('✅ IP change completed successfully');
        resolve();
      } else {
        console.error(`❌ IP change failed with code: ${code}`);
        reject(new Error(`IP change failed with code: ${code}`));
      }
    });
    
    pythonProcess.on('error', (error) => {
      console.error('❌ Failed to start IP change process:', error);
      reject(error);
    });
  });
};

const runIteration = async (iteration) => {
  console.log(`\n🔄 Starting iteration ${iteration}`);
  
  // Launch browser in incognito mode
  const browser = await chromium.launch({ 
    headless: false, // Set to true if you don't want to see the browser
  });
  
  // Create a new incognito context
  const context = await browser.newContext();
  
  // Create a new page
  const page = await context.newPage();
  
  // Array to store collected URLs
  const collectedUrls = new Set();
  
  // Flag to control monitoring
  let monitoringActive = true;
  
  // Function to save URL to file
  const saveUrl = async (url) => {
    try {
      await fs.appendFile('get_urls.txt', url + '\n');
      console.log(`✅ [Iteration ${iteration}] Saved URL: ${url}`);
    } catch (error) {
      console.error(`❌ [Iteration ${iteration}] Error saving URL:`, error);
    }
  };
  
  // Function to stop monitoring
  const stopMonitoring = () => {
    if (monitoringActive) {
      monitoringActive = false;
      console.log(`🛑 [Iteration ${iteration}] Monitoring stopped - Token URL found`);
      
      // Remove all event listeners
      page.removeAllListeners('response');
      page.removeAllListeners('framenavigated');
      page.removeAllListeners('request');
      
      if (checkInterval) {
        clearInterval(checkInterval);
      }
    }
  };
  
  // Listen for response events to capture navigation
  page.on('response', async (response) => {
    if (!monitoringActive) return;
    
    const url = response.url();
    
    // Check if URL contains /lab prefix
    if (url.includes('/lab')) {
      if (!collectedUrls.has(url)) {
        collectedUrls.add(url);
        await saveUrl(url);
        
        // Stop monitoring if we found the token URL
        if (url.includes('/lab?token=')) {
          stopMonitoring();
        }
      }
    }
  });
  
  // Listen for console messages (optional, for debugging)
  page.on('console', msg => {
    if (msg.type() === 'log') {
      console.log(`[Iteration ${iteration}] PAGE LOG:`, msg.text());
    }
  });
  
  let checkInterval;
  
  try {
    console.log(`🌐 [Iteration ${iteration}] Opening NiceGPU Playground...`);
    
    // Navigate to the playground
    await page.goto('https://www.nicegpu.com/playground', {
      waitUntil: 'networkidle',
      timeout: 60000
    });
    
    console.log(`✅ [Iteration ${iteration}] Page loaded. Monitoring for URL changes with /lab prefix...`);
    
    // Additional method: Check current URL periodically
    let previousUrl = page.url();
    
    // Set up periodic URL checking
    checkInterval = setInterval(async () => {
      if (!monitoringActive) return;
      
      try {
        const currentUrl = page.url();
        
        // If URL changed and contains /lab
        if (currentUrl !== previousUrl && currentUrl.includes('/lab')) {
          if (!collectedUrls.has(currentUrl)) {
            collectedUrls.add(currentUrl);
            await saveUrl(currentUrl);
            
            // Stop monitoring if we found the token URL
            if (currentUrl.includes('/lab?token=')) {
              stopMonitoring();
            }
          }
        }
        
        previousUrl = currentUrl;
      } catch (error) {
        console.log(`[Iteration ${iteration}] Interval check error:`, error.message);
      }
    }, 2000); // Check every 2 seconds
    
    // Also listen for frame navigation
    page.on('framenavigated', async (frame) => {
      if (!monitoringActive) return;
      
      const url = frame.url();
      if (url && url.includes('/lab')) {
        if (!collectedUrls.has(url)) {
          collectedUrls.add(url);
          await saveUrl(url);
          
          // Stop monitoring if we found the token URL
          if (url.includes('/lab?token=')) {
            stopMonitoring();
          }
        }
      }
    });
    
    // Listen for requests that might indicate navigation
    page.on('request', async (request) => {
      if (!monitoringActive) return;
      
      const url = request.url();
      if (url.includes('/lab')) {
        if (!collectedUrls.has(url)) {
          collectedUrls.add(url);
          await saveUrl(url);
          
          // Stop monitoring if we found the token URL
          if (url.includes('/lab?token=')) {
            stopMonitoring();
          }
        }
      }
    });
    
    console.log(`🔍 [Iteration ${iteration}] Monitoring active. Will stop automatically when token URL is found.`);
    
    // Keep the script running but monitoring can be stopped
    while (monitoringActive) {
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    
    console.log(`🏁 [Iteration ${iteration}] Script completed.`);
    
  } catch (error) {
    console.error(`❌ [Iteration ${iteration}] Error:`, error);
  } finally {
    await browser.close();
    console.log(`📝 [Iteration ${iteration}] Browser closed.`);
  }
};

// Main execution function
const main = async () => {
  const iterationCount = getIterationCount();
  
  console.log(`🚀 Starting ${iterationCount} iteration(s)...`);
  
  for (let i = 1; i <= iterationCount; i++) {
    await runIteration(i);
    
    // Check if we need to change IP (every 3 iterations)
    if (i % 3 === 0 && i < iterationCount) {
      console.log(`\n🔄 Processed ${i} iterations, changing IP address...`);
      
      try {
        await changeIP();
        console.log('⏳ Waiting 5 seconds before continuing...');
        await new Promise(resolve => setTimeout(resolve, 5000));
      } catch (error) {
        console.error('❌ IP change failed, but continuing with next iteration...');
      }
    }
    
    // Add a small delay between iterations (optional)
    if (i < iterationCount) {
      console.log(`⏳ Waiting 2 seconds before next iteration...`);
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
  }
  
  console.log(`\n🎉 All ${iterationCount} iterations completed!`);
};

// Run the main function
main().catch(console.error);
