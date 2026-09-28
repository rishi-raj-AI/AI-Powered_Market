import {expect,test} from '@playwright/test';

test('direct OTP keeps phone context, supports resend, and completes a safe return',async({page})=>{
  let requests=0;let verifiedPhone='';
  await page.route('**/api/v1/**',async route=>{
    const request=route.request(),url=new URL(request.url());
    if(url.pathname.endsWith('/auth/request-otp')){requests++;await new Promise(resolve=>setTimeout(resolve,80));return route.fulfill({status:200,json:{message:'OTP request accepted',expires_in_seconds:null,resend_after_seconds:null,request_limit:5,request_window_seconds:900}})}
    if(url.pathname.endsWith('/auth/verify-otp')){verifiedPhone=(await request.postDataJSON()).phone;return route.fulfill({status:200,json:{access_token:'application-token',token_type:'bearer'}})}
    if(url.pathname.endsWith('/users/me')){if(request.headers().authorization)return route.fulfill({status:200,json:{id:'customer',phone:'+919876543210',full_name:'Asha',role:'customer',is_active:true,is_verified:true}});return route.fulfill({status:401,json:{detail:'Not authenticated'}})}
    return route.fulfill({status:200,json:[]});
  });
  await page.goto('/login?next=%2Forders');
  await page.getByLabel('Mobile number').fill('98765 43210');
  await page.getByRole('button',{name:'Send OTP'}).click();
  await expect(page.getByLabel('One-time code')).toBeVisible();
  await expect(page.getByLabel('One-time code')).toBeEnabled();
  expect(requests).toBe(1);
  await page.getByRole('button',{name:'Resend code'}).click();
  await expect.poll(()=>requests).toBe(2);
  await page.getByLabel('One-time code').fill('123456');
  await page.getByRole('button',{name:'Verify & continue'}).click();
  await expect(page).toHaveURL(/\/orders$/);
  expect(verifiedPhone).toBe('98765 43210');
});

test('change number resets the challenge and role-restricted next is rejected',async({page})=>{
  await page.route('**/api/v1/**',async route=>{
    const request=route.request(),path=new URL(request.url()).pathname;
    if(path.endsWith('/auth/request-otp'))return route.fulfill({status:200,json:{message:'accepted',expires_in_seconds:null,resend_after_seconds:null,request_limit:5,request_window_seconds:900}});
    if(path.endsWith('/auth/verify-otp'))return route.fulfill({status:200,json:{access_token:'application-token',token_type:'bearer'}});
    if(path.endsWith('/users/me'))return request.headers().authorization?route.fulfill({status:200,json:{id:'customer',phone:'+919876543210',role:'customer',is_active:true,is_verified:true}}):route.fulfill({status:401,json:{detail:'Not authenticated'}});
    return route.fulfill({status:200,json:[]});
  });
  await page.goto('/login?next=%2Fadmin');
  await page.getByLabel('Mobile number').fill('9876543210');
  const firstOtpRequest=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith('/auth/request-otp'));
  await page.getByRole('button',{name:'Send OTP'}).click();
  await firstOtpRequest;
  await expect(page.getByLabel('One-time code')).toBeEnabled();
  await page.getByRole('button',{name:'Change number'}).click();
  await expect(page.getByLabel('Mobile number')).toBeEnabled();
  const secondOtpRequest=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith('/auth/request-otp'));
  await page.getByRole('button',{name:'Send OTP'}).click();
  await secondOtpRequest;
  await expect(page.getByLabel('One-time code')).toBeEnabled();
  await page.getByLabel('One-time code').fill('123456');
  await page.getByRole('button',{name:'Verify & continue'}).click();
  await expect(page).toHaveURL(/\/market$/);
});

test('verified token survives profile bootstrap failure without consuming another OTP',async({page})=>{
  let verifies=0,authenticatedMe=0;
  await page.route('**/api/v1/**',async route=>{
    const request=route.request(),path=new URL(request.url()).pathname;
    if(path.endsWith('/auth/request-otp'))return route.fulfill({status:200,json:{message:'accepted',expires_in_seconds:null,resend_after_seconds:null,request_limit:5,request_window_seconds:900}});
    if(path.endsWith('/auth/verify-otp')){verifies++;await new Promise(resolve=>setTimeout(resolve,80));return route.fulfill({status:200,json:{access_token:'application-token',token_type:'bearer'}})}
    if(path.endsWith('/users/me')&&request.headers().authorization){authenticatedMe++;if(authenticatedMe===1)return route.fulfill({status:503,json:{detail:'temporarily unavailable'}});return route.fulfill({status:200,json:{id:'customer',phone:'+919876543210',role:'customer',is_active:true,is_verified:true}})}
    if(path.endsWith('/users/me'))return route.fulfill({status:401,json:{detail:'Not authenticated'}});
    return route.fulfill({status:200,json:[]});
  });
  await page.goto('/login');await page.getByLabel('Mobile number').fill('9876543210');const otpRequest=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith('/auth/request-otp'));await page.getByRole('button',{name:'Send OTP'}).click();await otpRequest;await expect(page.getByLabel('One-time code')).toBeEnabled();await page.getByLabel('One-time code').fill('123456');await page.getByRole('button',{name:'Verify & continue'}).click();
  await expect(page.getByRole('button',{name:'Continue signed-in session'})).toBeVisible();expect(verifies).toBe(1);expect(await page.evaluate(()=>localStorage.getItem('gaonone_token'))).toBe('application-token');
  await page.getByRole('button',{name:'Continue signed-in session'}).click();await expect(page).toHaveURL(/\/market$/);expect(verifies).toBe(1);
});
