// Actual HTTPS app + native Chromium PDF viewer. Run only on the isolated test server.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import https from "node:https";
import { chromium } from "playwright";

const BASE="https://ui:8443",out="/out";
const proof={scope:"isolated actual API/Nginx/browser; synthetic journals and directory; one private RO PDF",cases:[]};
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const hash=data=>createHash("sha256").update(data).digest("hex");
const browser=await chromium.launch({channel:"chromium",headless:true,args:["--no-sandbox","--disable-dev-shm-usage"]});
async function login(page,username){
  await page.goto(BASE,{waitUntil:"networkidle"});
  await page.getByLabel("Benutzername oder UPN").fill(username);
  await page.getByLabel("Kennwort").fill("synthetic-user-password");
  await page.getByRole("button",{name:"Anmelden",exact:true}).click();
  await page.getByRole("heading",{name:"Übersicht",level:1,exact:true}).waitFor();
}
async function nav(page,label){
  const toggle=page.getByRole("button",{name:"Navigation öffnen",exact:true});
  if(await toggle.isVisible())await toggle.click();
  await page.getByRole("navigation",{name:"Hauptnavigation"}).getByRole("button",{name:label,exact:true}).click();
  await page.getByRole("heading",{name:label,level:1,exact:true}).waitFor();
}
async function get(context,path){const r=await context.request.get(BASE+path);assert.equal(r.status(),200);return r.json()}
async function post(context,path,data={}){
  const session=await get(context,"/api/auth/session");
  const r=await context.request.post(BASE+path,{data,headers:{Origin:BASE,"X-CSRF-Token":session.csrf_token}});
  assert.equal(r.status(),200,await r.text());return r.json();
}
async function retryEnabled(context,enabled){
  const session=await get(context,"/api/auth/session"),cfg=await get(context,"/api/admin/processing");
  const response=await context.request.put(BASE+"/api/admin/processing",{data:{expected_version:cfg.version,preview_enabled:cfg.preview_enabled,retry_enabled:enabled},headers:{Origin:BASE,"X-CSRF-Token":session.csrf_token}});
  assert.equal(response.status(),200);return response.json();
}
async function open(page,key,name){
  await nav(page,"Vorgänge");
  await page.getByRole("button",{name:"Details zu "+key,exact:true}).click();
  await page.getByRole("dialog",{name:"Vorgang und Original"}).waitFor();
  if(name)await page.getByRole("button",{name:"Anhang "+name+" anzeigen",exact:true}).click();
}
async function close(page){await page.getByRole("button",{name:"Vorgang schließen",exact:true}).click();await page.getByRole("dialog").waitFor({state:"hidden"})}
async function choose(page,label){await page.getByLabel("Zuordnung",{exact:true}).click();await page.getByRole("option",{name:label,exact:true}).click()}
async function resources(context){return get(context,"/api/test/resources")}
async function free(context){for(let i=0;i<80;i++){const r=await resources(context);if(r.free_slots===2&&r.directories===0)return r;await sleep(100)}throw new Error("Preview resources did not become free")}
const contexts=[];
try{
  const reader=await browser.newContext({ignoreHTTPSErrors:true,acceptDownloads:true,viewport:{width:1440,height:1050}});contexts.push(reader);
  const page=await reader.newPage();page.setDefaultTimeout(20000);
  const browserDiagnostics=[];
  page.on('console',msg=>{if(msg.type()==='error')browserDiagnostics.push(msg.text())});
  page.on('requestfailed',request=>browserDiagnostics.push(request.failure()?.errorText||'request_failed'));
  const errors=[];page.on("pageerror",error=>errors.push(error.message));
  await login(page,"reader");const state=await get(reader,"/api/test/state");
  assert.equal((await get(reader,"/api/processes/stats")).unknown_open,4);
  const detail=await get(reader,"/api/processes/"+state.active),pdf=detail.attachments.find(a=>a.name==="Test-PDF.pdf");
  const route="/api/attachments/"+pdf.id+"/original";
  const original=await reader.request.get(BASE+route);assert.equal(original.status(),200);
  assert.equal(hash(await original.body()),state.original_sha256);
  assert.equal(original.headers()["content-type"],"application/pdf");
  assert.equal(original.headers()["x-frame-options"],"SAMEORIGIN");
  assert.match(original.headers()["content-security-policy"],/frame-ancestors 'self'/);
  assert.equal(original.headers()["cache-control"],"no-store");
  const portal=await reader.request.get(BASE);assert.equal(portal.headers()["x-frame-options"],"DENY");
  assert.match(portal.headers()["content-security-policy"],/frame-ancestors 'none'/);
  await open(page,state.active,"Test-PDF.pdf");
  assert.equal(await page.getByRole("button",{name:"Zuordnung freigeben",exact:true}).count(),0);
  await page.locator("iframe.original-frame").waitFor();
  await sleep(2200);await free(reader);
  const embedded=await page.locator("iframe.original-frame").evaluate(frame=>!!frame.contentDocument?.querySelector('embed[type="application/pdf"]'));
  assert.equal(embedded,true,"Native PDF embed element was not created");
  proof.pdf_browser_diagnostics=browserDiagnostics;
  proof.pdf_frames=await Promise.all(page.frames().map(async frame=>({url:frame.url(),viewer:await frame.evaluate(()=>{
    const viewer=document.querySelector('pdf-viewer');
    return viewer?{progress:viewer.loadProgress,loaded:viewer.loaded,plugin:!!viewer.shadowRoot?.querySelector('embed')}:null;
  }).catch(()=>null)})));
  await page.screenshot({path:out+"/private-reader-pdf.png",fullPage:true});
  const popupPromise=page.waitForEvent("popup");await page.getByRole("link",{name:"In neuem Tab öffnen",exact:true}).click();
  const popup=await popupPromise;await popup.waitForLoadState("domcontentloaded");await sleep(1200);
  assert.ok(popup.url().includes(route));await popup.screenshot({path:out+"/private-reader-newtab.png"});await popup.close();
  const downloadPromise=page.waitForEvent("download");await page.getByRole("link",{name:"Original herunterladen",exact:true}).click();
  const download=await downloadPromise;assert.equal(hash(await readFile(await download.path())),state.original_sha256);await download.delete();
  await close(page);await nav(page,"Unbekannt");
  await page.locator("tbody tr").first().waitFor();
  assert.equal(await page.locator("tbody tr").count(),4);
  await page.setViewportSize({width:420,height:900});await open(page,state.active,"Test-PDF.pdf");await sleep(1000);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
  await page.screenshot({path:out+"/private-reader-mobile.png",fullPage:true});await close(page);
  proof.cases.push({case:"reader_private_pdf_headers_native_embed_newtab_download_mobile",ok:true,unknown_attachments:4,private_hash_matched:true,native_embed:true,visual_review_required:true});
  await reader.close();

  const admin=await browser.newContext({ignoreHTTPSErrors:true,viewport:{width:1440,height:1050}});contexts.push(admin);
  const a=await admin.newPage();a.setDefaultTimeout(20000);a.on("pageerror",error=>errors.push(error.message));
  await login(a,"admin");
  // Real accepted approval, then malformed successful response: pending must survive full reload.
  const approvalCalls=[];let truncate=true;
  await a.route("**/api/attachments/*/approve",async intercept=>{
    approvalCalls.push({body:JSON.parse(intercept.request().postData()),csrf:intercept.request().headers()["x-csrf-token"]});
    if(truncate){truncate=false;const response=await intercept.fetch();assert.equal(response.status(),200);await intercept.fulfill({status:200,contentType:"application/json",body:"{"})}
    else await intercept.continue();
  });
  await open(a,state.active,"Test-PDF.pdf");assert.equal(await a.getByLabel("Zuordnung",{exact:true}).inputValue(),"");
  await choose(a,"PDF-Rechnung");await a.getByRole("button",{name:"Zuordnung freigeben",exact:true}).click();
  await a.getByText(/Die Serverantwort ist unvollständig/).waitFor();
  await close(a);await a.reload({waitUntil:"networkidle"});
  await a.getByRole("button",{name:"Abmelden",exact:true}).click();await login(a,"admin");
  await open(a,state.active,"Test-PDF.pdf");await a.getByRole("button",{name:"Ursprüngliche Anforderung abgleichen",exact:true}).click();
  await a.getByText(/Zuordnung bestätigt/).waitFor();
  assert.equal(approvalCalls.length,2);assert.deepEqual(approvalCalls[0].body,approvalCalls[1].body);assert.notEqual(approvalCalls[0].csrf,approvalCalls[1].csrf);
  await a.unroute("**/api/attachments/*/approve");await close(a);
  const advanced=await post(admin,"/api/test/advance");assert.equal(advanced.published,1);
  const processed=advanced.detail.attachments.find(r=>r.id===pdf.id);assert.equal(processed.status,"processed");assert.equal(processed.storage_receipt.publication_attempts,1);
  proof.cases.push({case:"approval_truncated_200_reauth_reload_original_intent",ok:true,same_payload:true,fresh_csrf:true,one_correction:true,simulated_publications:1});

  // Real accepted retry is consumed into a new failed revision before the response is lost.
  const retryCalls=[];let retryStep=0;
  await a.route("**/api/processes/*/retry",async intercept=>{
    retryCalls.push({body:JSON.parse(intercept.request().postData()),csrf:intercept.request().headers()["x-csrf-token"]});
    if(retryStep++===0){await retryEnabled(admin,false);const response=await intercept.fetch();assert.equal(response.status(),409);await retryEnabled(admin,true);await intercept.fulfill({response})}
    else if(retryStep===2){const response=await intercept.fetch();assert.equal(response.status(),200);await post(admin,"/api/test/retry-fail");await intercept.abort("failed")}
    else await intercept.continue();
  });
  await open(a,state.retrycase,"Technischer Fehler.pdf");await a.getByRole("button",{name:"Technische Wiederholung freigeben",exact:true}).click();
  await a.getByRole("button",{name:"Abgewiesene Anforderung schließen",exact:true}).waitFor();
  await a.getByRole("button",{name:"Ursprüngliche Anforderung abgleichen",exact:true}).click();
  await a.waitForFunction(()=>!document.querySelector('[aria-label="Vorgang schließen"]')?.disabled);
  assert.equal(await a.getByRole("button",{name:"Abgewiesene Anforderung schließen",exact:true}).count(),0);
  await close(a);await a.reload({waitUntil:"networkidle"});await a.getByRole("button",{name:"Abmelden",exact:true}).click();await login(a,"admin");
  await open(a,state.retrycase,"Technischer Fehler.pdf");
  const beforeRetry=await get(admin,"/api/processes/"+state.retrycase);assert.equal(beforeRetry.revision,1);assert.equal(beforeRetry.can_retry,true);
  assert.equal(await a.getByRole("button",{name:"Technische Wiederholung freigeben",exact:true}).count(),0);
  await a.getByRole("button",{name:"Ursprüngliche Anforderung abgleichen",exact:true}).click();await a.getByText("Technische Wiederholung im Protokoll bestätigt.",{exact:true}).waitFor();
  assert.equal(retryCalls.length,3);assert.deepEqual(retryCalls[0].body,retryCalls[1].body);assert.deepEqual(retryCalls[1].body,retryCalls[2].body);assert.notEqual(retryCalls[0].csrf,retryCalls[2].csrf);
  assert.equal((await get(admin,"/api/processes/"+state.retrycase)).retry_requests.length,1);
  await a.unroute("**/api/processes/*/retry");await close(a);
  proof.cases.push({case:"retry_rejected_then_accepted_response_lost_revision_change_reauth",ok:true,same_original_revision:true,same_request_id:true,fresh_csrf:true,durable_retry_count:1});

  await open(a,state.active,"Zweiter Anhang.pdf");await choose(a,"Ignorieren");await a.getByRole("button",{name:"Zuordnung freigeben",exact:true}).dblclick();
  await a.getByText(/Zuordnung bestätigt/).waitFor();await close(a);
  const second=await post(admin,"/api/test/advance");assert.equal(second.published,0);assert.equal(second.detail.attachments.filter(r=>r.approval).length,2);
  assert.equal((await get(admin,"/api/processes/stats")).unknown_open,2);
  await nav(a,"Archiv");await a.getByRole("button",{name:"Details zu "+state.archived,exact:true}).click();
  assert.equal(await a.getByRole("button",{name:"Zuordnung freigeben",exact:true}).count(),0);assert.equal(await a.getByRole("button",{name:"Technische Wiederholung freigeben",exact:true}).count(),0);
  await close(a);
  for(const mode of ["missing","changed"]){await post(admin,"/api/test/source-mode",{mode});const result=await admin.request.get(BASE+route);assert.equal(result.status(),409);await free(admin)}
  await post(admin,"/api/test/source-mode",{mode:"normal"});
  assert.equal(hash(await (await admin.request.get(BASE+route)).body()),state.original_sha256);
  proof.cases.push({case:"double_click_partial_mail_receipts_archive_missing_changed_original",ok:true,no_republication:true,archive_readonly:true,changed_and_missing_rejected:true});
  await nav(a,"Administration");await a.getByLabel("Neue Originalvorschauen erlauben",{exact:true}).uncheck();await a.getByRole("button",{name:"Verarbeitungseinstellungen speichern",exact:true}).click();await a.getByText("Einstellungen gespeichert.",{exact:true}).waitFor();
  assert.equal((await admin.request.get(BASE+route)).status(),503);
  await a.getByLabel("Neue Originalvorschauen erlauben",{exact:true}).check();await a.getByRole("button",{name:"Verarbeitungseinstellungen speichern",exact:true}).click();await sleep(300);
  await free(admin);

  // Two real 25MiB GET streams via the actual Nginx route, deliberately unread downstream.
  const limits=await get(admin,"/api/processes/"+state.maximum),cookies=(await admin.cookies(BASE)).map(c=>c.name+"="+c.value).join("; ");
  let peak=0,capacity=0,rawReady=0,monitor=true;
  const observation=(async()=>{while(monitor){const r=await resources(admin);peak=Math.max(peak,r.used_bytes);capacity=r.capacity_bytes;rawReady=Math.max(rawReady,r.raw_ready);await sleep(40)}})();
  function stalled(url){return new Promise((resolve,reject)=>{const req=https.get(url,{rejectUnauthorized:false,headers:{Cookie:cookies}},res=>{res.pause();const item={req,res,status:res.statusCode,bytes:0,error:null};res.on("error",e=>{item.error=e.code||e.name});resolve(item)});req.on("error",reject)})}
  const started=Date.now(),streams=await Promise.all(limits.attachments.map(row=>stalled(BASE+"/api/attachments/"+row.id+"/original")));
  assert.ok(streams.every(s=>s.status===200));assert.equal((await resources(admin)).free_slots,0);
  const third=await admin.request.get(BASE+route);assert.equal(third.status(),503);
  await sleep(Math.max(0,started+14000-Date.now()));
  const after=await resources(admin);assert.equal(after.free_slots,2);assert.equal(after.directories,0);
  for(const stream of streams){await new Promise(resolve=>{let ended=false;const done=()=>{if(!ended){ended=true;resolve()}};stream.res.on("data",chunk=>{stream.bytes+=chunk.length});stream.res.once("end",done);stream.res.once("close",done);stream.res.once("aborted",done);stream.res.resume();setTimeout(()=>{stream.req.destroy();done()},2000)})}
  monitor=false;await observation;
  assert.equal(capacity,128*1024*1024);assert.ok(peak>=100*1024*1024&&peak<capacity,{peak,capacity});assert.equal(rawReady,2);assert.ok(streams.every(s=>s.bytes<25*1024*1024));
  proof.cases.push({case:"nginx_two_25mib_streams_slow_consumers_third_request_and_deadline",ok:true,tmpfs_capacity_bytes:capacity,peak_tmpfs_used_bytes:peak,simultaneous_raw_downloads:rawReady,third_status:503,slots_after_deadline:after.free_slots,private_dirs_after_deadline:after.directories,transferred_bytes:streams.map(s=>s.bytes),test_response_budget_seconds:12});
  assert.deepEqual(errors,[]);proof.ok=true;
}catch(error){proof.ok=false;proof.error=error.stack||String(error);for(const context of contexts){for(const page of context.pages()){try{await page.screenshot({path:out+"/private-failure-"+contexts.indexOf(context)+".png",fullPage:true})}catch{}}}}
finally{for(const context of contexts){try{await context.close()}catch{}}await browser.close()}
console.log(JSON.stringify(proof));if(!proof.ok)process.exitCode=1;
