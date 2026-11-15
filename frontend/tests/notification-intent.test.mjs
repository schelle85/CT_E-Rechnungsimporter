import { test } from "node:test";
import assert from "node:assert/strict";
import { ensureTestIntent, readTestIntent, closeTestIntent, testReceiptMatches } from "../src/notification-intent.ts";
function memory(){const rows=new Map();return {getItem:key=>rows.get(key)||null,setItem:(key,value)=>rows.set(key,value),removeItem:key=>rows.delete(key)}}
const identity="1".repeat(32),scope="a".repeat(64),uuid="11111111-2222-4333-8444-555555555555";
const confirmed=intent=>({slot_key:"b".repeat(64),kind:"test",request_id:uuid,actor:intent.actor,scope_key:scope,config_version:1,payload_hash:"c".repeat(64),state:"accepted",reservations:1,http_status:202,created_at:1});
test("response loss, reload and new settings retain the original UUID/version/scope",()=>{
  const storage=memory();const first=ensureTestIntent(storage,identity,scope,1,()=>uuid);
  assert.deepEqual(readTestIntent(storage,identity),first);
  assert.deepEqual(ensureTestIntent(storage,identity,"d".repeat(64),2,()=>{throw Error("must not create another UUID")}),first);
  assert.equal(readTestIntent(storage,"2".repeat(32)),null);
});
test("actor, scope and original version must all match a confirmed terminal receipt",()=>{
  const storage=memory(),intent=ensureTestIntent(storage,identity,scope,1,()=>uuid),row=confirmed(intent);
  for(const mutation of [{actor:"ad:"+"2".repeat(32)},{scope_key:"d".repeat(64)},{config_version:2},{request_id:"66666666-2222-4333-8444-555555555555"}]){
    assert.equal(testReceiptMatches(intent,{...row,...mutation}),false);
    assert.throws(()=>closeTestIntent(storage,identity,{...row,...mutation}));
  }
  assert.throws(()=>closeTestIntent(storage,identity,{...row,state:"prepared",reservations:0,http_status:null}));
  closeTestIntent(storage,identity,row);assert.equal(readTestIntent(storage,identity),null);
});
test("failed storage prevents the first HTTP-capable intent, malformed storage is retained",()=>{
  const storage=memory();storage.setItem=()=>{throw Error("storage refused")};
  assert.throws(()=>ensureTestIntent(storage,identity,scope,1,()=>uuid));
  const broken={getItem:()=>"{",setItem:()=>{throw Error("must not overwrite")},removeItem:()=>{throw Error("must not delete")}};
  assert.throws(()=>ensureTestIntent(broken,identity,scope,1,()=>uuid));
});
