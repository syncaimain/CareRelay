/** Run on Node 22: node --experimental-strip-types demo/record_demo.ts */
import { chromium, expect } from '@playwright/test';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
const baseURL=process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:3104';
const dataset=JSON.parse(await readFile('demo/dataset.json','utf8'));
await mkdir('demo/assets/screenshots',{recursive:true}); await mkdir('demo/assets/video',{recursive:true});
const browser=await chromium.launch();
const context=await browser.newContext({viewport:{width:1920,height:1080},recordVideo:{dir:'demo/assets/video',size:{width:1920,height:1080}}});
const page=await context.newPage(); const errors:string[]=[];
page.on('pageerror',e=>errors.push(e.message));
const started=Date.now(); const timeline:{name:string;seconds:number}[]=[];
const mark=(name:string)=>{const seconds=Number(((Date.now()-started)/1000).toFixed(2));timeline.push({name,seconds});console.log(`${seconds}s ${name}`);};
const pause=(ms=3500)=>page.waitForTimeout(ms);
const screenshot=(name:string)=>page.screenshot({path:`demo/assets/screenshots/${name}.png`});
const navigate=async(name:string)=>{await page.getByRole('button',{name,exact:true}).click();await pause(400);};
const state=()=>page.evaluate(async()=>{const token=sessionStorage.getItem('carerelay-token');return(await fetch('/api/state',{headers:{Authorization:'Bearer '+token}})).json();});
try {
 await page.goto(baseURL); await page.waitForLoadState('networkidle');
 mark('The family coordination burden'); await pause(4500);
 await page.getByRole('button',{name:'Create fictional care circle'}).click();
 await expect(page.getByRole('heading',{name:'Good to see you, Alex.'})).toBeVisible();
 mark('Four fictional caregivers'); await pause(4500);
 await navigate('Import messages'); await page.getByRole('button',{name:'Load fictional conversation'}).click();
 await expect(page.getByLabel('Messages and notes')).toHaveValue(dataset.demo_text);
 await page.getByLabel('Messages and notes').fill(dataset.demo_text.replace('Confirm the clinic appointment on','The clinic appointment is on'));
 await screenshot('02-source');mark('Original messages and missing return ride');await pause(6000);
 await page.getByRole('button',{name:'Find coordination tasks'}).click();mark('Real local model processing');
 await expect(page.getByRole('heading',{name:'Review queue',exact:true})).toBeVisible({timeout:240000});
 await screenshot('03-evidence');mark('Source-linked suggestions');await pause(4500);
 let reviewed=0;
 while(await page.locator('.review-card').count()) {
  if(++reviewed>12)throw new Error('Unexpected queue size. Inspect manually.');
  const count=await page.locator('.review-card').count();
  const card=page.locator('.review-card').first();const quote=await card.locator('blockquote').innerText();
  const date=quote.match(/(\d{4}-\d{2}-\d{2}) at (\d{2}:\d{2})/);
  if(!date)await card.getByRole('button',{name:'Reject',exact:true}).click();
  else {
   await card.getByLabel('Due date & time (PKT)').fill(`${date[1]}T${date[2]}`);
   if(quote.includes('Maya')){
    await card.getByLabel('Task category').selectOption('transport');
    await card.getByLabel('Proposed caregiver').selectOption({label:'Maya'});
    await card.getByLabel('Open questions / uncertainty').fill('Maya has a work shift that morning. Driver availability needs confirmation; assignment not accepted.');
   }else await card.getByLabel('Open questions / uncertainty').fill('');
   await card.getByLabel('I checked the source',{exact:false}).check();await pause(1500);
   await card.getByRole('button',{name:'Approve suggestion'}).click();
  }
  // The first locator is live; wait for the count to decrease rather than its next match to disappear.
  await expect(page.locator('.review-card')).toHaveCount(count-1);
 }
 await navigate('Responsibility board');mark('Approved plan: travel is still unclaimed');await screenshot('04-board');await pause(5000);
 const initialState=await state();
 const original=initialState.tasks.find((t:any)=>t.status==='confirmed'&&t.kind==='appointment'&&t.quote.includes('clinic appointment'));
 if(!original)throw new Error('No original clinic appointment was extracted. Do not fabricate a result.');
 const robinProfile=initialState.caregivers.find((c:any)=>c.name==='Robin');
 await navigate('Privacy & access');await page.getByLabel('Current demo caregiver').selectOption(String(robinProfile.id));
 await expect(page.locator('.user-row strong')).toHaveText('Robin');await navigate('Responsibility board');
 const robinCard=page.locator('.task-card').filter({hasText:'library'}).first();
 await robinCard.getByRole('button',{name:'I can take this'}).click();await expect(robinCard).toContainText('Accepted responsibility');
 mark('Robin explicitly accepts her own responsibility');await pause(3500);
 await navigate('Privacy & access');await page.getByLabel('Current demo caregiver').selectOption(String(initialState.me.id));
 await expect(page.locator('.user-row strong')).toHaveText('Alex');await navigate('Import inbox');
 await page.getByLabel('Source label').fill('Appointment changed · synthetic update');
 await page.getByLabel('Messages and notes').fill(dataset.reschedule_text);mark('A real reschedule notice');await pause(4500);
 await page.getByRole('button',{name:'Find coordination tasks'}).click();
 await expect(page.getByRole('heading',{name:'Review queue',exact:true})).toBeVisible({timeout:240000});
 const change=page.locator('.review-card').filter({hasText:'RESCHEDULE'}).first();await expect(change).toBeVisible();
 await change.getByLabel('Due date & time (PKT)').fill('2026-10-27T10:30');
 await change.getByLabel('Task category').selectOption('appointment');
 await change.getByLabel('Original approved task').selectOption(String(original.id));
 await change.getByLabel('Open questions / uncertainty').fill('Appointment moved. Check transport separately; no replacement ride has been accepted.');
 await change.getByLabel('I checked the source',{exact:false}).check();await screenshot('05-reschedule');await pause(4000);
 const changeId=Number((await change.locator('.review-top>span:last-child').innerText()).replace('#',''));
 await change.getByRole('button',{name:'Approve suggestion'}).click();
 await expect.poll(async()=>(await state()).tasks.find((t:any)=>t.id===changeId)?.status).toBe('confirmed');
 await expect.poll(async()=>(await state()).tasks.find((t:any)=>t.id===original.id)?.status).toBe('cancelled');
 while(await page.locator('.review-card').count()){const count=await page.locator('.review-card').count();await page.locator('.review-card').first().getByRole('button',{name:'Reject',exact:true}).click();await expect(page.locator('.review-card')).toHaveCount(count-1);}
 await navigate('Calendar');await page.getByLabel('Calendar date').fill('2026-10-27');
 mark('Replacement date, with history preserved');await screenshot('07-calendar');await pause(4000);
 await navigate('Handoffs');await page.getByRole('button',{name:'Prepare day brief'}).click();
 await expect(page.locator('.handoff-text')).toBeVisible({timeout:240000});
 await expect(page.locator('.handoff-text')).toContainText('Verified and accepted');
 await expect(page.locator('.handoff-text')).toContainText('Unresolved / needs a check');
 mark('Accepted commitments and unresolved questions');await pause(5000);
 await page.getByRole('button',{name:'Approve for manual sharing'}).click();
 await expect(page.getByRole('button',{name:'Copy approved handoff'})).toBeVisible();
 await screenshot('06-handoff');mark('Human approval before manual sharing');await pause(4000);
 await navigate('Overview');await screenshot('01-overview');mark('The whole plan, in one place');
 const elapsed=Date.now()-started;if(elapsed<115000)await pause(115000-elapsed);
 const finalState=await state();
 await writeFile('docs/demo-recording.json',JSON.stringify({synthetic:true,baseURL,seconds:Number(((Date.now()-started)/1000).toFixed(2)),timeline,pageErrors:errors,approvedTasks:finalState.tasks.filter((t:any)=>t.status==='confirmed').length,acceptedTasks:finalState.tasks.filter((t:any)=>t.accepted&&t.status==='confirmed').length,supersededTaskCancelled:finalState.tasks.find((t:any)=>t.id===original.id)?.status==='cancelled',sourceCount:finalState.sources.length},null,2));
 if(errors.length)throw new Error(errors.join('; '));
}finally {
 const video=page.video();await context.close();const actual=await video?.path();
 if(actual){const relative=path.relative(process.cwd(),actual);await writeFile('demo/assets/video/recording-path.txt',relative);console.log('Silent recording:',relative);}
 await browser.close();
}
