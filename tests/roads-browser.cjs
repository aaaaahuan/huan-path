const {chromium}=require('../work/browser-test/node_modules/playwright');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const jobsRoot=process.env.HUAN_PATH_JOBS_DIR || 'jobs';
const completed=fs.readdirSync(jobsRoot).find(id=>{const dir=path.join(jobsRoot,id);return fs.existsSync(path.join(dir,'web/metadata.json'))&&JSON.parse(fs.readFileSync(path.join(dir,'status.json'))).status==='completed'&&JSON.parse(fs.readFileSync(path.join(dir,'web/metadata.json'))).roads?.count>0});
assert(completed,'测试作品根中需要有道路的完成作品');
(async()=>{const browser=await chromium.launch({executablePath:path.resolve('work/browser-test/shell/chrome-headless-shell-mac-arm64/chrome-headless-shell'),headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()===404)errors.push('404 '+r.url())});
 await page.goto(`http://127.0.0.1:8766/jobs/${completed}/web/?embedded=1`,{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>window.featureStatus?.enabled.roads,undefined,{timeout:45000});assert((await page.locator('#road-status').textContent()).trim().length>0);assert(await page.locator('#import-roads').isVisible());
 await page.locator('#top').click();await page.waitForTimeout(1200);await page.screenshot({path:'work/screens/roads-round2-overview.png'});
 await page.locator('[data-feature="forest"]').click();await page.locator('[data-feature="roads"]').click();assert.equal(await page.locator('[data-feature="roads"]').getAttribute('aria-pressed'),'false');await page.locator('[data-feature="roads"]').click();
 await page.mouse.move(650,500);await page.mouse.wheel(0,-700);await page.waitForTimeout(1000);await page.screenshot({path:'work/screens/roads-round2-zoom.png'});assert.deepEqual(errors,[]);
 await page.setViewportSize({width:700,height:850});await page.waitForTimeout(300);assert(await page.locator('#road-status').isVisible());assert(await page.locator('#import-roads').isVisible());
 fs.writeFileSync('work/roads-browser-validation.json',JSON.stringify({status:'passed',webgl:await page.evaluate(()=>window.modelStatus),errors,screenshots:['roads-round2-overview.png','roads-round2-zoom.png'],checks:['embedded source and import entry','overview and zoom','forest and road toggles','no page errors or 404']},null,2));console.log('Roads real WebGL browser passed');
 }finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
