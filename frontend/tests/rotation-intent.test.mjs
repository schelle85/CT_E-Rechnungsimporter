import { test } from "node:test";
import assert from "node:assert/strict";
import { ensureRotationIntent, readRotationIntent, rotationIntentKey, rotationReceiptMatches, closeRotationIntent, discardStaleRotationIntent, rotationReceiptPath } from "../src/rotation-intent.ts";
import { api, ApiProtocolError } from "../src/api.ts";
const identity="1".repeat(32), scope="a".repeat(64), fingerprint="b".repeat(64), operation="11111111-2222-4333-8444-555555555555";
function memory(){ const rows=new Map();return {getItem:k=>rows.get(k)??null,setItem:(k,v)=>rows.set(k,v),removeItem:k=>rows.delete(k)} }
const ensure=storage=>ensureRotationIntent(storage,identity,scope,4,fingerprint,()=>operation);
const receipt=intent=>({operation_id:operation,scope_key:scope,actor:intent.actor,trigger_kind:"manual",request_hash:"c".repeat(64),expected_revision:4,
  old_fingerprint:fingerprint,state:"completed",revision:12,error_code:null,created_at:1,updated_at:5});
function fetchMock(t,fn){const before=globalThis.fetch;globalThis.fetch=fn;t.after(()=>{globalThis.fetch=before})}

test("response loss, browser restart, certificate/config changes and new session retain the original request",async t=>{
  const storage=memory(),original=ensure(storage),sent=[];
  fetchMock(t,async(path,opts)=>{assert.deepEqual(readRotationIntent(storage,identity),original);sent.push({body:opts.body,csrf:opts.headers.get("X-CSRF-Token")});
    if(sent.length===1)throw Error("synthetic response lost");
    return new Response(JSON.stringify({ok:true,persisted:true,receipt:receipt(original)}));});
  await assert.rejects(api("/api/rotation/request",{method:"POST",body:JSON.stringify(original.payload)},"old-session"));
  const reopened=ensureRotationIntent(storage,identity,"d".repeat(64),100,"e".repeat(64),()=>{throw Error("no second UUID")});
  assert.deepEqual(reopened,original);
  const result=await api("/api/rotation/request",{method:"POST",body:JSON.stringify(reopened.payload)},"new-session");
  assert.equal(rotationReceiptMatches(reopened,result.receipt),true);assert.equal(sent[0].body,sent[1].body);assert.notEqual(sent[0].csrf,sent[1].csrf);
  assert.equal(readRotationIntent(storage,"2".repeat(32)),null);
  const query=new URL(rotationReceiptPath(reopened),"https://fixture.example.invalid").searchParams;
  assert.equal(query.get("operation_id"),operation);assert.equal(query.get("expected_revision"),"4");assert.equal(query.get("old_fingerprint"),fingerprint);
});

test("storage failure, ignored writes and malformed stored requests cannot produce a sendable new intent",()=>{
  for(const storage of [{getItem:()=>null,setItem:()=>{throw Error("quota")}}, {getItem:()=>null,setItem:()=>{}}])assert.throws(()=>ensure(storage));
  for(const bad of ["", "{",JSON.stringify({actor:"ad:"+identity,payload:{operation_id:operation}})]){
    const storage={getItem:()=>bad,setItem:()=>{throw Error("must not overwrite")},removeItem:()=>{throw Error("must not delete")}};
    assert.throws(()=>ensure(storage));
  }
});

test("unknown and in-flight states remain bound; only a matching terminal receipt allows explicit close",()=>{
  for(const state of ["requested","prepared","registration_started","registration_unknown","registered","candidate_verified","adoption_prepared","adopting","rollback_unknown","adopted","overlap","cleanup_started","cleanup_unknown"]){
    const storage=memory(),intent=ensure(storage);assert.throws(()=>closeRotationIntent(storage,identity,{...receipt(intent),state}));assert.deepEqual(readRotationIntent(storage,identity),intent);
  }
  for(const state of ["completed","failed","registration_rejected"]){const storage=memory(),intent=ensure(storage);closeRotationIntent(storage,identity,{...receipt(intent),state});assert.equal(readRotationIntent(storage,identity),null)}
});

test("terminal receipts cannot close another actor, scope, revision, fingerprint, UUID or trigger",()=>{
  const storage=memory(),intent=ensure(storage);
  for(const changed of [{actor:"ad:"+"2".repeat(32)},{scope_key:"d".repeat(64)},{expected_revision:5},{old_fingerprint:"e".repeat(64)},
    {operation_id:"66666666-2222-4333-8444-555555555555"},{trigger_kind:"automatic"},{request_hash:""},{state:"constructor"}]){
    assert.equal(rotationReceiptMatches(intent,{...receipt(intent),...changed}),false);assert.throws(()=>closeRotationIntent(storage,identity,{...receipt(intent),...changed}));
  }
  assert.deepEqual(readRotationIntent(storage,identity),intent);
});

test("discard requires a later head revision followed by a missing original receipt, in that order",async()=>{
  const storage=memory(),intent=ensure(storage),calls=[];
  await discardStaleRotationIntent(storage,identity,async()=>{calls.push("head");return {scope_key:scope,revision:5}},async current=>{calls.push("receipt");assert.deepEqual(current,intent);return null});
  assert.deepEqual(calls,["head","receipt"]);assert.equal(readRotationIntent(storage,identity),null);
});

test("missing, accepted, stale-scope, concurrent-replacement and interrupted readbacks never discard an uncertain intent",async()=>{
  const scenarios=[
    {status:{scope_key:scope,revision:4},row:null}, {status:{scope_key:"d".repeat(64),revision:5},row:null},
    {status:{scope_key:scope,revision:5},accepted:true}, {status:{scope_key:scope,revision:5},interrupt:true},
    {status:{scope_key:scope,revision:5},replace:true},
  ];
  for(const scenario of scenarios){
    const storage=memory(),intent=ensure(storage);
    await assert.rejects(discardStaleRotationIntent(storage,identity,async()=>scenario.status,async()=>{
      if(scenario.interrupt)throw Error("readback interrupted");
      if(scenario.replace)storage.setItem(rotationIntentKey(identity),JSON.stringify({...intent,payload:{...intent.payload,expected_revision:8}}));
      return scenario.accepted?receipt(intent):null;
    }));
    assert.notEqual(readRotationIntent(storage,identity),null);
  }
});

test("missing, malformed and truncated successful receipts cannot confirm POST; nullable GET is only absence",async t=>{
  for(const body of ["{","{}",JSON.stringify({ok:true,persisted:true,receipt:null}),JSON.stringify({ok:true,persisted:true,receipt:{state:"completed"}})]){
    fetchMock(t,async()=>new Response(body));await assert.rejects(api("/api/rotation/request",{method:"POST",body:"{}"}),ApiProtocolError);
  }
  fetchMock(t,async()=>new Response(JSON.stringify({ok:true,persisted:true,receipt:null})));
  await assert.rejects(api("/api/rotation/request?operation_id="+operation),ApiProtocolError);
  fetchMock(t,async()=>new Response(JSON.stringify({ok:true,persisted:false,receipt:null})));
  await assert.rejects(api("/api/rotation/request",{method:"POST",body:"{}"}),ApiProtocolError);
  assert.equal((await api("/api/rotation/request?operation_id="+operation)).receipt,null);
});

test("status refuses stale or differently bound Host evidence and never fabricates successful renewal",async t=>{
  const host={available:true,schema_version:1,source_commit:"f".repeat(40),deployment_id:operation,instance_id:operation,scope_key:scope,boot_id:operation,observed_at:900,
    last_check:null,last_attempt:null,last_renewal:null,operation:null,timers:{daily:false,opportunity:false,next_check_at:null}};
  const status={scope_key:scope,revision:0,enabled:true,can_edit:false,checked_at:1000,last_successful_check_at:null,active:null,host,
    local:{code:"notification_certificate_unavailable"},schedule:{timezone:"Europe/Berlin",daily_time:"03:35",renew_before_days:30,overlap_days:7}};
  for(const changed of [{observed_at:819},{observed_at:1001},{scope_key:"d".repeat(64)},{last_renewal:{at:901,operation_id:operation,fingerprint}},
    {timers:{daily:false,opportunity:true,next_check_at:1500}},{operation:{phase:"committed"}}]){
    fetchMock(t,async()=>new Response(JSON.stringify({...status,host:{...host,...changed}})));await assert.rejects(api("/api/rotation/status"),ApiProtocolError);
  }
  for(const confirmedHost of [host,{available:false,code:"rotation_status_unconfirmed"}]){
    fetchMock(t,async()=>new Response(JSON.stringify({...status,host:confirmedHost})));
    const read=await api("/api/rotation/status");assert.equal(read.last_successful_check_at,null);assert.equal(read.host.available,confirmedHost.available);
    if(read.host.available)assert.equal(read.host.last_renewal,null);
  }
});
