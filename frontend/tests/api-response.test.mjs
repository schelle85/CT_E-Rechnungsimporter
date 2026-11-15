import { test } from "node:test";
import assert from "node:assert/strict";
import { api, ApiError, ApiProtocolError } from "../src/api.ts";
const mid="a".repeat(64),path="/api/processes/"+mid+"/retry";
function mock(t,response){const prior=globalThis.fetch;globalThis.fetch=async()=>response;t.after(()=>{globalThis.fetch=prior})}
test("truncated successful mutation and GET bodies are unconfirmed errors",async t=>{
  for(const target of [path,"/api/processes"]){
    mock(t,new Response("{",{status:200,headers:{"Content-Type":"application/json"}}));
    await assert.rejects(api(target,target===path?{method:"POST",body:"{}"}:{}),ApiProtocolError);
  }
});
test("missing mutation receipt and missing GET data are never successful empty results",async t=>{
  for(const target of [path,"/api/processes","/api/unknown"]){
    mock(t,new Response("{}",{status:200}));
    await assert.rejects(api(target,target===path?{method:"POST",body:"{}"}:{}),ApiProtocolError);
  }
});
test("401 still invalidates the session when its JSON body is truncated",async t=>{
  const prior=globalThis.window;let events=0;globalThis.window={dispatchEvent:e=>{assert.equal(e.type,"session-invalid");events++}};
  t.after(()=>{globalThis.window=prior});mock(t,new Response("{",{status:401}));
  await assert.rejects(api("/api/processes"),error=>error instanceof ApiError&&error.status===401);
  assert.equal(events,1);
});
test("a fresh CSRF header accompanies the same frozen original business body",async t=>{
  const prior=globalThis.fetch;const sent=[];t.after(()=>{globalThis.fetch=prior});
  globalThis.fetch=async(url,options)=>{sent.push({body:options.body,csrf:options.headers.get("X-CSRF-Token")});return new Response(JSON.stringify({request_key:"b".repeat(64),message_key:mid,expected_revision:0,state:"failed"}),{status:200})};
  const body=JSON.stringify({request_id:"original-uuid",expected_revision:0});
  await api(path,{method:"POST",body},"first-csrf");await api(path,{method:"POST",body},"fresh-csrf");
  assert.equal(sent[0].body,sent[1].body);assert.notEqual(sent[0].csrf,sent[1].csrf);
});

test("missing or malformed report and certificate fields are not confirmed data",async t=>{
  for(const target of ["/api/admin/reports?period=daily","/api/notifications/certificate"]){
    mock(t,new Response(JSON.stringify(target.includes("reports")?{counts:{messages:0}}:{checked_at:1,local:{},warning:null,proof:null}),{status:200}));
    await assert.rejects(api(target),ApiProtocolError);
  }
});

test("zero reports remain valid actual data, including every category",async t=>{
  const counts=Object.fromEntries(["messages","attachments","unknown_open","stored_receipts","duplicates","attachment_errors","blocked_messages","E-Rechnung","PDF","Zahlungsavis","Mahnung"].map(key=>[key,0]));
  mock(t,new Response(JSON.stringify({synthetic:false,start:1,end:2,as_of:3,timezone:"Europe/Berlin",counts}),{status:200}));
  assert.equal((await api("/api/admin/reports")).counts.messages,0);
});
