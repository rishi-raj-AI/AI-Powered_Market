import {defineConfig,devices} from '@playwright/test';

export default defineConfig({
  testDir:'./e2e',
  timeout:30_000,
  expect:{timeout:7_500},
  fullyParallel:true,
  forbidOnly:!!process.env.CI,
  retries:process.env.CI?1:0,
  workers:process.env.CI?2:undefined,
  reporter:process.env.CI?[['list'],['html',{outputFolder:'playwright-report',open:'never'}]]:'list',
  use:{
    baseURL:'http://127.0.0.1:3100',
    trace:'retain-on-failure',
    screenshot:'only-on-failure',
    video:'retain-on-failure',
  },
  projects:[
    {name:'chromium',use:{...devices['Desktop Chrome']}},
    {name:'firefox',use:{...devices['Desktop Firefox']}},
    {name:'webkit',use:{...devices['Desktop Safari']}},
    {name:'mobile-chrome',use:{...devices['Pixel 7']}},
  ],
  webServer:{
    command:'npm run dev -- --hostname 127.0.0.1 --port 3100',
    url:'http://127.0.0.1:3100',
    reuseExistingServer:!process.env.CI,
    timeout:120_000,
    env:{NEXT_PUBLIC_API_URL:'http://localhost:8000/api/v1'},
  },
});
